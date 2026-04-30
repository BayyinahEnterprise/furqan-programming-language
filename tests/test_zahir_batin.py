"""
Zahir/batin type-checker tests (Phase 2.4 / Session 1.3).

The checker's contract from the Furqan thesis paper §3.2:

    A function whose parameter is declared as ``Type.zahir`` may
    only access that parameter's zahir layer. A ``Type.batin``
    parameter is the symmetric dual. Only a function named
    ``verify`` may take an unqualified compound-type parameter
    (the cross-layer construct).

The tests below pair each property with concrete .furqan fixtures
under ``tests/fixtures/zahir_batin/{valid,invalid}/``. The
fixture-driven sweeps are the empirical surface — adding a new
fixture to either directory automatically extends coverage. The
named-property tests below them pin specific behaviours (per-case
diagnostic content, verify-name discipline, AST extraction
correctness) that the sweep alone would not guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.zahir_batin import (
    PRIMITIVE_NAME,
    VERIFY_FUNCTION_NAME,
    check_module,
    check_module_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "zahir_batin"
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
    diagnostics = check_module(module)
    assert diagnostics == [], (
        f"valid fixture {fixture.name} produced diagnostics: "
        f"{[d.diagnosis for d in diagnostics]}"
    )


@pytest.mark.parametrize("fixture", _all(INVALID_DIR), ids=lambda p: p.name)
def test_every_invalid_fixture_produces_at_least_one_diagnostic(
    fixture: Path,
) -> None:
    module = _load(fixture)
    diagnostics = check_module(module)
    assert diagnostics, (
        f"invalid fixture {fixture.name} produced zero diagnostics — "
        f"the zahir/batin checker silently accepted a structural "
        f"violation. That is the M1 failure mode the language is "
        f"built to prevent."
    )


def test_each_directory_is_non_empty() -> None:
    """The valid/ and invalid/ subdirectories must each contain at
    least one fixture, otherwise the sweep above is silently vacuous
    (a Process-2 risk in the test surface itself)."""
    assert _all(VALID_DIR), "tests/fixtures/zahir_batin/valid/ is empty"
    assert _all(INVALID_DIR), "tests/fixtures/zahir_batin/invalid/ is empty"


# ---------------------------------------------------------------------------
# Case 1 — zahir-typed function reads a batin field
# ---------------------------------------------------------------------------

def test_case_1_zahir_function_reading_batin_emits_marad() -> None:
    fixture = INVALID_DIR / "zahir_reads_batin.furqan"
    diagnostics = check_module(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert isinstance(d, Marad)
    assert d.primitive == PRIMITIVE_NAME
    # The diagnosis names the function, the parameter, and the rule
    # by case number for cross-reference with the thesis paper.
    assert "display" in d.diagnosis
    assert "doc" in d.diagnosis
    assert "Case 1" in d.diagnosis
    assert "zahir" in d.diagnosis
    assert "batin" in d.diagnosis


def test_case_1_diagnostic_location_is_the_offending_access() -> None:
    fixture = INVALID_DIR / "zahir_reads_batin.furqan"
    d = check_module(_load(fixture))[0]
    src_lines = fixture.read_text().splitlines()
    line_text = src_lines[d.location.line - 1]
    assert "doc.batin" in line_text


# ---------------------------------------------------------------------------
# Case 2 — batin-typed function reads a zahir field
# ---------------------------------------------------------------------------

def test_case_2_batin_function_reading_zahir_emits_marad() -> None:
    fixture = INVALID_DIR / "batin_reads_zahir.furqan"
    diagnostics = check_module(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "extract" in d.diagnosis
    assert "Case 2" in d.diagnosis


def test_case_2_diagnostic_names_both_layers_correctly() -> None:
    fixture = INVALID_DIR / "batin_reads_zahir.furqan"
    d = check_module(_load(fixture))[0]
    # The diagnosis should mention 'batin' as the declared layer and
    # 'zahir' as the accessed layer.
    declared_idx = d.diagnosis.find("layer 'batin'")
    accessed_idx = d.diagnosis.find("'zahir' layer")
    assert declared_idx != -1, "declared batin layer not named"
    assert accessed_idx != -1, "accessed zahir layer not named"


# ---------------------------------------------------------------------------
# Case 3 — non-verify function with an unqualified compound-type param
# ---------------------------------------------------------------------------

def test_case_3_non_verify_unqualified_param_emits_marad() -> None:
    fixture = INVALID_DIR / "non_verify_unqualified_param.furqan"
    diagnostics = check_module(_load(fixture))
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert d.primitive == PRIMITIVE_NAME
    assert "display" in d.diagnosis
    assert VERIFY_FUNCTION_NAME in d.diagnosis
    assert "Case 3" in d.diagnosis
    # The marad's location should point at the parameter declaration,
    # not the body access.
    src_lines = fixture.read_text().splitlines()
    line_text = src_lines[d.location.line - 1]
    assert "fn display(doc:" in line_text


def test_case_3_does_not_double_fire_on_body_access() -> None:
    """Per the checker's design, a Case 3 violation suppresses
    body-access diagnostics for the offending parameter — the
    parameter's declared layer is ``None`` (unqualified), so there
    is no single layer to compare against. The marad reports the
    parameter declaration only, not also a Case 1/2 marad on the
    body access."""
    fixture = INVALID_DIR / "non_verify_unqualified_param.furqan"
    diagnostics = check_module(_load(fixture))
    assert len(diagnostics) == 1, (
        f"Case 3 fixture should produce exactly 1 diagnostic; "
        f"got {len(diagnostics)}"
    )


# ---------------------------------------------------------------------------
# Verify discipline — verify is the only function permitted both layers
# ---------------------------------------------------------------------------

def test_verify_function_with_unqualified_param_passes() -> None:
    fixture = VALID_DIR / "verify_reads_both.furqan"
    diagnostics = check_module(_load(fixture))
    assert diagnostics == []


def test_verify_function_reading_only_one_layer_still_passes() -> None:
    """Verify may access either layer or both. Reading only one is
    permitted — the verify discipline is about *being allowed to*
    cross layers, not about being required to."""
    fixture = VALID_DIR / "verify_reads_one.furqan"
    diagnostics = check_module(_load(fixture))
    assert diagnostics == []


def test_verify_is_the_canonical_function_name() -> None:
    """The checker compares fn.name against the literal string
    ``verify`` (NAMING.md §1.5). This test pins that constant so
    a future rename is a structural decision, not a typo."""
    assert VERIFY_FUNCTION_NAME == "verify"


# ---------------------------------------------------------------------------
# Document compound type parses cleanly with no functions
# ---------------------------------------------------------------------------

def test_compound_type_only_module_passes_trivially() -> None:
    fixture = VALID_DIR / "document_compound.furqan"
    module = _load(fixture)
    assert module.compound_types, "compound type def did not parse"
    assert module.compound_types[0].name == "Document"
    assert module.compound_types[0].zahir.layer == "zahir"
    assert module.compound_types[0].batin.layer == "batin"
    assert check_module(module) == []


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_a_violation() -> None:
    fixture = INVALID_DIR / "zahir_reads_batin.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_module_strict(module)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_accepts_a_clean_module_silently() -> None:
    fixture = VALID_DIR / "verify_reads_both.furqan"
    assert check_module_strict(_load(fixture)) is None


# ---------------------------------------------------------------------------
# Marad rendering — primitive tag and required fields
# ---------------------------------------------------------------------------

def test_marad_render_includes_primitive_tag_and_recovery_advice() -> None:
    fixture = INVALID_DIR / "zahir_reads_batin.furqan"
    d = check_module(_load(fixture))[0]
    rendered = d.render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered


# ---------------------------------------------------------------------------
# AST extraction — pre-scan correctness (the checker depends on this)
# ---------------------------------------------------------------------------

def test_layer_access_pre_scan_extracts_both_zahir_and_batin() -> None:
    """The verify_reads_both fixture's body is
    ``compare(doc.zahir, doc.batin)``. The pre-scan must extract
    BOTH accesses; if it extracted only the first, the checker would
    falsely accept a verify body that only reads one layer when the
    fixture actually reads both."""
    fixture = VALID_DIR / "verify_reads_both.furqan"
    module = _load(fixture)
    fn = module.functions[0]
    layers = sorted(a.layer for a in fn.accesses)
    assert layers == ["batin", "zahir"]


def test_english_alias_in_body_access_is_normalised() -> None:
    """A body that uses the English alias ``surface`` instead of
    ``zahir`` must produce a LayerAccess whose canonical layer is
    ``zahir`` (NAMING.md §1.6). The alias is preserved on
    layer_alias_used for diagnostic quoting."""
    src = """
    bismillah AliasInBody {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_excluded
    }

    type Document {
        zahir { rendered_text: String }
        batin { raw_bytes: Bytes }
    }

    fn verify(doc: Document) {
        check(doc.surface)
    }
    """
    module = parse(src, file="<inline>")
    fn = module.functions[0]
    assert len(fn.accesses) == 1
    access = fn.accesses[0]
    assert access.layer == "zahir"
    assert access.layer_alias_used == "surface"
    # And the checker treats it as zahir for rule purposes.
    assert check_module(module) == []
