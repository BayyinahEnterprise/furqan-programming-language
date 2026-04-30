"""
Return-expression type matching checker tests (D22 / v0.8.1).

The checker's contract: every return expression whose type is
statically known must match the function's declared return type.
Uncheckable expressions (anything that is not an IntegrityLiteral
or IncompleteLiteral) produce no diagnostic.

Together with ring-close R3 (presence) and D11 status-coverage
(consumer-side propagation), D22 closes the return-type contract:
* R3: you must return something
* D22: you must return the right type
* D11: your callers must propagate your type honestly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker import (
    check_bismillah,
    check_incomplete,
    check_ring_close,
    check_status_coverage,
    check_zahir_batin,
)
from furqan.checker.return_type_match import (
    PRIMITIVE_NAME,
    check_return_type_match,
    check_return_type_match_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "return_type_match"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load(path: Path):
    return parse(path.read_text(), file=str(path))


def _all_valid():
    return sorted(VALID_DIR.glob("*.furqan"))


def _all_invalid():
    return sorted(INVALID_DIR.glob("*.furqan"))


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _all_valid(), ids=lambda p: p.name)
def test_every_valid_fixture_produces_zero_diagnostics(fixture: Path) -> None:
    diags = check_return_type_match(_load(fixture))
    assert diags == [], (
        f"valid fixture {fixture.name} produced diagnostics: {diags}"
    )


@pytest.mark.parametrize("fixture", _all_invalid(), ids=lambda p: p.name)
def test_every_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    diags = check_return_type_match(_load(fixture))
    assert diags, (
        f"invalid fixture {fixture.name} produced zero diagnostics"
    )
    for d in diags:
        assert d.primitive == PRIMITIVE_NAME


def test_each_directory_is_non_empty() -> None:
    assert _all_valid()
    assert _all_invalid()


def test_primitive_name_is_stable() -> None:
    assert PRIMITIVE_NAME == "return_type_match"


# ---------------------------------------------------------------------------
# Case M1 - basic mismatches
# ---------------------------------------------------------------------------

def test_m1_fires_when_incomplete_returned_but_integrity_declared() -> None:
    fixture = INVALID_DIR / "integrity_declared_incomplete_returned.furqan"
    diags = check_return_type_match(_load(fixture))
    assert len(diags) == 1
    d = diags[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case M1" in d.diagnosis
    assert "Integrity" in d.diagnosis
    assert "Incomplete" in d.diagnosis


def test_m1_fires_when_integrity_returned_but_custom_type_declared() -> None:
    fixture = INVALID_DIR / "custom_type_returns_integrity.furqan"
    diags = check_return_type_match(_load(fixture))
    assert len(diags) == 1
    d = diags[0]
    assert "DocumentReport" in d.diagnosis
    assert "Integrity" in d.diagnosis


def test_m1_marad_carries_correct_primitive_name() -> None:
    fixture = INVALID_DIR / "integrity_declared_incomplete_returned.furqan"
    d = check_return_type_match(_load(fixture))[0]
    assert d.primitive == "return_type_match"


def test_m1_names_the_function() -> None:
    fixture = INVALID_DIR / "integrity_declared_incomplete_returned.furqan"
    d = check_return_type_match(_load(fixture))[0]
    assert "scan" in d.diagnosis


def test_m1_location_points_at_return_statement() -> None:
    fixture = INVALID_DIR / "integrity_declared_incomplete_returned.furqan"
    d = check_return_type_match(_load(fixture))[0]
    assert d.location.file.endswith("integrity_declared_incomplete_returned.furqan")
    assert d.location.line >= 1


# ---------------------------------------------------------------------------
# Union matching
# ---------------------------------------------------------------------------

def test_integrity_matches_integrity_or_incomplete_union() -> None:
    """A bare-Integrity return inside a function declared
    -> Integrity | Incomplete is honest. No M1."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> Integrity | Incomplete {
        return Integrity
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert diags == []


