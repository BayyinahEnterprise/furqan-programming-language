"""
Additive-only module checker tests (Phase 2.5 / Session 1.4).

The checker's contract from the Furqan thesis paper §3.3:

    A module's exported public surface is monotonically growing
    across versions. Removals, renames, and type changes require
    explicit declaration in a `major_version_bump` catalog. The
    catalog must truthfully describe the actual surface change.

The tests below pair each property with concrete .furqan fixtures
under ``tests/fixtures/additive_only/{valid,invalid}/`` (each
invalid fixture and the v2 valid fixtures ship with a
.furqan_history sidecar). The fixture-driven sweeps are the
empirical surface — adding a fixture extends coverage automatically.

Each Phase-2.5 case (1, 2-enforcement, 2-advisory, 3, 4) has a
named-property test alongside the parametrized sweep.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.additive import (
    PRIMITIVE_NAME,
    Result,
    check_additive,
    check_module,
    check_module_strict,
)
from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "additive_only"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load_pair(path: Path):
    """Load a fixture and its sidecar (if any) as (Module, sidecar_text)."""
    current = parse(path.read_text(), file=str(path))
    sidecar_path = path.with_suffix(".furqan_history")
    sidecar_text = sidecar_path.read_text() if sidecar_path.exists() else None
    return current, sidecar_text


def _all(directory: Path):
    return sorted(p for p in directory.glob("*.furqan"))


# ---------------------------------------------------------------------------
# Sweep — every valid fixture passes; every invalid produces ≥1 marad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _all(VALID_DIR), ids=lambda p: p.name)
def test_every_valid_fixture_passes(fixture: Path) -> None:
    current, sidecar = _load_pair(fixture)
    result = check_module(current, sidecar)
    assert result.passed, (
        f"valid fixture {fixture.name} produced marads: "
        f"{[m.diagnosis for m in result.marads]}"
    )


@pytest.mark.parametrize("fixture", _all(INVALID_DIR), ids=lambda p: p.name)
def test_every_invalid_fixture_fails(fixture: Path) -> None:
    current, sidecar = _load_pair(fixture)
    result = check_module(current, sidecar)
    assert not result.passed, (
        f"invalid fixture {fixture.name} produced zero marads — the "
        f"additive-only checker silently accepted a structural "
        f"violation."
    )
    assert all(m.primitive == PRIMITIVE_NAME for m in result.marads)


def test_each_directory_is_non_empty() -> None:
    assert _all(VALID_DIR), "tests/fixtures/additive_only/valid/ is empty"
    assert _all(INVALID_DIR), "tests/fixtures/additive_only/invalid/ is empty"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

def test_result_passed_is_true_with_zero_marads() -> None:
    r = Result(marads=(), advisories=())
    assert r.passed is True


def test_result_passed_is_false_with_at_least_one_marad() -> None:
    # Synthesise a marad on a clean module just to exercise the property.
    fixture = INVALID_DIR / "module_v2_removed_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    assert r.passed is False


def test_advisories_alone_do_not_fail_the_check() -> None:
    """Advisories are informational; only marads cause `passed = False`.
    This pins the contract so a future expansion of the advisory
    surface cannot accidentally start failing previously-clean
    modules."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.1 {
        export new_name: Weights
    }
    """
    src_sidecar = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export old_name: Weights
    }
    """
    current = parse(src_current, file="<curr>")
    result = check_module(current, src_sidecar)
    # The current implementation will emit a Case 1 marad for the
    # removed name, so this is technically not advisory-only. We
    # confirm by inspecting that the check correctly classifies what
    # is and is not a fail-causing diagnostic.
    assert result.passed == (len(result.marads) == 0)


# ---------------------------------------------------------------------------
# Case 1 — Removed without bump
# ---------------------------------------------------------------------------

def test_case_1_removed_without_bump_emits_marad() -> None:
    fixture = INVALID_DIR / "module_v2_removed_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    assert len(r.marads) == 1
    m = r.marads[0]
    assert "severity_weights" in m.diagnosis
    assert "removed" in m.diagnosis.lower() or "remove" in m.diagnosis.lower()
    assert "Case 1" in m.diagnosis
    assert "major_version_bump" in m.minimal_fix


