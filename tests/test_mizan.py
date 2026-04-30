"""
Mizan well-formedness checker tests (Phase 2.7 / Session 1.6).

The checker's contract from the Furqan thesis paper §Primitive 4:

    Every mizan block declares all three canonical calibration
    commands (la_tatghaw, la_tukhsiru, bil_qist) exactly once,
    in canonical order.

Three checker cases are tested here (M3 unknown-field is enforced
at the parser layer per §6.4 — its tests live in test_parser.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.mizan import (
    PRIMITIVE_NAME,
    REQUIRED_MIZAN_FIELDS,
    check_mizan,
    check_mizan_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mizan"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load(path: Path):
    return parse(path.read_text(), file=str(path))


def _all_valid():
    """All valid fixtures."""
    return sorted(VALID_DIR.glob("*.furqan"))


def _all_invalid_for_checker():
    """Invalid fixtures the CHECKER processes (excluding M3 which
    is parser-layer)."""
    return sorted(
        p for p in INVALID_DIR.glob("*.furqan")
        if p.name != "unknown_field.furqan"
    )


# ---------------------------------------------------------------------------
# Sweep — every valid fixture passes; every invalid (checker-eligible)
# produces exactly one marad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _all_valid(), ids=lambda p: p.name)
def test_every_valid_fixture_produces_zero_diagnostics(fixture: Path) -> None:
    module = _load(fixture)
    diagnostics = check_mizan(module)
    assert diagnostics == [], (
        f"valid fixture {fixture.name} produced diagnostics: "
        f"{[d.diagnosis for d in diagnostics]}"
    )


@pytest.mark.parametrize(
    "fixture", _all_invalid_for_checker(), ids=lambda p: p.name,
)
def test_every_checker_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    module = _load(fixture)
    diagnostics = check_mizan(module)
    assert diagnostics, (
        f"invalid fixture {fixture.name} produced zero diagnostics"
    )
    assert all(d.primitive == PRIMITIVE_NAME for d in diagnostics)


def test_each_directory_is_non_empty() -> None:
    assert _all_valid()
    assert _all_invalid_for_checker()


# ---------------------------------------------------------------------------
# Constants pinned (NAMING.md surface)
# ---------------------------------------------------------------------------

def test_required_mizan_fields_canonical_set_and_order() -> None:
    """The three canonical mizan fields and their canonical order
    are pinned. A future expansion that reorders them would be a
    structural change requiring a minor-version bump (the Quranic
    sequence at Ar-Rahman 55:7-9 anchors this order)."""
    assert REQUIRED_MIZAN_FIELDS == ("la_tatghaw", "la_tukhsiru", "bil_qist")


# ---------------------------------------------------------------------------
# Case M1 — Missing required field
# ---------------------------------------------------------------------------

def test_case_m1_missing_la_tatghaw_emits_marad() -> None:
    fixture = INVALID_DIR / "missing_la_tatghaw.furqan"
    diagnostics = check_mizan(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case M1" in d.diagnosis
    assert "'la_tatghaw'" in d.diagnosis
    assert "do-not-transgress" in d.diagnosis


def test_case_m1_inline_missing_each_field() -> None:
    """For each canonical field, build a mizan block omitting only
    that field and assert the M1 marad fires citing the missing
    name. This pins that the missing-field detection works for
    all three canonical fields, not only la_tatghaw."""
    base_fields = {
        "la_tatghaw":  "la_tatghaw:  fp_rate < 0.05",
        "la_tukhsiru": "la_tukhsiru: detection > 0.90",
        "bil_qist":    "bil_qist:    calibrate(c)",
    }
    bismillah_block = (
        "bismillah Demo {\n"
        "    authority: NAMING_MD\n"
        "    serves: purpose_hierarchy.balance_for_living_systems\n"
        "    scope: cal\n"
        "    not_scope: nothing\n"
        "}\n"
    )
    for missing_field in REQUIRED_MIZAN_FIELDS:
        body = "\n".join(
            v for k, v in base_fields.items() if k != missing_field
        )
        # Without la_tatghaw the surviving fields stay in canonical
        # order; without la_tukhsiru we'd produce la_tatghaw + bil_qist
        # which is in order; without bil_qist we'd produce la_tatghaw +
        # la_tukhsiru which is in order. So no M4 marad accidentally
        # fires alongside the M1 marad.
        src = f"{bismillah_block}mizan demo {{\n{body}\n}}\n"
        module = parse(src, file="<inline>")
        diagnostics = check_mizan(module)
        m1 = [d for d in diagnostics if "Case M1" in d.diagnosis]
        assert len(m1) == 1, (
            f"missing {missing_field}: expected exactly one M1 "
            f"marad; got {[d.diagnosis for d in diagnostics]}"
        )
        assert f"'{missing_field}'" in m1[0].diagnosis


def test_case_m1_does_not_fire_on_complete_block() -> None:
    fixture = VALID_DIR / "detection_threshold.furqan"
    diagnostics = check_mizan(_load(fixture))
    assert all("Case M1" not in d.diagnosis for d in diagnostics)


# ---------------------------------------------------------------------------
# Case M2 — Duplicate field
# ---------------------------------------------------------------------------

def test_case_m2_duplicate_la_tatghaw_emits_marad() -> None:
    fixture = INVALID_DIR / "duplicate_field.furqan"
    diagnostics = check_mizan(_load(fixture))
    m2 = [d for d in diagnostics if "Case M2" in d.diagnosis]
    assert len(m2) == 1
    d = m2[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "'la_tatghaw'" in d.diagnosis


def test_case_m2_fires_per_extra_occurrence() -> None:
    """If a field is declared three times, the marad fires twice
    (once per occurrence after the first). This pins the
    "first-occurrence-wins" semantics of the duplicate check."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    mizan triple_upper {
        la_tatghaw:  fp_rate < 0.05
        la_tatghaw:  fp_rate < 0.10
        la_tatghaw:  fp_rate < 0.20
        la_tukhsiru: detection > 0.90
        bil_qist:    calibrate(c)
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_mizan(module)
    m2 = [d for d in diagnostics if "Case M2" in d.diagnosis]
    assert len(m2) == 2


