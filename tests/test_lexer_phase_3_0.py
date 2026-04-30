"""
Phase 3.0 lexer tests: D10 (TokenizeError structured location) and
D14 (string escape sequences).

Both items are additive on the tokenizer's external surface:

* D10: ``TokenizeError`` gains ``line`` / ``column`` attributes
  with a default of ``0``. Every existing raise site is updated to
  pass them; existing message strings are unchanged.
* D14: string literals accept four backslash escapes - ``\\n``,
  ``\\t``, ``\\\\``, ``\\"``. The tokenizer validates the escape at
  lex time; the parser unescapes the inner content for the
  :class:`StringLiteral` value.
"""

from __future__ import annotations

import pytest

from furqan.parser import parse, ParseError
from furqan.parser.tokenizer import (
    TokenizeError,
    TokenKind,
    _unescape_string,
    tokenize,
)


# ---------------------------------------------------------------------------
# D14 - escape sequences (positive paths)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_inner,expected_value",
    [
        (r"hello\nworld", "hello\nworld"),
        (r"col1\tcol2", "col1\tcol2"),
        (r"path\\to", "path\\to"),
        (r'a\"quoted\"b', 'a"quoted"b'),
        (r"mix \n and \t and \\", "mix \n and \t and \\"),
        ("plain text no escapes", "plain text no escapes"),
    ],
    ids=[
        "newline_escape",
        "tab_escape",
        "literal_backslash",
        "embedded_double_quote",
        "mixed_escapes",
        "no_escapes_unchanged",
    ],
)
def test_string_escape_unescapes_to_expected_value(
    raw_inner: str, expected_value: str,
) -> None:
    """A string literal containing the named escape produces a
    StringLiteral whose `value` field is the expected unescaped form."""
    src = f'''
    bismillah Demo {{
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: noop
        not_scope: nothing_excluded
    }}

    fn report() -> Integrity | Incomplete {{
        if not failed {{
            return Integrity
        }}
        return Incomplete {{
            reason: "{raw_inner}",
            max_confidence: 0.5,
            partial_findings: empty_list
        }}
    }}
    '''
    module = parse(src, file="<inline>")
    # Walk the AST to find the Incomplete literal's reason field.
    fn = module.functions[0]
    # Find the bare-return-Incomplete statement.
    from furqan.parser.ast_nodes import IncompleteLiteral, ReturnStmt
    incomplete_lit = None
    for stmt in fn.statements:
        if isinstance(stmt, ReturnStmt) and isinstance(stmt.value, IncompleteLiteral):
            incomplete_lit = stmt.value
            break
    assert incomplete_lit is not None, "no Incomplete literal found"
    reason_field = next(f for f in incomplete_lit.fields if f.name == "reason")
    assert reason_field.value.value == expected_value


def test_unescape_helper_directly_on_each_escape() -> None:
    """The exported helper function ``_unescape_string`` accepts the
    raw inner content (no surrounding quotes) and returns the
    unescaped form. Pinned on each canonical escape."""
    assert _unescape_string("a\\nb") == "a\nb"
    assert _unescape_string("a\\tb") == "a\tb"
    assert _unescape_string("a\\\\b") == "a\\b"
    assert _unescape_string('a\\"b') == 'a"b'
    assert _unescape_string("plain") == "plain"


def test_unescape_helper_on_empty_input() -> None:
    assert _unescape_string("") == ""


# ---------------------------------------------------------------------------
# D14 - error paths
# ---------------------------------------------------------------------------

def test_unknown_escape_raises_tokenize_error() -> None:
    """An escape character outside the canonical set raises TokenizeError."""
    src = '"hello \\q world"'
    with pytest.raises(TokenizeError) as exc:
        tokenize(src)
    assert "Unknown escape sequence" in str(exc.value)
    assert "\\q" in str(exc.value)


def test_unterminated_escape_at_end_of_input_raises() -> None:
    """A backslash at end of input (no terminator quote) raises."""
    src = '"abc\\'
    with pytest.raises(TokenizeError) as exc:
        tokenize(src)
    assert "Unterminated escape sequence" in str(exc.value)


# ---------------------------------------------------------------------------
# D10 - TokenizeError structured location fields
# ---------------------------------------------------------------------------

def test_tokenize_error_carries_line_and_column_on_unknown_char() -> None:
    """The unrecognised-character raise site populates line/column."""
    # The '@' is on line 1, column 1.
    with pytest.raises(TokenizeError) as exc:
        tokenize("@")
    assert exc.value.line == 1
    assert exc.value.column == 1


