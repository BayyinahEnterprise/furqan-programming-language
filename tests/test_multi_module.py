"""
Multi-module graph analysis (D9/D20) and cross-module type
resolution (D23) tests.

Covers the Project class, dependency_graph, topological_order,
check_graph (G1/G2/G3), check_all (D23 cross-module type
resolution driver), and CLI directory mode.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from furqan import Project
from furqan.errors.marad import Advisory, Marad
from furqan.parser import parse


FIXTURES = Path(__file__).parent / "fixtures" / "multi_module"
EXAMPLES_MULTI = Path(__file__).parent.parent / "examples" / "multi"
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


def _trivial_fn() -> str:
    return "\nfn placeholder() -> Integrity {\n    return Integrity\n}\n"


def _project_from_inline(modules: dict[str, str]) -> Project:
    """Build a Project by parsing inline source dict."""
    proj = Project()
    for name, src in modules.items():
        module = parse(src, file=f"<{name}>")
        proj.modules[module.bismillah.name] = module
        proj.file_paths[module.bismillah.name] = Path(f"<{name}>")
    return proj


# ---------------------------------------------------------------------------
# Project construction
# ---------------------------------------------------------------------------

def test_add_file_indexes_by_bismillah_name() -> None:
    proj = Project()
    proj.add_file(FIXTURES / "valid/standalone/lonely.furqan")
    assert "Lonely" in proj.modules
    assert proj.file_paths["Lonely"].name == "lonely.furqan"


def test_add_directory_finds_all_furqan_files() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/linear_chain")
    assert set(proj.modules) == {"Foundation", "DataLoader", "Analytics"}


def test_dependency_graph_returns_adjacency_list() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/linear_chain")
    g = proj.dependency_graph()
    assert g["Foundation"] == []
    assert g["DataLoader"] == ["Foundation"]
    assert g["Analytics"] == ["DataLoader"]


def test_duplicate_bismillah_name_raises() -> None:
    proj = Project()
    proj.add_file(FIXTURES / "valid/standalone/lonely.furqan")
    with pytest.raises(ValueError, match="duplicate bismillah name"):
        proj.add_file(FIXTURES / "valid/standalone/lonely.furqan")


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def test_linear_chain_sorts_correctly() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/linear_chain")
    order = proj.topological_order()
    assert order is not None
    assert order.index("Foundation") < order.index("DataLoader")
    assert order.index("DataLoader") < order.index("Analytics")


def test_diamond_sorts_d_before_b_and_c() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/diamond")
    order = proj.topological_order()
    assert order is not None
    assert order.index("D") < order.index("B")
    assert order.index("D") < order.index("C")
    assert order.index("B") < order.index("A")
    assert order.index("C") < order.index("A")


def test_standalone_sorts_trivially() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/standalone")
    assert proj.topological_order() == ["Lonely"]


def test_cycle_returns_none() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/cycle")
    assert proj.topological_order() is None


def test_long_cycle_returns_none() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/long_cycle")
    assert proj.topological_order() is None


# ---------------------------------------------------------------------------
# Graph checker
# ---------------------------------------------------------------------------

def test_g1_missing_target_fires() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/missing_target")
    diags = proj.check_graph()
    g1 = [d for d in diags if isinstance(d, Marad) and "Case G1" in d.diagnosis]
    assert len(g1) == 1


def test_g1_names_the_missing_module() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/missing_target")
    g1 = next(
        d for d in proj.check_graph()
        if isinstance(d, Marad) and "Case G1" in d.diagnosis
    )
    assert "NotInProject" in g1.diagnosis
    assert "'A'" in g1.diagnosis


def test_g2_cycle_fires_on_two_modules() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/cycle")
    diags = proj.check_graph()
    g2 = [d for d in diags if isinstance(d, Marad) and "Case G2" in d.diagnosis]
    assert len(g2) == 1
    assert "Alpha -> Beta -> Alpha" in g2[0].diagnosis


def test_g2_cycle_fires_on_three_modules() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/long_cycle")
    g2 = next(
        d for d in proj.check_graph()
        if isinstance(d, Marad) and "Case G2" in d.diagnosis
    )
    assert "LCA -> LCB -> LCC -> LCA" in g2.diagnosis


def test_g2_names_all_modules_in_cycle() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/long_cycle")
    g2 = next(
        d for d in proj.check_graph()
        if isinstance(d, Marad) and "Case G2" in d.diagnosis
    )
    for name in ("LCA", "LCB", "LCC"):
        assert name in g2.diagnosis


def test_g3_orphan_produces_advisory() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/missing_target")
    advisories = [
        d for d in proj.check_graph()
        if isinstance(d, Advisory) and "Case G3" in d.message
    ]
    assert len(advisories) == 1
    assert "Other" in advisories[0].message


def test_g3_does_not_fire_on_single_module_project() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/standalone")
    advisories = [
        d for d in proj.check_graph() if isinstance(d, Advisory)
    ]
    assert advisories == []


# ---------------------------------------------------------------------------
# Cross-module type resolution (D23 driver)
# ---------------------------------------------------------------------------

def test_type_from_direct_dependency_does_not_fire_r1() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/cross_module_type")
    results = proj.check_all()
    a_diags = results.get("A", [])
    r1 = [
        d for d in a_diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_type_not_in_any_dependency_fires_r1() -> None:
    """A module without a tanzil declaration referring to a type
    elsewhere still fires R1: the Project does not silently
    propagate types to consumers that did not declare a dependency."""
    proj = _project_from_inline({
        "B": _bismillah("B", "declare") + dedent("""
            type Report {
                zahir { name: String }
                batin { id: ID }
            }
        """) + "\nfn make() -> Report {\n    return Report\n}\n",
        "A": _bismillah("A", "consume") + dedent("""
            fn use_it() -> Report {
                return Report
            }
        """),
    })
    results = proj.check_all()
    a_diags = results.get("A", [])
    r1 = [
        d for d in a_diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "Report" in r1[0].diagnosis


def test_transitive_type_without_direct_dep_fires_r1() -> None:
    """Direct-only resolution: A depends on B, B depends on C, C
    declares Type. A using Type must declare depends_on: C
    explicitly."""
    proj = _project_from_inline({
        "C": _bismillah("C", "core") + dedent("""
            type Data {
                zahir { name: String }
                batin { id: ID }
            }
        """) + "\nfn make() -> Data {\n    return Data\n}\n",
        "B": _bismillah("B", "middle") + dedent("""
            tanzil b_deps {
                depends_on: C
            }
        """),
        "A": _bismillah("A", "top") + dedent("""
            tanzil a_deps {
                depends_on: B
            }

            fn try_data() -> Data {
                return Data
            }
        """),
    })
    results = proj.check_all()
    a_diags = results.get("A", [])
    r1 = [
        d for d in a_diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "Data" in r1[0].diagnosis


def test_transitive_type_with_direct_dep_does_not_fire() -> None:
    """If A re-declares depends_on: C, then Data is in A's import
    set and R1 stays silent."""
    proj = _project_from_inline({
        "C": _bismillah("C", "core") + dedent("""
            type Data {
                zahir { name: String }
                batin { id: ID }
            }
        """) + "\nfn make() -> Data {\n    return Data\n}\n",
        "B": _bismillah("B", "middle") + dedent("""
            tanzil b_deps {
                depends_on: C
            }
        """),
        "A": _bismillah("A", "top") + dedent("""
            tanzil a_deps {
                depends_on: B
                depends_on: C
            }

            fn try_data() -> Data {
                return Data
            }
        """),
    })
    results = proj.check_all()
    a_diags = results.get("A", [])
    r1 = [
        d for d in a_diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


# ---------------------------------------------------------------------------
# Project.check_all
# ---------------------------------------------------------------------------

def test_check_all_returns_per_module_diagnostics() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/cross_module_type")
    results = proj.check_all()
    assert set(results) == {"A", "B"}


def test_check_all_stops_on_graph_cycle() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/cycle")
    results = proj.check_all()
    assert "__graph__" in results
    assert "Alpha" not in results
    assert "Beta" not in results


def test_check_all_passes_on_clean_multi_module_project() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/linear_chain")
    results = proj.check_all()
    for name in ("Foundation", "DataLoader", "Analytics"):
        marads = [
            d for d in results.get(name, []) if isinstance(d, Marad)
        ]
        assert marads == [], f"{name} produced marads: {marads}"


def test_check_all_diamond_passes() -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid/diamond")
    results = proj.check_all()
    for name in ("A", "B", "C", "D"):
        marads = [
            d for d in results.get(name, []) if isinstance(d, Marad)
        ]
        assert marads == []


def test_check_all_surfaces_g1_alongside_per_module() -> None:
    """G1 is a Marad but not a cycle; check_all proceeds with per-
    module checks AND surfaces __graph__ for the missing target."""
    proj = Project()
    proj.add_directory(FIXTURES / "invalid/missing_target")
    results = proj.check_all()
    assert "__graph__" in results
    # Per-module results still ran (no cycle short-circuit).
    assert "A" in results
    assert "Other" in results


# ---------------------------------------------------------------------------
# Backward compatibility (single-module ring-close path unchanged)
# ---------------------------------------------------------------------------

def test_ring_close_default_imported_types_unchanged() -> None:
    """An R1 reference to a type with no project context still
    fires under the default empty frozenset - the single-module
    behaviour is preserved."""
    src = _bismillah("Alone", "scan") + dedent("""
        fn use() -> NotDefined {
            return NotDefined
        }
    """)
    from furqan.checker.ring_close import check_ring_close
    module = parse(src, file="<inline>")
    diags = check_ring_close(module)
    r1 = [
        d for d in diags
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1


# ---------------------------------------------------------------------------
# CLI directory mode
# ---------------------------------------------------------------------------

def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*FURQAN_CMD, *args],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=Path(__file__).parent.parent,
    )


def test_cli_directory_passes_on_valid() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "valid" / "linear_chain"),
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "3 modules" in result.stdout


def test_cli_directory_reports_cycle() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "invalid" / "cycle"),
    )
    assert result.returncode == 1
    assert "GRAPH" in result.stdout
    assert "Alpha -> Beta -> Alpha" in result.stdout


def test_cli_directory_reports_missing_target() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "invalid" / "missing_target"),
    )
    assert result.returncode == 1
    assert "NotInProject" in result.stdout


def test_cli_graph_only_flag() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "invalid" / "cycle"), "--graph-only",
    )
    assert result.returncode == 1
    assert "GRAPH" in result.stdout
    assert "Alpha -> Beta -> Alpha" in result.stdout


def test_cli_directory_strict_mode_returns_3() -> None:
    result = _run_cli(
        "check", str(FIXTURES / "invalid" / "cycle"), "--strict",
    )
    assert result.returncode == 3


def test_cli_examples_multi_passes() -> None:
    """The examples/multi demo set should pass cleanly."""
    result = _run_cli("check", str(EXAMPLES_MULTI))
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "3 modules" in result.stdout


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_directory_no_crash(tmp_path: Path) -> None:
    """A directory with no .furqan files exits cleanly, exit 0."""
    result = _run_cli("check", str(tmp_path))
    assert result.returncode == 0
    assert "0 modules" in result.stdout


def test_single_file_directory_works(tmp_path: Path) -> None:
    """A directory containing exactly one .furqan file is handled
    by the directory path."""
    (tmp_path / "only.furqan").write_text(
        _bismillah("Only", "noop") + _trivial_fn()
    )
    result = _run_cli("check", str(tmp_path))
    assert result.returncode == 0
    assert "1 modules" in result.stdout


def test_single_file_mode_unchanged() -> None:
    """File path with .furqan suffix still uses single-file mode."""
    result = _run_cli(
        "check", str(EXAMPLES_MULTI / "foundation.furqan"),
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "9 checkers ran" in result.stdout


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def test_project_exported_from_top_level_package() -> None:
    from furqan import GRAPH_PRIMITIVE_NAME, Project as P  # noqa: F401
    assert P is Project
    assert GRAPH_PRIMITIVE_NAME == "graph"


def test_project_module_all_matches_public_surface() -> None:
    from furqan import project as proj_module
    expected = {
        "GRAPH_PRIMITIVE_NAME",
        "GraphDiagnostic",
        "Project",
    }
    assert set(proj_module.__all__) == expected


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "subdir",
    sorted(p.name for p in (FIXTURES / "valid").iterdir() if p.is_dir()),
)
def test_every_valid_fixture_passes_check_all(subdir: str) -> None:
    proj = Project()
    proj.add_directory(FIXTURES / "valid" / subdir)
    results = proj.check_all()
    # No __graph__ key on a clean project, OR a __graph__ block
    # that contains only Advisories.
    if "__graph__" in results:
        marads = [
            d for d in results["__graph__"] if isinstance(d, Marad)
        ]
        assert marads == [], (
            f"valid/{subdir} produced graph marads: {marads}"
        )
    for name, diags in results.items():
        if name == "__graph__":
            continue
        marads = [d for d in diags if isinstance(d, Marad)]
        assert marads == [], (
            f"valid/{subdir} module {name} produced marads: {marads}"
        )


@pytest.mark.parametrize(
    "subdir",
    sorted(p.name for p in (FIXTURES / "invalid").iterdir() if p.is_dir()),
)
def test_every_invalid_fixture_produces_a_marad(subdir: str) -> None:
    """An invalid multi-module fixture must produce at least one
    Marad somewhere in the project: either at the graph level
    (G1/G2 fixtures) or at a per-module level (D23 cross-module
    type fixtures). check_all() unifies both views."""
    proj = Project()
    proj.add_directory(FIXTURES / "invalid" / subdir)
    results = proj.check_all()
    total_marads = 0
    for diags in results.values():
        total_marads += sum(1 for d in diags if isinstance(d, Marad))
    assert total_marads >= 1, (
        f"invalid/{subdir} produced no marads anywhere in the project"
    )
