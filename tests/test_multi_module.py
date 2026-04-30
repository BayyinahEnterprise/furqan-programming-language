"""
Multi-module graph analysis tests (D9/D20, Phase 1).

Covers :class:`furqan.project.Project` construction, dependency-graph
building, topological sort, and the three graph-level checker cases
(G1 missing target, G2 cross-module cycle, G3 orphan advisory). Also
covers the CLI directory-mode contract added in v0.10.0.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from furqan import Project
from furqan.errors.marad import Advisory, Marad
from furqan.parser.ast_nodes import Module


FIXTURES = Path(__file__).parent / "fixtures" / "multi_module"
LINEAR = FIXTURES / "valid" / "linear_chain"
DIAMOND = FIXTURES / "valid" / "diamond"
STANDALONE = FIXTURES / "valid" / "standalone"
MISSING = FIXTURES / "invalid" / "missing_target"
CYCLE = FIXTURES / "invalid" / "cycle"
LONG_CYCLE = FIXTURES / "invalid" / "long_cycle"

FURQAN_CMD = [sys.executable, "-m", "furqan"]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*FURQAN_CMD, *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path(__file__).parent.parent,
    )


# ---------------------------------------------------------------------------
# Project construction
# ---------------------------------------------------------------------------

def test_add_file_parses_and_indexes_by_bismillah_name() -> None:
    project = Project()
    module = project.add_file(LINEAR / "foundation.furqan")
    assert isinstance(module, Module)
    assert "Foundation" in project.modules
    assert project.modules["Foundation"] is module


def test_add_file_records_path() -> None:
    project = Project()
    project.add_file(LINEAR / "foundation.furqan")
    assert project.file_paths["Foundation"] == LINEAR / "foundation.furqan"


def test_add_directory_finds_all_furqan_files() -> None:
    project = Project()
    modules = project.add_directory(LINEAR)
    assert len(modules) == 3
    assert set(project.modules.keys()) == {
        "Foundation",
        "DataLoader",
        "Analytics",
    }


def test_add_directory_returns_empty_for_no_furqan_files(
    tmp_path: Path,
) -> None:
    project = Project()
    result = project.add_directory(tmp_path)
    assert result == []
    assert project.modules == {}


def test_add_directory_is_non_recursive(tmp_path: Path) -> None:
    """Files in subdirectories are not picked up."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.furqan").write_text(
        (LINEAR / "foundation.furqan").read_text()
    )
    project = Project()
    project.add_directory(tmp_path)
    assert project.modules == {}


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

def test_dependency_graph_returns_adjacency_list() -> None:
    project = Project()
    project.add_directory(LINEAR)
    graph = project.dependency_graph()
    assert graph["Foundation"] == []
    assert graph["DataLoader"] == ["Foundation"]
    assert graph["Analytics"] == ["DataLoader"]


def test_dependency_graph_diamond_shape() -> None:
    project = Project()
    project.add_directory(DIAMOND)
    graph = project.dependency_graph()
    assert graph["D"] == []
    assert graph["B"] == ["D"]
    assert graph["C"] == ["D"]
    assert sorted(graph["A"]) == ["B", "C"]


def test_dependency_graph_module_with_no_tanzil_block_has_empty_list() -> None:
    project = Project()
    project.add_directory(STANDALONE)
    graph = project.dependency_graph()
    assert graph == {"Solo": []}


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

def test_linear_chain_sorts_correctly() -> None:
    project = Project()
    project.add_directory(LINEAR)
    order = project.topological_order()
    assert order == ["Foundation", "DataLoader", "Analytics"]


def test_diamond_sorts_with_d_before_b_and_c() -> None:
    project = Project()
    project.add_directory(DIAMOND)
    order = project.topological_order()
    assert order is not None
    assert order.index("D") < order.index("B")
    assert order.index("D") < order.index("C")
    assert order.index("B") < order.index("A")
    assert order.index("C") < order.index("A")


def test_standalone_module_sorts_trivially() -> None:
    project = Project()
    project.add_directory(STANDALONE)
    order = project.topological_order()
    assert order == ["Solo"]


def test_cycle_returns_none() -> None:
    project = Project()
    project.add_directory(CYCLE)
    assert project.topological_order() is None


def test_long_cycle_returns_none() -> None:
    project = Project()
    project.add_directory(LONG_CYCLE)
    assert project.topological_order() is None


