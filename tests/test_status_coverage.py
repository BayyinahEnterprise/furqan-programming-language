"""
Status-coverage checker tests (D11 / v0.8.0).

The checker's contract: every function that calls a producer (a
function returning ``Integrity | Incomplete``) must either propagate
the union honestly (S3) or be flagged for collapse (S1, Marad) or
discard (S2, Advisory).

Two classes of test live here:

* Per-case property tests pin S1, S2, S3 on small inline modules
  whose shape isolates exactly one rule.
* Sweep tests guarantee every fixture behaves as the directory
  layout implies (valid -> zero diagnostics; invalid -> at least
  one).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker import (
    check_additive,
    check_bismillah,
    check_incomplete,
    check_mizan,
    check_ring_close,
    check_status_coverage,
    check_tanzil,
    check_zahir_batin,
)
from furqan.checker.status_coverage import (
    PRIMITIVE_NAME,
    check_status_coverage,
    check_status_coverage_strict,
)
from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "status_coverage"
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
    diags = check_status_coverage(_load(fixture))
    assert diags == [], (
        f"valid fixture {fixture.name} produced diagnostics: {diags}"
    )


@pytest.mark.parametrize("fixture", _all_invalid(), ids=lambda p: p.name)
def test_every_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    diags = check_status_coverage(_load(fixture))
    assert diags, (
        f"invalid fixture {fixture.name} produced zero diagnostics"
    )
    for d in diags:
        assert d.primitive == PRIMITIVE_NAME


def test_each_directory_is_non_empty() -> None:
    assert _all_valid()
    assert _all_invalid()


def test_primitive_name_is_stable() -> None:
    assert PRIMITIVE_NAME == "status_coverage"


# ---------------------------------------------------------------------------
# Case S1 - Status collapse (Marad)
# ---------------------------------------------------------------------------

def test_s1_collapse_fires_when_caller_returns_bare_integrity() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    diags = check_status_coverage(_load(fixture))
    marads = [d for d in diags if isinstance(d, Marad)]
    assert len(marads) == 1
    d = marads[0]
    assert "Case S1" in d.diagnosis


def test_s1_collapse_names_the_producer_function() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    d = check_status_coverage(_load(fixture))[0]
    assert "deep_scan" in d.diagnosis


def test_s1_collapse_names_the_caller_function() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    d = check_status_coverage(_load(fixture))[0]
    assert "summarize" in d.diagnosis


def test_s1_marad_carries_correct_primitive_name() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    d = check_status_coverage(_load(fixture))[0]
    assert d.primitive == "status_coverage"


def test_s1_fires_per_call_site() -> None:
    """Two callers each collapsing the same producer fire S1 twice -
    one Marad per caller's call site, matching the per-occurrence
    discipline of Tanzil T1."""
    fixture = INVALID_DIR / "multiple_collapses.furqan"
    diags = check_status_coverage(_load(fixture))
    marads = [d for d in diags if isinstance(d, Marad)]
    assert len(marads) == 2
    callers = {m.diagnosis.split("'")[1] for m in marads}
    assert callers == {"caller_one", "caller_two"}


def test_s1_location_points_at_the_call_site() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    d = check_status_coverage(_load(fixture))[0]
    assert d.location.file.endswith("status_collapse.furqan")
    assert d.location.line >= 1


def test_s1_fires_on_union_with_wrong_arms() -> None:
    """A return type that IS a union but whose arms are not exactly
    Integrity and Incomplete is still a collapse - the caller has
    narrowed away the producer's incompleteness."""
    src = """
    bismillah WrongUnion {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn produce() -> Integrity | Incomplete {
        if not ready {
            return Incomplete {
                reason: "not ready",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        return Integrity
    }

    fn consume() -> Integrity | OtherType {
        produce()
        return Integrity
    }
    """
    diags = check_status_coverage(parse(src, file="<inline>"))
    s1 = [d for d in diags if isinstance(d, Marad) and "Case S1" in d.diagnosis]
    assert len(s1) == 1


# ---------------------------------------------------------------------------
# Case S2 - Status discard (Advisory)
# ---------------------------------------------------------------------------

def test_s2_discard_fires_when_caller_has_no_return_type() -> None:
    fixture = INVALID_DIR / "status_discard.furqan"
    diags = check_status_coverage(_load(fixture))
    advisories = [d for d in diags if isinstance(d, Advisory)]
    assert len(advisories) == 1
    d = advisories[0]
    assert "Case S2" in d.message
    assert "main" in d.message
    assert "run_scan" in d.message


def test_s2_produces_advisory_not_marad() -> None:
    fixture = INVALID_DIR / "status_discard.furqan"
    d = check_status_coverage(_load(fixture))[0]
    assert isinstance(d, Advisory)
    assert not isinstance(d, Marad)


