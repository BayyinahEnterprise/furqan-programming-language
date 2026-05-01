"""
D23 cross-module type resolution tests.

Pin the contract for ``check_ring_close``'s ``imported_types``
keyword-only parameter (the mechanism) and the multi-module driver
that populates it from each module's direct dependencies (the
policy). Direct-only scoping: a module sees compound type names
exported by its DIRECTLY declared dependencies; transitive
visibility through a dep's deps is not granted automatically.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from furqan import Project
from furqan.checker.ring_close import (
    check_ring_close,
    check_ring_close_strict,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser import parse


FIXTURES = Path(__file__).parent / "fixtures" / "multi_module"
FURQAN_CMD = [sys.executable, "-m", "furqan"]


def _bismillah(name: str, scope: str = "noop") -> str:
    return dedent(f"""\
        bismillah {name} {{
            authority: NAMING_MD
            serves: purpose_hierarchy.balance_for_living_systems
            scope: {scope}
            not_scope: nothing_excluded
        }}
        """)


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*FURQAN_CMD, *args],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=Path(__file__).parent.parent,
    )


# ---------------------------------------------------------------------------
# imported_types parameter contract (single-module call sites)
# ---------------------------------------------------------------------------

def test_imported_types_default_is_empty_frozenset() -> None:
    """The default value preserves pre-D23 behaviour: a reference to
    an undeclared, non-builtin type still fires R1."""
    src = _bismillah("Demo", "scan") + dedent("""
        fn use() -> ImportedType {
            return ImportedType
        }
    """)
    diagnostics = check_ring_close(parse(src, file="<inline>"))
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1


def test_imported_types_is_keyword_only() -> None:
    src = _bismillah("Demo", "scan") + dedent("""
        type Local {
            zahir { name: String }
            batin { id: ID }
        }

        fn use() -> Local {
            return Local
        }
    """)
    module = parse(src, file="<inline>")
    with pytest.raises(TypeError):
        check_ring_close(module, frozenset({"X"}))  # type: ignore[misc]


def test_imported_type_suppresses_r1_on_param() -> None:
    src = _bismillah("Demo", "scan") + dedent("""
        type Local {
            zahir { name: String }
            batin { id: ID }
        }

        fn use(input: Imported) -> Local {
            return Local
        }
    """)
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"Imported"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_imported_type_suppresses_r1_on_return() -> None:
    src = _bismillah("Demo", "scan") + dedent("""
        fn use() -> Imported {
            return Imported
        }
    """)
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"Imported"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_imported_type_suppresses_r1_on_union_arm() -> None:
    src = _bismillah("Demo", "scan") + dedent("""
        fn maybe() -> ImportedA | ImportedB {
            return ImportedA
        }
    """)
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"ImportedA", "ImportedB"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_unknown_type_still_fires_r1_with_imports() -> None:
    """A type not in imported_types and not declared locally still
    fires R1 - imports are additive, not blanket."""
    src = _bismillah("Demo", "scan") + dedent("""
        fn use() -> Unknown {
            return Unknown
        }
    """)
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"Other", "Another"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "Unknown" in r1[0].diagnosis


def test_builtin_types_still_exempt_with_imports() -> None:
    """Integrity / Incomplete remain resolvable regardless of
    imported_types - the builtin set is unioned, not replaced."""
    src = _bismillah("Demo", "scan") + dedent("""
        fn scan() -> Integrity | Incomplete {
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
    """)
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"X"}),
    )
    assert diagnostics == []


def test_r4_not_affected_by_imported_types() -> None:
    """R4 fires on a locally-declared type that no local function
    references. Imports cannot make a local type 'used'."""
    src = _bismillah("Demo", "scan") + dedent("""
        type Local {
            zahir { name: String }
            batin { id: ID }
        }

        fn use() -> Imported {
            return Imported
        }
    """)
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"Imported"}),
    )
    r4 = [
        d for d in diagnostics
        if "Case R4" in getattr(d, "message", "")
    ]
    assert len(r4) == 1
    assert "Local" in r4[0].message


def test_check_ring_close_strict_forwards_imported_types() -> None:
    """The strict variant must also forward imported_types so the
    fail-fast path agrees with the soft path on cross-module
    resolution."""
    src = _bismillah("Demo", "scan") + dedent("""
        fn use() -> Imported {
            return Imported
        }
    """)
    module = parse(src, file="<inline>")
    # Without imports, strict raises on R1.
    with pytest.raises(MaradError):
        check_ring_close_strict(module)
    # With imports providing the type, strict returns module clean.
    returned = check_ring_close_strict(
        module, imported_types=frozenset({"Imported"}),
    )
    assert returned is module


# ---------------------------------------------------------------------------
# Multi-module integration via Project.check_all
# ---------------------------------------------------------------------------

def test_cross_module_type_fixture_passes() -> None:
    """The valid/cross_module_type fixture has TypeConsumer using
    Report from TypeProvider via tanzil. Project.check_all wires
    imported_types and R1 stays silent."""
    proj = Project()
    proj.add_directory(FIXTURES / "valid/cross_module_type")
    results = proj.check_all()
    for name, diags in results.items():
        if name == "__graph__":
            continue
        marads = [d for d in diags if isinstance(d, Marad)]
        assert marads == [], f"{name} produced marads: {marads}"


def test_type_not_in_dep_fires_r1() -> None:
    """invalid/type_not_in_dep: A depends on B, but A references
    MysteryType which neither defines."""
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/type_not_in_dep")
    results = proj.check_all()
    consumer_diags = results.get("DataConsumer", [])
    r1 = [
        d for d in consumer_diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "MysteryType" in r1[0].diagnosis


def test_transitive_type_without_direct_dep_fires_r1() -> None:
    """invalid/transitive_type: top depends on middle, middle
    depends on base. Base defines BaseType. Top references BaseType
    without depending on base directly. Direct-only scoping fires
    R1 on top."""
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/transitive_type")
    results = proj.check_all()
    top_diags = results.get("Top", [])
    r1 = [
        d for d in top_diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "BaseType" in r1[0].diagnosis
    # Base and Middle individually pass.
    for name in ("Base", "Middle"):
        marads = [
            d for d in results.get(name, [])
            if isinstance(d, Marad) and "Case R1" in d.diagnosis
        ]
        assert marads == []


def test_diamond_does_not_grant_transitive_type_visibility() -> None:
    """Even in a diamond shape (A -> B, A -> C, B -> D, C -> D), A
    sees types declared in B and C (its direct deps) but NOT types
    declared in D (only reachable transitively through B/C)."""
    proj = Project()
    # Build inline: A depends on B; B depends on D and defines no
    # types; D defines DType. A's reference to DType must fire R1.
    from textwrap import dedent
    sources = {
        "D": _bismillah("D", "core") + dedent("""
            type DType {
                zahir { name: String }
                batin { id: ID }
            }
        """) + "\nfn make() -> DType { return DType }\n",
        "B": _bismillah("B", "middle") + dedent("""
            tanzil b_deps {
                depends_on: D
            }
        """),
        "A": _bismillah("A", "top") + dedent("""
            tanzil a_deps {
                depends_on: B
            }

            fn use() -> DType {
                return DType
            }
        """),
    }
    for name, src in sources.items():
        module = parse(src, file=f"<{name}>")
        proj.modules[module.bismillah.name] = module
        proj.file_paths[module.bismillah.name] = Path(f"<{name}>")
    results = proj.check_all()
    a_marads = [
        d for d in results.get("A", [])
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(a_marads) == 1
    assert "DType" in a_marads[0].diagnosis


# ---------------------------------------------------------------------------
# CLI directory mode integration
# ---------------------------------------------------------------------------

def test_cli_directory_cross_module_passes() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "valid" / "cross_module_type"),
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "2 modules" in result.stdout


def test_cli_directory_missing_type_reports_r1() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "invalid" / "type_not_in_dep"),
    )
    assert result.returncode == 1
    assert "MARAD" in result.stdout
    assert "MysteryType" in result.stdout


def test_cli_directory_transitive_type_reports_r1() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "invalid" / "transitive_type"),
    )
    assert result.returncode == 1
    assert "BaseType" in result.stdout
    assert "Top" in result.stdout


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

def test_single_file_check_unchanged() -> None:
    """A pre-D23 single-file caller of check_ring_close (no
    imported_types argument) gets the v0.9.x behaviour: only local
    types and builtins resolve."""
    src = _bismillah("Solo", "scan") + dedent("""
        type Local {
            zahir { name: String }
            batin { id: ID }
        }

        fn use() -> Local {
            return Local
        }
    """)
    module = parse(src, file="<inline>")
    assert check_ring_close(module) == []


def test_single_file_cli_unchanged() -> None:
    """furqan check <file.furqan> still uses single-file mode and
    has no imported_types context."""
    example = (
        Path(__file__).parent.parent / "examples" / "clean_module.furqan"
    )
    result = _run_cli("check", str(example))
    assert result.returncode == 0
    assert "9 checkers ran" in result.stdout
