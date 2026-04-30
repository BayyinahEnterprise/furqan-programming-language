"""
Tests for the tokenizer (Phase 2.1).

The tokenizer's contract is small. The tests pin the small surface so
the parser layer (Phase 2.2) and every checker (Phase 2.3+) can rely
on it. Each test pins one named property; the test name is the property.
"""

from __future__ import annotations

import pytest

from furqan.parser.tokenizer import (
    KEYWORDS,
    Token,
    TokenizeError,
    TokenKind,
    tokenize,
)


# ---------------------------------------------------------------------------
# EOF and emptiness
# ---------------------------------------------------------------------------

def test_empty_source_yields_only_eof() -> None:
    tokens = tokenize("")
    assert len(tokens) == 1
    assert tokens[0].kind == TokenKind.EOF
    assert tokens[0].line == 1
    assert tokens[0].column == 1


def test_whitespace_only_source_yields_only_eof() -> None:
    tokens = tokenize("   \n\t\r\n  ")
    assert [t.kind for t in tokens] == [TokenKind.EOF]


# ---------------------------------------------------------------------------
# Identifiers and keywords
# ---------------------------------------------------------------------------

def test_identifier_is_tokenized_as_ident() -> None:
    tokens = tokenize("ScanService")
    assert [t.kind for t in tokens] == [TokenKind.IDENT, TokenKind.EOF]
    assert tokens[0].lexeme == "ScanService"


def test_snake_case_identifier_is_tokenized_as_ident() -> None:
    tokens = tokenize("orchestrate_scans")
    assert tokens[0].kind == TokenKind.IDENT
    assert tokens[0].lexeme == "orchestrate_scans"


def test_underscore_prefix_identifier_is_accepted() -> None:
    tokens = tokenize("_internal")
    assert tokens[0].kind == TokenKind.IDENT


def test_every_keyword_lexes_to_its_token_kind() -> None:
    for lexeme, kind in KEYWORDS.items():
        tokens = tokenize(lexeme)
        assert tokens[0].kind is kind, f"keyword {lexeme!r} did not map to {kind}"
        assert tokens[0].lexeme == lexeme


def test_arabic_and_english_aliases_lex_to_distinct_kinds() -> None:
    """``bismillah`` and ``scope_block`` must lex to different kinds.

    The parser is responsible for treating them as the same construct
    (NAMING.md §1). The tokenizer's job is to preserve which one the
    user wrote so error messages can quote source faithfully.
    """
    bism = tokenize("bismillah")[0]
    eng = tokenize("scope_block")[0]
    assert bism.kind is TokenKind.BISMILLAH
    assert eng.kind is TokenKind.SCOPE_BLOCK
    assert bism.kind is not eng.kind


# ---------------------------------------------------------------------------
# Punctuation
# ---------------------------------------------------------------------------

def test_single_character_punctuation_is_tokenized() -> None:
    src = "{}():,."
    expected = [
        TokenKind.LBRACE, TokenKind.RBRACE,
        TokenKind.LPAREN, TokenKind.RPAREN,
        TokenKind.COLON, TokenKind.COMMA, TokenKind.DOT,
        TokenKind.EOF,
    ]
    assert [t.kind for t in tokenize(src)] == expected


def test_arrow_is_tokenized_as_a_single_token() -> None:
    tokens = tokenize("->")
    assert [t.kind for t in tokens] == [TokenKind.ARROW, TokenKind.EOF]
    assert tokens[0].lexeme == "->"


def test_lone_minus_is_not_lexable_in_phase_2() -> None:
    # Phase 2 has no arithmetic; a bare '-' is unrecognised. This pins
    # the negative space — an oversight that introduces '-' as a valid
    # token without explicit decision would break this test.
    with pytest.raises(TokenizeError):
        tokenize("a - b")


# ---------------------------------------------------------------------------
# Comments and whitespace
# ---------------------------------------------------------------------------

def test_line_comment_is_discarded() -> None:
    tokens = tokenize("// this is a comment\nfn")
    assert [t.kind for t in tokens] == [TokenKind.FN, TokenKind.EOF]