def test_incomplete_matches_integrity_or_incomplete_union() -> None:
    """A return-Incomplete inside a function declared
    -> Integrity | Incomplete is honest."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> Integrity | Incomplete {
        return Incomplete {
            reason: "missing",
            max_confidence: 0.5,
            partial_findings: empty_list
        }
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert diags == []


def test_integrity_does_not_match_custom_type() -> None:
    fixture = INVALID_DIR / "custom_type_returns_integrity.furqan"
    diags = check_return_type_match(_load(fixture))
    assert len(diags) == 1


def test_union_with_one_arm_matching_still_accepts_only_those_arms() -> None:
    """A union -> Integrity | OtherType accepts only Integrity and
    OtherType. An Incomplete return is still a mismatch."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type OtherType {
        zahir { name: String }
        batin { id: ID }
    }

    fn scan() -> Integrity | OtherType {
        return Incomplete {
            reason: "wrong arm",
            max_confidence: 0.5,
            partial_findings: empty_list
        }
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert len(diags) == 1
    assert "Incomplete" in diags[0].diagnosis


# ---------------------------------------------------------------------------
# Uncheckable expressions - honest silence
# ---------------------------------------------------------------------------

def test_ident_expr_return_produces_no_diagnostic() -> None:
    fixture = VALID_DIR / "uncheckable_return.furqan"
    diags = check_return_type_match(_load(fixture))
    assert diags == []


def test_string_literal_return_would_not_be_inferrable_today() -> None:
    """Pinning the design choice: only Integrity/Incomplete
    literals are inferrable. A future phase may add string-typed
    return inference, but today a string return is silent."""
    # Strings cannot appear at top-level return position in current
    # grammar (they live inside Incomplete-literal field values),
    # so we exercise this property by inspecting the helper directly.
    from furqan.parser.ast_nodes import StringLiteral, SourceSpan
    from furqan.checker.return_type_match import _infer_return_type
    span = SourceSpan(file="<inline>", line=1, column=1)
    inferred = _infer_return_type(StringLiteral(value="x", span=span))
    assert inferred is None


def test_ident_expr_inference_returns_none() -> None:
    from furqan.parser.ast_nodes import IdentExpr, SourceSpan
    from furqan.checker.return_type_match import _infer_return_type
    span = SourceSpan(file="<inline>", line=1, column=1)
    assert _infer_return_type(IdentExpr(name="x", span=span)) is None


# ---------------------------------------------------------------------------
# Else-body recursion
# ---------------------------------------------------------------------------

def test_m1_fires_inside_else_body() -> None:
    """The recursive walker descends into IfStmt.else_body. A
    mismatch in the else-arm fires M1 just like one in the
    if-body."""
    fixture = INVALID_DIR / "mismatch_in_else.furqan"
    diags = check_return_type_match(_load(fixture))
    # Two mismatches: if-body returns Integrity (mismatch on Report),
    # else-body returns Incomplete (mismatch on Report).
    assert len(diags) == 2


def test_m1_fires_per_branch_in_else() -> None:
    fixture = INVALID_DIR / "mismatch_in_else.furqan"
    diags = check_return_type_match(_load(fixture))
    # The two diagnostics name different inferred types - one for
    # the if-body's Integrity return, one for the else-body's
    # Incomplete return. Both name the declared type "Report".
    inferred_set = set()
    for d in diags:
        if "returns a Integrity" in d.diagnosis:
            inferred_set.add("Integrity")
        elif "returns a Incomplete" in d.diagnosis:
            inferred_set.add("Incomplete")
        assert "Report" in d.diagnosis
    assert inferred_set == {"Integrity", "Incomplete"}


def test_walker_descends_into_nested_if_inside_else() -> None:
    """A return inside an if nested within an else body is still
    visited (recursive descent into both arms at every level)."""
    src = """
    bismillah NestedDemo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: maybe
        not_scope: nothing_excluded
    }

    fn maybe() -> Integrity {
        if not a {
            return Integrity
        } else {
            if b {
                return Incomplete {
                    reason: "deeply nested mismatch",
                    max_confidence: 0.5,
                    partial_findings: empty_list
                }
            }
        }
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert len(diags) == 1
    assert "Incomplete" in diags[0].diagnosis


# ---------------------------------------------------------------------------
# Per-return-site firing
# ---------------------------------------------------------------------------

def test_m1_fires_per_return_statement() -> None:
    """Multiple mismatching returns in the same function each fire
    a separate M1 (per-occurrence discipline matches Tanzil T1 and
    status-coverage S1)."""
    src = """
    bismillah Multi {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: pick
        not_scope: nothing_excluded
    }

    fn pick() -> Integrity {
        if a {
            return Incomplete {
                reason: "first",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        if b {
            return Incomplete {
                reason: "second",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        return Incomplete {
            reason: "third",
            max_confidence: 0.5,
            partial_findings: empty_list
        }
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert len(diags) == 3


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_function_with_no_return_type_skipped() -> None:
    fixture = VALID_DIR / "no_return_type.furqan"
    diags = check_return_type_match(_load(fixture))
    assert diags == []


def test_function_with_no_return_statements_passes() -> None:
    """A function declaring a return type but missing the return
    statement is ring-close R3's concern, not D22's. D22 has no
    return-expression to inspect; it stays silent."""
    src = """
    bismillah NoBody {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: empty
        not_scope: nothing_excluded
    }

    fn empty() -> Integrity {
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert diags == []


def test_module_with_no_functions_passes_trivially() -> None:
    src = """
    bismillah NoFunctions {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: types_only
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { id: ID }
    }
    """
    diags = check_return_type_match(parse(src, file="<inline>"))
    assert diags == []


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_raises_on_m1() -> None:
    fixture = INVALID_DIR / "integrity_declared_incomplete_returned.furqan"
    with pytest.raises(MaradError) as exc:
        check_return_type_match_strict(_load(fixture))
    assert exc.value.marad.primitive == PRIMITIVE_NAME


def test_strict_returns_module_on_clean_check() -> None:
    fixture = VALID_DIR / "integrity_returns_integrity.furqan"
    module = _load(fixture)
    returned = check_return_type_match_strict(module)
    assert returned is module


def test_strict_raises_on_first_marad_only() -> None:
    """When the body has multiple mismatches, strict variant raises
    on the first one. The remaining mismatches are still reachable
    via the non-strict variant."""
    fixture = INVALID_DIR / "mismatch_in_else.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError):
        check_return_type_match_strict(module)
    # Non-strict still surfaces both.
    diags = check_return_type_match(module)
    assert len(diags) == 2


# ---------------------------------------------------------------------------
# Cross-primitive composition
# ---------------------------------------------------------------------------

def test_d22_composes_with_ring_close_and_status_coverage() -> None:
    """The seven-primitive integration capstone fixture passes
    every prior checker AND D22 (the function returns
    Integrity | Incomplete and both arms match the union)."""
    fixture = (
        Path(__file__).parent / "fixtures" / "ring_close" / "valid"
        / "closed_ring_with_all_primitives.furqan"
    )
    module = parse(fixture.read_text(), file=fixture.name)
    for fn in (
        check_bismillah, check_zahir_batin, check_incomplete,
        check_ring_close, check_status_coverage,
        check_return_type_match,
    ):
        diags = fn(module)
        marads = [d for d in diags if isinstance(d, Marad)]
        assert marads == [], f"{fn.__name__} fired marads on capstone: {marads}"


def test_d22_composes_with_d11_on_chained_producers() -> None:
    """Two producers that mutually call each other - both honest -
    pass D22 and D11 simultaneously."""
    src = """
    bismillah Composed {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn first() -> Integrity | Incomplete {
        if not a {
            return Incomplete {
                reason: "first",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        return Integrity
    }

    fn second() -> Integrity | Incomplete {
        first()
        if not b {
            return Incomplete {
                reason: "second",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        return Integrity
    }
    """
    module = parse(src, file="<inline>")
    assert check_return_type_match(module) == []
    assert check_status_coverage(module) == []


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def test_return_type_match_marad_render_carries_primitive_tag() -> None:
    fixture = INVALID_DIR / "integrity_declared_incomplete_returned.furqan"
    d = check_return_type_match(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def test_public_surface_exports_d22_entry_points() -> None:
    from furqan.checker import (  # noqa: F401
        RETURN_TYPE_MATCH_PRIMITIVE_NAME,
        check_return_type_match,
        check_return_type_match_strict,
    )
    assert RETURN_TYPE_MATCH_PRIMITIVE_NAME == "return_type_match"


def test_module_all_matches_public_surface() -> None:
    from furqan.checker import return_type_match as rtm
    expected = {
        "PRIMITIVE_NAME",
        "check_return_type_match",
        "check_return_type_match_strict",
    }
    assert set(rtm.__all__) == expected