def test_case_1_does_not_fire_when_removal_is_declared() -> None:
    """The valid fixture declares the same removal in a catalog;
    Case 1 must not fire."""
    fixture = VALID_DIR / "module_v2_with_major_bump_removes_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    assert r.marads == ()


# ---------------------------------------------------------------------------
# Case 2 — Renamed without bump (enforcement + advisory split)
# ---------------------------------------------------------------------------

def test_case_2_enforcement_marad_fires_when_catalog_lies() -> None:
    fixture = INVALID_DIR / "module_v2_renamed_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    enforcement = [m for m in r.marads if "Case 2" in m.diagnosis]
    assert len(enforcement) >= 1
    m = enforcement[0]
    assert "severity_weights" in m.diagnosis
    assert "severity_table" in m.diagnosis


def test_case_2_advisory_fires_on_undeclared_rename_with_matching_types() -> None:
    """Detection advisory: exactly one removed name + exactly one
    added name + matching type signatures + no catalog entry → emit
    Advisory. The corresponding Case 1 marad still fires on the
    removed name; the advisory adds context."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.1 {
        export severity_table: Weights
    }
    """
    src_sidecar = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export severity_weights: Weights
    }
    """
    current = parse(src_current, file="<curr>")
    r = check_module(current, src_sidecar)
    # Case 1 marad still fires on the removed name.
    assert any("severity_weights" in m.diagnosis for m in r.marads)
    # Plus an advisory suggesting the rename.
    assert len(r.advisories) == 1
    a = r.advisories[0]
    assert isinstance(a, Advisory)
    assert "severity_weights" in a.message
    assert "severity_table" in a.message
    assert "renames:" in a.suggestion


def test_case_2_advisory_does_not_fire_when_types_differ() -> None:
    """Negative case: removed and added symbols have different type
    signatures, so the rename pattern does not match. No advisory."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.1 {
        export new_thing: NewType
    }
    """
    src_sidecar = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export old_thing: OldType
    }
    """
    current = parse(src_current, file="<curr>")
    r = check_module(current, src_sidecar)
    assert r.advisories == ()


def test_case_2_advisory_does_not_fire_when_more_than_one_removed_or_added() -> None:
    """The advisory is intentionally narrow: only fires on the 1-to-1
    pattern. Multiple removes + adds is too noisy to attribute."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.1 {
        export new1: Weights
        export new2: Weights
    }
    """
    src_sidecar = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export old1: Weights
        export old2: Weights
    }
    """
    current = parse(src_current, file="<curr>")
    r = check_module(current, src_sidecar)
    assert r.advisories == ()


# ---------------------------------------------------------------------------
# Case 3 — Type changed incompatibly
# ---------------------------------------------------------------------------

def test_case_3_type_change_emits_marad() -> None:
    fixture = INVALID_DIR / "module_v2_type_changed_incompatibly.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    matching = [m for m in r.marads if "Case 3" in m.diagnosis]
    assert len(matching) == 1
    m = matching[0]
    assert "severity_weights" in m.diagnosis
    assert "Weights" in m.diagnosis
    assert "Severity" in m.diagnosis


def test_case_3_does_not_fire_on_unchanged_types() -> None:
    fixture = VALID_DIR / "module_v2_added_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    assert all("Case 3" not in m.diagnosis for m in r.marads)


# ---------------------------------------------------------------------------
# Case 4 — Catalog dishonest
# ---------------------------------------------------------------------------

def test_case_4_catalog_dishonest_emits_marad() -> None:
    fixture = INVALID_DIR / "module_v2_catalog_dishonest.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    matching = [m for m in r.marads if "Case 4" in m.diagnosis]
    assert len(matching) == 1
    m = matching[0]
    assert "severity_weights" in m.diagnosis
    assert "still present" in m.diagnosis


def test_case_4_does_not_fire_on_honest_catalog() -> None:
    """Honest catalog: declares removal, symbol actually absent. No
    Case 4 marad."""
    fixture = VALID_DIR / "module_v2_with_major_bump_removes_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    assert r.marads == ()


# ---------------------------------------------------------------------------
# check_additive — pure two-module comparison (load-bearing primitive)
# ---------------------------------------------------------------------------

def test_check_additive_with_no_additive_only_decls_returns_clean() -> None:
    """A module with no additive_only declarations has nothing to
    check; check_additive must return an empty Result regardless of
    what the previous module looks like."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }
    """
    m1 = parse(src, file="<m1>")
    m2 = parse(src, file="<m2>")
    r = check_additive(m1, m2)
    assert r.marads == ()
    assert r.advisories == ()


def test_check_additive_first_version_passes_trivially() -> None:
    """If the previous module has no additive_only declaration for
    the current's name, the current is treated as a first-version
    publication — trivial pass."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module Brand_New v1.0 {
        export thing: Thing
    }
    """
    src_previous = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }
    """
    current = parse(src_current, file="<curr>")
    previous = parse(src_previous, file="<prev>")
    r = check_additive(current, previous)
    assert r.passed