def test_inline_comment_after_token_is_discarded() -> None:
    tokens = tokenize("fn // tail comment")
    assert [t.kind for t in tokens] == [TokenKind.FN, TokenKind.EOF]


# ---------------------------------------------------------------------------
# Line and column tracking
# ---------------------------------------------------------------------------

def test_line_numbers_are_one_indexed_and_advance_past_newlines() -> None:
    tokens = tokenize("fn\nfn")
    assert tokens[0].line == 1
    assert tokens[1].line == 2


def test_column_numbers_are_one_indexed_for_first_token() -> None:
    tokens = tokenize("fn")
    assert tokens[0].column == 1


def test_column_numbers_advance_within_a_line() -> None:
    tokens = tokenize("fn fn")
    assert tokens[0].column == 1
    assert tokens[1].column == 4


# ---------------------------------------------------------------------------
# A representative full snippet (end-to-end smoke)
# ---------------------------------------------------------------------------

def test_minimal_bismillah_block_lexes_without_error() -> None:
    src = """
    bismillah ScanService {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: orchestrate_scans
        not_scope: parse_files, render_output
    }
    """
    kinds = [t.kind for t in tokenize(src)]
    # We only assert the high-level shape — the parser tests will
    # verify the exact sequence.
    assert TokenKind.BISMILLAH in kinds
    assert kinds.count(TokenKind.LBRACE) == 1
    assert kinds.count(TokenKind.RBRACE) == 1
    assert TokenKind.NOT_SCOPE in kinds
    assert kinds[-1] is TokenKind.EOF


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def test_unknown_character_raises_with_location() -> None:
    with pytest.raises(TokenizeError) as exc_info:
        tokenize("fn $\n")
    msg = str(exc_info.value)
    assert "$" in msg
    assert "line 1" in msg
    assert "column 4" in msg


def test_error_message_lists_accepted_punctuation_for_orientation() -> None:
    """A marad-style diagnosis names what the language accepts so the
    user can recover. The tokenizer's error is the lowest-level
    diagnostic surface; the higher tiers (parser, checker) build on it.
    """
    with pytest.raises(TokenizeError) as exc_info:
        tokenize("@")
    msg = str(exc_info.value)
    assert "{" in msg and "}" in msg and "->" in msg


# ---------------------------------------------------------------------------
# Token equality is structural (frozen dataclass)
# ---------------------------------------------------------------------------

def test_token_is_frozen_and_hashable() -> None:
    t = Token(TokenKind.IDENT, "X", 1, 1)
    # Frozen dataclasses are hashable by default.
    {t}
    with pytest.raises((AttributeError, Exception)):
        # frozen=True raises FrozenInstanceError on assignment
        t.line = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Phase 2.5 (Session 1.4) — NUMBER token + six new keywords
# ---------------------------------------------------------------------------

def test_single_digit_lexes_as_number() -> None:
    tokens = tokenize("1")
    assert [t.kind for t in tokens] == [TokenKind.NUMBER, TokenKind.EOF]
    assert tokens[0].lexeme == "1"


def test_multi_digit_integer_lexes_as_number() -> None:
    tokens = tokenize("42")
    assert tokens[0].kind == TokenKind.NUMBER
    assert tokens[0].lexeme == "42"


def test_dotted_number_lexes_as_number_dot_number() -> None:
    """Phase 2.5 lex choice: NUMBER is integer-only; dotted forms are
    reconstructed by the parser using DOT as a separator (see
    docs/internals/LEXER.md §1)."""
    tokens = tokenize("1.0")
    assert [t.kind for t in tokens] == [
        TokenKind.NUMBER, TokenKind.DOT, TokenKind.NUMBER, TokenKind.EOF
    ]
    assert tokens[0].lexeme == "1"
    assert tokens[2].lexeme == "0"


def test_three_component_dotted_number_lexes_consistently() -> None:
    """v2.3.4 - style component lists should chain DOT NUMBER pairs."""
    tokens = tokenize("2.3.4")
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.NUMBER, TokenKind.DOT,
        TokenKind.NUMBER, TokenKind.DOT,
        TokenKind.NUMBER, TokenKind.EOF,
    ]


