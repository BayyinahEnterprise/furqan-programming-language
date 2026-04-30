"""
Tanzil build-ordering checker tests (Phase 2.8 / Session 1.7).

The checker's contract: every tanzil block in a module declares
its build-ordering dependencies with no self-references and no
duplicates; an empty block produces an Advisory rather than a
Marad. Multi-module graph analysis is D9, deferred to Phase 3+.

Three diagnostic cases are tested here (T3 unknown-field is
enforced at the parser layer per §6.4 routing — its test lives in
test_parser.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.tanzil import (
    PRIMITIVE_NAME,
    check_tanzil,
    check_tanzil_strict,
)
from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "tanzil"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load(path: Path):
    return parse(path.read_text(), file=str(path))


def _all_valid():
    return sorted(VALID_DIR.glob("*.furqan"))


def _all_invalid_for_checker():
    """Invalid fixtures the CHECKER processes (excluding
    unknown_field.furqan, which is parser-layer)."""
    return sorted(
        p for p in INVALID_DIR.glob("*.furqan")
        if p.name != "unknown_field.furqan"
    )


# ---------------------------------------------------------------------------
# Sweep — every valid fixture passes; every checker-eligible invalid
# fixture produces at least one diagnostic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _all_valid(), ids=lambda p: p.name)
def test_every_valid_fixture_produces_zero_diagnostics(fixture: Path) -> None:
    module = _load(fixture)
    diagnostics = check_tanzil(module)
    assert diagnostics == [], (
        f"valid fixture {fixture.name} produced diagnostics: "
        f"{diagnostics}"
    )


@pytest.mark.parametrize(
    "fixture", _all_invalid_for_checker(), ids=lambda p: p.name,
)
def test_every_checker_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    module = _load(fixture)
    diagnostics = check_tanzil(module)
    assert diagnostics, (
        f"invalid fixture {fixture.name} produced zero diagnostics"
    )
    for d in diagnostics:
        assert d.primitive == PRIMITIVE_NAME


def test_each_directory_is_non_empty() -> None:
    assert _all_valid()
    assert _all_invalid_for_checker()


# ---------------------------------------------------------------------------
# Case T1 — Self-dependency (Marad)
# ---------------------------------------------------------------------------

def test_t1_self_dependency_emits_marad() -> None:
    fixture = INVALID_DIR / "self_dependency.furqan"
    diagnostics = check_tanzil(_load(fixture))
    marads = [d for d in diagnostics if isinstance(d, Marad)]
    assert len(marads) == 1
    d = marads[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case T1" in d.diagnosis
    assert "self-dependency" in d.diagnosis.lower()
    assert "Circular" in d.diagnosis  # the module name


def test_t1_does_not_fire_when_dependencies_are_distinct() -> None:
    fixture = VALID_DIR / "multiple_deps.furqan"
    diagnostics = check_tanzil(_load(fixture))
    assert all("Case T1" not in getattr(d, "diagnosis", "") for d in diagnostics)


def test_t1_marad_carries_correct_primitive_name() -> None:
    fixture = INVALID_DIR / "self_dependency.furqan"
    d = check_tanzil(_load(fixture))[0]
    assert d.primitive == "tanzil_well_formed"


def test_t1_inline_each_dependency_against_self() -> None:
    """For an inline-constructed module whose tanzil block lists
    its own bismillah name three times, T1 fires three times (once
    per occurrence). Confirms T1 is not gated on first-occurrence
    semantics."""
    src = """
    bismillah Self {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    tanzil triple_self {
        depends_on: Self
        depends_on: Self
        depends_on: Self
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_tanzil(module)
    t1 = [d for d in diagnostics if isinstance(d, Marad) and "Case T1" in d.diagnosis]
    # Every occurrence of `depends_on: Self` is a self-dependency.
    assert len(t1) == 3


# ---------------------------------------------------------------------------
# Case T2 — Duplicate dependency (Marad)
# ---------------------------------------------------------------------------

def test_t2_duplicate_emits_marad() -> None:
    fixture = INVALID_DIR / "duplicate_dependency.furqan"
    diagnostics = check_tanzil(_load(fixture))
    t2 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case T2" in d.diagnosis
    ]
    assert len(t2) == 1
    d = t2[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "CoreModule" in d.diagnosis


def test_t2_does_not_fire_on_distinct_paths() -> None:
    fixture = VALID_DIR / "multiple_deps.furqan"
    diagnostics = check_tanzil(_load(fixture))
    assert all(
        "Case T2" not in getattr(d, "diagnosis", "") for d in diagnostics
    )


def test_t2_fires_per_extra_occurrence() -> None:
    """If a dependency is declared three times, T2 fires twice
    (once per occurrence after the first). First-occurrence-wins
    semantics."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    tanzil triple_dup {
        depends_on: CoreModule
        depends_on: CoreModule
        depends_on: CoreModule
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_tanzil(module)
    t2 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case T2" in d.diagnosis
    ]
    assert len(t2) == 2


def test_t2_marad_carries_correct_primitive_name() -> None:
    fixture = INVALID_DIR / "duplicate_dependency.furqan"
    diagnostics = check_tanzil(_load(fixture))
    t2 = next(d for d in diagnostics if "Case T2" in d.diagnosis)
    assert t2.primitive == "tanzil_well_formed"


# ---------------------------------------------------------------------------
# Case T3 — Empty block (Advisory, not Marad)
# ---------------------------------------------------------------------------

def test_t3_empty_block_produces_advisory() -> None:
    fixture = INVALID_DIR / "empty_block.furqan"
    diagnostics = check_tanzil(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert isinstance(d, Advisory)
    assert d.primitive == PRIMITIVE_NAME
    assert "Case T3" in d.message
    assert "zero dependencies" in d.message


def test_t3_advisory_is_not_a_marad() -> None:
    """An Advisory is NOT a Marad. A Phase-3 multi-error reporter
    that filters by type must see them as distinct dataclasses."""
    fixture = INVALID_DIR / "empty_block.furqan"
    d = check_tanzil(_load(fixture))[0]
    assert not isinstance(d, Marad)
    assert isinstance(d, Advisory)


def test_t3_short_circuits_t1_and_t2() -> None:
    """An empty block triggers only T3 — T1 and T2 have nothing
    to inspect when there are zero entries. This pins that the
    short-circuit is real (T3 returns before the T1/T2 loops)."""
    fixture = INVALID_DIR / "empty_block.furqan"
    diagnostics = check_tanzil(_load(fixture))
    assert len(diagnostics) == 1
    assert isinstance(diagnostics[0], Advisory)


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_marad() -> None:
    fixture = INVALID_DIR / "self_dependency.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_tanzil_strict(module)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_does_not_raise_on_advisory_only() -> None:
    """An empty tanzil block produces an Advisory but no Marad.
    The strict variant must NOT raise — Advisories are
    informational, not failures."""
    fixture = INVALID_DIR / "empty_block.furqan"
    module = _load(fixture)
    returned = check_tanzil_strict(module)
    assert returned is module


def test_strict_variant_returns_module_on_pass() -> None:
    fixture = VALID_DIR / "single_module_no_deps.furqan"
    module = _load(fixture)
    returned = check_tanzil_strict(module)
    assert returned is module


# ---------------------------------------------------------------------------
# Marad rendering
# ---------------------------------------------------------------------------

def test_tanzil_marad_render_carries_primitive_tag_and_recovery() -> None:
    fixture = INVALID_DIR / "self_dependency.furqan"
    d = check_tanzil(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


def test_tanzil_advisory_render_carries_advisory_prefix() -> None:
    fixture = INVALID_DIR / "empty_block.furqan"
    d = check_tanzil(_load(fixture))[0]
    rendered = d.render()
    assert f"[advisory:{PRIMITIVE_NAME}]" in rendered
    assert "suggestion:" in rendered


# ---------------------------------------------------------------------------
# Cross-primitive non-interference
# ---------------------------------------------------------------------------

def test_module_with_no_tanzil_decls_passes_trivially() -> None:
    """A module declaring no tanzil blocks has nothing for the
    Tanzil checker to fire on. Pins that the checker is non-
    invasive on pre-2.8 surfaces."""
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
    assert check_tanzil(module) == []


def test_tanzil_and_mizan_check_independently() -> None:
    """A module declaring both a tanzil block and a mizan block
    has both checkers run on its AST without interference. The
    fixture exercises this composition; both checkers must report
    their own diagnostics independently."""
    fixture = VALID_DIR / "tanzil_with_types_and_functions.furqan"
    module = _load(fixture)
    from furqan.checker.mizan import check_mizan

    tanzil_diagnostics = check_tanzil(module)
    mizan_diagnostics = check_mizan(module)
    # The fixture is well-formed for both primitives.
    assert tanzil_diagnostics == []
    assert mizan_diagnostics == []


# ---------------------------------------------------------------------------
# Reflexivity audit (M3-equivalent for Tanzil)
# ---------------------------------------------------------------------------

def test_check_tanzil_module_has_no_unknown_field_branch() -> None:
    """Per Phase 2.8 routing rationale, T3-equivalent (unknown
    field head) is enforced at the parser layer; the checker has
    no business inspecting field-head names against the canonical
    set because by the time a TanzilDecl reaches the checker,
    every field head is canonical by construction.

    This test grep-audits the checker source to confirm no
    defensive `if field_name != "depends_on"` branch snuck in. If
    such a branch is added, this test fires; the branch is dead
    code per the routing rationale and should be removed.
    """
    import inspect
    from furqan.checker import tanzil as tanzil_module
    src = inspect.getsource(tanzil_module)
    # Filter to the function bodies (after the first `def`); the
    # module docstring legitimately discusses the M3-equivalent
    # routing in prose, which would false-fire a top-level grep.
    first_def = src.find("\ndef ")
    body_after_first_def = src[first_def:] if first_def != -1 else ""
    forbidden_patterns = [
        '!= "depends_on"',
        "!= 'depends_on'",
        "unknown field",
        "Unknown field",
        "not in",  # broad-stroke guard against dead defensive code
    ]
    for pat in forbidden_patterns:
        assert pat not in body_after_first_def, (
            f"checker function body contains forbidden pattern "
            f"{pat!r} — this is the dead defensive code the §6.4 "
            f"routing rationale forbids. Remove it."
        )
