"""
Phase 3.0 D15 tests - `else` arm of an if statement.

Coverage:
* Tokenizer recognises ``else`` as TokenKind.ELSE.
* Parser parses an if-else statement and populates ``else_body``.
* A no-else if-statement still parses and produces an empty
  ``else_body`` tuple (additive-only invariant on IfStmt).
* Ring-close R3 finds a return inside an else-body (no marad on a
  function whose only return lives in the else arm).
* Scan-incomplete walker descends into else-body with FLIPPED guard
  polarity (a bare-Integrity return in the else of an `if not <expr>`
  fires Case A).
* Round-trip on the existing scan-incomplete fixtures (no else
  anywhere) still passes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.incomplete import check_incomplete
from furqan.checker.ring_close import check_ring_close
from furqan.errors.marad import Marad
from furqan.parser import ParseError, parse
from furqan.parser.ast_nodes import IfStmt, ReturnStmt
from furqan.parser.tokenizer import KEYWORDS, TokenKind, tokenize


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "else"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


# ---------------------------------------------------------------------------
# Tokenizer - ELSE keyword
# ---------------------------------------------------------------------------

def test_tokenizer_recognises_else_keyword() -> None:
    assert "else" in KEYWORDS
    assert KEYWORDS["else"] == TokenKind.ELSE


def test_tokenizer_keyword_count_is_28_after_d15() -> None:
    assert len(KEYWORDS) == 28


def test_tokenize_emits_else_token() -> None:
    tokens = tokenize("else")
    kinds = [t.kind for t in tokens if t.kind is not TokenKind.EOF]
    assert kinds == [TokenKind.ELSE]


# ---------------------------------------------------------------------------
# AST - IfStmt.else_body default is empty tuple (additive-only)
# ---------------------------------------------------------------------------

def test_ifstmt_else_body_default_is_empty_tuple() -> None:
    """A pre-Phase-3.0 IfStmt construction (no else_body kwarg) gives
    an empty tuple - the field is additive with a default."""
    from furqan.parser.ast_nodes import (
        IdentExpr, IntegrityLiteral, NotExpr, SourceSpan,
    )
    span = SourceSpan(file="<inline>", line=1, column=1)
    node = IfStmt(
        condition=NotExpr(operand=IdentExpr(name="x", span=span), span=span),
        body=(ReturnStmt(value=IntegrityLiteral(span=span), span=span),),
        span=span,
    )
    assert node.else_body == ()


# ---------------------------------------------------------------------------
# Parser - if-else parses, else_body populated
# ---------------------------------------------------------------------------

def test_parser_populates_else_body() -> None:
    fixture = VALID_DIR / "if_else_both_return.furqan"
    module = parse(fixture.read_text(), file=fixture.name)
    fn = module.functions[0]
    if_stmt = next(s for s in fn.statements if isinstance(s, IfStmt))
    assert len(if_stmt.body) == 1
    assert len(if_stmt.else_body) == 1


def test_parser_no_else_leaves_else_body_empty() -> None:
    fixture = VALID_DIR / "if_only_no_else.furqan"
    module = parse(fixture.read_text(), file=fixture.name)
    fn = module.functions[0]
    for stmt in fn.statements:
        if isinstance(stmt, IfStmt):
            assert stmt.else_body == ()


def test_parser_else_with_inner_if_round_trips() -> None:
    fixture = VALID_DIR / "else_with_inner_if.furqan"
    module = parse(fixture.read_text(), file=fixture.name)
    fn = module.functions[0]
    outer_if = next(s for s in fn.statements if isinstance(s, IfStmt))
    # The else-body contains an inner IfStmt.
    has_inner = any(isinstance(s, IfStmt) for s in outer_if.else_body)
    assert has_inner


def test_parser_else_without_brace_is_parse_error() -> None:
    src = """
    bismillah X {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: x
        not_scope: nothing_excluded
    }

    fn f() -> Integrity | Incomplete {
        if not e {
            return Integrity
        } else return Integrity
    }
    """
    with pytest.raises(ParseError):
        parse(src, file="<inline>")


# ---------------------------------------------------------------------------
# Ring-close R3 - descent into else_body
# ---------------------------------------------------------------------------

def test_ring_close_r3_silent_when_only_else_arm_returns() -> None:
    """A function whose return statement lives only in the else-arm
    must not fire R3. The presence of a return anywhere in the
    statement tree (including else_body) satisfies the syntactic
    gate."""
    src = """
    bismillah ElseOnly {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: x
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { id: ID }
    }

    fn ingest() -> Document {
        if not ready {
        } else {
            return Document
        }
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(module)
    r3 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R3" in d.diagnosis
    ]
    assert r3 == []


