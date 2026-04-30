"""
Furqan tokenizer, Phase 2 minimal surface syntax.

A hand-written single-pass tokenizer. No regex engine, no parser
generator. The reader of this file sees every byte of the lexical
contract.

The minimal surface syntax tokenized in Phase 2 (Bismillah primitive
session) covers:

* Keywords:
    - ``bismillah`` (canonical)         /  ``scope_block`` (English alias)
    - ``authority``, ``serves``, ``scope``, ``not_scope`` (field names
      inside a Bismillah block)
    - ``fn``                             (function declaration)
* Identifiers:        snake_case or PascalCase, ASCII letters + digits + ``_``
* Punctuation:        ``{`` ``}`` ``:`` ``,`` ``(`` ``)`` ``.``
* Multi-char tokens:  ``->`` (the function-return-type arrow)
* Comments:           ``// to end of line``  (discarded)
* Whitespace:         spaces, tabs, newlines (discarded; line numbers
                      tracked)

Anything else is a ``TokenizeError``: silent acceptance of unknown
characters is the failure mode this layer must prevent.

Future-work surface (registered, not implemented this session):

* String literals (needed by ``serves: "purpose_hierarchy.truth_over_falsehood"``)
* Numeric literals (needed by Mizan bounds)
* The ``zahir`` / ``batin`` / ``additive_only`` / ``mizan`` / ``tanzil``
  / ``ring_close`` / ``marad`` keywords are recognised as identifiers
  here and will be promoted to keyword status by their owning checker
  modules in subsequent sessions. This is the ``additive-only`` discipline
  applied to the tokenizer's own keyword set.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


# ---------------------------------------------------------------------------
# Token kinds
# ---------------------------------------------------------------------------

class TokenKind(Enum):
    """Lexical categories produced by the tokenizer.

    The set is intentionally small. Each entry corresponds to one lexical
    decision the parser will switch on. Adding a new kind requires
    extending the parser's switch as well, the additive-only invariant
    on the tokenizer's surface is enforced by the parser's own tests.
    """

    # Keywords (canonical Arabic + English aliases).
    BISMILLAH = "bismillah"   # canonical
    SCOPE_BLOCK = "scope_block"  # English alias for bismillah
    AUTHORITY = "authority"
    SERVES = "serves"
    SCOPE = "scope"
    NOT_SCOPE = "not_scope"
    FN = "fn"
    # Phase 2.4 promotions (Session 1.3). The zahir/batin primitive
    # requires these to be lexed as keywords so the parser can
    # unambiguously recognise compound-type declarations and
    # layer-qualified type paths. Per NAMING.md §1, ``zahir`` and
    # ``batin`` each carry an English alias (``surface``, ``depth``);
    # the aliases are first-class equivalents at the lexer level.
    #
    # NOT promoted (deliberate): ``verify``. Promoting ``verify`` to a
    # keyword would prohibit every non-type-verification use of the
    # word across the entire language surface, an unacceptable scope
    # constraint for a common English word. The zahir/batin checker
    # recognises ``verify`` by function-name comparison at the
    # checker layer, not by lexical token kind.
    TYPE = "type"
    ZAHIR = "zahir"
    SURFACE = "surface"   # English alias for zahir
    BATIN = "batin"
    DEPTH = "depth"       # English alias for batin
    # Phase 2.5 promotions (Session 1.4), additive-only module
    # checker primitive. Six new keywords plus the NUMBER token for
    # version literals. Each keyword passes the common-English-word
    # test from NAMING.md §1.5: every one is a structural primitive
    # of the module/versioning system, not a runtime concept that
    # might collide with a user's variable name.
    #
    # Forward-compat: NUMBER will also be needed by Phase 2.7 Mizan
    # bounds; landing it here is additive-up-the-stack.
    ADDITIVE_ONLY = "additive_only"
    MODULE = "module"
    EXPORT = "export"
    MAJOR_VERSION_BUMP = "major_version_bump"
    REMOVES = "removes"
    RENAMES = "renames"
    # Phase 2.6 promotions (Session 1.5), scan-incomplete return-type
    # primitive. Three flow-control keywords (`if`, `not`, `return`)
    # plus the union-type punctuation (`|`) plus a string-literal token
    # kind for the `reason:` field of Incomplete. Each flow-control
    # keyword passes the common-English-word test from NAMING.md §1.5
    # because they are flow-control structures, not domain concepts a
    # user might want as identifiers.
    #
    # NOT promoted (deliberate): ``Integrity`` and ``Incomplete``.
    # They live in the type-name namespace alongside ``Registry``,
    # ``Weights``, ``ScanLimits``. Promotion to keyword would break
    # any existing identifier collision; the type-name-namespace
    # placement is forward-compatible and the checker recognises them
    # by string-equality at the AST level.
    IF = "if"
    NOT = "not"
    RETURN = "return"
    # Phase 3.0 promotion (Session 1.9), else arm of an if statement.
    # See NAMING.md §1.6 for promotion rationale; LEXER.md §2 documents
    # the additive-on-the-rejection-side discipline this row honours.
    ELSE = "else"
    # Phase 2.7 promotions (Session 1.6), Mizan three-valued
    # calibration block. Four new keywords for the block head and
    # the three required field heads. None are common English
    # words; the snake-case-with-underscore form encodes the
    # Arabic transliteration of the multi-word phrase (per
    # NAMING.md §1.7). The thesis paper §Primitive 4 sets the
    # three-valued calibration discipline: do not transgress, do
    # not make deficient, calibrate fairly.
    MIZAN = "mizan"
    LA_TATGHAW = "la_tatghaw"
    LA_TUKHSIRU = "la_tukhsiru"
    BIL_QIST = "bil_qist"
    # Phase 2.8 promotions (Session 1.7): Tanzil build-ordering
    # primitive. Two new keywords: the block declaration head
    # (`tanzil`) and the single canonical field-head keyword
    # (`depends_on`). The discipline is that a module declares its
    # build-order dependencies in a structured block the checker
    # can verify for well-formedness. Multi-module
    # graph analysis is D9, deferred to Phase 3+.
    TANZIL = "tanzil"
    DEPENDS_ON = "depends_on"

    # Identifiers (anything that lexes as a name but is not a keyword).
    IDENT = "ident"
    # Numeric literal, integer (a contiguous run of digits). See
    # docs/internals/LEXER.md §1 for the version-literal lexing
    # decision (Phase 2.5).
    NUMBER = "number"
    # String literal, Phase 2.6 minimal form: ``"..."`` with no
    # escape sequences. The closing quote terminates the literal.
    # See docs/internals/LEXER.md §4 for the no-escape decision.
    STRING = "string"

    # Punctuation.
    LBRACE = "{"
    RBRACE = "}"
    LPAREN = "("
    RPAREN = ")"
    COLON = ":"
    COMMA = ","
    DOT = "."
    ARROW = "->"
    # Phase 2.6: ``|`` for union return types. Single-character
    # token; multi-character forms (``||``) are not in the language.
    PIPE = "|"
    # Phase 2.7 (Session 1.6): comparison operators for Mizan bound
    # expressions. Single-character tokens; multi-character forms
    # (``<=``, ``>=``, ``==``) are deferred to a later phase if a
    # fixture requires them.
    LT = "<"
    GT = ">"

    # End of file.
    EOF = "eof"


# Map of source-text keyword -> TokenKind. The Arabic and English
# aliases for ``bismillah`` both live here as first-class entries; the
# parser treats them as the same construct (NAMING.md §1).
KEYWORDS: Final[dict[str, TokenKind]] = {
    "bismillah": TokenKind.BISMILLAH,
    "scope_block": TokenKind.SCOPE_BLOCK,
    "authority": TokenKind.AUTHORITY,
    "serves": TokenKind.SERVES,
    "scope": TokenKind.SCOPE,
    "not_scope": TokenKind.NOT_SCOPE,
    "fn": TokenKind.FN,
    # Phase 2.4 (Session 1.3), zahir/batin keywords + type definition.
    "type": TokenKind.TYPE,
    "zahir": TokenKind.ZAHIR,
    "surface": TokenKind.SURFACE,
    "batin": TokenKind.BATIN,
    "depth": TokenKind.DEPTH,
    # Phase 2.5 (Session 1.4), additive-only module keywords.
    "additive_only": TokenKind.ADDITIVE_ONLY,
    "module": TokenKind.MODULE,
    "export": TokenKind.EXPORT,
    "major_version_bump": TokenKind.MAJOR_VERSION_BUMP,
    "removes": TokenKind.REMOVES,
    "renames": TokenKind.RENAMES,
    # Phase 2.6 (Session 1.5), scan-incomplete flow-control keywords.
    "if": TokenKind.IF,
    "not": TokenKind.NOT,
    "return": TokenKind.RETURN,
    # Phase 3.0 (D15), else arm of an if statement.
    "else": TokenKind.ELSE,
    # Phase 2.7 (Session 1.6), Mizan calibration block keywords.
    "mizan": TokenKind.MIZAN,
    "la_tatghaw": TokenKind.LA_TATGHAW,
    "la_tukhsiru": TokenKind.LA_TUKHSIRU,
    "bil_qist": TokenKind.BIL_QIST,
    # Phase 2.8 (Session 1.7), Tanzil build-ordering keywords.
    "tanzil": TokenKind.TANZIL,
    "depends_on": TokenKind.DEPENDS_ON,
}


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Token:
    """A single lexical token.

    ``lexeme`` is the literal source-text slice the token was produced
    from; ``line`` and ``column`` are 1-indexed and refer to the start
    of the lexeme. The location is recorded eagerly because a marad
    error type without a location is a degenerate diagnosis (see
    ``errors/marad.py`` once that module exists).
    """

    kind: TokenKind
    lexeme: str
    line: int
    column: int


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TokenizeError(Exception):
    """Raised on a character the tokenizer cannot classify.

    The exception carries the exact line/column so a higher-level
    diagnostic (the eventual ``marad`` wrapping) can report the
    location to the user. Bare ``Exception`` subclassing is deliberate
   , a tokenize error is a structural error, not a value-domain
    error, so it does not inherit from a value-error hierarchy.

    Phase 3.0 (D10): the location is now exposed as structured
    ``line`` / ``column`` attributes alongside the human-readable
    message. The message string still carries the same prose for
    backward compatibility; the new fields are additive. Callers that
    wrap a ``TokenizeError`` into a higher-level diagnostic (for
    example, the additive-only sidecar load path) can read the
    structured fields directly rather than parsing the message.

    Both ``line`` and ``column`` default to ``0`` so any pre-existing
    raise site that has not yet been updated continues to construct
    successfully, the additive-only invariant on the public surface
    is preserved at the constructor level.
    """

    def __init__(self, message: str, *, line: int = 0, column: int = 0) -> None:
        super().__init__(message)
        self.line: int = line
        self.column: int = column


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def tokenize(source: str) -> list[Token]:
    """Tokenize a Furqan source string into a list of :class:`Token`.

    The returned list always ends with a single ``EOF`` token. Empty
    input produces ``[Token(EOF, '', 1, 1)]``. The tokenizer is a
    single forward pass; it does not backtrack.
    """

    tokens: list[Token] = []
    pos = 0
    line = 1
    col = 1
    n = len(source)

    while pos < n:
        ch = source[pos]

        # ---- whitespace -------------------------------------------------
        if ch == "\n":
            pos += 1
            line += 1
            col = 1
            continue
        if ch in (" ", "\t", "\r"):
            pos += 1
            col += 1
            continue

        # ---- line comment ----------------------------------------------
        if ch == "/" and pos + 1 < n and source[pos + 1] == "/":
            # Skip to end of line. The newline itself is consumed by
            # the whitespace branch on the next iteration.
            while pos < n and source[pos] != "\n":
                pos += 1
                col += 1
            continue

        # ---- single-character punctuation ------------------------------
        single_char = _SINGLE_PUNCT.get(ch)
        if single_char is not None:
            tokens.append(Token(single_char, ch, line, col))
            pos += 1
            col += 1
            continue

        # ---- multi-character punctuation: '->' -------------------------
        if ch == "-" and pos + 1 < n and source[pos + 1] == ">":
            tokens.append(Token(TokenKind.ARROW, "->", line, col))
            pos += 2
            col += 2
            continue

        # ---- identifier / keyword --------------------------------------
        if _is_ident_start(ch):
            start = pos
            start_col = col
            while pos < n and _is_ident_continue(source[pos]):
                pos += 1
                col += 1
            lexeme = source[start:pos]
            kind = KEYWORDS.get(lexeme, TokenKind.IDENT)
            tokens.append(Token(kind, lexeme, line, start_col))
            continue

        # ---- string literal (Phase 2.6, escapes added in Phase 3.0) ---
        # The closing quote terminates the literal. A newline inside
        # the literal is a tokenize error (rather than silently
        # absorbing it), Phase 2.6 does not yet support multi-line
        # strings; broader lexing registered for a future phase.
        #
        # Phase 3.0 (D14) adds backslash-escape support for four
        # canonical sequences: \n (newline), \t (tab), \\ (literal
        # backslash), \" (literal double quote). An unknown escape
        # (e.g. \q) raises TokenizeError. An escape followed by end-
        # of-input also raises. The lexeme captured on the Token is
        # the RAW source form (including the surrounding quotes and
        # escape backslashes); the parser unescapes the inner content
        # before placing it on the StringLiteral AST node.
        # See docs/internals/LEXER.md §4 for the rationale.
        if ch == '"':
            start = pos
            start_col = col
            start_line = line
            pos += 1   # consume opening quote
            col += 1
            while pos < n and source[pos] != '"':
                if source[pos] == "\n":
                    raise TokenizeError(
                        f"Unterminated string literal at line {start_line}, "
                        f"column {start_col}: a newline inside a string "
                        f"literal is a tokenize error in Phase 2.6 "
                        f"(no multi-line strings yet).",
                        line=start_line,
                        column=start_col,
                    )
                if source[pos] == "\\":
                    # Validate the escape at lex time, the parser
                    # unescapes for the AST value, but the tokenizer
                    # rejects unknown sequences here so the source
                    # location is the actual escape position rather
                    # than the parser's later view.
                    pos += 1
                    col += 1
                    if pos >= n:
                        raise TokenizeError(
                            f"Unterminated escape sequence at line "
                            f"{line}, column {col}: end of input "
                            f"reached after backslash. Escapes inside "
                            f"a string literal must be one of: \\n, "
                            f"\\t, \\\\, \\\".",
                            line=line,
                            column=col,
                        )
                    esc = source[pos]
                    if esc not in ("n", "t", "\\", '"'):
                        raise TokenizeError(
                            f"Unknown escape sequence '\\{esc}' at "
                            f"line {line}, column {col}. Furqan "
                            f"strings recognise four escapes: \\n "
                            f"(newline), \\t (tab), \\\\ (literal "
                            f"backslash), \\\" (literal double quote).",
                            line=line,
                            column=col,
                        )
                    # Consume the escape character; it is part of the
                    # raw lexeme, not separately processed here.
                    pos += 1
                    col += 1
                    continue
                pos += 1
                col += 1
            if pos >= n:
                raise TokenizeError(
                    f"Unterminated string literal at line {start_line}, "
                    f"column {start_col}: end of input reached before "
                    f"closing '\"'.",
                    line=start_line,
                    column=start_col,
                )
            # Capture the content INCLUDING the surrounding quotes for
            # the lexeme so the parser sees the source-literal form.
            pos += 1   # consume closing quote
            col += 1
            tokens.append(Token(
                TokenKind.STRING, source[start:pos], start_line, start_col,
            ))
            continue

        # ---- numeric literal (Phase 2.5) -------------------------------
        # Lexer choice: integer-only NUMBER (a run of ASCII digits).
        # Multi-component literals like ``1.0``, ``1.2.3``, and Phase
        # 2.7 Mizan decimals like ``0.05`` are reconstructed at the
        # parser level using DOT as a separator. This keeps the lexer
        # simple and the dotted forms unambiguous.
        # See lexer/README.md for the rationale.
        if ch.isascii() and ch.isdigit():
            start = pos
            start_col = col
            while pos < n and source[pos].isascii() and source[pos].isdigit():
                pos += 1
                col += 1
            tokens.append(Token(
                TokenKind.NUMBER, source[start:pos], line, start_col,
            ))
            continue

        # ---- unknown character -----------------------------------------
        raise TokenizeError(
            f"Unrecognised character {ch!r} at line {line}, column {col}. "
            f"The tokenizer accepts identifiers, keywords "
            f"({', '.join(sorted(KEYWORDS.keys()))}), and the punctuation "
            f"{{ }} ( ) : , . ->. Comments use '//'. Anything else is a "
            f"structural error in the source.",
            line=line,
            column=col,
        )

    tokens.append(Token(TokenKind.EOF, "", line, col))
    return tokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SINGLE_PUNCT: Final[dict[str, TokenKind]] = {
    "{": TokenKind.LBRACE,
    "}": TokenKind.RBRACE,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    ":": TokenKind.COLON,
    ",": TokenKind.COMMA,
    ".": TokenKind.DOT,
    # Phase 2.6 (Session 1.5), pipe for union return types.
    "|": TokenKind.PIPE,
    # Phase 2.7 (Session 1.6), comparison operators for Mizan.
    "<": TokenKind.LT,
    ">": TokenKind.GT,
}


def _is_ident_start(ch: str) -> bool:
    """First character of an identifier: ASCII letter or underscore."""
    return ch.isascii() and (ch.isalpha() or ch == "_")


def _is_ident_continue(ch: str) -> bool:
    """Continuation of an identifier: ASCII alphanumeric or underscore."""
    return ch.isascii() and (ch.isalnum() or ch == "_")


# Phase 3.0 (D14), public helper for the parser to unescape the
# inner content of a STRING token's lexeme. The tokenizer validates
# escape shape at lex time; this helper translates the validated
# raw form into the AST-node value. Kept module-private (leading
# underscore) because parser-internal code is the only legitimate
# consumer; downstream tooling that needs a string's value should
# read it from the AST node.
_ESCAPE_TABLE: Final[dict[str, str]] = {
    "n": "\n",
    "t": "\t",
    "\\": "\\",
    '"': '"',
}


def _unescape_string(raw: str) -> str:
    """Unescape a Furqan string-literal's inner content.

    The input is the substring between the surrounding quotes (the
    parser strips those before calling this). Backslash escapes are
    expanded according to ``_ESCAPE_TABLE``; the tokenizer guarantees
    every backslash in ``raw`` is followed by one of the four
    canonical escape characters, so the lookup cannot miss.
    """
    result: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] == "\\" and i + 1 < n:
            esc = raw[i + 1]
            # The tokenizer already validated the escape shape; the
            # lookup is total over what can reach this function. The
            # ``.get`` fallback is a defensive paranoia for the case
            # where this helper is called on un-tokenized input.
            result.append(_ESCAPE_TABLE.get(esc, raw[i:i + 2]))
            i += 2
        else:
            result.append(raw[i])
            i += 1
    return "".join(result)


__all__ = [
    "Token",
    "TokenKind",
    "TokenizeError",
    "KEYWORDS",
    "tokenize",
]
