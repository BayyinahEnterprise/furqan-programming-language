"""
All-paths-return analysis tests (D24 / v0.8.2).

The checker's contract: every control-flow path through a typed
function's body must reach a return statement. The analysis is
exact for the current grammar - IfStmt is the only branching
construct, so structural recursion is sufficient.

D24 deliberately delineates from ring-close R3:
* R3 fires when a typed function has ZERO return statements.
* D24 fires when a typed function has at least one return but
  not every path reaches one.
A function with zero returns triggers R3 only; D24 stays silent
to avoid double-reporting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker import (
    check_all_paths_return,
    check_bismillah,
    check_incomplete,
    check_return_type_match,
    check_ring_close,
    check_status_coverage,
    check_zahir_batin,
)
from furqan.checker.all_paths_return import (
    PRIMITIVE_NAME,
    _all_paths_return,
    _any_return_exists,
    check_all_paths_return,
    check_all_paths_return_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "all_paths_return"
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
    diags = check_all_paths_return(_load(fixture))
    assert diags == [], (
        f"valid fixture {fixture.name} produced diagnostics: {diags}"
    )


@pytest.mark.parametrize("fixture", _all_invalid(), ids=lambda p: p.name)
def test_every_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    diags = check_all_paths_return(_load(fixture))
    assert diags
    for d in diags:
        assert d.primitive == PRIMITIVE_NAME


def test_each_directory_is_non_empty() -> None:
    assert _all_valid()
    assert _all_invalid()


def test_primitive_name_is_stable() -> None:
    assert PRIMITIVE_NAME == "all_paths_return"


# ---------------------------------------------------------------------------
# Core algorithm - direct unit tests on _all_paths_return
# ---------------------------------------------------------------------------

def test_bare_return_passes() -> None:
    fixture = VALID_DIR / "bare_return.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert diags == []


def test_if_else_both_return_passes() -> None:
    fixture = VALID_DIR / "if_else_both_return.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert diags == []


def test_return_after_if_without_else_passes() -> None:
    """The IfStmt itself does not all-paths-return (no else), but
    the bare return that follows the if covers the fall-through
    path. The for-loop walks past the IfStmt and finds the return."""
    fixture = VALID_DIR / "return_after_if.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert diags == []


def test_if_without_else_no_trailing_return_fails() -> None:
    fixture = INVALID_DIR / "if_without_else.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert len(diags) == 1
    assert "Case P1" in diags[0].diagnosis


def test_if_else_one_branch_missing_return_fails() -> None:
    fixture = INVALID_DIR / "if_else_one_missing.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert len(diags) == 1


# ---------------------------------------------------------------------------
# Nested if/else
# ---------------------------------------------------------------------------

def test_nested_if_else_all_return_passes() -> None:
    fixture = VALID_DIR / "nested_if_else_all_return.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert diags == []


def test_nested_inner_branch_missing_fails() -> None:
    fixture = INVALID_DIR / "nested_gap.furqan"
    diags = check_all_paths_return(_load(fixture))
    assert len(diags) == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_function_with_no_return_type_skipped() -> None:
    """Void functions are not subject to D24 - they have no
    return-type contract."""
    src = """
    bismillah Void {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: noop
        not_scope: nothing_excluded
    }

    fn noop() {
        if not done {
            log_event(state)
        }
    }
    """
    diags = check_all_paths_return(parse(src, file="<inline>"))
    assert diags == []


def test_function_with_no_return_at_all_skipped() -> None:
    """A typed function with zero returns is ring-close R3's
    territory. D24 stays silent to avoid double-reporting."""
    src = """
    bismillah Empty {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: empty
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { id: ID }
    }

    fn empty() -> Document {
        log_event(state)
    }
    """
    diags = check_all_paths_return(parse(src, file="<inline>"))
    assert diags == []


def test_function_with_only_calls_and_return_type_skipped() -> None:
    """Same as above - a body with only calls is R3's concern.
    D24 stays silent."""
    src = """
    bismillah CallsOnly {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: act
        not_scope: nothing_excluded
    }

    fn act() -> Integrity {
        do_a()
        do_b()
    }
    """
    diags = check_all_paths_return(parse(src, file="<inline>"))
    assert diags == []


def test_module_with_no_functions_passes_trivially() -> None:
    src = """
    bismillah TypesOnly {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: declare
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { id: ID }
    }
    """
    diags = check_all_paths_return(parse(src, file="<inline>"))
    assert diags == []


# ---------------------------------------------------------------------------
# R3 / D24 delineation - no double diagnostic
# ---------------------------------------------------------------------------

def test_p1_does_not_fire_when_r3_would_fire() -> None:
    """A typed function with zero returns triggers R3 (which fires
    its own marad) but NOT D24's P1. Confirms the
    `_any_return_exists` short-circuit prevents double-reporting."""
    src = """
    bismillah ZeroReturns {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: empty
        not_scope: nothing_excluded
    }

    fn empty() -> Integrity {
    }
    """
    module = parse(src, file="<inline>")
    # R3 should fire, D24 should not.
    ring_diags = check_ring_close(module)
    d24_diags = check_all_paths_return(module)
    r3_marads = [
        d for d in ring_diags
        if isinstance(d, Marad) and "Case R3" in d.diagnosis
    ]
    assert len(r3_marads) == 1
    assert d24_diags == []


def test_d24_fires_only_after_r3_passes() -> None:
    """A function that passes R3 (has at least one return) but
    fails D24 (not all paths return) produces exactly one P1
    marad and zero R3 marads."""
    fixture = INVALID_DIR / "if_without_else.furqan"
    module = _load(fixture)
    ring_diags = check_ring_close(module)
    d24_diags = check_all_paths_return(module)
    r3_marads = [
        d for d in ring_diags
        if isinstance(d, Marad) and "Case R3" in d.diagnosis
    ]
    assert r3_marads == []
    assert len(d24_diags) == 1


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_raises_on_p1() -> None:
    fixture = INVALID_DIR / "if_without_else.furqan"
    with pytest.raises(MaradError) as exc:
        check_all_paths_return_strict(_load(fixture))
    assert exc.value.marad.primitive == PRIMITIVE_NAME


def test_strict_returns_module_on_clean_check() -> None:
    fixture = VALID_DIR / "if_else_both_return.furqan"
    module = _load(fixture)
    returned = check_all_paths_return_strict(module)
    assert returned is module


# ---------------------------------------------------------------------------
# Cross-primitive composition
# ---------------------------------------------------------------------------

def test_d24_composes_with_all_checkers_on_capstone() -> None:
    """The seven-primitive integration capstone fixture (refactored
    in v0.8.2 to use if/else) passes every checker including D24."""
    fixture = (
        Path(__file__).parent / "fixtures" / "ring_close" / "valid"
        / "closed_ring_with_all_primitives.furqan"
    )
    module = parse(fixture.read_text(), file=fixture.name)
    for fn in (
        check_bismillah, check_zahir_batin, check_incomplete,
        check_ring_close, check_status_coverage,
        check_return_type_match, check_all_paths_return,
    ):
        diags = fn(module)
        marads = [d for d in diags if isinstance(d, Marad)]
        assert marads == [], f"{fn.__name__} fired marads: {marads}"


# ---------------------------------------------------------------------------
# Marad rendering
# ---------------------------------------------------------------------------

def test_p1_marad_carries_correct_primitive_name() -> None:
    fixture = INVALID_DIR / "if_without_else.furqan"
    d = check_all_paths_return(_load(fixture))[0]
    assert d.primitive == "all_paths_return"


def test_p1_marad_names_the_function() -> None:
    fixture = INVALID_DIR / "if_without_else.furqan"
    d = check_all_paths_return(_load(fixture))[0]
    assert "scan" in d.diagnosis


def test_p1_marad_render_carries_primitive_tag_and_recovery() -> None:
    fixture = INVALID_DIR / "if_without_else.furqan"
    d = check_all_paths_return(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


# ---------------------------------------------------------------------------
# Algorithm helpers - direct unit tests
# ---------------------------------------------------------------------------

def test_all_paths_return_helper_on_empty_tuple() -> None:
    """An empty body has no return at all - returns False."""
    assert _all_paths_return(()) is False


def test_any_return_exists_helper_on_empty_tuple() -> None:
    assert _any_return_exists(()) is False


def test_all_paths_return_helper_on_single_return() -> None:
    """A single ReturnStmt at the top of a sequence is sufficient."""
    src = """
    bismillah X {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: x
        not_scope: nothing_excluded
    }

    fn one() -> Integrity {
        return Integrity
    }
    """
    fn = parse(src, file="<inline>").functions[0]
    assert _all_paths_return(fn.statements) is True


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def test_public_surface_exports_d24_entry_points() -> None:
    from furqan.checker import (  # noqa: F401
        ALL_PATHS_RETURN_PRIMITIVE_NAME,
        check_all_paths_return,
        check_all_paths_return_strict,
    )
    assert ALL_PATHS_RETURN_PRIMITIVE_NAME == "all_paths_return"


def test_module_all_matches_public_surface() -> None:
    from furqan.checker import all_paths_return as apr
    expected = {
        "PRIMITIVE_NAME",
        "check_all_paths_return",
        "check_all_paths_return_strict",
    }
    assert set(apr.__all__) == expected
