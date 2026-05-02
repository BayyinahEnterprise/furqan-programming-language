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


# ---------------------------------------------------------------------------
# v0.11.0: producer_predicate parameter
# ---------------------------------------------------------------------------

def test_producer_predicate_default_uses_integrity_incomplete() -> None:
    """Calling check_status_coverage without the parameter behaves
    identically to the v0.10.x default: only Integrity | Incomplete
    union returns count as producers."""
    fixture = INVALID_DIR / "status_collapse.furqan"
    diags_default = check_status_coverage(_load(fixture))
    # The default must produce the same Marad set as the canonical
    # helper would.
    from furqan.checker.status_coverage import _is_integrity_incomplete_union
    diags_explicit = check_status_coverage(
        _load(fixture),
        producer_predicate=_is_integrity_incomplete_union,
    )
    assert len(diags_default) == len(diags_explicit) == 1
    assert isinstance(diags_default[0], Marad)
    assert isinstance(diags_explicit[0], Marad)


def test_producer_predicate_custom_function_used() -> None:
    """A custom predicate that accepts every union return type makes
    every union-returning function a producer. Pin that the custom
    predicate is actually consulted, not the canonical helper."""
    src = """
    bismillah Custom {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type DocA {
        zahir { name: String }
        batin { id: ID }
    }

    type DocB {
        zahir { name: String }
        batin { id: ID }
    }

    fn produce_docs() -> DocA | DocB {
        return DocA
    }

    fn consume() -> DocA {
        produce_docs()
        return DocA
    }
    """
    module = parse(src, file="<inline>")
    # Without a custom predicate, no producer is detected (the
    # union arms are not Integrity/Incomplete).
    assert check_status_coverage(module) == []
    # With a permissive predicate that accepts every union, the
    # call to produce_docs becomes a producer-call and consume's
    # bare-DocA return collapses it.
    diags = check_status_coverage(
        module, producer_predicate=lambda rt: True,
    )
    marads = [d for d in diags if isinstance(d, Marad)]
    assert len(marads) == 1
    assert "consume" in marads[0].diagnosis
    assert "produce_docs" in marads[0].diagnosis


def test_producer_predicate_keyword_only() -> None:
    """The new parameter is keyword-only. Passing it positionally
    raises TypeError. Pins the deliberate signature."""
    src = """
    bismillah X {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: x
        not_scope: nothing_excluded
    }

    fn x() -> Integrity {
        return Integrity
    }
    """
    module = parse(src, file="<inline>")
    with pytest.raises(TypeError):
        check_status_coverage(module, lambda rt: True)  # type: ignore[misc]


def test_producer_predicate_threads_into_check_calls() -> None:
    """v0.11.0: the predicate must be threaded into _check_calls, not
    just used during the producer-map build. This test sets up a
    module where:

      - Producer P returns the v0 helper's accepted shape
        (Integrity | Incomplete) AND the custom predicate also
        accepts it.
      - Consumer C returns Integrity | OtherType (a union that the
        v0 helper rejects but the custom predicate accepts as
        'honest propagation').

    Under the v0 helper, C's call to P would fire S1 (the union
    arms aren't exactly Integrity and Incomplete). Under a custom
    predicate that accepts both shapes, C's call to P should NOT
    fire S1 because the per-call-site check honours the predicate.

    If the predicate were threaded only at the producer-map build,
    the per-call check would still use the canonical helper and
    fire S1. This test fails on the half-applied bug-fix shape.
    """
    src = """
    bismillah Threading {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type OtherType {
        zahir { name: String }
        batin { id: ID }
    }

    fn produce() -> Integrity | Incomplete {
        if not missing {
            return Integrity
        } else {
            return Incomplete {
                reason: "missing",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
    }

    fn consume() -> Integrity | OtherType {
        produce()
        return Integrity
    }
    """
    module = parse(src, file="<inline>")

    def lenient_predicate(rt) -> bool:
        # Accept both Integrity|Incomplete AND Integrity|OtherType
        # as 'honest propagation' shapes.
        arms = {rt.left.base, rt.right.base}
        return "Integrity" in arms

    diags = check_status_coverage(
        module, producer_predicate=lenient_predicate,
    )
    s1 = [d for d in diags if isinstance(d, Marad) and "Case S1" in d.diagnosis]
    # If the predicate is NOT threaded into _check_calls, S1 fires
    # because the per-call-site check still uses the canonical helper.
    # If it IS threaded, S1 stays silent.
    assert s1 == [], (
        "producer_predicate is not threaded into _check_calls: the "
        "per-call-site producer-shape check still uses the canonical "
        "_is_integrity_incomplete_union, which makes the bug-fix "
        "half-applied. See v0.11.0 CHANGELOG."
    )


def test_strict_variant_forwards_producer_predicate() -> None:
    """The strict variant must forward the predicate. A custom
    predicate that flags a Marad must cause the strict variant to
    raise; without forwarding, it would silently pass."""
    src = """
    bismillah StrictForward {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type DocA {
        zahir { name: String }
        batin { id: ID }
    }

    type DocB {
        zahir { name: String }
        batin { id: ID }
    }

    fn produce_docs() -> DocA | DocB {
        return DocA
    }

    fn consume() -> DocA {
        produce_docs()
        return DocA
    }
    """
    module = parse(src, file="<inline>")
    # Default predicate: no producer detected, strict returns module.
    from furqan.checker.status_coverage import check_status_coverage_strict
    returned = check_status_coverage_strict(module)
    assert returned is module
    # Permissive predicate: produce_docs is a producer; consume's
    # DocA narrowing fires S1; strict variant must raise.
    with pytest.raises(MaradError) as exc:
        check_status_coverage_strict(
            module, producer_predicate=lambda rt: True,
        )
    assert exc.value.marad.primitive == PRIMITIVE_NAME
