"""
Furqan AST nodes — Phase 2 minimal surface syntax.

Every node is a frozen dataclass. The AST is immutable by construction
— a checker pass walks but never mutates. This is the structural form
of the additive-only invariant applied to the AST itself: a checker
that mutates the tree is by definition operating on a different tree
than the one it was given, breaking the surface/depth correspondence
the language is built to enforce.

Node set (Phase 2.2):

* :class:`Module`         — the top-level translation unit; a list of
                            top-level items (Bismillah blocks and
                            function definitions) plus the source-file
                            path.
* :class:`BismillahBlock` — the four-field Bismillah declaration.
* :class:`FunctionDef`    — a function definition, with a list of call
                            references encountered in its body. Phase
                            2 does not parse expressions; the body is
                            modelled as the set of qualified names
                            invoked, which is what the Bismillah scope
                            checker needs.
* :class:`CallRef`        — a single call site: a qualified name path
                            (e.g. ``parse_files`` or ``stdlib.io.read``)
                            with the location at which it was found.

The AST is intentionally *thinner* than the eventual full surface
syntax. Adding a node class is additive; removing or renaming one is
forbidden by NAMING.md §6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final


# ---------------------------------------------------------------------------
# Common shape: every node carries a source location for diagnostic
# wrapping. Phase 2 records line and column at the *first token* of the
# node; the parser assigns these from the token stream.
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SourceSpan:
    """1-indexed source position pointing at the node's first token.

    ``file`` is the source path (or ``"<source>"`` for in-memory input).
    A ``SourceSpan`` is the load-bearing field on every diagnostic; an
    error without a SourceSpan is not yet a marad (NAMING.md §5).
    """

    file: str
    line: int
    column: int


# ---------------------------------------------------------------------------
# CallRef
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CallRef:
    """A reference to a callable, encountered inside a function body.

    The ``path`` field is a tuple of identifier components. A bare
    ``parse_files`` is ``("parse_files",)``; a qualified ``self.scan`` is
    ``("self", "scan")``. The Bismillah scope checker compares the
    *first* component (the head of the path) against the module's
    declared ``not_scope`` list. This matches the thesis paper §3.1
    rule: a Bismillah block excludes *operations*, and an operation is
    named by its head identifier.
    """

    path: tuple[str, ...]
    span: SourceSpan

    @property
    def head(self) -> str:
        """First component of the call path — the symbol the checker
        compares against ``not_scope``."""
        return self.path[0]

    @property
    def qualified(self) -> str:
        """Dotted form, used in diagnostics for legibility."""
        return ".".join(self.path)


# ---------------------------------------------------------------------------
# BismillahBlock
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class BismillahBlock:
    """The four-field Bismillah declaration at the head of a module.

    Per Furqan thesis §3.1, every module opens with four fields:

    * ``authority`` — the standards or contracts that govern this unit.
    * ``serves``    — the level of the purpose hierarchy plus the
                      specific objective. Phase 2 records this as the
                      raw qualified-name path (e.g. ``purpose_hierarchy
                      .truth_over_falsehood``); the Mizan-aware checker
                      in a later session will validate the hierarchy
                      reference.
    * ``scope``     — operations permitted inside this module.
    * ``not_scope`` — operations explicitly excluded. The Bismillah
                      scope checker (this session's deliverable) is
                      responsible for verifying that no call site in the
                      module body invokes a head identifier listed here.

    The ``alias_used`` field records whether the user wrote
    ``bismillah`` (canonical) or ``scope_block`` (English alias). The
    parser treats them identically; the field is preserved so an error
    message can quote the source faithfully.
    """

    name: str
    authority: tuple[str, ...]
    serves: tuple[tuple[str, ...], ...]      # one or more qualified-name paths
    scope: tuple[str, ...]
    not_scope: tuple[str, ...]
    span: SourceSpan
    alias_used: str  # "bismillah" or "scope_block"


# ---------------------------------------------------------------------------
# FunctionDef
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FunctionDef:
    """A function definition.

    Sessions 1.0–1.2 (Phase 2.0–2.3): the Bismillah scope checker only
    needs the function's call-reference set, so the body is modelled as
    a tuple of :class:`CallRef`. Phase 2.4 (Session 1.3) extends the
    node additively with three new fields:

    * ``params``     — typed parameter declarations (was opaquely
                       consumed pre-2.4; replaces F1 from Session 1.2)
    * ``return_type``— optional :class:`TypePath` after ``->`` (replaces
                       F2 from Session 1.2)
    * ``accesses``   — :class:`LayerAccess` records pre-scanned from
                       the body's call-argument lists; the input to the
                       zahir/batin checker

    Every existing v0.1.x reader continues to work: ``fn.name``,
    ``fn.calls``, ``fn.span`` all return the same values they did at
    Session 1.2. The new fields are pure additions on the read
    surface.
    """

    name: str
    calls: tuple[CallRef, ...]
    span: SourceSpan
    # Phase 2.4 additive extensions — ``()`` and ``None`` defaults
    # preserve the v0.1.x construction shape for any caller that
    # somehow still constructs FunctionDef without these fields. The
    # parser is the only constructor in practice and always passes
    # the new fields explicitly.
    params: tuple[ParamDecl, ...] = ()
    return_type: "ReturnType | None" = None
    accesses: tuple[LayerAccess, ...] = ()
    # Phase 2.6 additive extension — the structured statement tree.
    # ``calls`` and ``accesses`` are derived from ``statements`` by
    # walking the tree; pre-2.6 readers continue to see identical
    # content on those fields. The scan-incomplete checker reads
    # ``statements`` directly to walk if/return structure.
    statements: "tuple[Statement, ...]" = ()


# ---------------------------------------------------------------------------
# Phase 2.4 — zahir/batin AST surface
# ---------------------------------------------------------------------------
#
# The four nodes below model the compound-type declaration grammar
# from thesis §3.2:
#
#     type Document {
#         zahir { rendered_text: String, ... }
#         batin { raw_bytes: Bytes, ... }
#     }
#
# Plus the parameter-type and layer-access nodes used by FunctionDef.
# Every node is additive on the v0.1.x AST: no existing node is
# renamed or removed.

@dataclass(frozen=True, slots=True)
class TypePath:
    """A parameter or return-type expression.

    Phase 2.4 forms:
      * ``Document``           → ``TypePath(base="Document", layer=None)``
      * ``Document.zahir``     → ``TypePath(base="Document", layer="zahir")``
      * ``Document.batin``     → ``TypePath(base="Document", layer="batin")``

    The ``layer`` value is normalised to the canonical Arabic form
    (``"zahir"`` / ``"batin"``) regardless of whether the user wrote
    the Arabic or English alias (NAMING.md §1). The original lexeme
    is preserved on ``layer_alias_used`` so error messages can quote
    source faithfully.
    """

    base: str
    layer: str | None  # None | "zahir" | "batin"  (canonical only)
    span: SourceSpan
    layer_alias_used: str | None = None  # original lexeme (zahir|surface|batin|depth|None)


@dataclass(frozen=True, slots=True)
class FieldDecl:
    """A single field inside a zahir or batin layer block.

    Phase 2.4 restricts field types to bare IDENT — the type
    expression grammar (generics, references, function types) is a
    later-phase surface. The restriction is enforced by the parser;
    a complex type expression in a field position is a parse error,
    not a checker error.
    """

    name: str
    type_name: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class LayerBlock:
    """A ``zahir { ... }`` or ``batin { ... }`` block inside a
    compound-type declaration.

    The ``layer`` value is the canonical Arabic form. The
    ``alias_used`` field records the lexeme the user wrote (one of
    ``zahir``, ``surface``, ``batin``, ``depth``).
    """

    layer: str  # canonical: "zahir" or "batin"
    fields: tuple[FieldDecl, ...]
    span: SourceSpan
    alias_used: str  # lexeme as written


@dataclass(frozen=True, slots=True)
class CompoundTypeDef:
    """A top-level ``type Name { zahir { ... } batin { ... } }`` block.

    Phase 2.4 requires both layers to be present — a compound type
    that omits one layer is structurally degenerate (it is not a
    surface/depth distinction; it is a single-layer type and should
    use a future plain-type construct instead). Order is fixed:
    ``zahir`` block first, ``batin`` block second.
    """

    name: str
    zahir: LayerBlock
    batin: LayerBlock
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ParamDecl:
    """A function parameter declaration: ``name: TypePath``.

    Phase 2.4 requires every parameter to carry a type annotation.
    Untyped parameters are a parse error. The parameter's type-path
    is the load-bearing input to the zahir/batin checker.
    """

    name: str
    type_path: TypePath
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class LayerAccess:
    """An access to a zahir or batin layer of a compound-typed value
    inside a function body.

    Phase 2.4 extracts these by pre-scanning the call-argument lists
    for the pattern ``IDENT '.' (ZAHIR|BATIN)``. The pre-scan is a
    minimal additive extension on top of the existing opaque arg-list
    consumer (Session 1.2 c.3 hardening keeps that consumer's
    structural soundness; the pre-scan only *reads* tokens, it does
    not change the rejection contract).

    The first segment (``param_name``) names the value being accessed
    — typically a function parameter — and the second (``layer``) is
    the canonical Arabic layer name. Anything beyond ``param.layer``
    (e.g., ``doc.zahir.rendered_text`` continues with a field name)
    is irrelevant to the checker's layer rule.
    """

    param_name: str
    layer: str   # canonical: "zahir" or "batin"
    span: SourceSpan
    layer_alias_used: str  # lexeme as written (zahir|surface|batin|depth)


# ---------------------------------------------------------------------------
# Phase 2.5 — additive-only AST surface (Session 1.4)
# ---------------------------------------------------------------------------
#
# The five additions below model the versioned-module declaration
# grammar from thesis §3.3:
#
#     additive_only module ScanRegistry v1.0 {
#         export mechanism_registry: Registry
#         export severity_weights: Weights
#         export scan_limits: ScanLimits
#     }
#
# Plus the major_version_bump catalog grammar that documents
# breaking changes:
#
#     additive_only module ScanRegistry v2.0 {
#         export mechanism_registry: Registry
#         export scan_limits: ScanLimits
#
#         major_version_bump {
#             removes: severity_weights
#             renames: old_name -> new_name
#         }
#     }
#
# Every node is additive on the v0.2.x AST. ``Module`` is extended
# additively with ``additive_only_modules`` field.

@dataclass(frozen=True, slots=True)
class VersionLiteral:
    """A semver-shaped version expression like ``v1.0`` or ``v2.3.4``.

    The ``components`` tuple stores the dotted-numeric components in
    order (``v1.0`` → ``(1, 0)``; ``v2.3.4`` → ``(2, 3, 4)``).
    Phase 2.5 expects exactly two components (``major``, ``minor``);
    longer forms parse but use only the first two for adjacency
    comparison until a future phase formalises patch-level semantics.
    """

    components: tuple[int, ...]
    span: SourceSpan

    @property
    def major(self) -> int:
        return self.components[0]

    @property
    def minor(self) -> int:
        return self.components[1] if len(self.components) >= 2 else 0

    def render(self) -> str:
        """Canonical text form, e.g. ``v1.0``."""
        return "v" + ".".join(str(c) for c in self.components)


@dataclass(frozen=True, slots=True)
class ExportDecl:
    """A single ``export name: TypePath`` line inside an
    additive_only module.

    Phase 2.5's checker compares exports across versions by name and
    by structural type-path equality. ``name`` is a snake_case
    identifier; ``type_path`` is a Phase-2.4 :class:`TypePath`.
    """

    name: str
    type_path: TypePath
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class RemovesEntry:
    """A ``removes: <name>`` entry inside a major_version_bump
    catalog.

    Each entry names exactly one symbol that the developer is
    explicitly removing from the public surface. The checker enforces
    that the named symbol (a) was present in the previous version
    and (b) is absent from the current version (Case 4 — catalog
    must not lie).
    """

    name: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class RenamesEntry:
    """A ``renames: <old> -> <new>`` entry inside a
    major_version_bump catalog.

    The checker enforces that ``old_name`` is absent from the
    current exports AND ``new_name`` is present (Case 2 enforcement).
    A catalog claiming a rename that did not happen is the same
    structural dishonesty as a removal that did not happen.
    """

    old_name: str
    new_name: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MajorVersionBump:
    """The optional ``major_version_bump { ... }`` catalog inside an
    additive_only module declaration.

    The catalog is the explicit escape valve: a developer who needs
    to break the additive-only invariant declares the breakage here,
    making it visible to every downstream consumer at compile time.

    An empty catalog (``major_version_bump {}``) is benign — it
    asserts "I have considered breaking changes and there are none."
    A catalog with entries is the load-bearing surface for Cases 1,
    2, and 4 of the additive-only checker.
    """

    removes: tuple[RemovesEntry, ...]
    renames: tuple[RenamesEntry, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class AdditiveOnlyModuleDecl:
    """A top-level ``additive_only module Name vN.M { ... }`` block.

    The two load-bearing pieces are :attr:`exports` (the public
    surface this version commits to) and :attr:`bump_catalog` (the
    truthful enumeration of any breaking changes from the prior
    version). The checker compares exports across versions; the
    catalog is consulted to determine whether a removal, rename, or
    type change is honest or silent.
    """

    name: str
    version: VersionLiteral
    exports: tuple[ExportDecl, ...]
    bump_catalog: MajorVersionBump | None
    span: SourceSpan


# ---------------------------------------------------------------------------
# Phase 2.6 — scan-incomplete AST surface (Session 1.5)
# ---------------------------------------------------------------------------
#
# Phase 2.6 introduces statement-level grammar in function bodies:
# `if` blocks, `return` statements, expressions (including the
# Incomplete literal). Pre-2.6 function bodies were modelled as a
# tuple of CallRefs because the bismillah and zahir/batin checkers
# only needed call references and layer accesses. Phase 2.6 retains
# both pre-existing fields (`fn.calls`, `fn.accesses`) and ADDS a
# `fn.statements` field carrying the structured statement tree —
# the new field is what the scan-incomplete checker walks.
#
# The pre-2.6 fields are populated by walking `statements` and
# extracting calls/accesses recursively. Every Phase 2.3–2.5 reader
# of `fn.calls` continues to see identical content.
#
# All node classes below are frozen dataclasses with slots — the
# AST is immutable by construction.

# --- Expressions (all forms a value can take in a return-statement) ---


@dataclass(frozen=True, slots=True)
class StringLiteral:
    """A double-quoted string literal, e.g. ``"encrypted"``.

    Phase 2.6 lexer form is the smallest sufficient: no escape
    sequences. The ``value`` field carries the unwrapped content
    (without surrounding quotes); the ``span`` points at the
    opening quote.
    """

    value: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class NumberLiteral:
    """A numeric literal, possibly dotted-decimal.

    The ``lexeme`` field is the source-text form joined back from
    the tokenizer's NUMBER + (DOT NUMBER)* sequence (e.g.,
    ``"0.5"`` for the source ``0.5``). Numeric interpretation is
    deferred to the Phase 2.7 Mizan checker; Phase 2.6 stores the
    lexeme verbatim.
    """

    lexeme: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IdentExpr:
    """A bare identifier reference (e.g., ``empty_list``,
    ``findings_so_far``)."""

    name: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IdentList:
    """A comma-separated identifier list, used for the
    ``partial_findings:`` field of an Incomplete literal.

    Phase 2.6 chose to model partial-findings as an identifier list
    rather than a fully general expression list: the producer-side
    checker does not need to evaluate the contents, only confirm
    the field is present and parses cleanly. Future phases may
    promote this to a richer expression list if a fixture requires
    it.
    """

    items: tuple[str, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class NotExpr:
    """A unary ``not <expr>`` form, used to negate an
    incompleteness predicate in an ``if`` condition.

    The Phase 2.6 producer-side check requires every bare-Integrity
    return to live inside an ``if not <expr>`` body; the ``not``
    is what marks the path as having ruled out incompleteness.
    """

    operand: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IntegrityLiteral:
    """A bare ``Integrity`` reference in expression position.

    Phase 2.6 does not parse the structured-record form
    ``Integrity { score: ..., findings: ... }`` — that is later-
    phase work. The bare form is sufficient for the scan-incomplete
    primitive: the checker only needs to recognise that a return
    statement produces an Integrity value, not to inspect its
    fields.
    """

    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IncompleteField:
    """A single ``name: value`` line inside an Incomplete literal."""

    name: str
    value: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IncompleteLiteral:
    """An ``Incomplete { reason: ..., max_confidence: ...,
    partial_findings: ... }`` constructor literal.

    Phase 2.6 grammar accepts any field set; the checker
    (`check_incomplete`, Case B) emits a marad if the canonical
    three required fields (``reason``, ``max_confidence``,
    ``partial_findings``) are not all present. The ``fields``
    tuple preserves source order so a Phase-3 formatter can
    round-trip the literal.
    """

    fields: tuple[IncompleteField, ...]
    span: SourceSpan


# Expression is a sum type (union) — Python doesn't have a
# first-class sum type but the typing-level annotation lets static
# checkers see the variants.
#
# Note on the BinaryComparisonExpr variant (Phase 2.7): the Python
# ``|`` operator does not accept string forward references at
# runtime, and BinaryComparisonExpr is defined below this point.
# Static type-checkers should treat the variant set as also
# including BinaryComparisonExpr for any function annotated
# ``Expression``; runtime code inspects the AST via isinstance
# checks on the concrete classes, so the documentation-only
# Expression alias does not need to enumerate every variant.
Expression = (
    StringLiteral
    | NumberLiteral
    | IdentExpr
    | IdentList
    | NotExpr
    | IntegrityLiteral
    | IncompleteLiteral
)


# --- Statements (forms a function body can take) ---


@dataclass(frozen=True, slots=True)
class CallStmt:
    """A statement that is a single call expression: ``foo()`` or
    ``a.b.c()``.

    The ``call`` field is the existing :class:`CallRef` so the
    pre-2.6 collection code (`fn.calls`) continues to see the same
    structure. Phase 2.6 wraps it in a Statement variant so the
    body's tree is uniformly typed.
    """

    call: CallRef
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ReturnStmt:
    """A ``return <expression>`` statement.

    Phase 2.6's producer-side checker walks the function body
    looking for return statements whose ``value`` is an
    :class:`IntegrityLiteral`; every such return must sit inside
    an ``if not <expr>`` body or the function declares a non-union
    return type.
    """

    value: Expression
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IfStmt:
    """An ``if <condition> { <body> }`` (optionally followed by
    ``else { <else_body> }``) statement.

    Phase 2.6 shipped without an else arm; Phase 3.0 (D15) lands it
    additively. The ``else_body`` field defaults to the empty tuple
    so every pre-Phase-3.0 :class:`IfStmt` construction continues to
    succeed without modification — the additive-only invariant on
    AST shape is preserved at the dataclass level.

    The condition is an :class:`Expression`; both bodies are tuples
    of statements.

    The ``negated`` property is the load-bearing signal for the
    scan-incomplete Case A check: an if-body whose enclosing ``if``
    has condition of the form ``not <expr>`` is considered to have
    "ruled out incompleteness" for the purposes of the syntactic
    check. The else-body, when present, has the OPPOSITE polarity:
    it executes when the condition is false, so an ``if not <expr>``
    else-body has effectively ``<expr>`` (non-negated) as its guard.
    The scan-incomplete walker accounts for this flip.
    """

    condition: Expression
    body: tuple["Statement", ...]
    span: SourceSpan
    # Phase 3.0 (D15) additive extension. Default empty tuple means
    # "no else arm" — semantically identical to the Phase 2.6 IfStmt.
    else_body: tuple["Statement", ...] = ()

    @property
    def negated(self) -> bool:
        """True iff the condition is a :class:`NotExpr`."""
        return isinstance(self.condition, NotExpr)


# Statement is a sum type — same pattern as Expression.
Statement = CallStmt | ReturnStmt | IfStmt


# --- Return type expressions ---


@dataclass(frozen=True, slots=True)
class UnionType:
    """A binary union return-type, e.g. ``Integrity | Incomplete``.

    Phase 2.6 grammar restricts unions to two arms (binary). Triple
    unions (``A | B | C``) are not supported; if a future fixture
    requires them, the grammar can extend to a tuple of arms
    additively. ``left`` and ``right`` are :class:`TypePath`
    nodes — the same shape Phase 2.4 zahir/batin uses for
    parameter types.
    """

    left: TypePath
    right: TypePath
    span: SourceSpan


# ReturnType is a sum type: a function's return type can be either
# a single TypePath, a UnionType, or absent (no `->` clause).
ReturnType = TypePath | UnionType


# ---------------------------------------------------------------------------
# Phase 2.7 — Mizan three-valued calibration AST surface (Session 1.6)
# ---------------------------------------------------------------------------
#
# Phase 2.7 introduces top-level `mizan` blocks for calibration
# discipline declarations (thesis §Primitive 4, anchored on
# Ar-Rahman 55:7-9). The block carries three required fields:
# la_tatghaw (do not transgress), la_tukhsiru (do not make
# deficient), bil_qist (calibrate fairly). Phase 2.7 also adds
# binary comparison expressions (`<`, `>`) for the bound
# expressions; chained comparisons (`a < b < c`) are deliberately
# rejected at parse time as non-associative.
#
# Module gains an additive `mizan_decls` field carrying the
# parsed mizan declarations. Pre-2.7 module readers see
# `mizan_decls = ()`; their Phase-2.0–2.6 access patterns are
# preserved.


class ComparisonOp(Enum):
    """Binary comparison operators in expression position.

    Phase 2.7 supports two operators (``<`` and ``>``); chained
    comparisons of either are a parse error (non-associative
    grammar). Multi-character forms (``<=``, ``>=``, ``==``,
    ``!=``) are deferred to a later phase if a fixture requires
    them.
    """

    LT = "<"
    GT = ">"


@dataclass(frozen=True, slots=True)
class BinaryComparisonExpr:
    """A binary comparison: ``<expr> < <expr>`` or ``<expr> > <expr>``.

    Phase 2.7's only comparison form. The operator's symbolic form
    is preserved on :attr:`op` so a future formatter can round-
    trip the source text. The grammar is non-associative: chained
    forms (``a < b < c``) are rejected at parse time, not silently
    expanded to a Python-style transitive shape — silent expansion
    would be exactly the kind of zahir/batin divergence the
    framework is built to detect.
    """

    left: "Expression"
    op: ComparisonOp
    right: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MizanField:
    """A single ``<keyword>: <expression>`` line inside a mizan
    block.

    The ``name`` field carries the canonical Arabic keyword as a
    string (one of ``"la_tatghaw"``, ``"la_tukhsiru"``,
    ``"bil_qist"``). The parser enforces field-head position at
    keyword level (§6.4); by the time a MizanField is constructed,
    the name is guaranteed to be one of the three canonical
    values. The well-formedness checker (`check_mizan`) walks the
    sequence of MizanField nodes for the M1/M2/M4 rules.
    """

    name: str
    value: "Expression"
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MizanDecl:
    """A top-level ``mizan <Name> { ... }`` calibration block.

    The :attr:`fields` tuple preserves source order (load-bearing
    for the M4 out-of-order check) and may contain duplicates
    (load-bearing for the M2 duplicate check) — the well-
    formedness checker is the layer that enforces those rules
    over a parsed AST.

    Per Phase 2.7 §6.4, the parser ensures every entry in
    :attr:`fields` has one of the three canonical names; M3
    (unknown field) is therefore not a checker case (it would be
    structurally unreachable inside `check_mizan`).
    """

    name: str
    fields: tuple[MizanField, ...]
    span: SourceSpan


# ---------------------------------------------------------------------------
# Phase 2.8 — Tanzil build-ordering AST surface (Session 1.7)
# ---------------------------------------------------------------------------
#
# Phase 2.8 introduces top-level `tanzil` blocks for build-ordering
# declarations (Al-Isra 17:106 — "revealed progressively, tanzilan").
# Each block declares zero or more `depends_on:` entries, naming
# other modules that must be built and verified before this one.
# Phase 2.8 ships the single-module declaration surface and a
# well-formedness checker for it (T1 self-dependency, T2 duplicate,
# T3 empty-block advisory). Multi-module graph analysis (cycle
# detection across modules, topological sort, existence
# verification) is D9, deferred to Phase 3+.


@dataclass(frozen=True, slots=True)
class DependencyEntry:
    """A single ``depends_on: <ModulePath>`` line inside a tanzil
    block.

    The ``module_path`` field carries the identifier naming the
    depended-on module. Phase 2.8 stores this as a string (the
    module name); Phase 3+ multi-module analysis (D9) will resolve
    these to actual Module objects across the dependency graph.
    """

    module_path: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class TanzilDecl:
    """A top-level ``tanzil <Name> { depends_on: X ... }`` block.

    The :attr:`dependencies` tuple preserves source order (load-
    bearing for the T2 duplicate check — first-occurrence-wins
    semantics require knowing which entry came first). Per Phase
    2.8 the checker operates on a single module's tanzil
    declaration; cross-module graph analysis is D9.
    """

    name: str
    dependencies: "tuple[DependencyEntry, ...]"
    span: SourceSpan


# ---------------------------------------------------------------------------
# Module (translation unit)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Module:
    """A whole .furqan file.

    A module contains exactly one Bismillah block (the opening
    declaration), zero or more compound-type declarations
    (``type Name { zahir { ... } batin { ... } }``), zero or more
    additive-only module declarations
    (``additive_only module Name vN.M { ... }``, Phase 2.5), and
    zero or more function definitions.

    Phase 2.4 added ``compound_types``; Phase 2.5 adds
    ``additive_only_modules``. Both are additive on the read surface:
    a Phase-2.0–2.3 module that has neither parses to
    ``Module(..., compound_types=(), additive_only_modules=())`` and
    every prior field/access path on the dataclass is preserved.
    """

    bismillah: BismillahBlock
    functions: tuple[FunctionDef, ...]
    source_path: str   # the file the module was parsed from
    compound_types: tuple[CompoundTypeDef, ...] = ()
    additive_only_modules: tuple[AdditiveOnlyModuleDecl, ...] = ()
    # Phase 2.7 additive extension — top-level Mizan calibration
    # blocks. A module that declares no `mizan` blocks parses to
    # ``mizan_decls=()``; every prior field/access path on the
    # dataclass is preserved.
    mizan_decls: "tuple[MizanDecl, ...]" = ()
    # Phase 2.8 additive extension — top-level Tanzil build-ordering
    # blocks. A module that declares no `tanzil` blocks parses to
    # ``tanzil_decls=()``; every prior field/access path on the
    # dataclass is preserved.
    tanzil_decls: "tuple[TanzilDecl, ...]" = ()


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__: Final[list[str]] = [
    # v0.1.x nodes
    "SourceSpan",
    "CallRef",
    "BismillahBlock",
    "FunctionDef",
    "Module",
    # Phase 2.4 nodes (Session 1.3)
    "TypePath",
    "FieldDecl",
    "LayerBlock",
    "CompoundTypeDef",
    "ParamDecl",
    "LayerAccess",
    # Phase 2.5 nodes (Session 1.4)
    "VersionLiteral",
    "ExportDecl",
    "RemovesEntry",
    "RenamesEntry",
    "MajorVersionBump",
    "AdditiveOnlyModuleDecl",
    # Phase 2.6 nodes (Session 1.5) — scan-incomplete
    "StringLiteral",
    "NumberLiteral",
    "IdentExpr",
    "IdentList",
    "NotExpr",
    "IntegrityLiteral",
    "IncompleteField",
    "IncompleteLiteral",
    "CallStmt",
    "ReturnStmt",
    "IfStmt",
    "UnionType",
    # Phase 2.7 nodes (Session 1.6) — Mizan calibration block
    "ComparisonOp",
    "BinaryComparisonExpr",
    "MizanField",
    "MizanDecl",
    # Phase 2.8 nodes (Session 1.7) — Tanzil build-ordering
    "DependencyEntry",
    "TanzilDecl",
]