def test_topological_order_is_deterministic() -> None:
    """Two equivalent projects produce the same sort."""
    p1 = Project()
    p1.add_directory(DIAMOND)
    p2 = Project()
    p2.add_directory(DIAMOND)
    assert p1.topological_order() == p2.topological_order()


# ---------------------------------------------------------------------------
# Graph checker cases
# ---------------------------------------------------------------------------

def test_g1_missing_target_fires() -> None:
    project = Project()
    project.add_directory(MISSING)
    diagnostics = project.check_graph()
    g1_marads = [
        d
        for d in diagnostics
        if isinstance(d, Marad) and "G1" in d.diagnosis
    ]
    assert len(g1_marads) == 1


def test_g1_names_the_missing_module() -> None:
    project = Project()
    project.add_directory(MISSING)
    diagnostics = project.check_graph()
    marads = [d for d in diagnostics if isinstance(d, Marad)]
    assert any("'B'" in m.diagnosis for m in marads)
    assert any("'A'" in m.diagnosis for m in marads)


def test_g1_primitive_is_graph() -> None:
    project = Project()
    project.add_directory(MISSING)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    assert all(m.primitive == "graph" for m in marads)


def test_g2_cycle_fires_on_two_module_cycle() -> None:
    project = Project()
    project.add_directory(CYCLE)
    diagnostics = project.check_graph()
    g2_marads = [
        d
        for d in diagnostics
        if isinstance(d, Marad) and "cycle" in d.diagnosis.lower()
    ]
    assert len(g2_marads) >= 1


def test_g2_cycle_fires_on_three_module_cycle() -> None:
    project = Project()
    project.add_directory(LONG_CYCLE)
    diagnostics = project.check_graph()
    g2_marads = [
        d
        for d in diagnostics
        if isinstance(d, Marad) and "cycle" in d.diagnosis.lower()
    ]
    assert len(g2_marads) >= 1


def test_g2_names_all_modules_in_two_cycle() -> None:
    project = Project()
    project.add_directory(CYCLE)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    cycle_marad = next(
        m for m in marads if "cycle" in m.diagnosis.lower()
    )
    assert "A" in cycle_marad.diagnosis
    assert "B" in cycle_marad.diagnosis


def test_g2_names_all_modules_in_long_cycle() -> None:
    project = Project()
    project.add_directory(LONG_CYCLE)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    cycle_marad = next(
        m for m in marads if "cycle" in m.diagnosis.lower()
    )
    for name in ("A", "B", "C"):
        assert name in cycle_marad.diagnosis


def test_g2_renders_arrow_chain() -> None:
    project = Project()
    project.add_directory(LONG_CYCLE)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    cycle_marad = next(
        m for m in marads if "cycle" in m.diagnosis.lower()
    )
    assert "->" in cycle_marad.diagnosis


def test_g3_orphan_produces_advisory(tmp_path: Path) -> None:
    """A module with no deps and no incoming edges, alongside another
    connected pair, fires G3."""
    # B -> C connected pair, A is orphan.
    (tmp_path / "a.furqan").write_text(
        "bismillah A {\n"
        "    authority: NAMING_MD\n"
        "    serves: purpose_hierarchy.balance_for_living_systems\n"
        "    scope: orphan\n"
        "    not_scope: nothing_excluded\n"
        "}\n"
    )
    (tmp_path / "b.furqan").write_text(
        "bismillah B {\n"
        "    authority: NAMING_MD\n"
        "    serves: purpose_hierarchy.balance_for_living_systems\n"
        "    scope: side_b\n"
        "    not_scope: nothing_excluded\n"
        "}\n"
        "tanzil b_deps {\n"
        "    depends_on: C\n"
        "}\n"
    )
    (tmp_path / "c.furqan").write_text(
        "bismillah C {\n"
        "    authority: NAMING_MD\n"
        "    serves: purpose_hierarchy.balance_for_living_systems\n"
        "    scope: side_c\n"
        "    not_scope: nothing_excluded\n"
        "}\n"
    )
    project = Project()
    project.add_directory(tmp_path)
    diagnostics = project.check_graph()
    advisories = [d for d in diagnostics if isinstance(d, Advisory)]
    assert any("'A'" in a.message for a in advisories)


def test_g3_does_not_fire_for_single_module_project() -> None:
    """A project with one module is not orphan-flagged. Trivially
    standalone."""
    project = Project()
    project.add_directory(STANDALONE)
    advisories = [
        d for d in project.check_graph() if isinstance(d, Advisory)
    ]
    assert advisories == []


# ---------------------------------------------------------------------------
# Valid projects, zero graph diagnostics
# ---------------------------------------------------------------------------