def test_ring_close_r3_silent_on_if_else_both_return_fixture() -> None:
    fixture = VALID_DIR / "if_else_both_return.furqan"
    module = parse(fixture.read_text(), file=fixture.name)
    assert check_ring_close(module) == []


# ---------------------------------------------------------------------------
# Scan-incomplete - else_body descent with flipped polarity
# ---------------------------------------------------------------------------

def test_scan_incomplete_case_a_fires_in_else_body() -> None:
    """The else-arm of `if not encrypted` runs when encrypted is true
    - incompleteness is NOT ruled out, so bare Integrity there is
    Case-A dishonest. Confirms the polarity-flip in the walker."""
    fixture = INVALID_DIR / "else_bare_integrity.furqan"
    module = parse(fixture.read_text(), file=fixture.name)
    diagnostics = check_incomplete(module)
    assert len(diagnostics) >= 1
    assert any("Case A" in d.diagnosis for d in diagnostics)


def test_scan_incomplete_silent_on_honest_else_fixture() -> None:
    """A return-Incomplete in the else-arm of `if not encrypted` is
    structurally correct - no Case A or Case B marad."""
    fixture = VALID_DIR / "if_else_both_return.furqan"
    module = parse(fixture.read_text(), file=fixture.name)
    diagnostics = check_incomplete(module)
    assert diagnostics == []


def test_scan_incomplete_else_polarity_flip_on_non_negated_condition() -> None:
    """When the if-condition is non-negated (`if encrypted`), the
    else-arm is effectively `not encrypted` (incompleteness ruled out
    on the else-side) - bare Integrity in the else is honest."""
    src = """
    bismillah FlipDemo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> Integrity | Incomplete {
        if encrypted {
            return Incomplete {
                reason: "encrypted",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        } else {
            return Integrity
        }
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_incomplete(module)
    case_a = [d for d in diagnostics if "Case A" in d.diagnosis]
    assert case_a == []


# ---------------------------------------------------------------------------
# Round-trip - pre-Phase-3.0 fixtures still pass identically
# ---------------------------------------------------------------------------

def test_pre_d15_scan_incomplete_fixtures_still_pass() -> None:
    """Every Phase 2.6 valid scan-incomplete fixture (none of which
    use `else`) must still produce zero diagnostics under the
    Phase 3.0 walker - the descent is opt-in via the empty-tuple
    default."""
    valid_dir = Path(__file__).parent / "fixtures" / "scan_incomplete" / "valid"
    for fixture in sorted(valid_dir.glob("*.furqan")):
        module = parse(fixture.read_text(), file=fixture.name)
        diagnostics = check_incomplete(module)
        assert diagnostics == [], (
            f"Phase 2.6 fixture {fixture.name} regressed under "
            f"Phase 3.0 D15: {diagnostics}"
        )


# ---------------------------------------------------------------------------
# Sweep - else-fixture directory cleanly exercises every dimension
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture", sorted(VALID_DIR.glob("*.furqan")), ids=lambda p: p.name,
)
def test_every_valid_else_fixture_passes_both_checkers(
    fixture: Path,
) -> None:
    module = parse(fixture.read_text(), file=fixture.name)
    inc = check_incomplete(module)
    ring = check_ring_close(module)
    assert inc == [], f"{fixture.name}: scan-incomplete = {inc}"
    assert ring == [], f"{fixture.name}: ring-close = {ring}"


@pytest.mark.parametrize(
    "fixture", sorted(INVALID_DIR.glob("*.furqan")), ids=lambda p: p.name,
)
def test_every_invalid_else_fixture_fires_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    module = parse(fixture.read_text(), file=fixture.name)
    inc = check_incomplete(module)
    assert inc, f"{fixture.name}: scan-incomplete unexpectedly empty"