def test_v_prefixed_version_literal_lexes_as_ident_dot_number() -> None:
    """The 'v' in v1.0 stays inside the IDENT (because identifiers
    permit digits in continuation positions). Then DOT NUMBER for
    the minor."""
    tokens = tokenize("v1.0")
    assert [t.kind for t in tokens] == [
        TokenKind.IDENT, TokenKind.DOT, TokenKind.NUMBER, TokenKind.EOF
    ]
    assert tokens[0].lexeme == "v1"


def test_additive_only_keyword_promotion() -> None:
    tokens = tokenize("additive_only")
    assert tokens[0].kind == TokenKind.ADDITIVE_ONLY
    assert tokens[0].lexeme == "additive_only"


def test_module_keyword_promotion() -> None:
    tokens = tokenize("module")
    assert tokens[0].kind == TokenKind.MODULE


def test_export_keyword_promotion() -> None:
    tokens = tokenize("export")
    assert tokens[0].kind == TokenKind.EXPORT


def test_major_version_bump_keyword_promotion() -> None:
    tokens = tokenize("major_version_bump")
    assert tokens[0].kind == TokenKind.MAJOR_VERSION_BUMP


def test_removes_keyword_promotion() -> None:
    tokens = tokenize("removes")
    assert tokens[0].kind == TokenKind.REMOVES


def test_renames_keyword_promotion() -> None:
    tokens = tokenize("renames")
    assert tokens[0].kind == TokenKind.RENAMES


def test_full_additive_only_header_lexes_correctly() -> None:
    """Smoke test on the canonical declaration head."""
    tokens = tokenize("additive_only module ScanRegistry v1.0")
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.ADDITIVE_ONLY,
        TokenKind.MODULE,
        TokenKind.IDENT,
        TokenKind.IDENT,        # 'v1'
        TokenKind.DOT,
        TokenKind.NUMBER,       # '0'
        TokenKind.EOF,
    ]


# ---------------------------------------------------------------------------
# Phase 2.6 (Session 1.5) — STRING token + flow-control keywords + PIPE
# ---------------------------------------------------------------------------

def test_string_literal_lexes_with_surrounding_quotes() -> None:
    tokens = tokenize('"hello"')
    assert [t.kind for t in tokens] == [TokenKind.STRING, TokenKind.EOF]
    assert tokens[0].lexeme == '"hello"'


def test_empty_string_literal_lexes() -> None:
    tokens = tokenize('""')
    assert tokens[0].kind == TokenKind.STRING
    assert tokens[0].lexeme == '""'


def test_string_with_inner_punctuation_lexes_as_single_token() -> None:
    """The lexer treats every byte between matching quotes as the
    string's content. Punctuation like commas and parens inside the
    string is part of the lexeme, not separate tokens."""
    tokens = tokenize('"a, b, c"')
    assert tokens[0].kind == TokenKind.STRING
    assert tokens[0].lexeme == '"a, b, c"'


def test_unterminated_string_literal_raises() -> None:
    with pytest.raises(TokenizeError) as exc_info:
        tokenize('"unterminated')
    assert "Unterminated string literal" in str(exc_info.value)


def test_string_with_embedded_newline_raises() -> None:
    """Phase 2.6 has no multi-line strings; newline inside quotes
    is a tokenize error."""
    with pytest.raises(TokenizeError) as exc_info:
        tokenize('"first\nsecond"')
    assert "Unterminated string literal" in str(exc_info.value)


def test_pipe_punctuation_lexes() -> None:
    tokens = tokenize("Integrity | Incomplete")
    assert [t.kind for t in tokens] == [
        TokenKind.IDENT,
        TokenKind.PIPE,
        TokenKind.IDENT,
        TokenKind.EOF,
    ]


def test_if_keyword_promotion() -> None:
    tokens = tokenize("if")
    assert tokens[0].kind == TokenKind.IF


def test_not_keyword_promotion() -> None:
    tokens = tokenize("not")
    assert tokens[0].kind == TokenKind.NOT


def test_return_keyword_promotion() -> None:
    tokens = tokenize("return")
    assert tokens[0].kind == TokenKind.RETURN