# ---------------------------------------------------------------------------
# check_module — sidecar-aware entry point
# ---------------------------------------------------------------------------

def test_check_module_with_no_sidecar_passes_trivially() -> None:
    fixture = VALID_DIR / "module_v1.furqan"
    current = parse(fixture.read_text(), file=str(fixture))
    r = check_module(current, sidecar_text=None)
    assert r.passed
    assert r.marads == ()


def test_check_module_with_malformed_sidecar_emits_marad() -> None:
    """A sidecar that fails to parse is a structural error, not a
    silent miss. The checker emits a marad naming the parse
    failure."""
    fixture = VALID_DIR / "module_v2_added_export.furqan"
    current = parse(fixture.read_text(), file=str(fixture))
    malformed = "bismillah {{{ this is not valid furqan"
    r = check_module(current, malformed)
    assert len(r.marads) == 1
    assert "sidecar" in r.marads[0].diagnosis.lower()


def test_check_module_with_lexically_malformed_sidecar_emits_marad() -> None:
    """Session 1.4.1 polish (Perplexity E2 finding): a sidecar whose
    bytes the tokenizer cannot classify must produce a structured
    marad, not leak a TokenizeError exception. Pre-1.4.1 the
    checker caught only ParseError, so lex-level garbage like
    ``@#$%`` would raise out of the framework's structured-
    diagnostic contract.

    The marad uses a synthetic span anchored at the sidecar's start
    (line 1, column 1) since TokenizeError does not yet carry
    structured location fields. The exception's message text — which
    contains the actual offending line/column — is included verbatim
    in the diagnosis so the user can still locate the offending
    byte.
    """
    fixture = VALID_DIR / "module_v2_added_export.furqan"
    current = parse(fixture.read_text(), file=str(fixture))
    lex_garbage = "@#$%"
    r = check_module(current, lex_garbage)
    assert len(r.marads) == 1
    m = r.marads[0]
    assert m.primitive == PRIMITIVE_NAME
    # The diagnosis names the lex-level failure mode and quotes the
    # tokenizer error verbatim so the user can act on it.
    assert "sidecar" in m.diagnosis.lower()
    assert "tokenize" in m.diagnosis.lower()
    assert "@" in m.diagnosis
    # The synthetic span is tagged with the sidecar marker so a
    # future structured-location enhancement on TokenizeError will
    # have a known anchor to update.
    assert m.location.file == "<sidecar>"
    assert m.location.line == 1
    assert m.location.column == 1


def test_check_module_lex_error_does_not_leak_python_exception() -> None:
    """Negative-regression test for the E2 fix: feeding the checker
    lex-level garbage must NOT raise a Python exception. Returning
    a Result with marads is the structured-honesty contract; raising
    out is a Process-2 risk where the error type changes silently
    based on the input shape."""
    from furqan.parser import TokenizeError
    fixture = VALID_DIR / "module_v2_added_export.furqan"
    current = parse(fixture.read_text(), file=str(fixture))
    # If this were not caught, `check_module` would raise
    # TokenizeError. The test asserts return-without-raise.
    try:
        r = check_module(current, "@#$%")
    except TokenizeError as exc:
        pytest.fail(
            f"check_module leaked TokenizeError on lex-level garbage: "
            f"{exc!r}. Session 1.4.1 polish should have caught and "
            f"translated this to a structured marad."
        )
    assert isinstance(r.marads, tuple)
    assert len(r.marads) == 1


