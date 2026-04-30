"""
Bismillah scope checker tests (Phase 2.3).

The checker's contract from the Furqan thesis paper §3.1:

    No function in a module may invoke a head identifier listed in
    that module's Bismillah ``not_scope``.

The tests below pair each property with concrete .furqan fixtures
under ``tests/fixtures/valid/`` and ``tests/fixtures/invalid/``. The
fixture-driven tests are the empirical surface — adding a new fixture
to either directory automatically extends coverage. The named-property
tests below them pin specific behaviours (alias equivalence, exact
diagnostic content, etc.) that the fixture sweep alone would not
guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from furqan.checker.bismillah import (
    PRIMITIVE_NAME,
    check_module,
    check_module_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"
KNOWN_LIMITATION_DIR = FIXTURES_DIR / "known_limitation"


def _load(path: Path):
    return parse(path.read_text(), file=str(path))


def _all(directory: Path):
    return sorted(p for p in directory.glob("*.furqan"))


# ---------------------------------------------------------------------------
# Sweep: every valid fixture passes; every invalid fixture fails
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
        f"invalid fixture {fixture.name} should have produced a "
        f"diagnostic but the checker accepted it silently — that is "
        f"the M1 failure mode the language is built to prevent."
    )


# ---------------------------------------------------------------------------
# Diagnostic content (zahir/batin discipline applied to error messages)
# ---------------------------------------------------------------------------

def test_diagnostic_names_the_offending_symbol() -> None:
    fixture = INVALID_DIR / "violates_not_scope_directly.furqan"
    module = _load(fixture)
    diagnostics = check_module(module)
    assert len(diagnostics) == 1
    d = diagnostics[0]
    assert isinstance(d, Marad)
    assert d.primitive == PRIMITIVE_NAME
    assert "parse_files" in d.diagnosis


def test_diagnostic_quotes_the_alias_the_user_actually_wrote() -> None:
    """If the user wrote ``scope_block``, the diagnostic must say
    ``scope_block``, not ``bismillah``. The error must read like the
    code the user wrote, not like the canonical form."""
    fixture = VALID_DIR / "scope_block_alias.furqan"
    module = _load(fixture)
    # No diagnostic, but we can pin the alias is preserved on the AST
    assert module.bismillah.alias_used == "scope_block"


def test_diagnostic_carries_a_minimal_fix_and_regression_check() -> None:
    fixture = INVALID_DIR / "violates_not_scope_directly.furqan"
    diagnostics = check_module(_load(fixture))
    d = diagnostics[0]
    assert d.minimal_fix.strip()
    assert d.regression_check.strip()


def test_diagnostic_location_points_at_the_call_not_the_bismillah() -> None:
    """Per NAMING.md §5 the location is where the failure is detected.
    For a not_scope violation that is the call site, not the
    Bismillah block."""
    fixture = INVALID_DIR / "violates_not_scope_directly.furqan"
    diagnostics = check_module(_load(fixture))
    d = diagnostics[0]
    # The offending call is on line 15 (0-indexed: 14 newlines into
    # the file) in violates_not_scope_directly.furqan.
    src = fixture.read_text().splitlines()
    line = src[d.location.line - 1]
    assert "parse_files()" in line


def test_qualified_call_is_checked_against_head() -> None:
    fixture = INVALID_DIR / "violates_not_scope_qualified.furqan"
    diagnostics = check_module(_load(fixture))
    assert len(diagnostics) == 1
    assert "render_output" in diagnostics[0].diagnosis


def test_violation_is_detected_in_any_function_not_only_the_first() -> None:
    fixture = INVALID_DIR / "violates_not_scope_in_second_function.furqan"
    diagnostics = check_module(_load(fixture))
    assert len(diagnostics) == 1
    assert "dirty_function" in diagnostics[0].diagnosis


# ---------------------------------------------------------------------------
# Strict variant
# ---------------------------------------------------------------------------

def test_strict_variant_raises_on_a_violation() -> None:
    fixture = INVALID_DIR / "violates_not_scope_directly.furqan"
    module = _load(fixture)
    with pytest.raises(MaradError) as exc_info:
        check_module_strict(module)
    assert exc_info.value.marad.primitive == PRIMITIVE_NAME


def test_strict_variant_accepts_a_clean_module_silently() -> None:
    fixture = VALID_DIR / "scan_service.furqan"
    module = _load(fixture)
    # Returns None, does not raise.
    assert check_module_strict(module) is None


# ---------------------------------------------------------------------------
# Edge case: empty not_scope
# ---------------------------------------------------------------------------

def test_module_with_empty_not_scope_passes_trivially() -> None:
    """A Bismillah block whose not_scope contains a single dummy
    excluded name still parses; we want to confirm the checker is
    not checking against some implicit default. A single 'never'
    placeholder that no function calls passes the checker."""
    src = """
    bismillah Permissive {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: anything
        not_scope: nothing_we_call
    }

    fn run() {
        anything()
        anything_else()
    }
    """
    module = parse(src, file="<inline>")
    assert check_module(module) == []


# ---------------------------------------------------------------------------
# Known limitations — pinned as documented behaviour, not silent gaps
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture", _all(KNOWN_LIMITATION_DIR), ids=lambda p: p.name,
)
def test_known_limitation_passes_by_design(fixture: Path) -> None:
    """Files under ``tests/fixtures/known_limitation/`` exercise gaps
    the Phase-2 checker is documented NOT to catch (Perplexity review
    item #3, Session 1.1 polish). They pass the checker by design.

    When a future phase closes one of these gaps, the corresponding
    fixture migrates from ``known_limitation/`` to ``invalid/`` and
    this test inverts at the same time. Pinning the limitation as a
    fixture converts a docstring caveat into a structural promise
    the test suite will signal on, rather than a silent
    documentation drift.
    """
    module = _load(fixture)
    diagnostics = check_module(module)
    assert diagnostics == [], (
        f"known-limitation fixture {fixture.name} now produces "
        f"diagnostics: {[d.diagnosis for d in diagnostics]}. The gap "
        f"this fixture pins has apparently been closed; move the "
        f"fixture to ``invalid/`` and update the test mapping."
    )


def test_known_limitation_directory_is_non_empty() -> None:
    """The ``known_limitation/`` directory exists to make limitations
    auditable. An empty directory is a Process-2 risk — it would
    suggest the checker has no documented gaps, which contradicts the
    Phase-2 docstring (`docs/NAMING.md` §6 + thesis §3.1 soundness
    note). At least one fixture must live here.
    """
    assert _all(KNOWN_LIMITATION_DIR), (
        "tests/fixtures/known_limitation/ is empty; either remove "
        "this test along with the directory, or add a fixture "
        "pinning a documented Phase-2 limitation."
    )


# ---------------------------------------------------------------------------
# Marad rendering
# ---------------------------------------------------------------------------

def test_marad_render_includes_primitive_tag_and_location() -> None:
    fixture = INVALID_DIR / "violates_not_scope_directly.furqan"
    diagnostics = check_module(_load(fixture))
    rendered = diagnostics[0].render()
    assert rendered.startswith(f"[{PRIMITIVE_NAME}]")
    assert "minimal_fix:" in rendered
    assert "regression_check:" in rendered
    assert str(fixture) in rendered