def test_linear_chain_zero_graph_marads() -> None:
    project = Project()
    project.add_directory(LINEAR)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    assert marads == []


def test_diamond_zero_graph_marads() -> None:
    project = Project()
    project.add_directory(DIAMOND)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    assert marads == []


def test_standalone_zero_graph_diagnostics() -> None:
    project = Project()
    project.add_directory(STANDALONE)
    assert project.check_graph() == []


# ---------------------------------------------------------------------------
# Marad shape contracts
# ---------------------------------------------------------------------------

def test_g1_marad_has_four_required_fields() -> None:
    project = Project()
    project.add_directory(MISSING)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    m = marads[0]
    assert m.primitive == "graph"
    assert m.diagnosis
    assert m.minimal_fix
    assert m.regression_check
    assert m.location is not None


def test_g2_marad_has_four_required_fields() -> None:
    project = Project()
    project.add_directory(CYCLE)
    marads = [
        d for d in project.check_graph() if isinstance(d, Marad)
    ]
    m = next(d for d in marads if "cycle" in d.diagnosis.lower())
    assert m.primitive == "graph"
    assert m.diagnosis
    assert m.minimal_fix
    assert m.regression_check
    assert m.location is not None


# ---------------------------------------------------------------------------
# CLI directory mode
# ---------------------------------------------------------------------------

def test_cli_directory_check_passes_on_linear_chain() -> None:
    result = _run("check", str(LINEAR))
    assert result.returncode == 0
    assert "MARAD" not in result.stdout


def test_cli_directory_check_passes_on_diamond() -> None:
    result = _run("check", str(DIAMOND))
    assert result.returncode == 0
    assert "MARAD" not in result.stdout


def test_cli_directory_check_reports_missing_target() -> None:
    result = _run("check", str(MISSING))
    assert result.returncode == 1
    assert "MARAD" in result.stdout
    assert "Graph violations" in result.stdout


def test_cli_directory_check_reports_two_cycle() -> None:
    result = _run("check", str(CYCLE))
    assert result.returncode == 1
    assert "MARAD" in result.stdout
    assert "cycle" in result.stdout.lower()
    assert "A -> B" in result.stdout or "A -> B -> A" in result.stdout


def test_cli_directory_check_reports_three_cycle() -> None:
    result = _run("check", str(LONG_CYCLE))
    assert result.returncode == 1
    assert "A -> B -> C -> A" in result.stdout


def test_cli_graph_only_skips_per_module() -> None:
    """--graph-only suppresses ring_close R2 advisories from the
    empty fixture modules."""
    result = _run("check", str(LINEAR), "--graph-only")
    assert result.returncode == 0
    assert "PASS" in result.stdout
    # No per-module advisories should appear in graph-only mode.
    assert "ring_close" not in result.stdout


def test_cli_graph_only_alone_on_file_errors() -> None:
    """--graph-only without a directory is rejected."""
    result = _run(
        "check",
        str(LINEAR / "foundation.furqan"),
        "--graph-only",
    )
    assert result.returncode == 1
    assert "directory" in result.stderr


def test_cli_directory_strict_mode_returns_three() -> None:
    result = _run("check", str(CYCLE), "--strict")
    assert result.returncode == 3


def test_cli_empty_directory_passes(tmp_path: Path) -> None:
    result = _run("check", str(tmp_path))
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "0 modules" in result.stdout


def test_cli_single_file_directory_works(tmp_path: Path) -> None:
    """A directory with exactly one .furqan file works in directory
    mode."""
    src = (LINEAR / "foundation.furqan").read_text()
    (tmp_path / "only.furqan").write_text(src)
    result = _run("check", str(tmp_path), "--graph-only")
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "1 modules" in result.stdout


# ---------------------------------------------------------------------------
# Backward compatibility: single-file mode still works
# ---------------------------------------------------------------------------

def test_cli_single_file_mode_unchanged() -> None:
    """A single .furqan file argument continues to work; the empty
    fixture body emits an advisory but the exit code is 0."""
    result = _run("check", str(LINEAR / "foundation.furqan"))
    assert result.returncode == 0
    assert "MARAD" not in result.stdout


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def test_project_is_exported_from_top_level() -> None:
    import furqan
    assert hasattr(furqan, "Project")
    assert furqan.Project is Project


def test_project_module_primitive_name_is_graph() -> None:
    from furqan.project import PRIMITIVE_NAME
    assert PRIMITIVE_NAME == "graph"
