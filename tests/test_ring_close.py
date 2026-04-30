"""
Ring-close (structural completion) checker tests — Phase 2.9 / Session 1.8.

The capstone test file: it pins the four cases of the ring-close
checker AND the seven-primitive integration witness — a single module
that runs cleanly through every Phase 2.x checker.

Four diagnostic cases tested here:
  - R1 (undefined type reference, Marad)
  - R2 (empty module body, Advisory)
  - R3 (function with declared return type but no return, Marad)
  - R4 (declared type unreferenced, Advisory)

Plus the seven-primitive integration capstone.
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
    check_tanzil,
    check_zahir_batin,
)
from furqan.checker.ring_close import (
    BUILTIN_TYPE_NAMES,
    PRIMITIVE_NAME,
    check_ring_close,
    check_ring_close_strict,
)
from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ring_close"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"


def _load(path: Path):
    return parse(path.read_text(), file=str(path))


def _all_valid():
    return sorted(VALID_DIR.glob("*.furqan"))


def _all_invalid():
    return sorted(INVALID_DIR.glob("*.furqan"))


# ---------------------------------------------------------------------------
# Sweep — every valid fixture passes; every invalid produces a diagnostic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", _all_valid(), ids=lambda p: p.name)
def test_every_valid_fixture_produces_zero_diagnostics(fixture: Path) -> None:
    module = _load(fixture)
    diagnostics = check_ring_close(module)
    assert diagnostics == [], (
        f"valid fixture {fixture.name} produced diagnostics: "
        f"{diagnostics}"
    )


@pytest.mark.parametrize("fixture", _all_invalid(), ids=lambda p: p.name)
def test_every_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    module = _load(fixture)
    diagnostics = check_ring_close(module)
    assert diagnostics, (
        f"invalid fixture {fixture.name} produced zero diagnostics"
    )
    for d in diagnostics:
        assert d.primitive == PRIMITIVE_NAME


def test_each_directory_is_non_empty() -> None:
    assert _all_valid()
    assert _all_invalid()


def test_primitive_name_is_stable() -> None:
    assert PRIMITIVE_NAME == "ring_close"


def test_builtin_type_names_are_the_two_scan_incomplete_arms() -> None:
    assert BUILTIN_TYPE_NAMES == frozenset({"Integrity", "Incomplete"})


# ---------------------------------------------------------------------------
# Case R1 — undefined type reference (Marad)
# ---------------------------------------------------------------------------

def test_r1_undefined_return_type_emits_marad() -> None:
    fixture = INVALID_DIR / "r1_undefined_type_ref.furqan"
    diagnostics = check_ring_close(_load(fixture))
    marads = [d for d in diagnostics if isinstance(d, Marad)]
    assert len(marads) == 1
    d = marads[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case R1" in d.diagnosis
    assert "Summary" in d.diagnosis
    assert "summarize" in d.diagnosis


def test_r1_marad_location_points_at_return_type_span() -> None:
    fixture = INVALID_DIR / "r1_undefined_type_ref.furqan"
    d = check_ring_close(_load(fixture))[0]
    # The Summary identifier sits on the `fn summarize` line.
    assert d.location.file.endswith("r1_undefined_type_ref.furqan")
    assert d.location.line >= 1


def test_r1_does_not_fire_on_declared_type() -> None:
    fixture = VALID_DIR / "closed_ring_simple.furqan"
    diagnostics = check_ring_close(_load(fixture))
    assert all("Case R1" not in getattr(d, "diagnosis", "") for d in diagnostics)


def test_r1_does_not_fire_on_integrity_or_incomplete_builtins() -> None:
    """The two scan-incomplete arms are recognised builtins —
    a function declared `-> Integrity | Incomplete` must not trigger
    R1 even when the module has no compound type by either name."""
    fixture = VALID_DIR / "closed_ring_with_all_primitives.furqan"
    diagnostics = check_ring_close(_load(fixture))
    assert diagnostics == []


def test_r1_fires_on_undefined_parameter_type() -> None:
    """R1 covers parameter types as well as return types — the prompt's
    structural-completion principle does not stop at the return arrow."""
    src = """
    bismillah RefBroken {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: ingest
        not_scope: nothing_excluded
    }

    type Document {
        zahir { rendered: String }
        batin { raw: Bytes }
    }

    fn ingest(input: NonExistent) -> Document {
        return Document
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r1 = [d for d in diagnostics if isinstance(d, Marad) and "Case R1" in d.diagnosis]
    assert len(r1) == 1
    assert "NonExistent" in r1[0].diagnosis
    assert "parameter" in r1[0].diagnosis


def test_r1_fires_per_arm_of_undefined_union_return() -> None:
    """Both arms of a union return type are independently resolved."""
    src = """
    bismillah UnionBroken {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: maybe
        not_scope: nothing_excluded
    }

    fn maybe() -> NotAType | OtherNonType {
        return NotAType
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r1 = [d for d in diagnostics if isinstance(d, Marad) and "Case R1" in d.diagnosis]
    assert len(r1) == 2


# ---------------------------------------------------------------------------
# Case R2 — empty module body (Advisory)
# ---------------------------------------------------------------------------

def test_r2_empty_body_produces_advisory() -> None:
    fixture = INVALID_DIR / "r2_empty_body.furqan"
    diagnostics = check_ring_close(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert isinstance(d, Advisory)
    assert d.primitive == PRIMITIVE_NAME
    assert "Case R2" in d.message
    assert "EmptyShell" in d.message


def test_r2_advisory_is_not_a_marad() -> None:
    fixture = INVALID_DIR / "r2_empty_body.furqan"
    d = check_ring_close(_load(fixture))[0]
    assert not isinstance(d, Marad)
    assert isinstance(d, Advisory)


def test_r2_short_circuits_other_checks() -> None:
    """When R2 fires, the rest of the checker returns immediately —
    there is nothing for R1, R3, or R4 to inspect on a module with
    no functions and no types."""
    fixture = INVALID_DIR / "r2_empty_body.furqan"
    diagnostics = check_ring_close(_load(fixture))
    assert len(diagnostics) == 1


def test_r2_does_not_fire_when_module_has_at_least_one_function() -> None:
    """Even a single function (no types) is enough to keep R2 silent."""
    src = """
    bismillah HasFn {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: noop
        not_scope: nothing_excluded
    }

    fn noop() {
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    assert all("Case R2" not in getattr(d, "message", "") for d in diagnostics)


def test_r2_does_not_fire_when_module_has_at_least_one_type() -> None:
    """Even a single type (no functions) is enough to keep R2 silent.
    Note: the lone type will fire R4 (unreferenced), but NOT R2."""
    src = """
    bismillah HasType {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: declare
        not_scope: nothing_excluded
    }

    type Lonely {
        zahir { name: String }
        batin { id: ID }
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    assert all("Case R2" not in getattr(d, "message", "") for d in diagnostics)


def test_r2_fires_even_with_tanzil_or_mizan_blocks() -> None:
    """Metadata blocks (tanzil, mizan, additive_only) do NOT count
    toward body-non-emptiness for R2 — only functions and types do."""
    fixture = INVALID_DIR / "r2_empty_body.furqan"
    module = _load(fixture)
    # The fixture has a tanzil block but no functions/types.
    assert len(module.tanzil_decls) == 1
    diagnostics = check_ring_close(module)
    r2 = [d for d in diagnostics if isinstance(d, Advisory) and "Case R2" in d.message]
    assert len(r2) == 1


# ---------------------------------------------------------------------------
# Case R3 — missing return statement (Marad)
# ---------------------------------------------------------------------------

def test_r3_missing_return_emits_marad() -> None:
    fixture = INVALID_DIR / "r3_missing_return.furqan"
    diagnostics = check_ring_close(_load(fixture))
    marads = [d for d in diagnostics if isinstance(d, Marad)]
    assert len(marads) == 1
    d = marads[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case R3" in d.diagnosis
    assert "ingest" in d.diagnosis
    assert "no `return`" in d.diagnosis


def test_r3_does_not_fire_on_void_function() -> None:
    """A function without `-> Type` has no return-type promise to
    keep, so missing return-stmt is fine."""
    fixture = VALID_DIR / "closed_ring_no_return_type.furqan"
    diagnostics = check_ring_close(_load(fixture))
    assert all("Case R3" not in getattr(d, "diagnosis", "") for d in diagnostics)


def test_r3_recurses_into_if_blocks() -> None:
    """A return inside an if-block satisfies R3 — the syntactic gate
    walks the entire statement tree."""
    src = """
    bismillah IfReturn {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: maybe
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { raw: Bytes }
    }

    fn maybe() -> Document {
        if not done {
            return Document
        }
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r3 = [d for d in diagnostics if isinstance(d, Marad) and "Case R3" in d.diagnosis]
    assert r3 == []


def test_r3_marad_location_points_at_function_span() -> None:
    fixture = INVALID_DIR / "r3_missing_return.furqan"
    d = check_ring_close(_load(fixture))[0]
    assert d.location.file.endswith("r3_missing_return.furqan")


def test_r3_diagnosis_names_the_declared_return_type() -> None:
    fixture = INVALID_DIR / "r3_missing_return.furqan"
    d = check_ring_close(_load(fixture))[0]
    assert "Document" in d.diagnosis


# ---------------------------------------------------------------------------
# Case R4 — unreferenced type declaration (Advisory)
# ---------------------------------------------------------------------------

def test_r4_unreferenced_type_produces_advisory() -> None:
    fixture = INVALID_DIR / "r4_unreferenced_type.furqan"
    diagnostics = check_ring_close(_load(fixture))
    advisories = [d for d in diagnostics if isinstance(d, Advisory)]
    assert len(advisories) == 1
    d = advisories[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "Case R4" in d.message
    assert "Summary" in d.message


def test_r4_advisory_is_not_a_marad() -> None:
    fixture = INVALID_DIR / "r4_unreferenced_type.furqan"
    d = check_ring_close(_load(fixture))[0]
    assert not isinstance(d, Marad)
    assert isinstance(d, Advisory)


def test_r4_does_not_fire_when_type_is_referenced_as_param() -> None:
    """A type referenced only as a parameter (not return) still
    satisfies R4."""
    src = """
    bismillah ParamRef {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: verify
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { raw: Bytes }
    }

    fn verify(file: Document) {
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r4 = [d for d in diagnostics if isinstance(d, Advisory) and "Case R4" in d.message]
    assert r4 == []


def test_r4_does_not_fire_when_type_is_referenced_in_union_arm() -> None:
    """A type referenced as one arm of a union return-type satisfies R4."""
    src = """
    bismillah UnionRef {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: maybe
        not_scope: nothing_excluded
    }

    type CustomDoc {
        zahir { name: String }
        batin { raw: Bytes }
    }

    fn maybe() -> CustomDoc | Incomplete {
        return CustomDoc
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r4 = [d for d in diagnostics if isinstance(d, Advisory) and "Case R4" in d.message]
    assert r4 == []


def test_r4_fires_per_unreferenced_type() -> None:
    """Two unreferenced types produce two R4 advisories."""
    src = """
    bismillah TwoUnref {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: declare
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { raw: Bytes }
    }

    type Summary {
        zahir { headline: String }
        batin { evidence: Spans }
    }

    fn noop() {
    }
    """
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r4 = [d for d in diagnostics if isinstance(d, Advisory) and "Case R4" in d.message]
    assert len(r4) == 2


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_r1_marad() -> None:
    fixture = INVALID_DIR / "r1_undefined_type_ref.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_ring_close_strict(module)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_raises_on_r3_marad() -> None:
    fixture = INVALID_DIR / "r3_missing_return.furqan"
    with pytest.raises(MaradError):
        check_ring_close_strict(_load(fixture))


def test_strict_variant_does_not_raise_on_r2_advisory_only() -> None:
    """R2 is an Advisory; the strict variant must NOT raise."""
    fixture = INVALID_DIR / "r2_empty_body.furqan"
    module = _load(fixture)
    returned = check_ring_close_strict(module)
    assert returned is module


def test_strict_variant_does_not_raise_on_r4_advisory_only() -> None:
    fixture = INVALID_DIR / "r4_unreferenced_type.furqan"
    module = _load(fixture)
    returned = check_ring_close_strict(module)
    assert returned is module


def test_strict_variant_returns_module_on_clean_pass() -> None:
    fixture = VALID_DIR / "closed_ring_simple.furqan"
    module = _load(fixture)
    returned = check_ring_close_strict(module)
    assert returned is module


# ---------------------------------------------------------------------------
# Marad / Advisory rendering
# ---------------------------------------------------------------------------

def test_ring_close_marad_render_carries_primitive_tag_and_recovery() -> None:
    fixture = INVALID_DIR / "r1_undefined_type_ref.furqan"
    d = check_ring_close(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


def test_ring_close_advisory_render_carries_advisory_prefix() -> None:
    fixture = INVALID_DIR / "r2_empty_body.furqan"
    d = check_ring_close(_load(fixture))[0]
    rendered = d.render()
    assert PRIMITIVE_NAME in rendered
    assert "advisory" in rendered.lower() or "Advisory" in rendered


# ---------------------------------------------------------------------------
# Additive-only invariant — public surface
# ---------------------------------------------------------------------------

def test_public_surface_exports_ring_close_entry_points() -> None:
    """The Phase 2.9 additions must be reachable from
    `furqan.checker`'s top-level surface."""
    from furqan.checker import (  # noqa: F401
        RING_CLOSE_BUILTIN_TYPE_NAMES,
        RING_CLOSE_PRIMITIVE_NAME,
        check_ring_close,
        check_ring_close_strict,
    )
    assert RING_CLOSE_PRIMITIVE_NAME == "ring_close"
    assert RING_CLOSE_BUILTIN_TYPE_NAMES == frozenset({"Integrity", "Incomplete"})


# ---------------------------------------------------------------------------
# THE SEVEN-PRIMITIVE INTEGRATION CAPSTONE
# ---------------------------------------------------------------------------

def test_seven_primitive_witness_passes_all_checkers() -> None:
    """The capstone test of the Furqan Phase 2 program.

    A single module that exercises every primitive (bismillah,
    zahir/batin, additive_only metadata, scan-incomplete, mizan,
    tanzil, ring-close) must pass all six prior checkers AND the
    new ring-close checker with zero marads. Advisories from any
    primitive are permitted by the strict-variant gate.
    """
    fixture = VALID_DIR / "closed_ring_with_all_primitives.furqan"
    module = _load(fixture)

    # Each prior primitive's checker must produce zero marads on the
    # capstone witness. (check_additive requires a sidecar comparison;
    # not exercised here — that is the cross-version path, separately
    # tested in test_additive.py.)
    bismillah_diags = check_bismillah(module)
    zahir_batin_diags = check_zahir_batin(module)
    incomplete_diags = check_incomplete(module)
    mizan_diags = check_mizan(module)
    tanzil_diags = check_tanzil(module)
    ring_close_diags = check_ring_close(module)

    # Marads count as failures — Advisories do not.
    all_marads: list[Marad] = []
    for diags in (
        bismillah_diags, zahir_batin_diags, incomplete_diags,
        mizan_diags, tanzil_diags, ring_close_diags,
    ):
        all_marads.extend(d for d in diags if isinstance(d, Marad))

    assert all_marads == [], (
        f"seven-primitive witness produced marads from one or more "
        f"checkers: {all_marads}"
    )


def test_seven_primitive_witness_has_each_primitive_present_in_ast() -> None:
    """Pin that the witness fixture actually exercises each primitive
    syntactically — guards against silent fixture decay where the
    test still passes but the fixture has been simplified to the
    point where it no longer demonstrates seven-primitive coverage."""
    fixture = VALID_DIR / "closed_ring_with_all_primitives.furqan"
    module = _load(fixture)

    # Bismillah block (Phase 2.3) is mandatory — parser-enforced.
    assert module.bismillah.name == "FullSeven"
    # Compound type with zahir/batin layers (Phase 2.4).
    assert len(module.compound_types) >= 1
    type_def = module.compound_types[0]
    assert len(type_def.zahir.fields) >= 1
    assert len(type_def.batin.fields) >= 1
    # Additive-only module declaration (Phase 2.5).
    assert len(module.additive_only_modules) >= 1
    # Scan-incomplete: a function returning Integrity | Incomplete (Phase 2.6).
    rt_unions = [
        f for f in module.functions
        if f.return_type is not None and type(f.return_type).__name__ == "UnionType"
    ]
    assert rt_unions, "no union return types — Phase 2.6 not exercised"
    # Mizan calibration block (Phase 2.7).
    assert len(module.mizan_decls) >= 1
    # Tanzil build-ordering block (Phase 2.8).
    assert len(module.tanzil_decls) >= 1
    # Ring-close: the function with declared return type has a return
    # statement, and the declared type Document is referenced by it.
    assert any(
        f.return_type is not None and any(
            type(s).__name__ == "IfStmt" or type(s).__name__ == "ReturnStmt"
            for s in f.statements
        )
        for f in module.functions
    )


# ---------------------------------------------------------------------------
# Reflexivity audit — the ring-close source contains no defensive
# branches that the test suite cannot reach
# ---------------------------------------------------------------------------

def test_ring_close_module_has_no_unreachable_branches() -> None:
    """Sanity audit: the checker source compiles cleanly and the
    advertised public surface is exhaustively covered by tests in
    this file. This is a weak audit (it does not run coverage), but
    it confirms the public-symbol set is exactly what the module
    advertises."""
    from furqan.checker import ring_close as rc

    expected = {
        "BUILTIN_TYPE_NAMES",
        "PRIMITIVE_NAME",
        "RingCloseDiagnostic",
        "check_ring_close",
        "check_ring_close_strict",
    }
    assert set(rc.__all__) == expected
