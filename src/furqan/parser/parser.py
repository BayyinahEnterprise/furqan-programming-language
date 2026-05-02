"""
Furqan recursive-descent parser — Phase 2 minimal surface syntax.

Grammar (BNF, Phase 2.2 subset)::

    module       := bismillah_block function_def*
    bismillah_block
                 := ('bismillah' | 'scope_block') IDENT '{' field+ '}'
    field        := authority_field | serves_field | scope_field | not_scope_field
    authority_field
                 := 'authority' ':' qual_name (',' qual_name)*
    serves_field := 'serves' ':' qual_name (',' qual_name)*
    scope_field  := 'scope' ':' IDENT (',' IDENT)*
    not_scope_field
                 := 'not_scope' ':' IDENT (',' IDENT)*
    qual_name    := IDENT ('.' IDENT)*
    function_def := 'fn' IDENT '(' ')' '{' call* '}'
    call         := qual_name '(' ')'

The parser is single-pass and produces a fully constructed
:class:`Module`. There is no error-recovery layer; the first parse
error raises :class:`ParseError` with a SourceSpan pointing at the
offending token. (Error recovery is a Phase 3 surface concern; per
NAMING.md §6 it cannot be removed once added, so we hold off until the
ergonomics are observed.)

The body of a function is *only* parsed for call sites. Phase 2 has no
expression grammar. A call is recognised by the qual-name + '()'
pattern. Anything else inside ``fn`` braces (assignments, control
flow) is a Phase-3 concern; here we error on anything that is not a
call.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ast_nodes import (
    AdditiveOnlyModuleDecl,
    BinaryComparisonExpr,
    BismillahBlock,
    CallRef,
    CallStmt,
    ComparisonOp,
    CompoundTypeDef,
    DependencyEntry,
    ExportDecl,
    FieldDecl,
    FunctionDef,
    IdentExpr,
    IdentList,
    IfStmt,
    IncompleteField,
    IncompleteLiteral,
    IntegrityLiteral,
    LayerAccess,
    LayerBlock,
    MajorVersionBump,
    MizanDecl,
    MizanField,
    Module,
    NotExpr,
    NumberLiteral,
    ParamDecl,
    RemovesEntry,
    RenamesEntry,
    ReturnStmt,
    SourceSpan,
    StringLiteral,
    TanzilDecl,
    TypePath,
    UnionType,
    VersionLiteral,
)
from .tokenizer import Token, TokenKind, _unescape_string, tokenize


# ---------------------------------------------------------------------------
# Layer alias normalisation (Phase 2.4)
# ---------------------------------------------------------------------------
#
# The English aliases ``surface`` and ``depth`` map to the canonical
# Arabic forms ``zahir`` and ``batin`` respectively. The mapping lives
# at module scope (rather than as a method) because both the parser
# and the layer-access pre-scan reuse it; a single source of truth
# avoids drift.

_LAYER_OF_TOKEN: dict[TokenKind, str] = {
    TokenKind.ZAHIR: "zahir",
    TokenKind.SURFACE: "zahir",
    TokenKind.BATIN: "batin",
    TokenKind.DEPTH: "batin",
}

_LAYER_TOKEN_KINDS: tuple[TokenKind, ...] = (
    TokenKind.ZAHIR, TokenKind.SURFACE, TokenKind.BATIN, TokenKind.DEPTH,
)


# ---------------------------------------------------------------------------
# ParseError
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """Raised on the first unrecoverable parse failure.

    Carries a :class:`SourceSpan` so the eventual marad wrapper can
    place a diagnostic at the offending token. The ``message`` field is
    the diagnosis sentence; the ``span`` field is the location.
    """

    def __init__(self, message: str, span: SourceSpan) -> None:
        super().__init__(f"{message} (at {span.file}:{span.line}:{span.column})")
        self.message = message
        self.span = span


# ---------------------------------------------------------------------------
# Parser resource limits (Q9 / Q10 from QUESTIONS.md, closed in v0.11.0)
# ---------------------------------------------------------------------------
#
# Maximum nesting depth for parse-time recursion. Conservative for
# Python's default 1000-frame stack with several frames per parse-block
# call, plus headroom for callers above the parser. Empirically the
# pre-v0.11.0 implementation parsed depth=200 cleanly and crashed at
# depth=500 with RecursionError on CPython 3.12 default settings.
# Raising this requires raising the Python recursion limit too.
#
# The depth-guard turns a Python RecursionError (free-form traceback,
# wrong exit code) into a structured ParseError with a precise line
# number, honouring marad.py's contract that errors in Furqan are
# structured diagnoses, not thrown exceptions with prose strings.
# Closes the discipline violation flagged by Q9 in QUESTIONS.md.
MAX_NESTING_DEPTH: int = 200


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

@dataclass
class _Parser:
    """Single-pass recursive descent over a token stream.

    Internal class; the public surface is :func:`parse`. Mutable state
    is contained: ``pos`` advances monotonically across the token list.
    """

    tokens: list[Token]
    file: str
    pos: int = 0

    # ---- low-level helpers -------------------------------------------------

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind is not TokenKind.EOF:
            self.pos += 1
        return tok

    def check(self, *kinds: TokenKind) -> bool:
        return self.peek().kind in kinds

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.check(*kinds):
            return self.advance()
        return None

    def expect(self, kind: TokenKind, what: str) -> Token:
        tok = self.peek()
        if tok.kind is not kind:
            raise ParseError(
                f"Expected {what} ({kind.name}), got {tok.kind.name} {tok.lexeme!r}",
                self._span(tok),
            )
        return self.advance()

    def _span(self, tok: Token) -> SourceSpan:
        return SourceSpan(file=self.file, line=tok.line, column=tok.column)

    # ---- top-level ---------------------------------------------------------

    def parse_module(self) -> Module:
        bismillah = self.parse_bismillah_block()
        functions: list[FunctionDef] = []
        compound_types: list[CompoundTypeDef] = []
        additive_only_modules: list[AdditiveOnlyModuleDecl] = []
        mizan_decls: list[MizanDecl] = []
        tanzil_decls: list[TanzilDecl] = []
        while not self.check(TokenKind.EOF):
            if self.check(TokenKind.FN):
                functions.append(self.parse_function_def())
                continue
            if self.check(TokenKind.TYPE):
                # Phase 2.4 (Session 1.3): top-level compound type
                # declaration. Order is free relative to functions —
                # a type may be declared before or after the functions
                # that use it. The checker resolves references after
                # the full module is parsed.
                compound_types.append(self.parse_compound_type_def())
                continue
            if self.check(TokenKind.ADDITIVE_ONLY):
                # Phase 2.5 (Session 1.4): top-level additive-only
                # module declaration. A .furqan file may declare zero
                # or more such modules; the additive-only checker
                # compares each against its sidecar history.
                additive_only_modules.append(
                    self.parse_additive_only_module_decl()
                )
                continue
            if self.check(TokenKind.MIZAN):
                # Phase 2.7 (Session 1.6): top-level Mizan
                # calibration block. A .furqan file may declare zero
                # or more such blocks. The well-formedness checker
                # walks each block's field list for M1/M2/M4 rules.
                mizan_decls.append(self.parse_mizan_decl())
                continue
            if self.check(TokenKind.TANZIL):
                # Phase 2.8 (Session 1.7): top-level Tanzil
                # build-ordering block. A .furqan file may declare
                # zero or more such blocks. The well-formedness
                # checker walks each block's dependency list for
                # T1 (self-dep) and T2 (duplicate) rules; T3 (empty
                # block) is an Advisory.
                tanzil_decls.append(self.parse_tanzil_decl())
                continue
            if self.check(TokenKind.BISMILLAH, TokenKind.SCOPE_BLOCK):
                tok = self.peek()
                raise ParseError(
                    "Only one Bismillah block per module is permitted; "
                    "the second declaration would silently override the "
                    "first. Per Furqan thesis §3.1 the Bismillah is the "
                    "module's authority source and must be unique.",
                    self._span(tok),
                )
            tok = self.peek()
            raise ParseError(
                f"Unexpected {tok.kind.name} {tok.lexeme!r}; expected "
                f"a function definition (fn), a compound-type "
                f"declaration (type), an additive-only module "
                f"declaration (additive_only module), a mizan "
                f"calibration block (mizan), a tanzil "
                f"build-ordering block (tanzil), or end of file.",
                self._span(tok),
            )
        # If the file is empty after the Bismillah block, that is
        # legal: a module may declare scope without yet implementing
        # any function. The Bismillah scope checker has nothing to
        # check in that case and trivially passes.
        return Module(
            bismillah=bismillah,
            functions=tuple(functions),
            source_path=self.file,
            compound_types=tuple(compound_types),
            additive_only_modules=tuple(additive_only_modules),
            mizan_decls=tuple(mizan_decls),
            tanzil_decls=tuple(tanzil_decls),
        )

    # ---- Bismillah block ---------------------------------------------------

    def parse_bismillah_block(self) -> BismillahBlock:
        # The Arabic and English aliases are treated identically by
        # the parser (NAMING.md §1). The original lexeme is preserved
        # in ``alias_used`` so error messages can quote the source.
        if self.check(TokenKind.BISMILLAH, TokenKind.SCOPE_BLOCK):
            head = self.advance()
            alias = head.lexeme
        else:
            tok = self.peek()
            raise ParseError(
                "Every module must open with a Bismillah block "
                "('bismillah' or 'scope_block'). Per Furqan thesis §3.1 "
                "the Bismillah declares the module's authority, "
                "purpose, scope, and exclusions; without it the "
                "subsequent type rules have no anchor.",
                self._span(tok),
            )
        head_span = self._span(head)

        name_tok = self.expect(TokenKind.IDENT, "module name after 'bismillah'")
        self.expect(TokenKind.LBRACE, "'{' to open the Bismillah block")

        authority: tuple[str, ...] | None = None
        serves: tuple[tuple[str, ...], ...] | None = None
        scope: tuple[str, ...] | None = None
        not_scope: tuple[str, ...] | None = None

        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            if self.match(TokenKind.AUTHORITY):
                self.expect(TokenKind.COLON, "':' after 'authority'")
                authority = self._parse_ident_list()
            elif self.match(TokenKind.SERVES):
                self.expect(TokenKind.COLON, "':' after 'serves'")
                serves = self._parse_qual_name_list()
            elif self.match(TokenKind.SCOPE):
                self.expect(TokenKind.COLON, "':' after 'scope'")
                scope = self._parse_ident_list()
            elif self.match(TokenKind.NOT_SCOPE):
                self.expect(TokenKind.COLON, "':' after 'not_scope'")
                not_scope = self._parse_ident_list()
            else:
                tok = self.peek()
                raise ParseError(
                    f"Unrecognised field {tok.lexeme!r} inside Bismillah "
                    f"block. Phase 2 accepts: 'authority', 'serves', "
                    f"'scope', 'not_scope'.",
                    self._span(tok),
                )

        self.expect(TokenKind.RBRACE, "'}' to close the Bismillah block")

        # All four fields are required. A Bismillah block missing its
        # ``serves`` field is the canonical Process-2 risk: the module
        # is structurally compliant (it parses) but functionally
        # uncalibrated. Per the thesis paper §3.1, a missing
        # ``serves`` clause is a compiler error, not a warning.
        missing: list[str] = []
        if authority is None:
            missing.append("authority")
        if serves is None:
            missing.append("serves")
        if scope is None:
            missing.append("scope")
        if not_scope is None:
            missing.append("not_scope")
        if missing:
            raise ParseError(
                f"Bismillah block {name_tok.lexeme!r} is missing required "
                f"field(s): {', '.join(missing)}. Per Furqan thesis "
                f"§3.1 every Bismillah declares authority, serves, "
                f"scope, and not_scope. A missing field is a structural "
                f"error, not a default-able omission.",
                head_span,
            )

        return BismillahBlock(
            name=name_tok.lexeme,
            authority=authority,            # type: ignore[arg-type]
            serves=serves,                  # type: ignore[arg-type]
            scope=scope,                    # type: ignore[arg-type]
            not_scope=not_scope,            # type: ignore[arg-type]
            span=head_span,
            alias_used=alias,
        )

    def _parse_ident_list(self) -> tuple[str, ...]:
        items = [self.expect(TokenKind.IDENT, "identifier").lexeme]
        while self.match(TokenKind.COMMA):
            items.append(self.expect(TokenKind.IDENT, "identifier after ','").lexeme)
        return tuple(items)

    def _parse_qual_name_list(self) -> tuple[tuple[str, ...], ...]:
        items: list[tuple[str, ...]] = [self._parse_qual_name()]
        while self.match(TokenKind.COMMA):
            items.append(self._parse_qual_name())
        return tuple(items)

    def _parse_qual_name(self) -> tuple[str, ...]:
        # Phase 2.4 (Session 1.3): after a DOT, accept either an
        # ordinary IDENT or one of the layer keywords (ZAHIR / SURFACE
        # / BATIN / DEPTH). The keyword case is required because
        # ``zahir`` and ``batin`` were promoted to keywords for the
        # zahir/batin primitive — without this extension a future
        # qualified-name use of a layer word would fail to parse where
        # it would have parsed at Phase 2.3. The extension is
        # additive on the acceptance side: every IDENT-only path that
        # parsed before still parses, plus the new layer-keyword
        # forms.
        head = self.expect(TokenKind.IDENT, "qualified name").lexeme
        parts = [head]
        while self.match(TokenKind.DOT):
            if self.check(TokenKind.IDENT, *_LAYER_TOKEN_KINDS):
                parts.append(self.advance().lexeme)
            else:
                tok = self.peek()
                raise ParseError(
                    f"Expected an identifier or layer keyword "
                    f"(zahir/surface/batin/depth) after '.', got "
                    f"{tok.kind.name} {tok.lexeme!r}.",
                    self._span(tok),
                )
        return tuple(parts)

    # ---- Phase 2.4 (Session 1.3): type-path parser -------------------------
    #
    # Replaces the F1/F2 opaque eaters from Session 1.2. A type path
    # in Phase 2.4 has exactly one of two shapes:
    #
    #   * IDENT                         — bare type name, e.g. ``Document``
    #   * IDENT '.' (zahir|batin alias) — layer-qualified, e.g. ``Document.zahir``
    #
    # Anything else is a parse error. Generics, function types, and
    # references are not yet in the surface.

    def _parse_type_path(self, what: str = "type") -> TypePath:
        base_tok = self.expect(TokenKind.IDENT, f"{what} name")
        layer: str | None = None
        layer_alias: str | None = None
        if self.match(TokenKind.DOT):
            tok = self.peek()
            if tok.kind in _LAYER_OF_TOKEN:
                self.advance()
                layer = _LAYER_OF_TOKEN[tok.kind]
                layer_alias = tok.lexeme
            else:
                raise ParseError(
                    f"Phase 2.4 type paths permit only 'zahir' / "
                    f"'surface' / 'batin' / 'depth' as a layer "
                    f"qualifier after '.', got {tok.kind.name} "
                    f"{tok.lexeme!r}.",
                    self._span(tok),
                )
        return TypePath(
            base=base_tok.lexeme,
            layer=layer,
            span=self._span(base_tok),
            layer_alias_used=layer_alias,
        )

    # ---- Phase 2.4: parameter list parser ----------------------------------
    #
    # Replaces F1 (the opaque param-list eater from Session 1.2). The
    # grammar is intentionally tight:
    #
    #   param_list := <empty> | param (',' param)*
    #   param      := IDENT ':' type_path
    #
    # Untyped parameters are not accepted; the type annotation is the
    # input the zahir/batin checker needs. A future Phase-3 expansion
    # may add default values, generics, or pattern parameters — those
    # would be additive on this grammar.

    def _parse_param_list(self) -> tuple[ParamDecl, ...]:
        if self.check(TokenKind.RPAREN):
            return ()
        params: list[ParamDecl] = [self._parse_param()]
        while self.match(TokenKind.COMMA):
            params.append(self._parse_param())
        return tuple(params)

    def _parse_param(self) -> ParamDecl:
        name_tok = self.expect(TokenKind.IDENT, "parameter name")
        self.expect(
            TokenKind.COLON,
            "':' after parameter name (Phase 2.4 requires every "
            "parameter to carry a type annotation)",
        )
        type_path = self._parse_type_path("parameter type")
        return ParamDecl(
            name=name_tok.lexeme,
            type_path=type_path,
            span=self._span(name_tok),
        )

    # ---- Phase 2.4: compound-type declaration ------------------------------

    def parse_compound_type_def(self) -> CompoundTypeDef:
        head = self.expect(TokenKind.TYPE, "'type'")
        head_span = self._span(head)
        name_tok = self.expect(
            TokenKind.IDENT,
            "compound-type name after 'type'",
        )
        self.expect(
            TokenKind.LBRACE,
            "'{' to open the compound-type body",
        )
        # Phase 2.4 requires both layers, in the order zahir then batin.
        # Either Arabic or English alias is accepted at each position
        # (NAMING.md §1).
        zahir_block = self._parse_layer_block(
            expected_layer="zahir",
            kind_options=(TokenKind.ZAHIR, TokenKind.SURFACE),
        )
        batin_block = self._parse_layer_block(
            expected_layer="batin",
            kind_options=(TokenKind.BATIN, TokenKind.DEPTH),
        )
        self.expect(
            TokenKind.RBRACE,
            "'}' to close the compound-type body",
        )
        return CompoundTypeDef(
            name=name_tok.lexeme,
            zahir=zahir_block,
            batin=batin_block,
            span=head_span,
        )

    def _parse_layer_block(
        self,
        *,
        expected_layer: str,
        kind_options: tuple[TokenKind, ...],
    ) -> LayerBlock:
        if not self.check(*kind_options):
            tok = self.peek()
            raise ParseError(
                f"Expected the {expected_layer!r} layer block "
                f"(use '{kind_options[0].value}' or its English alias "
                f"'{kind_options[1].value}'), got {tok.kind.name} "
                f"{tok.lexeme!r}. Phase 2.4 compound types require "
                f"exactly two layer blocks in the order "
                f"'zahir' then 'batin'.",
                self._span(tok),
            )
        head = self.advance()
        head_span = self._span(head)
        self.expect(
            TokenKind.LBRACE,
            f"'{{' to open the {expected_layer} layer block",
        )
        fields: list[FieldDecl] = []
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            fields.append(self._parse_field_decl())
        self.expect(
            TokenKind.RBRACE,
            f"'}}' to close the {expected_layer} layer block",
        )
        return LayerBlock(
            layer=expected_layer,
            fields=tuple(fields),
            span=head_span,
            alias_used=head.lexeme,
        )

    def _parse_field_decl(self) -> FieldDecl:
        name_tok = self.expect(TokenKind.IDENT, "field name")
        self.expect(TokenKind.COLON, "':' after field name")
        type_tok = self.expect(
            TokenKind.IDENT,
            "field type (Phase 2.4 restricts field types to bare "
            "identifiers; generics are deferred)",
        )
        return FieldDecl(
            name=name_tok.lexeme,
            type_name=type_tok.lexeme,
            span=self._span(name_tok),
        )

    # ---- Phase 2.5 (Session 1.4): additive-only module declaration --------
    #
    # Grammar:
    #
    #     ModuleDecl    := 'additive_only' 'module' IDENT VersionLit
    #                      '{' ExportList MajorBump? '}'
    #     VersionLit    := IDENT_v_prefix ('.' NUMBER)+
    #     ExportList    := ('export' IDENT ':' type_path)*
    #     MajorBump     := 'major_version_bump' '{' CatalogEntry* '}'
    #     CatalogEntry  := 'removes' ':' IdentList
    #                    | 'renames' ':' RenameList
    #     IdentList     := IDENT (',' IDENT)*
    #     RenameList    := Rename (',' Rename)*
    #     Rename        := IDENT '->' IDENT
    #
    # Strict parsers throughout. F1/F2 discipline applies: no opaque
    # eaters; every token is accounted for.

    def parse_additive_only_module_decl(self) -> AdditiveOnlyModuleDecl:
        head = self.expect(TokenKind.ADDITIVE_ONLY, "'additive_only'")
        head_span = self._span(head)
        self.expect(
            TokenKind.MODULE,
            "'module' after 'additive_only' (the keyword pair is the "
            "head of every additive-only module declaration)",
        )
        name_tok = self.expect(
            TokenKind.IDENT,
            "module name after 'additive_only module'",
        )
        version = self._parse_version_literal()
        self.expect(
            TokenKind.LBRACE,
            "'{' to open the additive_only module body",
        )

        exports: list[ExportDecl] = []
        bump_catalog: MajorVersionBump | None = None

        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            if self.check(TokenKind.EXPORT):
                exports.append(self._parse_export_decl())
                continue
            if self.check(TokenKind.MAJOR_VERSION_BUMP):
                if bump_catalog is not None:
                    tok = self.peek()
                    raise ParseError(
                        "Only one major_version_bump catalog per "
                        "additive_only module is permitted; a second "
                        "catalog would silently override the first.",
                        self._span(tok),
                    )
                bump_catalog = self._parse_major_version_bump()
                continue
            tok = self.peek()
            raise ParseError(
                f"Unexpected {tok.kind.name} {tok.lexeme!r} inside "
                f"additive_only module body; expected 'export' or "
                f"'major_version_bump'.",
                self._span(tok),
            )

        self.expect(
            TokenKind.RBRACE,
            "'}' to close the additive_only module body",
        )

        return AdditiveOnlyModuleDecl(
            name=name_tok.lexeme,
            version=version,
            exports=tuple(exports),
            bump_catalog=bump_catalog,
            span=head_span,
        )

    def _parse_version_literal(self) -> VersionLiteral:
        # The version literal is IDENT('vN') followed by one or more
        # ``DOT NUMBER`` pairs. The IDENT's lexeme must match the
        # ``v\d+`` pattern; the parser splits 'v' from the trailing
        # digits to extract the major component.
        ident = self.expect(
            TokenKind.IDENT,
            "version literal head (e.g. 'v1.0' or 'v2.3')",
        )
        head_span = self._span(ident)
        if not (
            len(ident.lexeme) >= 2
            and ident.lexeme[0] == "v"
            and ident.lexeme[1:].isdigit()
        ):
            raise ParseError(
                f"Version literal must begin with 'v' followed by "
                f"digits (e.g. 'v1.0', 'v2.3'), got {ident.lexeme!r}.",
                head_span,
            )
        components: list[int] = [int(ident.lexeme[1:])]
        # At least one trailing ``DOT NUMBER`` pair is required; Phase
        # 2.5 uses two-component versions (``vN.M``).
        if not self.check(TokenKind.DOT):
            raise ParseError(
                f"Version literal {ident.lexeme!r} is missing the "
                f"minor component (e.g. 'v1.0'). Phase 2.5 requires "
                f"at least two-component versions.",
                head_span,
            )
        while self.match(TokenKind.DOT):
            num_tok = self.expect(
                TokenKind.NUMBER,
                "numeric version component after '.'",
            )
            components.append(int(num_tok.lexeme))
        return VersionLiteral(
            components=tuple(components),
            span=head_span,
        )

    def _parse_export_decl(self) -> ExportDecl:
        head = self.expect(TokenKind.EXPORT, "'export'")
        head_span = self._span(head)
        name_tok = self.expect(
            TokenKind.IDENT,
            "exported symbol name after 'export'",
        )
        self.expect(TokenKind.COLON, "':' after exported symbol name")
        type_path = self._parse_type_path("export type")
        return ExportDecl(
            name=name_tok.lexeme,
            type_path=type_path,
            span=head_span,
        )

    def _parse_major_version_bump(self) -> MajorVersionBump:
        head = self.expect(TokenKind.MAJOR_VERSION_BUMP, "'major_version_bump'")
        head_span = self._span(head)
        self.expect(
            TokenKind.LBRACE,
            "'{' to open the major_version_bump catalog",
        )
        removes: list[RemovesEntry] = []
        renames: list[RenamesEntry] = []
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            if self.check(TokenKind.REMOVES):
                removes.extend(self._parse_removes_entries())
                continue
            if self.check(TokenKind.RENAMES):
                renames.extend(self._parse_renames_entries())
                continue
            tok = self.peek()
            raise ParseError(
                f"Unexpected {tok.kind.name} {tok.lexeme!r} inside "
                f"major_version_bump catalog; expected 'removes' or "
                f"'renames'.",
                self._span(tok),
            )
        self.expect(
            TokenKind.RBRACE,
            "'}' to close the major_version_bump catalog",
        )
        return MajorVersionBump(
            removes=tuple(removes),
            renames=tuple(renames),
            span=head_span,
        )

    def _parse_removes_entries(self) -> list[RemovesEntry]:
        self.expect(TokenKind.REMOVES, "'removes'")
        self.expect(TokenKind.COLON, "':' after 'removes'")
        entries: list[RemovesEntry] = []
        first = self.expect(
            TokenKind.IDENT,
            "removed symbol name after 'removes:'",
        )
        entries.append(RemovesEntry(name=first.lexeme, span=self._span(first)))
        while self.match(TokenKind.COMMA):
            tok = self.expect(
                TokenKind.IDENT,
                "removed symbol name after ','",
            )
            entries.append(RemovesEntry(name=tok.lexeme, span=self._span(tok)))
        return entries

    def _parse_renames_entries(self) -> list[RenamesEntry]:
        self.expect(TokenKind.RENAMES, "'renames'")
        self.expect(TokenKind.COLON, "':' after 'renames'")
        entries: list[RenamesEntry] = [self._parse_one_rename()]
        while self.match(TokenKind.COMMA):
            entries.append(self._parse_one_rename())
        return entries

    def _parse_one_rename(self) -> RenamesEntry:
        old_tok = self.expect(
            TokenKind.IDENT,
            "old symbol name in rename entry",
        )
        self.expect(
            TokenKind.ARROW,
            "'->' between old and new names in rename entry",
        )
        new_tok = self.expect(
            TokenKind.IDENT,
            "new symbol name in rename entry",
        )
        return RenamesEntry(
            old_name=old_tok.lexeme,
            new_name=new_tok.lexeme,
            span=self._span(old_tok),
        )

    # ---- Phase 2.7 (Session 1.6): Mizan calibration block ----------------
    #
    # Grammar:
    #
    #     MizanDecl  := 'mizan' IDENT '{' MizanField* '}'
    #     MizanField := MizanFieldHead ':' Expression ','?
    #     MizanFieldHead := 'la_tatghaw' | 'la_tukhsiru' | 'bil_qist'
    #
    # The field-head position accepts ONLY the three canonical
    # keyword tokens. Any other token (including IDENT) at that
    # position is a parse error — this is the §6.4 field-head
    # position enforcement that routes M3 (unknown field) to the
    # parser layer, leaving the checker to handle only M1
    # (missing), M2 (duplicate), and M4 (out-of-order) over a
    # well-formed AST.

    _MIZAN_FIELD_HEAD_TOKENS: "tuple[TokenKind, ...]" = (
        TokenKind.LA_TATGHAW,
        TokenKind.LA_TUKHSIRU,
        TokenKind.BIL_QIST,
    )

    def parse_mizan_decl(self) -> MizanDecl:
        head = self.expect(TokenKind.MIZAN, "'mizan'")
        head_span = self._span(head)
        name_tok = self.expect(
            TokenKind.IDENT,
            "mizan calibration block name after 'mizan'",
        )
        self.expect(
            TokenKind.LBRACE,
            "'{' to open the mizan calibration block",
        )
        fields: list[MizanField] = []
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            fields.append(self._parse_mizan_field())
            # Optional trailing comma (consistent with Incomplete
            # literal grammar from Phase 2.6).
            self.match(TokenKind.COMMA)
        self.expect(
            TokenKind.RBRACE,
            "'}' to close the mizan calibration block",
        )
        return MizanDecl(
            name=name_tok.lexeme,
            fields=tuple(fields),
            span=head_span,
        )

    def _parse_mizan_field(self) -> MizanField:
        # Field-head position enforcement (§6.4): only the three
        # canonical keyword tokens are accepted here. Any other
        # token raises a parse error with the diagnosis text
        # pinned by the v0.5.0 grammar contract.
        if not self.check(*self._MIZAN_FIELD_HEAD_TOKENS):
            tok = self.peek()
            raise ParseError(
                f"unexpected token in mizan field-head position; "
                f"expected one of la_tatghaw, la_tukhsiru, bil_qist. "
                f"Got {tok.kind.name} {tok.lexeme!r}. Per Phase 2.7 "
                f"§6.4, mizan field heads are keyword tokens; an "
                f"identifier or other token here cannot be promoted "
                f"to a field name.",
                self._span(tok),
            )
        head = self.advance()
        # Map the token kind back to the canonical Arabic name.
        # The lexeme of the keyword token IS the canonical name
        # (lexer maps "la_tatghaw" → TokenKind.LA_TATGHAW), so we
        # use the lexeme directly.
        self.expect(
            TokenKind.COLON,
            "':' after mizan field name",
        )
        value = self._parse_expression()
        return MizanField(
            name=head.lexeme,
            value=value,
            span=self._span(head),
        )

    # ---- Phase 2.8 (Session 1.7): Tanzil build-ordering block ------------
    #
    # Grammar:
    #
    #     TanzilDecl      := 'tanzil' IDENT '{' DependencyEntry* '}'
    #     DependencyEntry := 'depends_on' ':' IDENT
    #
    # The field-head position accepts ONLY the canonical
    # `depends_on` keyword. Any other token (including IDENT) at
    # that position is a parse error — same routing discipline as
    # Mizan §6.4 / M3, leaving the checker to handle only T1
    # (self-dependency), T2 (duplicate), and T3 (empty-block
    # advisory) over a well-formed AST.

    def parse_tanzil_decl(self) -> TanzilDecl:
        head = self.expect(TokenKind.TANZIL, "'tanzil'")
        head_span = self._span(head)
        name_tok = self.expect(
            TokenKind.IDENT,
            "tanzil build-ordering block name after 'tanzil'",
        )
        self.expect(
            TokenKind.LBRACE,
            "'{' to open the tanzil build-ordering block",
        )
        dependencies: list[DependencyEntry] = []
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            dependencies.append(self._parse_dependency_entry())
        self.expect(
            TokenKind.RBRACE,
            "'}' to close the tanzil build-ordering block",
        )
        return TanzilDecl(
            name=name_tok.lexeme,
            dependencies=tuple(dependencies),
            span=head_span,
        )

    def _parse_dependency_entry(self) -> DependencyEntry:
        # Field-head position enforcement: only the `depends_on`
        # keyword is accepted. Any other token raises ParseError
        # with the diagnosis text pinned by the v0.6.0 grammar
        # contract. By the time a DependencyEntry reaches the
        # checker, every entry's field head is canonical by
        # construction.
        if not self.check(TokenKind.DEPENDS_ON):
            tok = self.peek()
            raise ParseError(
                f"unexpected token in tanzil dependency position; "
                f"expected 'depends_on', got {tok.kind.name} "
                f"{tok.lexeme!r}. Per Phase 2.8, tanzil field heads "
                f"are keyword tokens; an unknown entry here cannot "
                f"be promoted to a field name.",
                self._span(tok),
            )
        head = self.advance()
        self.expect(
            TokenKind.COLON,
            "':' after 'depends_on'",
        )
        path_tok = self.expect(
            TokenKind.IDENT,
            "module name after 'depends_on:'",
        )
        return DependencyEntry(
            module_path=path_tok.lexeme,
            span=self._span(head),
        )

    # ---- function definition ----------------------------------------------

    def parse_function_def(self) -> FunctionDef:
        head = self.expect(TokenKind.FN, "'fn'")
        head_span = self._span(head)
        name_tok = self.expect(TokenKind.IDENT, "function name after 'fn'")
        self.expect(TokenKind.LPAREN, "'(' to open parameter list")
        # Phase 2.4 (Session 1.3): replaces F1 — the opaque parameter
        # eater is gone. Parameters are now parsed strictly:
        # ``IDENT ':' type_path``, comma-separated. The zahir/batin
        # checker reads ``params`` to determine each parameter's
        # declared layer.
        params = self._parse_param_list()
        self.expect(TokenKind.RPAREN, "')' to close parameter list")
        # Phase 2.4 (Session 1.3): replaces F2 — the opaque return-
        # type eater is gone. The return type, if present, is parsed
        # as a ``TypePath``. Empty arrow forms (``-> {``) are now a
        # parse error rather than a silent loss of intent.
        # Phase 2.6 (Session 1.5) extends the return-type parser to
        # accept binary unions (``TypePath '|' TypePath``) so that
        # ``-> Integrity | Incomplete`` parses to a UnionType node.
        return_type = None
        if self.match(TokenKind.ARROW):
            return_type = self._parse_return_type()
        self.expect(TokenKind.LBRACE, "'{' to open function body")
        # Phase 2.6 (Session 1.5): the function body is now a
        # statement tree, not a flat list of calls. We populate three
        # parallel collections from a single body walk:
        #   * ``statements`` — the structured tree (new, for the
        #     scan-incomplete checker)
        #   * ``calls`` — flattened CallRef list (for the bismillah
        #     checker; pre-2.6 contract preserved)
        #   * ``accesses`` — flattened LayerAccess list (for the
        #     zahir/batin checker; pre-2.6 contract preserved)
        # The walk is recursive: an IfStmt's body is descended for
        # nested calls and accesses.
        statements: list = []  # list[Statement]
        calls: list[CallRef] = []
        accesses: list[LayerAccess] = []
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            stmt = self._parse_statement(calls, accesses)
            statements.append(stmt)
        self.expect(TokenKind.RBRACE, "'}' to close function body")
        return FunctionDef(
            name=name_tok.lexeme,
            calls=tuple(calls),
            span=head_span,
            params=params,
            return_type=return_type,
            accesses=tuple(accesses),
            statements=tuple(statements),
        )

    # ---- Phase 2.6: return-type parser (extends Phase 2.4) ----------------

    def _parse_return_type(self):
        """Parse a return-type expression. Phase 2.6 forms:

        * ``TypePath`` — a single type, e.g. ``Integrity`` or
          ``Document.zahir``.
        * ``TypePath '|' TypePath`` — a binary union, e.g.
          ``Integrity | Incomplete``.

        Phase 2.6 restricts unions to two arms (binary). Triple
        unions are not supported; a future fixture requiring them
        would extend the grammar additively to a tuple of arms.
        """
        left = self._parse_type_path("return type")
        if not self.check(TokenKind.PIPE):
            return left
        # Union form. The pipe token's span anchors the union node.
        pipe_tok = self.advance()
        right = self._parse_type_path("right side of return-type union")
        return UnionType(
            left=left,
            right=right,
            span=self._span(pipe_tok),
        )

    # ---- Phase 2.6: statement and expression parsers ----------------------

    def _parse_statement(
        self,
        calls: list[CallRef],
        accesses: list[LayerAccess],
        *,
        depth: int = 0,
    ):
        """Parse a single statement at function-body scope.

        ``calls`` and ``accesses`` are accumulators threaded through
        the parse so that the pre-2.6 ``fn.calls`` and ``fn.accesses``
        contracts continue to receive every CallRef and LayerAccess
        nested anywhere in the body — calls inside if-bodies are
        flattened to the top level, preserving the bismillah- and
        zahir/batin-checker contracts.

        ``depth`` (v0.11.0 / Q9) is the static-recursion depth-guard.
        Each nested ``if { ... }`` increments it through
        :meth:`_parse_if_statement`. When the depth crosses
        :data:`MAX_NESTING_DEPTH`, a structured :class:`ParseError` is
        raised at the current token's source span instead of letting
        Python's recursion limit fire a free-form ``RecursionError``.

        Phase 2.6 statement forms:
          * ``return <expr>``        → :class:`ReturnStmt`
          * ``if <expr> { ... }``    → :class:`IfStmt`
          * ``<qual_name> ( ... )``  → :class:`CallStmt` (legacy form)
        """
        if depth > MAX_NESTING_DEPTH:
            tok = self.peek()
            raise ParseError(
                f"Nesting depth at line {tok.line} exceeds the parser "
                f"limit ({MAX_NESTING_DEPTH}). The parser supports "
                f"finite nesting; this input exceeds the limit. Split "
                f"deeply nested blocks into smaller helper functions. "
                f"(Q9: this preserves marad.py's structured-diagnosis "
                f"contract on hostile input; the pre-v0.11.0 parser "
                f"would have produced a Python RecursionError "
                f"traceback at this point.)",
                self._span(tok),
            )
        if self.check(TokenKind.RETURN):
            return self._parse_return_statement()
        if self.check(TokenKind.IF):
            return self._parse_if_statement(calls, accesses, depth=depth)
        if self.check(TokenKind.IDENT):
            head_tok = self.peek()
            call, call_accesses = self._parse_call()
            calls.append(call)
            accesses.extend(call_accesses)
            return CallStmt(call=call, span=self._span(head_tok))
        tok = self.peek()
        raise ParseError(
            f"Inside a function body Phase 2.6 expects a statement: "
            f"`return <expr>`, `if <expr> {{ ... }}`, or a call "
            f"expression `name(...)`. Found {tok.kind.name} "
            f"{tok.lexeme!r}.",
            self._span(tok),
        )

    def _parse_return_statement(self) -> ReturnStmt:
        head = self.expect(TokenKind.RETURN, "'return'")
        value = self._parse_expression()
        return ReturnStmt(value=value, span=self._span(head))

    def _parse_if_statement(
        self,
        calls: list[CallRef],
        accesses: list[LayerAccess],
        *,
        depth: int = 0,
    ) -> IfStmt:
        head = self.expect(TokenKind.IF, "'if'")
        condition = self._parse_expression()
        self.expect(TokenKind.LBRACE, "'{' to open if-body")
        body: list = []
        # v0.11.0 (Q9): nested statements parse at depth+1 so the
        # depth-guard in _parse_statement fires before Python's
        # recursion limit does.
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            body.append(
                self._parse_statement(calls, accesses, depth=depth + 1)
            )
        self.expect(TokenKind.RBRACE, "'}' to close if-body")

        # Phase 3.0 (D15) — optional else arm. The else keyword,
        # when present, is consumed here; absent, we leave the
        # token stream untouched so the surrounding statement
        # loop continues normally. The empty-tuple default on the
        # IfStmt dataclass preserves Phase 2.6 semantics for the
        # no-else case.
        else_body: list = []
        if self.check(TokenKind.ELSE):
            self.advance()  # consume 'else'
            self.expect(TokenKind.LBRACE, "'{' to open else-body")
            while not self.check(TokenKind.RBRACE, TokenKind.EOF):
                else_body.append(
                    self._parse_statement(calls, accesses, depth=depth + 1)
                )
            self.expect(TokenKind.RBRACE, "'}' to close else-body")

        return IfStmt(
            condition=condition,
            body=tuple(body),
            span=self._span(head),
            else_body=tuple(else_body),
        )

    def _parse_expression(self):
        """Parse a single expression value.

        Phase 2.7 (Session 1.6): the expression entry-point now
        wraps the Phase 2.6 primary-expression parser with a
        non-associative binary-comparison layer. After parsing one
        primary expression, if the next token is a comparison
        operator (LT or GT) we consume it, parse the right-hand
        primary, and return a :class:`BinaryComparisonExpr`. If
        ANOTHER comparison operator follows that, we raise — the
        grammar is non-associative; chained comparisons (``a < b
        < c``) are a parse error rather than a silent left- or
        right-associative interpretation.

        See Phase 2.7 §6.4 for the rationale: silent expansion of
        ``a < b < c`` to ``a < b AND b < c`` is exactly the kind
        of zahir/batin divergence the language is built to detect
        (the surface looks like one comparison; the depth would be
        two ANDed comparisons).
        """
        left = self._parse_primary_expression()
        if not self.check(TokenKind.LT, TokenKind.GT):
            return left
        op_tok = self.advance()
        op = (
            ComparisonOp.LT if op_tok.kind is TokenKind.LT
            else ComparisonOp.GT
        )
        right = self._parse_primary_expression()
        # Non-associativity check: another comparison operator at
        # this level is a parse error.
        if self.check(TokenKind.LT, TokenKind.GT):
            stray = self.peek()
            raise ParseError(
                f"Chained comparison `a < b < c` (and any chain of "
                f"comparison operators) is not permitted in Furqan; "
                f"the comparison grammar is non-associative. "
                f"Parenthesise explicitly or restructure the "
                f"expression. (Per Phase 2.7 §6.4: silent expansion "
                f"to `a < b AND b < c` would be a zahir/batin "
                f"divergence — the source surface declares one "
                f"comparison, the depth would be two ANDed "
                f"comparisons.)",
                self._span(stray),
            )
        return BinaryComparisonExpr(
            left=left,
            op=op,
            right=right,
            span=self._span(op_tok),
        )

    def _parse_primary_expression(self):
        """Parse a single primary (non-comparison) expression.

        Phase 2.6 expression forms (a deliberately small set —
        anything beyond these belongs to a later phase):
          * ``not <expr>``                       → :class:`NotExpr`
          * ``Incomplete { reason: ..., ... }``  → :class:`IncompleteLiteral`
          * ``Integrity``                        → :class:`IntegrityLiteral`
          * ``"..."`` (STRING)                   → :class:`StringLiteral`
          * dotted NUMBER form (e.g. ``0.5``)    → :class:`NumberLiteral`
          * ``foo(...)`` or ``a.b.c(...)``       → :class:`IdentExpr`
            (call form folded into the IDENT path; the call's
            arguments are absorbed but the head is recorded)
          * ``foo``                              → :class:`IdentExpr`

        Phase 2.7 wraps this with a non-associative binary-
        comparison layer in :func:`_parse_expression` above.
        """
        if self.check(TokenKind.NOT):
            head = self.advance()
            operand = self._parse_expression()
            return NotExpr(operand=operand, span=self._span(head))
        if self.check(TokenKind.STRING):
            return self._parse_string_literal()
        if self.check(TokenKind.NUMBER):
            return self._parse_number_literal()
        if self.check(TokenKind.IDENT):
            head_tok = self.peek()
            # Look-ahead: ``Incomplete`` followed by ``{`` is the
            # constructor literal; ``Integrity`` standalone is the
            # bare-Integrity form; any other IDENT is either a call
            # or a bare identifier reference.
            if (
                head_tok.lexeme == "Incomplete"
                and self.pos + 1 < len(self.tokens)
                and self.tokens[self.pos + 1].kind is TokenKind.LBRACE
            ):
                return self._parse_incomplete_literal()
            if head_tok.lexeme == "Integrity":
                self.advance()
                return IntegrityLiteral(span=self._span(head_tok))
            # Fall-through: bare identifier or call.
            self.advance()
            # If the next token is LPAREN we have a call; consume
            # the argument list opaquely (Phase 2.6 has no need to
            # extract callee arguments as expressions yet — the
            # arguments are absorbed by the existing call-arg
            # tolerance with brace-rejection from Session 1.2).
            if self.check(TokenKind.LPAREN):
                self.advance()  # consume LPAREN
                paren_depth = 1
                while paren_depth > 0 and not self.check(TokenKind.EOF):
                    if self.match(TokenKind.LPAREN):
                        paren_depth += 1
                        continue
                    if self.match(TokenKind.RPAREN):
                        paren_depth -= 1
                        continue
                    if self.check(TokenKind.LBRACE, TokenKind.RBRACE):
                        # Same Session-1.2 rejection rule: braces are
                        # block delimiters, not expression tokens.
                        stray = self.peek()
                        raise ParseError(
                            f"Stray brace inside call argument list "
                            f"(Phase 2.6 has no expression-shaped "
                            f"brace tokens; this would silently mask "
                            f"AST extraction).",
                            self._span(stray),
                        )
                    self.advance()
            return IdentExpr(
                name=head_tok.lexeme,
                span=self._span(head_tok),
            )
        tok = self.peek()
        raise ParseError(
            f"Phase 2.6 expression position expects one of: "
            f"`not <expr>`, a string literal, a number, an "
            f"identifier (with optional call form), the bare "
            f"`Integrity` keyword, or an `Incomplete {{ ... }}` "
            f"literal. Found {tok.kind.name} {tok.lexeme!r}.",
            self._span(tok),
        )

    def _parse_string_literal(self) -> StringLiteral:
        tok = self.expect(TokenKind.STRING, "string literal")
        # The lexeme includes the surrounding quotes AND any backslash
        # escapes in their raw form; the AST node carries the
        # unwrapped, unescaped content. The tokenizer has already
        # validated escape shape at lex time, so unescape here cannot
        # encounter an unknown sequence (Phase 3.0 D14).
        assert tok.lexeme.startswith('"') and tok.lexeme.endswith('"')
        return StringLiteral(
            value=_unescape_string(tok.lexeme[1:-1]),
            span=self._span(tok),
        )

    def _parse_number_literal(self) -> NumberLiteral:
        head = self.expect(TokenKind.NUMBER, "number literal")
        # Phase 2.5 lexer choice: NUMBER is integer-only. Multi-
        # component numerics (decimals, version-style) are
        # reconstructed at parse time using DOT separators.
        parts: list[str] = [head.lexeme]
        while self.match(TokenKind.DOT):
            num = self.expect(
                TokenKind.NUMBER,
                "numeric component after '.'",
            )
            parts.append(num.lexeme)
        return NumberLiteral(
            lexeme=".".join(parts),
            span=self._span(head),
        )

    def _parse_incomplete_literal(self) -> IncompleteLiteral:
        head = self.expect(TokenKind.IDENT, "'Incomplete'")
        assert head.lexeme == "Incomplete"
        self.expect(TokenKind.LBRACE, "'{' to open Incomplete literal")
        fields: list[IncompleteField] = []
        while not self.check(TokenKind.RBRACE, TokenKind.EOF):
            fields.append(self._parse_incomplete_field())
            # Optional trailing comma between fields.
            if not self.check(TokenKind.RBRACE, TokenKind.EOF):
                # Allow either `,` separator or whitespace-only.
                self.match(TokenKind.COMMA)
        self.expect(TokenKind.RBRACE, "'}' to close Incomplete literal")
        return IncompleteLiteral(
            fields=tuple(fields),
            span=self._span(head),
        )

    def _parse_incomplete_field(self) -> IncompleteField:
        name_tok = self.expect(
            TokenKind.IDENT,
            "field name inside Incomplete literal",
        )
        self.expect(TokenKind.COLON, "':' after field name")
        # Field-value dispatch by field name (Phase 2.6 minimum):
        #   * ``reason``           → STRING
        #   * ``max_confidence``   → NUMBER ('.' NUMBER)*
        #   * ``partial_findings`` → IDENT (',' IDENT)*  (IdentList)
        # Unknown field names accept a generic expression so the
        # parser does not lock the field set early; the checker
        # (Case B) is responsible for the required-field check.
        if name_tok.lexeme == "reason":
            value = self._parse_string_literal()
        elif name_tok.lexeme == "max_confidence":
            value = self._parse_number_literal()
        elif name_tok.lexeme == "partial_findings":
            value = self._parse_ident_list_expr()
        else:
            value = self._parse_expression()
        return IncompleteField(
            name=name_tok.lexeme,
            value=value,
            span=self._span(name_tok),
        )

    def _parse_ident_list_expr(self) -> IdentList:
        head = self.expect(
            TokenKind.IDENT,
            "identifier in partial_findings list",
        )
        items: list[str] = [head.lexeme]
        while self.match(TokenKind.COMMA):
            tok = self.expect(
                TokenKind.IDENT,
                "identifier after ',' in partial_findings list",
            )
            items.append(tok.lexeme)
        return IdentList(
            items=tuple(items),
            span=self._span(head),
        )

    def _parse_call(self) -> tuple[CallRef, list[LayerAccess]]:
        # Phase 2.4 (Session 1.3): _parse_call now returns BOTH the
        # CallRef (for the bismillah scope checker, unchanged
        # behaviour) AND a list of LayerAccess records pre-scanned
        # from the call's argument tokens (input to the zahir/batin
        # checker). The arg-list consumer keeps the Session-1.2
        # brace-rejection contract; the pre-scan only *reads* tokens,
        # it does not change the rejection contract.
        if not self.check(TokenKind.IDENT):
            tok = self.peek()
            raise ParseError(
                f"Inside a function body Phase 2 expects only call "
                f"expressions of the form 'name()' or 'a.b()'. Found "
                f"{tok.kind.name} {tok.lexeme!r}. Statement-level "
                f"constructs (assignments, control flow) are a Phase-3 "
                f"surface; the Bismillah scope checker only needs call "
                f"references to do its work.",
                self._span(tok),
            )
        head_tok = self.peek()
        path = self._parse_qual_name()
        self.expect(TokenKind.LPAREN, "'(' after call name")
        accesses: list[LayerAccess] = []
        # Argument list is consumed but not parsed (no expressions in
        # Phase 2). We tolerate identifiers, dots, commas, qualified
        # names, and nested parens inside the arg list; a real nested
        # call would need expression parsing, which is out of scope.
        #
        # Session-1.2 hardening (Perplexity review item c.3):
        # ----------------------------------------------------
        # Brace tokens ('{' / '}') inside the argument list are
        # structural errors. Phase 2's surface syntax uses braces
        # ONLY as block delimiters (function bodies, type bodies,
        # bismillah blocks); braces never appear inside expressions.
        # A brace inside an arg list would silently mask CallRef
        # extraction — for example ``x({ y() })`` would parse as
        # ``x()`` with the call to ``y`` lost in the opaque region.
        # The Bismillah scope checker depends on extraction being
        # complete, so a quietly-eaten brace is a Process-2 risk in
        # the parser itself.
        #
        # The fix is the simplest correct version: any brace token
        # encountered while the arg-list consumer is running raises
        # ParseError immediately. This is additive on the rejection
        # side (no previously-accepted input is now rejected that
        # was structurally valid) and consistent with the additive-
        # only invariant in NAMING.md §6.
        paren_depth = 1
        while paren_depth > 0 and not self.check(TokenKind.EOF):
            if self.match(TokenKind.LPAREN):
                paren_depth += 1
                continue
            if self.match(TokenKind.RPAREN):
                paren_depth -= 1
                continue
            if self.check(TokenKind.LBRACE):
                stray = self.peek()
                raise ParseError(
                    "Stray '{' inside call argument list. Phase 2 has no "
                    "expression grammar that uses brace tokens; a brace "
                    "inside an argument list would silently mask CallRef "
                    "extraction (the Bismillah scope checker depends on "
                    "extraction being complete). If you meant a block, "
                    "close the call first with ')' before opening it.",
                    self._span(stray),
                )
            if self.check(TokenKind.RBRACE):
                stray = self.peek()
                raise ParseError(
                    "Stray '}' inside call argument list. The arg list "
                    "must close with ')' before any block-level brace "
                    "appears. A '}' here would either close a structure "
                    "outside the arg list (silently corrupting the AST) "
                    "or balance an earlier stray '{' (which is itself a "
                    "structural error in Phase 2).",
                    self._span(stray),
                )
            # Phase 2.4 (Session 1.3): layer-access pre-scan.
            # Recognise the pattern ``IDENT '.' (zahir|surface|batin|
            # depth)`` inside the argument tokens and emit a
            # LayerAccess record. The scan is non-invasive: it does
            # not change which inputs the consumer accepts or rejects;
            # it only annotates the AST with structured access
            # information that the zahir/batin checker reads.
            #
            # We only match if the IDENT is immediately followed by a
            # DOT and a layer-keyword token. Anything else (a bare
            # identifier, an IDENT.IDENT path, a stray symbol) is
            # passed through to ``self.advance()`` for the existing
            # opaque-tolerance behaviour.
            if (
                self.check(TokenKind.IDENT)
                and self.pos + 2 < len(self.tokens)
                and self.tokens[self.pos + 1].kind is TokenKind.DOT
                and self.tokens[self.pos + 2].kind in _LAYER_OF_TOKEN
            ):
                ident_tok = self.advance()        # IDENT (param name)
                self.advance()                    # DOT
                layer_tok = self.advance()        # layer keyword
                accesses.append(LayerAccess(
                    param_name=ident_tok.lexeme,
                    layer=_LAYER_OF_TOKEN[layer_tok.kind],
                    span=self._span(ident_tok),
                    layer_alias_used=layer_tok.lexeme,
                ))
                continue
            self.advance()
        if paren_depth != 0:
            raise ParseError(
                "Unterminated call argument list — missing ')'",
                self._span(head_tok),
            )
        return (
            CallRef(path=path, span=self._span(head_tok)),
            accesses,
        )


# ---------------------------------------------------------------------------
# Phase 2.6 — statement-tree walker (Session 1.5)
# ---------------------------------------------------------------------------

def _collect_calls_and_accesses(
    stmt,
    calls: list[CallRef],
    accesses: list[LayerAccess],
) -> None:
    """Walk a statement and append CallRefs and LayerAccesses found
    in or beneath it to the provided lists.

    Phase 2.6 introduces statement-level grammar in function bodies.
    The pre-2.6 contract (``fn.calls`` is a flat tuple of every
    CallRef in the body, in source order) is preserved by this
    walker: call statements append directly; if-statements recurse
    into their body. Phase 2.6 expressions (Incomplete literal,
    return values, predicates) currently produce no nested calls,
    so the walker only needs to descend into IfStmt bodies.
    """
    if isinstance(stmt, CallStmt):
        calls.append(stmt.call)
        # Layer accesses are pre-scanned during _parse_call and
        # already attached to the call's span; we do not re-extract
        # here. Phase 2.4's accesses pre-scan ran inside the call's
        # arg-list consumer; that data is captured on the second
        # element of the _parse_call tuple but is folded into the
        # caller's list above.
        return
    if isinstance(stmt, IfStmt):
        for inner in stmt.body:
            _collect_calls_and_accesses(inner, calls, accesses)
        return
    if isinstance(stmt, ReturnStmt):
        # Return statements may carry expressions, but Phase 2.6
        # expressions do not produce CallRefs (calls inside
        # expressions are folded into IdentExpr names without
        # CallRef extraction). Future-phase work if needed.
        return
    # Unknown statement kind — defensive default.
    return


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(source: str, *, file: str = "<source>") -> Module:
    """Parse a Furqan source string into a :class:`Module`.

    ``file`` is used in :class:`SourceSpan` records so diagnostics can
    cite the path. For in-memory input, ``"<source>"`` is the
    conventional placeholder.

    v0.11.0 (Q9 belt-and-suspenders): any :class:`RecursionError`
    that escapes :data:`MAX_NESTING_DEPTH`'s static guard is caught
    here and re-raised as a structured :class:`ParseError`. The
    static guard inside :meth:`_Parser._parse_statement` is the
    primary defence; this catch covers any future recursive parse
    path the depth-counter does not yet thread through. Callers see
    a structured ``ParseError`` regardless of which guard fires.
    """
    try:
        tokens = tokenize(source)
        parser = _Parser(tokens=tokens, file=file)
        module = parser.parse_module()
        # After parsing the module the next token must be EOF
        # otherwise there is trailing junk we silently ignored,
        # which would be a zahir/batin divergence on the parser
        # itself.
        tail = parser.peek()
        if tail.kind is not TokenKind.EOF:
            raise ParseError(
                f"Unexpected trailing token {tail.lexeme!r} after the module body.",
                parser._span(tail),
            )
        return module
    except RecursionError:
        raise ParseError(
            "Input recursion exceeds the parser's stack budget. "
            "This is a Furqan parser limit, not a grammar error: "
            "the depth-guard at MAX_NESTING_DEPTH did not fire on "
            "this input shape, but Python's recursion limit did. "
            "Reduce nesting and retry. (Q9: belt-and-suspenders "
            "conversion of RecursionError to a structured "
            "ParseError. The static guard is the primary defence; "
            "this catch covers parse paths the depth-counter does "
            "not yet thread through.)",
            SourceSpan(file=file, line=1, column=1),
        ) from None


__all__ = [
    "ParseError",
    "parse",
]