def test_s2_advisory_carries_correct_primitive_name() -> None:
    fixture = INVALID_DIR / "status_discard.furqan"
    d = check_status_coverage(_load(fixture))[0]
    assert d.primitive == PRIMITIVE_NAME


# ---------------------------------------------------------------------------
# S3 - Honest propagation (no diagnostic)
# ---------------------------------------------------------------------------

def test_s3_honest_propagation_produces_zero_diagnostics() -> None:
    fixture = VALID_DIR / "honest_propagation.furqan"
    diags = check_status_coverage(_load(fixture))
    assert diags == []


def test_s3_recursive_call_is_valid() -> None:
    """A producer that calls itself trivially preserves the union -
    its own return type IS the union - so S3 fires (no diagnostic)."""
    fixture = VALID_DIR / "producer_calls_itself.furqan"
    diags = check_status_coverage(_load(fixture))
    assert diags == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_producers_in_module_passes_trivially() -> None:
    """A module with zero producers exits the checker immediately
    (the producer-map empty short-circuit)."""
    fixture = VALID_DIR / "no_producers.furqan"
    diags = check_status_coverage(_load(fixture))
    assert diags == []


def test_external_call_not_flagged() -> None:
    """A call to a callee not defined in this module is
    unresolvable; the checker neither flags it nor lets it cause
    an S1/S2 trigger. Cross-module resolution is D23."""
    fixture = VALID_DIR / "external_call_only.furqan"
    diags = check_status_coverage(_load(fixture))
    assert diags == []


def test_producer_calling_another_producer_both_checked() -> None:
    """Two producers that call each other both pass S3 - each one's
    call to the other dispatches against the producer map and finds
    the caller is itself a producer."""
    src = """
    bismillah TwoProducers {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn first() -> Integrity | Incomplete {
        second()
        if not done {
            return Incomplete {
                reason: "first not done",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        return Integrity
    }

    fn second() -> Integrity | Incomplete {
        if not done {
            return Incomplete {
                reason: "second not done",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
        return Integrity
    }
    """
    diags = check_status_coverage(parse(src, file="<inline>"))
    assert diags == []


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_raises_on_s1_marad() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    with pytest.raises(MaradError) as exc:
        check_status_coverage_strict(_load(fixture))
    assert exc.value.marad.primitive == PRIMITIVE_NAME


def test_strict_does_not_raise_on_s2_advisory() -> None:
    """S2 is an Advisory; the strict variant must NOT raise."""
    fixture = INVALID_DIR / "status_discard.furqan"
    module = _load(fixture)
    returned = check_status_coverage_strict(module)
    assert returned is module


def test_strict_returns_module_on_clean_check() -> None:
    fixture = VALID_DIR / "honest_propagation.furqan"
    module = _load(fixture)
    returned = check_status_coverage_strict(module)
    assert returned is module


# ---------------------------------------------------------------------------
# Cross-primitive non-interference
# ---------------------------------------------------------------------------

def test_module_with_status_coverage_and_all_seven_primitives() -> None:
    """The seven-primitive integration capstone fixture must not
    fire any S1/S2 - it is a single-producer module whose only
    function returns the union directly (no caller-collapse path)."""
    fixture = (
        Path(__file__).parent / "fixtures" / "ring_close" / "valid"
        / "closed_ring_with_all_primitives.furqan"
    )
    module = parse(fixture.read_text(), file=fixture.name)
    # All six prior checkers + ring-close + status-coverage all pass.
    for fn in (
        check_bismillah, check_zahir_batin, check_incomplete,
        check_mizan, check_tanzil, check_ring_close,
        check_status_coverage,
    ):
        diags = fn(module)
        marads = [d for d in diags if isinstance(d, Marad)]
        assert marads == [], f"{fn.__name__} fired marads on capstone: {marads}"


# ---------------------------------------------------------------------------
# Marad / Advisory rendering
# ---------------------------------------------------------------------------

def test_status_coverage_marad_render_carries_primitive_tag() -> None:
    fixture = INVALID_DIR / "status_collapse.furqan"
    d = check_status_coverage(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


def test_status_coverage_advisory_render_carries_advisory_prefix() -> None:
    fixture = INVALID_DIR / "status_discard.furqan"
    d = check_status_coverage(_load(fixture))[0]
    rendered = d.render()
    assert PRIMITIVE_NAME in rendered


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def test_public_surface_exports_status_coverage_entry_points() -> None:
    from furqan.checker import (  # noqa: F401
        STATUS_COVERAGE_PRIMITIVE_NAME,
        check_status_coverage,
        check_status_coverage_strict,
    )
    assert STATUS_COVERAGE_PRIMITIVE_NAME == "status_coverage"


def test_status_coverage_module_all_matches_public_surface() -> None:
    from furqan.checker import status_coverage as sc
    expected = {
        "PRIMITIVE_NAME",
        "StatusCoverageDiagnostic",
        "check_status_coverage",
        "check_status_coverage_strict",
    }
    assert set(sc.__all__) == expected