def test_integrity_lexes_as_ident_not_keyword() -> None:
    """Phase 2.6 deliberately does NOT promote `Integrity` and
    `Incomplete` to keywords (LEXER.md §5). They live in the type-
    name namespace alongside `Registry`, `Weights`, etc. The
    scan-incomplete checker recognises them by string-equality at
    the AST level."""
    for name in ["Integrity", "Incomplete"]:
        tokens = tokenize(name)
        assert tokens[0].kind == TokenKind.IDENT
        assert tokens[0].lexeme == name


def test_full_scan_incomplete_function_signature_lexes_correctly() -> None:
    """End-to-end smoke test on the canonical scan-incomplete
    function signature shape."""
    tokens = tokenize("fn scan(file: File) -> Integrity | Incomplete")
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [
        TokenKind.FN,
        TokenKind.IDENT,                    # scan
        TokenKind.LPAREN,
        TokenKind.IDENT,                    # file
        TokenKind.COLON,
        TokenKind.IDENT,                    # File
        TokenKind.RPAREN,
        TokenKind.ARROW,
        TokenKind.IDENT,                    # Integrity
        TokenKind.PIPE,
        TokenKind.IDENT,                    # Incomplete
    ]


# ---------------------------------------------------------------------------
# Phase 2.7 (Session 1.6) — Mizan keywords + LT/GT punctuation
# ---------------------------------------------------------------------------

def test_mizan_keyword_promotion() -> None:
    tokens = tokenize("mizan")
    assert tokens[0].kind == TokenKind.MIZAN


def test_la_tatghaw_keyword_promotion() -> None:
    tokens = tokenize("la_tatghaw")
    assert tokens[0].kind == TokenKind.LA_TATGHAW


def test_la_tukhsiru_keyword_promotion() -> None:
    tokens = tokenize("la_tukhsiru")
    assert tokens[0].kind == TokenKind.LA_TUKHSIRU


def test_bil_qist_keyword_promotion() -> None:
    tokens = tokenize("bil_qist")
    assert tokens[0].kind == TokenKind.BIL_QIST


def test_lt_punctuation_lexes() -> None:
    tokens = tokenize("a < b")
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.IDENT, TokenKind.LT, TokenKind.IDENT]


def test_gt_punctuation_lexes() -> None:
    tokens = tokenize("a > b")
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [TokenKind.IDENT, TokenKind.GT, TokenKind.IDENT]


def test_full_mizan_block_head_lexes_correctly() -> None:
    """End-to-end smoke test on the canonical mizan block head
    plus a single la_tatghaw bound expression."""
    tokens = tokenize(
        "mizan detection_threshold { la_tatghaw: false_positive_rate < 0.05 }"
    )
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [
        TokenKind.MIZAN,
        TokenKind.IDENT,           # detection_threshold
        TokenKind.LBRACE,
        TokenKind.LA_TATGHAW,
        TokenKind.COLON,
        TokenKind.IDENT,           # false_positive_rate
        TokenKind.LT,
        TokenKind.NUMBER,          # 0
        TokenKind.DOT,
        TokenKind.NUMBER,          # 05
        TokenKind.RBRACE,
    ]


# ---------------------------------------------------------------------------
# Phase 2.8 (Session 1.7) — Tanzil keywords
# ---------------------------------------------------------------------------

def test_tanzil_keyword_promotion() -> None:
    tokens = tokenize("tanzil")
    assert tokens[0].kind == TokenKind.TANZIL


def test_depends_on_keyword_promotion() -> None:
    tokens = tokenize("depends_on")
    assert tokens[0].kind == TokenKind.DEPENDS_ON


def test_full_tanzil_block_head_lexes_correctly() -> None:
    """End-to-end smoke test on the canonical tanzil block head
    plus a single depends_on entry."""
    tokens = tokenize(
        "tanzil build_order { depends_on: CoreModule }"
    )
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert kinds == [
        TokenKind.TANZIL,
        TokenKind.IDENT,           # build_order
        TokenKind.LBRACE,
        TokenKind.DEPENDS_ON,
        TokenKind.COLON,
        TokenKind.IDENT,           # CoreModule
        TokenKind.RBRACE,
    ]
