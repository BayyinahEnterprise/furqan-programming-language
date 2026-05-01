"""
Furqan Project: multi-module graph analysis (D9/D20) and cross-
module type resolution driver (D23).

A :class:`Project` indexes one or more parsed :class:`Module` objects
keyed by their bismillah name, computes the dependency graph from
each module's tanzil declarations, and provides:

* ``dependency_graph`` : adjacency list across the project
* ``topological_order`` : Kahn's algorithm sort, or ``None`` on cycle
* ``check_graph`` : G1 (missing target, Marad), G2 (cycle, Marad),
  G3 (orphan, Advisory)
* ``check_all`` : runs every per-module checker on every module,
  with cross-module type resolution via the ``imported_types``
  parameter on ``check_ring_close``

The cross-module type resolution is direct-only: a module sees the
compound type names exported by its directly declared dependencies
only, not transitively. This matches Python / Rust / Go module
semantics: to use C's types from A, A must declare ``depends_on: C``
explicitly.

D23 (cross-module ring-close R1) is fully delivered through this
module: the ring-close ``imported_types`` keyword-only parameter
that landed alongside the partial D23 work is now driven by
``Project.check_all`` to suppress R1 false positives on imported
types.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import List, Optional, Union

from furqan.errors.marad import Advisory, Marad
from furqan.parser import ParseError, parse
from furqan.parser.ast_nodes import Module
from furqan.parser.tokenizer import TokenizeError


GRAPH_PRIMITIVE_NAME: str = "graph"


GraphDiagnostic = Union[Marad, Advisory]


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class Project:
    """A collection of parsed Furqan modules with a dependency graph.

    Modules are keyed by their ``bismillah.name``. The bismillah
    primitive is parser-enforced as exactly-one-per-module, so each
    module has a unique name. Adding two modules with the same
    bismillah name raises :class:`ValueError` (the project model
    requires a one-to-one map).
    """

    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}
        self.file_paths: dict[str, Path] = {}

    # ---- ingestion --------------------------------------------------------

    def add_file(self, path: Path) -> Module:
        """Parse a single .furqan file and add it to the project.

        Raises ``ParseError`` / ``TokenizeError`` on parser failure;
        ``ValueError`` if the file's bismillah name is already in
        the project (a project requires unique bismillah names).
        """
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        module = parse(text, file=str(path))
        name = module.bismillah.name
        if name in self.modules:
            raise ValueError(
                f"duplicate bismillah name {name!r}: "
                f"{self.file_paths[name]} and {path}"
            )
        self.modules[name] = module
        self.file_paths[name] = path
        return module

    def add_directory(self, directory: Path) -> List[Module]:
        """Parse every .furqan file in the directory (non-recursive)
        and add each to the project. Returns the list of newly added
        modules.
        """
        directory = Path(directory)
        added: List[Module] = []
        for path in sorted(directory.glob("*.furqan")):
            added.append(self.add_file(path))
        return added

    # ---- graph ------------------------------------------------------------

    def dependency_graph(self) -> dict[str, list[str]]:
        """Adjacency list across the project: each module name maps
        to a list of the names it depends on (per its tanzil
        declarations). A module with no tanzil block maps to an
        empty list.
        """
        graph: dict[str, list[str]] = {}
        for name, module in self.modules.items():
            deps: list[str] = []
            for decl in module.tanzil_decls:
                for dep in decl.dependencies:
                    deps.append(dep.module_path)
            graph[name] = deps
        return graph

    def topological_order(self) -> Optional[List[str]]:
        """Return modules in topological (dependency-first) order
        via Kahn's algorithm. Returns ``None`` if the graph contains
        a cycle.
        """
        graph = self.dependency_graph()
        in_degree: dict[str, int] = defaultdict(int)
        for name in graph:
            in_degree[name] = 0
        for name, deps in graph.items():
            for dep in deps:
                # Edge dep -> name (dep must be built before name).
                # Increment in_degree of name; only count edges
                # where the source is in the project (out-of-project
                # edges are G1's concern, not the sort's).
                if dep in graph:
                    in_degree[name] += 1

        queue: deque[str] = deque(
            sorted(n for n, d in in_degree.items() if d == 0)
        )
        order: list[str] = []
        while queue:
            n = queue.popleft()
            order.append(n)
            # Walk consumers of n.
            for m, deps in graph.items():
                if n in deps:
                    in_degree[m] -= 1
                    if in_degree[m] == 0:
                        queue.append(m)
            # Re-sort the queue to keep iteration deterministic.
            queue = deque(sorted(queue))

        if len(order) != len(graph):
            return None
        return order

    # ---- graph-level diagnostics -----------------------------------------

    def check_graph(self) -> list[GraphDiagnostic]:
        """Run G1, G2, G3 on the dependency graph.

        G1 (Marad): missing dependency target.
        G2 (Marad): cross-module cycle.
        G3 (Advisory): orphan module (only when project size >= 2).
        """
        diagnostics: list[GraphDiagnostic] = []
        graph = self.dependency_graph()

        # G1: missing dependency targets.
        for name, deps in graph.items():
            for dep in deps:
                if dep not in graph:
                    diagnostics.append(self._g1_marad(name, dep))

        # G2: cycle detection.
        if self.topological_order() is None:
            cycle = self._find_cycle(graph)
            if cycle is not None:
                diagnostics.append(self._g2_marad(cycle))

        # G3: orphan module advisory (project size >= 2).
        if len(self.modules) >= 2:
            referenced: set[str] = set()
            for deps in graph.values():
                referenced.update(deps)
            for name, deps in graph.items():
                if not deps and name not in referenced:
                    diagnostics.append(self._g3_advisory(name))

        return diagnostics

    # ---- cross-module driver ---------------------------------------------

    def check_all(self) -> dict[str, list[GraphDiagnostic]]:
        """Run every per-module checker on every module, with cross-
        module type resolution. Returns ``{module_name: [diags]}``.

        A G2 cycle short-circuits: ``__graph__`` carries the graph-
        level diagnostics and per-module checks are skipped (a cyclic
        dependency graph cannot be ordered, and per-module type
        resolution would be ill-defined).
        """
        results: dict[str, list[GraphDiagnostic]] = {}

        graph_diagnostics = self.check_graph()
        if any(
            isinstance(d, Marad) and "Case G2" in d.diagnosis
            for d in graph_diagnostics
        ):
            results["__graph__"] = graph_diagnostics
            return results

        order = self.topological_order()
        if order is None:
            results["__graph__"] = graph_diagnostics
            return results

        # Always surface graph-level diagnostics (G1, G3) even when
        # we proceed to per-module checks.
        if graph_diagnostics:
            results["__graph__"] = list(graph_diagnostics)

        # Build a per-module type-export map.
        type_exports: dict[str, set[str]] = {}
        for name in order:
            module = self.modules[name]
            type_exports[name] = {
                ct.name for ct in module.compound_types
            }

        # Per-module checks (D23 driver).
        graph = self.dependency_graph()
        for name in order:
            module = self.modules[name]
            deps = graph.get(name, [])
            imported: set[str] = set()
            for dep_name in deps:
                if dep_name in type_exports:
                    imported.update(type_exports[dep_name])
            results[name] = _check_single_module(
                module, imported_types=frozenset(imported),
            )

        return results

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _find_cycle(
        graph: dict[str, list[str]],
    ) -> Optional[List[str]]:
        """DFS-based cycle finder. Returns the cycle as a list of
        names where ``cycle[0] == cycle[-1]`` (the same module
        appearing on both ends), or ``None`` if no cycle is reachable.
        Iteration uses sorted neighbours so the report is
        deterministic.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in graph}
        parent: dict[str, Optional[str]] = {n: None for n in graph}

        for start in sorted(graph):
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, list[str]]] = [
                (start, sorted(graph.get(start, [])))
            ]
            color[start] = GRAY
            while stack:
                node, neighbours = stack[-1]
                if not neighbours:
                    color[node] = BLACK
                    stack.pop()
                    continue
                nxt = neighbours.pop(0)
                if nxt not in color:
                    continue
                if color[nxt] == GRAY:
                    # Found a cycle: walk parent pointers from
                    # ``node`` back to ``nxt`` to build the path,
                    # then close the loop by appending ``nxt`` again.
                    path = [node]
                    p = parent[node]
                    while p is not None and p != nxt:
                        path.append(p)
                        p = parent[p]
                    path.append(nxt)
                    path.reverse()
                    path.append(nxt)
                    return path
                if color[nxt] == WHITE:
                    parent[nxt] = node
                    color[nxt] = GRAY
                    stack.append(
                        (nxt, sorted(graph.get(nxt, [])))
                    )
        return None

    def _g1_marad(self, source: str, missing: str) -> Marad:
        return Marad(
            primitive=GRAPH_PRIMITIVE_NAME,
            diagnosis=(
                f"module {source!r} declares a tanzil dependency on "
                f"{missing!r} but no module with that bismillah name "
                f"is in the project. Per Furqan D9/D20 (Case G1, "
                f"missing dependency target), a tanzil declaration "
                f"must reference a module the project can resolve. "
                f"The build pipeline cannot order a graph whose "
                f"edges point at non-existent nodes."
            ),
            location=self.modules[source].bismillah.span,
            minimal_fix=(
                f"either add a module with bismillah name "
                f"{missing!r} to the project (typically by adding "
                f"its .furqan file to the directory passed to the "
                f"checker), or remove the `depends_on: {missing}` "
                f"line from {source!r}'s tanzil block. If the "
                f"dependency is satisfied by a module outside this "
                f"project (a future cross-project import), the "
                f"resolution is registered as Phase 3+ work."
            ),
            regression_check=(
                f"after the fix, re-run the project graph check; "
                f"every tanzil dependency must resolve to a module "
                f"in the project."
            ),
        )

    def _g2_marad(self, cycle: List[str]) -> Marad:
        chain = " -> ".join(cycle)
        # Use the first module in the cycle for the location.
        location = self.modules[cycle[0]].bismillah.span
        return Marad(
            primitive=GRAPH_PRIMITIVE_NAME,
            diagnosis=(
                f"cross-module dependency cycle detected: {chain}. "
                f"Per Furqan D9/D20 (Case G2, dependency cycle), the "
                f"tanzil graph must be acyclic. A cycle means no "
                f"module in the cycle can be built before the "
                f"others - the discipline of progressive build "
                f"ordering breaks at the cycle edge."
            ),
            location=location,
            minimal_fix=(
                f"break the cycle by removing one of the "
                f"`depends_on:` lines along the chain. The right "
                f"edge to remove is usually the back-edge that "
                f"closes the cycle (the dependency that least "
                f"reflects the actual build-time prerequisite). If "
                f"each module in the cycle genuinely needs the "
                f"others, the design has a circular structural "
                f"problem that no per-module checker can resolve - "
                f"refactor so one module owns the shared concern."
            ),
            regression_check=(
                f"after the fix, re-run the graph check; "
                f"`topological_order()` must succeed (return a list, "
                f"not None)."
            ),
        )

    def _g3_advisory(self, name: str) -> Advisory:
        return Advisory(
            primitive=GRAPH_PRIMITIVE_NAME,
            message=(
                f"module {name!r} has no tanzil dependencies and is "
                f"not depended on by any other module in the "
                f"project. Per Furqan D9/D20 (Case G3, orphan "
                f"module), this is structurally ambiguous: the "
                f"module is in scope for the project but plays no "
                f"role in the dependency graph. It may be a stub, "
                f"a leftover after a refactor, or a legitimate "
                f"standalone helper - the advisory alerts the "
                f"developer; the strict-variant gate does not fire."
            ),
            location=self.modules[name].bismillah.span,
            suggestion=(
                f"if {name!r} is intentionally standalone (a CLI "
                f"entry point, a tooling helper), document the "
                f"intent in its bismillah block. If it is meant to "
                f"be consumed by other modules, add a "
                f"`depends_on: {name}` line in the consumer's "
                f"tanzil block. If it is leftover, remove the file."
            ),
        )


