"""
Scan-incomplete return-type checker tests (Phase 2.6 / Session 1.5).

The checker's contract from the Furqan thesis paper §4:

    A function declared `-> Integrity | Incomplete` cannot return
    bare `Integrity` from a path on which its own incompleteness
    signal was not syntactically ruled out (Case A). An `Incomplete`
    literal must declare reason, max_confidence, and partial_findings
    (Case B).

The tests pair each property with concrete .furqan fixtures under
``tests/fixtures/scan_incomplete/{valid,invalid}/``. The fixture-
driven sweeps are the empirical surface; named-property tests pin
each case independently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.incomplete import (
    INCOMPLETE_TYPE_NAME,
    INTEGRITY_TYPE_NAME,
    PRIMITIVE_NAME,
    REQUIRED_INCOMPLETE_FIELDS,
    check_incomplete,
    check_incomplete_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "scan_incomplete"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load(path: Path):
    return parse(path.read_text(), file=str(path))


def _all(directory: Path):
    return sorted(p for p in directory.glob("*.furqan"))


# ---------------------------------------------------------------------------
# Sweep — every valid fixture passes; every invalid produces ≥1 marad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _all(VALID_DIR), ids=lambda p: p.name)
def test_every_valid_fixture_produces_zero_diagnostics(fixture: Path) -> None:
    module = _load(fixture)
    diagnostics = check_incomplete(module)
    assert diagnostics == [], (
        f"valid fixture {fixture.name} produced diagnostics: "
        f"{[d.diagnosis for d in diagnostics]}"
    )


@pytest.mark.parametrize("fixture", _all(INVALID_DIR), ids=lambda p: p.name)
def test_every_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    module = _load(fixture)
    diagnostics = check_incomplete(module)
    assert diagnostics, (
        f"invalid fixture {fixture.name} produced zero diagnostics — "
        f"the scan-incomplete checker silently accepted a structural "
        f"violation."
    )
    assert all(d.primitive == PRIMITIVE_NAME for d in diagnostics)


def test_each_directory_is_non_empty() -> None:
    assert _all(VALID_DIR), "tests/fixtures/scan_incomplete/valid/ is empty"
    assert _all(INVALID_DIR), "tests/fixtures/scan_incomplete/invalid/ is empty"


# ---------------------------------------------------------------------------
# Constants pinned (NAMING.md surface)
# ---------------------------------------------------------------------------

def test_required_incomplete_fields_are_the_canonical_three() -> None:
    """The three required Incomplete literal fields are pinned by
    name. A future expansion that adds a fourth required field would
    be an additive-on-the-rejection-side change and would require a
    minor-version bump."""
    assert REQUIRED_INCOMPLETE_FIELDS == frozenset(
        {"reason", "max_confidence", "partial_findings"}
    )


def test_type_name_constants_are_canonical() -> None:
    assert INTEGRITY_TYPE_NAME == "Integrity"
    assert INCOMPLETE_TYPE_NAME == "Incomplete"


# ---------------------------------------------------------------------------
# Case A — bare Integrity returned without ruling out incompleteness
# ---------------------------------------------------------------------------

def test_case_a_unguarded_integrity_emits_marad() -> None:
    fixture = INVALID_DIR / "scan_returns_integrity_unguarded.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "scan_unsafely" in d.diagnosis
    assert "Case A" in d.diagnosis
    assert "Integrity | Incomplete" in d.diagnosis
    assert "not enclosed by any `if` body" in d.diagnosis


def test_case_a_inverted_guard_emits_marad() -> None:
    """A function with `if is_encrypted(file) { return Integrity }`
    has a guard but the polarity is inverted — the predicate held,
    so the path should produce Incomplete, not Integrity."""
    fixture = INVALID_DIR / "scan_returns_integrity_in_failure_branch.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "scan_inverted" in d.diagnosis
    assert "Case A" in d.diagnosis
    assert "not negated" in d.diagnosis


def test_case_a_does_not_fire_when_negated_guard_present() -> None:
    """The honest shape: `if not is_encrypted(file) { return Integrity }`
    explicitly rules out incompleteness before returning. Case A
    must accept this."""
    fixture = VALID_DIR / "scan_handles_both_paths.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert diagnostics == []


def test_case_a_does_not_fire_on_non_union_return_type() -> None:
    """A function declared `-> Integrity` (no union) is not subject
    to the Case A rule. The rule applies only to functions whose
    declared return type is the `Integrity | Incomplete` union."""
    fixture = VALID_DIR / "scan_returns_only_integrity.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert diagnostics == []


def test_case_a_does_not_fire_when_no_integrity_return_present() -> None:
    """A union-typed function whose only return path produces
    Incomplete has nothing for Case A to fire on (the rule guards
    bare-Integrity returns specifically)."""
    fixture = VALID_DIR / "scan_only_incomplete_path.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert diagnostics == []


# ---------------------------------------------------------------------------
# Case B — Incomplete literal missing required fields
# ---------------------------------------------------------------------------

def test_case_b_missing_reason_emits_marad() -> None:
    fixture = INVALID_DIR / "scan_incomplete_missing_reason.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case B" in d.diagnosis
    assert "'reason'" in d.diagnosis
    assert "describes WHY" in d.diagnosis


def test_case_b_missing_max_confidence_emits_marad() -> None:
    fixture = INVALID_DIR / "scan_incomplete_missing_max_confidence.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case B" in d.diagnosis
    assert "'max_confidence'" in d.diagnosis
    assert "SCAN_INCOMPLETE_CLAMP" in d.diagnosis


def test_case_b_does_not_fire_on_complete_literal() -> None:
    fixture = VALID_DIR / "scan_with_partial_findings.furqan"
    diagnostics = check_incomplete(_load(fixture))
    assert diagnostics == []


def test_case_b_fires_for_every_missing_field_independently() -> None:
    """An Incomplete literal missing all three fields produces three
    separate marads, one per missing field. The checker emits one
    marad per missing field rather than rolling them up so a Phase-3
    multi-error reporter can group by primitive but still surface
    each missing field's specific role text."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan_empty_incomplete(file: File) -> Integrity | Incomplete {
        return Incomplete {
        }
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_incomplete(module)
    case_b_diagnostics = [d for d in diagnostics if "Case B" in d.diagnosis]
    assert len(case_b_diagnostics) == 3
    field_names = {f"'{n}'" for n in REQUIRED_INCOMPLETE_FIELDS}
    diag_text = " ".join(d.diagnosis for d in case_b_diagnostics)
    for fname in field_names:
        assert fname in diag_text


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_violation() -> None:
    fixture = INVALID_DIR / "scan_returns_integrity_unguarded.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_incomplete_strict(module)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_returns_module_on_pass() -> None:
    fixture = VALID_DIR / "scan_handles_both_paths.furqan"
    module = _load(fixture)
    returned = check_incomplete_strict(module)
    assert returned is module


# ---------------------------------------------------------------------------
# Marad rendering
# ---------------------------------------------------------------------------

def test_case_a_marad_render_carries_primitive_tag_and_recovery() -> None:
    fixture = INVALID_DIR / "scan_returns_integrity_unguarded.furqan"
    d = check_incomplete(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


# ---------------------------------------------------------------------------
# Cross-primitive non-interference
# ---------------------------------------------------------------------------

def test_scan_incomplete_does_not_fire_on_bismillah_only_modules() -> None:
    """A module with no functions returning Integrity | Incomplete
    has nothing for the scan-incomplete checker to emit on. This
    pins that the checker is non-invasive on pre-2.6 surfaces."""
    src = """
    bismillah Quiet {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: stuff
        not_scope: nothing_excluded
    }

    fn run() {
    }
    """
    module = parse(src, file="<inline>")
    assert check_incomplete(module) == []