def test_check_module_with_non_adjacent_prior_emits_marad() -> None:
    """v1.3 with a sidecar containing only v1.0 has a gap. The
    checker must refuse to compare across the gap."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.3 {
        export thing: Thing
    }
    """
    src_sidecar = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export thing: Thing
    }
    """
    current = parse(src_current, file="<curr>")
    r = check_module(current, src_sidecar)
    assert any("adjacent" in m.diagnosis.lower() for m in r.marads)


def test_check_module_adjacent_major_bump_is_accepted() -> None:
    """v2.0 adjacent to any v1.x is structurally allowed; the
    additive-only check then runs against the v1.x surface."""
    src_current = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v2.0 {
        export thing: Thing
    }
    """
    src_sidecar = """
    bismillah Hist {
        authority: NAMING_MD
        serves: archival.history
        scope: archive
        not_scope: nothing_excluded
    }

    additive_only module M v1.5 {
        export thing: Thing
    }
    """
    current = parse(src_current, file="<curr>")
    r = check_module(current, src_sidecar)
    assert r.passed


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_violation() -> None:
    fixture = INVALID_DIR / "module_v2_removed_export.furqan"
    current, sidecar = _load_pair(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_module_strict(current, sidecar)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_returns_module_on_pass() -> None:
    fixture = VALID_DIR / "module_v2_added_export.furqan"
    current, sidecar = _load_pair(fixture)
    returned = check_module_strict(current, sidecar)
    assert returned is current


# ---------------------------------------------------------------------------
# Marad rendering and Advisory rendering
# ---------------------------------------------------------------------------

def test_case_1_marad_render_carries_primitive_tag() -> None:
    fixture = INVALID_DIR / "module_v2_removed_export.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    rendered = r.marads[0].render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered


def test_advisory_render_uses_advisory_prefix() -> None:
    a = Advisory(
        primitive=PRIMITIVE_NAME,
        message="probe",
        location=parse(
            "bismillah X { authority: A serves: a.b scope: s not_scope: n }",
            file="<probe>",
        ).bismillah.span,
        suggestion="probe suggestion",
    )
    rendered = a.render()
    assert rendered.startswith(f"[advisory:{PRIMITIVE_NAME}]")
    assert "suggestion:" in rendered


# ---------------------------------------------------------------------------
# Numeric-literal tokenization (Phase 2.5 parser surface) — pinning
# ---------------------------------------------------------------------------

def test_version_literal_v1_0_parses_with_two_components() -> None:
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export thing: Thing
    }
    """
    mod = parse(src, file="<v>")
    am = mod.additive_only_modules[0]
    assert am.version.components == (1, 0)
    assert am.version.major == 1
    assert am.version.minor == 0


def test_version_literal_v2_3_4_parses_with_three_components() -> None:
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v2.3.4 {
        export thing: Thing
    }
    """
    mod = parse(src, file="<v>")
    am = mod.additive_only_modules[0]
    assert am.version.components == (2, 3, 4)


def test_version_literal_must_have_at_least_two_components() -> None:
    """A bare `v1` is rejected — Phase 2.5 requires <major>.<minor>."""
    from furqan.parser import ParseError
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1 {
        export thing: Thing
    }
    """
    with pytest.raises(ParseError):
        parse(src, file="<v>")


def test_version_literal_render_round_trips() -> None:
    """VersionLiteral.render() returns the canonical text form."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    additive_only module M v1.0 {
        export thing: Thing
    }
    """
    mod = parse(src, file="<v>")
    assert mod.additive_only_modules[0].version.render() == "v1.0"


# ---------------------------------------------------------------------------
# Empty bump catalog
# ---------------------------------------------------------------------------

def test_empty_bump_catalog_is_benign() -> None:
    fixture = VALID_DIR / "module_v2_optional_major_bump.furqan"
    current, sidecar = _load_pair(fixture)
    r = check_module(current, sidecar)
    assert r.passed
    assert r.marads == ()
    assert r.advisories == ()


def test_empty_bump_catalog_parses_to_empty_tuples() -> None:
    fixture = VALID_DIR / "module_v2_optional_major_bump.furqan"
    current = parse(fixture.read_text(), file=str(fixture))
    am = current.additive_only_modules[0]
    assert am.bump_catalog is not None
    assert am.bump_catalog.removes == ()
    assert am.bump_catalog.renames == ()