# ---------------------------------------------------------------------------
# Per-module checker driver
# ---------------------------------------------------------------------------

def _check_single_module(
    module: Module,
    *,
    imported_types: frozenset[str] = frozenset(),
) -> list[GraphDiagnostic]:
    """Run all 9 per-module checkers on a single module, passing
    ``imported_types`` to ring-close so cross-module type references
    do not trigger R1.

    The additive-only checker is NOT run here: it requires a prior-
    version sidecar comparison, which the project-level driver does
    not provide. Cross-version checks belong to a separate workflow.
    """
    from furqan.checker import (
        check_all_paths_return,
        check_bismillah,
        check_incomplete,
        check_mizan,
        check_return_type_match,
        check_ring_close,
        check_status_coverage,
        check_tanzil,
        check_zahir_batin,
    )

    diagnostics: list[GraphDiagnostic] = []
    diagnostics.extend(check_bismillah(module))
    diagnostics.extend(check_zahir_batin(module))
    diagnostics.extend(check_mizan(module))
    diagnostics.extend(check_tanzil(module))
    diagnostics.extend(
        check_ring_close(module, imported_types=imported_types)
    )
    diagnostics.extend(check_incomplete(module))
    diagnostics.extend(check_status_coverage(module))
    diagnostics.extend(check_return_type_match(module))
    diagnostics.extend(check_all_paths_return(module))
    return diagnostics


__all__ = [
    "GRAPH_PRIMITIVE_NAME",
    "GraphDiagnostic",
    "Project",
]