def test_tokenize_error_carries_line_and_column_on_unknown_char_offset() -> None:
    """Non-trivial line/column: an unknown character on a later line."""
    with pytest.raises(TokenizeError) as exc:
        tokenize("ok\nok\n  @")
    assert exc.value.line == 3
    assert exc.value.column == 3


def test_tokenize_error_carries_line_and_column_on_unterminated_string() -> None:
    """Unterminated-string raise site populates the START location."""
    src = '   "no_close'
    with pytest.raises(TokenizeError) as exc:
        tokenize(src)
    # The opening quote is at column 4 on line 1.
    assert exc.value.line == 1
    assert exc.value.column == 4


def test_tokenize_error_carries_line_and_column_on_unknown_escape() -> None:
    """Unknown-escape raise site populates the escape character location."""
    src = '"abc\\q"'
    with pytest.raises(TokenizeError) as exc:
        tokenize(src)
    # '\q' begins at column 5 (after the opening quote at col 1 and
    # the three letters a,b,c at cols 2,3,4 and the '\' at col 5,
    # the unknown 'q' is at col 6 - but the implementation reports
    # the column of the escape character itself).
    assert exc.value.line == 1
    assert exc.value.column >= 5


def test_tokenize_error_default_line_column_is_zero() -> None:
    """Constructing a TokenizeError without keyword args gives 0/0
    (the additive-only-safe defaults that preserve back-compat)."""
    err = TokenizeError("plain message")
    assert err.line == 0
    assert err.column == 0


def test_tokenize_error_message_string_unchanged_for_existing_consumers() -> None:
    """The historical ``str(exc)`` rendering still includes the
    location-prose so any consumer that pattern-matched the message
    does not regress."""
    with pytest.raises(TokenizeError) as exc:
        tokenize("@")
    msg = str(exc.value)
    assert "line 1" in msg
    assert "column 1" in msg


# ---------------------------------------------------------------------------
# Composition - escape sequences round-trip cleanly through the
# whole parse path on a real fixture-shaped input
# ---------------------------------------------------------------------------

def test_escape_sequences_compose_with_existing_string_fixture_paths() -> None:
    """A more complex inline fixture exercising newline + tab + quote
    escapes inside a single Incomplete literal's reason field."""
    src = '''
    bismillah ScanWithEscapes {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> Integrity | Incomplete {
        if not encrypted {
            return Integrity
        }
        return Incomplete {
            reason: "header parsed\\nbody encrypted\\twith \\"AES\\"",
            max_confidence: 0.5,
            partial_findings: empty_list
        }
    }
    '''
    module = parse(src, file="<inline>")
    from furqan.parser.ast_nodes import IncompleteLiteral, ReturnStmt
    fn = module.functions[0]
    incomplete_lit = next(
        s.value for s in fn.statements
        if isinstance(s, ReturnStmt) and isinstance(s.value, IncompleteLiteral)
    )
    reason = next(f for f in incomplete_lit.fields if f.name == "reason")
    assert reason.value.value == 'header parsed\nbody encrypted\twith "AES"'


def test_token_with_escape_keeps_raw_lexeme_with_backslashes() -> None:
    """The Token.lexeme captured in the token stream preserves the
    raw source form including backslashes - only the parser's
    StringLiteral.value is the unescaped view."""
    tokens = tokenize(r'"a\nb"')
    string_tok = next(t for t in tokens if t.kind == TokenKind.STRING)
    assert string_tok.lexeme == r'"a\nb"'  # raw, with escape


# ---------------------------------------------------------------------------
# Existing behaviour preserved - strings without any escape are
# unchanged round-trippers
# ---------------------------------------------------------------------------

def test_plain_string_value_round_trip_is_identity() -> None:
    """A string with no backslashes produces the same value as before
    Phase 3.0 (the sub-string between the quotes)."""
    src = '''
    bismillah Plain {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> Integrity | Incomplete {
        if not encrypted {
            return Integrity
        }
        return Incomplete {
            reason: "ordinary text",
            max_confidence: 0.5,
            partial_findings: empty_list
        }
    }
    '''
    module = parse(src, file="<inline>")
    from furqan.parser.ast_nodes import IncompleteLiteral, ReturnStmt
    fn = module.functions[0]
    incomplete_lit = next(
        s.value for s in fn.statements
        if isinstance(s, ReturnStmt) and isinstance(s.value, IncompleteLiteral)
    )
    reason = next(f for f in incomplete_lit.fields if f.name == "reason")
    assert reason.value.value == "ordinary text"