# ---------------------------------------------------------------------------
# Case M4 — Out-of-order fields
# ---------------------------------------------------------------------------

def test_case_m4_out_of_order_emits_marad() -> None:
    fixture = INVALID_DIR / "out_of_order_fields.furqan"
    diagnostics = check_mizan(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case M4" in d.diagnosis
    assert "non-canonical order" in d.diagnosis
    assert "la_tatghaw, la_tukhsiru, bil_qist" in d.diagnosis


def test_case_m4_does_not_fire_when_a_field_is_missing() -> None:
    """M4 short-circuits when M1 fires: a missing field already
    produces the load-bearing diagnostic; a redundant M4 marad
    on a partial block would be confusing dual signal. This test
    pins the M1-then-M4 ordering."""
    fixture = INVALID_DIR / "missing_la_tatghaw.furqan"
    diagnostics = check_mizan(_load(fixture))
    assert all("Case M4" not in d.diagnosis for d in diagnostics)


def test_case_m4_does_not_fire_on_canonical_order() -> None:
    fixture = VALID_DIR / "detection_threshold.furqan"
    diagnostics = check_mizan(_load(fixture))
    assert all("Case M4" not in d.diagnosis for d in diagnostics)


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_violation() -> None:
    fixture = INVALID_DIR / "missing_la_tatghaw.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_mizan_strict(module)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_returns_module_on_pass() -> None:
    fixture = VALID_DIR / "detection_threshold.furqan"
    module = _load(fixture)
    returned = check_mizan_strict(module)
    assert returned is module


# ---------------------------------------------------------------------------
# Marad rendering
# ---------------------------------------------------------------------------

def test_mizan_marad_render_carries_primitive_tag_and_recovery() -> None:
    fixture = INVALID_DIR / "missing_la_tatghaw.furqan"
    d = check_mizan(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


# ---------------------------------------------------------------------------
# Cross-primitive non-interference
# ---------------------------------------------------------------------------

def test_module_with_no_mizan_decls_passes_trivially() -> None:
    """A module declaring no mizan blocks has nothing for the
    Mizan checker to fire on. This pins that the checker is
    non-invasive on pre-2.7 surfaces."""
    src = """
    bismillah Quiet {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: stuff
        not_scope: nothing
    }

    fn run() {
    }
    """
    module = parse(src, file="<inline>")
    assert check_mizan(module) == []


# ---------------------------------------------------------------------------
# Reflexivity audit (Step 7 unreachable-branch claim)
# ---------------------------------------------------------------------------

def test_check_mizan_module_has_no_unknown_field_branch() -> None:
    """Per Phase 2.7 §6.6 routing rationale, M3 (unknown field) is
    enforced at the parser layer; the checker has no business
    inspecting field-head names against the canonical set because
    by the time a MizanDecl reaches the checker, every field name
    is canonical by construction.

    This test grep-audits the checker source to confirm no
    defensive `if field_name not in REQUIRED_MIZAN_FIELDS` branch
    snuck in. If such a branch is added, this test fires; the
    branch is dead code per the routing rationale and should be
    removed.
    """
    import inspect
    from furqan.checker import mizan as mizan_module
    src = inspect.getsource(mizan_module)
    # Negative assertion: the checker must not contain a guard
    # against unknown field names.
    forbidden_patterns = [
        "not in REQUIRED_MIZAN_FIELDS",
        "unknown field",
        "Unknown field",
        "Case M3",
    ]
    for pat in forbidden_patterns:
        # An exception: the docstring discusses the M3 routing
        # rationale and *names* "Case M3" in the context of
        # explaining why it is NOT a checker case. Filter out
        # docstring-only mentions (which appear inside the module
        # docstring, before the first `def`).
        first_def = src.find("\ndef ")
        body_after_first_def = src[first_def:] if first_def != -1 else ""
        assert pat not in body_after_first_def, (
            f"checker function body contains forbidden pattern "
            f"{pat!r} — this is the dead defensive code the §6.6 "
            f"routing rationale forbids. Remove it."
        )
