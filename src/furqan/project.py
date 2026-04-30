"""
Multi-module project graph, Furqan D9/D20 (Phase 1).

A :class:`Project` parses multiple ``.furqan`` files, builds the
dependency graph from each module's tanzil declarations, and provides
the entry points for cross-module analysis. Three graph-level checker
cases ship in this module:

* **Case G1, missing dependency target (Marad).** A tanzil block
  declares ``depends_on: X`` but no module named ``X`` exists in the
  project. The dependency points to nothing.
* **Case G2, cross-module cycle (Marad).** The dependency graph
  contains a cycle (A depends on B, B depends on A, or longer
  chains). No valid build ordering exists; the cycle makes
  topological sort impossible.
* **Case G3, orphan module (Advisory).** A module has no tanzil
  declarations and no other module depends on it. It is disconnected
  from the dependency graph. Advisory rather than Marad: the module
  may legitimately be the project entry point or a standalone
  utility.

Per-module checkers (the existing nine: bismillah, zahir_batin,
mizan, tanzil, ring_close, incomplete, status_coverage,
return_type_match, all_paths_return) are not modified. The Project
class orchestrates them when directory mode is invoked from the CLI;
each module's structural diagnostics still come from the same
checker functions that single-file mode runs.

What this module does NOT do (deferred to D23 / Phase 3):

* Cross-module type resolution. Ring-close R1 still fires for any
  type not defined in the current module, even if the type is
  defined in a declared dependency. D23 (Phase 2 of multi-module
  support) will use the graph from this module to resolve type
  references across module boundaries.
* Cross-module status-coverage propagation. D11 still operates on a
  single module. Phase 3 will extend status-coverage tracking to
  follow function calls across module boundaries, again using the
  graph from this module as its foundation.
* External-dependency declarations. G1 fires on every dependency
  target not present in the project. There is currently no syntax
  for marking a dependency as external (vendored, from a registry,
  etc.). When that surface lands, G1 will gain an exception path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Union

from furqan.errors.marad import Advisory, Marad
from furqan.parser import parse
from furqan.parser.ast_nodes import Module, SourceSpan


PRIMITIVE_NAME: str = "graph"


# A graph diagnostic is either a Marad (G1 missing target, G2 cycle)
# or an Advisory (G3 orphan). The union mirrors the tanzil checker's
# return-type shape.
GraphDiagnostic = Union[Marad, Advisory]


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class Project:
    """A collection of parsed ``.furqan`` modules with a dependency graph.

    A Project is keyed by each module's bismillah name. Two files
    declaring the same bismillah name overwrite each other in
    :attr:`modules`; the second :meth:`add_file` call wins. (Detection
    of duplicate-name conflicts across files is deferred; the current
    contract assumes well-formed input where bismillah names are
    unique per project.)

    The class is mutable on the file-add surface but the dependency
    graph is recomputed from scratch on every call to
    :meth:`dependency_graph` or :meth:`check_graph`. No caching: the
    cost is linear in module count and the simplicity is worth more
    than the optimization at this size.
    """

    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}
        self.file_paths: dict[str, Path] = {}

    # ---- File loading -----------------------------------------------------

    def add_file(self, path: Path) -> Module:
        """Parse a ``.furqan`` file and add it to the project.

        Raises whatever the parser raises on malformed input
        (TokenizeError, ParseError); callers that want to continue
        on parse failure should wrap this call.
        """
        source = path.read_text(encoding="utf-8")
        module = parse(source, file=str(path))
        name = module.bismillah.name
        self.modules[name] = module
        self.file_paths[name] = path
        return module

    def add_directory(self, directory: Path) -> list[Module]:
        """Parse all ``.furqan`` files in ``directory`` (non-recursive).

        Files are loaded in sorted-path order for determinism. Empty
        directories return an empty list and do not error.
        """
        modules: list[Module] = []
        for path in sorted(directory.glob("*.furqan")):
            modules.append(self.add_file(path))
        return modules

    # ---- Graph construction ----------------------------------------------

    def dependency_graph(self) -> dict[str, list[str]]:
        """Build the adjacency list from tanzil declarations.

        Returns a dict mapping each module name in the project to the
        ordered list of names it depends on. Modules with no tanzil
        block (or with an empty tanzil block) map to an empty list.
        Dependency order within a module preserves source order;
        duplicate ``depends_on:`` entries (caught by the per-module
        T2 check) are reflected as repeated names in the list.
        """
        graph: dict[str, list[str]] = {}
        for name, module in self.modules.items():
            deps: list[str] = []
            for decl in module.tanzil_decls:
                for entry in decl.dependencies:
                    deps.append(entry.module_path)
            graph[name] = deps
        return graph

    def topological_order(self) -> list[str] | None:
        """Return modules in dependency order, or ``None`` on cycle.

        Uses Kahn's algorithm. Edge semantics: if module A declares
        ``depends_on: B``, then B must be built before A. The
        in-degree counted on each node is the number of OTHER nodes
        that node depends on (i.e. the number of prerequisites it
        still has unsatisfied). A node is ready when its in-degree
        hits zero.

        Returns the sorted list on success; returns ``None`` if a
        cycle prevents a complete sort. The caller can then invoke
        :meth:`_find_cycle` for the named cycle path.

        Edges to modules outside the project (i.e. missing dependency
        targets) are ignored for ordering purposes; G1 reports them
        separately. Within-project edges drive the sort.
        """
        graph = self.dependency_graph()
        in_degree: dict[str, int] = {name: 0 for name in graph}
        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1

        # Stable order: process names in sorted order at each step
        # so the topological sort is deterministic across runs.
        ready = sorted(n for n, d in in_degree.items() if d == 0)
        ordered: list[str] = []
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            # Decrement in-degree of every node that depends on
            # ``current`` (i.e. has ``current`` in its dep list).
            for name, deps in graph.items():
                if name in ordered:
                    continue
                if current in deps:
                    in_degree[name] -= 1
                    if in_degree[name] == 0 and name not in ready:
                        ready.append(name)
            ready.sort()

        if len(ordered) == len(graph):
            return ordered
        return None

    # ---- Graph checking --------------------------------------------------

    def check_graph(self) -> list[GraphDiagnostic]:
        """Run cross-module graph checks (G1, G2, G3).

        Returns a flat list of :class:`Marad` and :class:`Advisory`
        records. Order: G1 records first (one per missing target),
        then G2 (at most one per cycle, all involved modules named
        in the diagnosis), then G3 advisories for orphans.
        """
        diagnostics: list[GraphDiagnostic] = []
        graph = self.dependency_graph()

        # --- G1, missing dependency targets ---
        for name, module in self.modules.items():
            for decl in module.tanzil_decls:
                for entry in decl.dependencies:
                    if entry.module_path not in self.modules:
                        diagnostics.append(
                            _g1_missing_target_marad(
                                referrer=name,
                                tanzil_block=decl.name,
                                missing=entry.module_path,
                                span=entry.span,
                            )
                        )

        # --- G2, cross-module cycle ---
        for cycle in _find_all_cycles(graph):
            diagnostics.append(
                _g2_cycle_marad(cycle, self._span_for(cycle[0]))
            )

        # --- G3, orphan modules (Advisory) ---
        depended_on: set[str] = set()
        for deps in graph.values():
            for dep in deps:
                depended_on.add(dep)
        for name, module in self.modules.items():
            has_outgoing = any(
                decl.dependencies for decl in module.tanzil_decls
            )
            has_incoming = name in depended_on
            if not has_outgoing and not has_incoming and len(self.modules) > 1:
                diagnostics.append(
                    _g3_orphan_advisory(name, module.bismillah.span)
                )

        return diagnostics

    # ---- Helpers ----------------------------------------------------------

    def _span_for(self, module_name: str) -> SourceSpan:
        """Return a SourceSpan that points at the named module's
        bismillah block, used as the diagnostic location for graph
        marads that span multiple modules."""
        module = self.modules[module_name]
        return module.bismillah.span


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def _find_all_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Return one representative cycle per strongly-connected
    component containing a cycle.

    Implementation is a depth-first traversal with a stack tracking
    the current path. When a back edge is found (an edge to a node
    already on the current path), the cycle is the path slice from
    that node forward, plus the back-edge target as the closing
    node. Each detected cycle is canonicalized by rotating so its
    lexicographically-smallest member is first; this collapses
    duplicates produced by different DFS entry points into the same
    SCC.
    """
    cycles: list[list[str]] = []
    seen_canonical: set[tuple[str, ...]] = set()

    def visit(
        node: str,
        stack: list[str],
        on_stack: set[str],
        visited: set[str],
    ) -> None:
        stack.append(node)
        on_stack.add(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue  # missing target, G1 handles it
            if dep in on_stack:
                # Back edge, extract cycle.
                idx = stack.index(dep)
                cycle = stack[idx:] + [dep]
                canonical = _canonicalize_cycle(cycle)
                key = tuple(canonical)
                if key not in seen_canonical:
                    seen_canonical.add(key)
                    cycles.append(canonical)
            elif dep not in visited:
                visit(dep, stack, on_stack, visited)
        stack.pop()
        on_stack.discard(node)
        visited.add(node)

    visited: set[str] = set()
    for start in sorted(graph.keys()):
        if start not in visited:
            visit(start, [], set(), visited)
    return cycles


def _canonicalize_cycle(cycle: list[str]) -> list[str]:
    """Rotate ``cycle`` so its lexicographically-smallest node is
    first, then re-append that node at the end so the rendering
    reads as a closed loop (e.g. ``A -> B -> A``).

    The input is expected to already be a closed loop (last element
    equals first); the function strips the trailing duplicate, finds
    the rotation index, rotates, and re-appends the head.
    """
    if cycle and cycle[0] == cycle[-1]:
        body = cycle[:-1]
    else:
        body = list(cycle)
    if not body:
        return []
    smallest_idx = min(range(len(body)), key=lambda i: body[i])
    rotated = body[smallest_idx:] + body[:smallest_idx]
    return rotated + [rotated[0]]


# ---------------------------------------------------------------------------
# Diagnostic construction
# ---------------------------------------------------------------------------

def _g1_missing_target_marad(
    *,
    referrer: str,
    tanzil_block: str,
    missing: str,
    span: SourceSpan,
) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"module {referrer!r} declares a dependency on "
            f"{missing!r} in tanzil block {tanzil_block!r}, but no "
            f"module named {missing!r} was found in the project. "
            f"Per Furqan multi-module Case G1 (missing dependency "
            f"target), every depended-on module must exist somewhere "
            f"in the compilation set. The cross-module extension of "
            f"the tanzil T1/T2 well-formedness rules: T1 catches "
            f"self-dependency, T2 catches duplicates within a single "
            f"module, and G1 catches references to modules that are "
            f"not present in the project."
        ),
        location=span,
        minimal_fix=(
            f"either add a .furqan file declaring "
            f"`bismillah {missing} {{ ... }}` to the project, or "
            f"remove the `depends_on: {missing}` line from tanzil "
            f"block {tanzil_block!r} if the dependency is no longer "
            f"needed. If the dependency is intended as external "
            f"(vendored or from a registry), note that external-"
            f"dependency declarations are not yet supported, see the "
            f"D9/D20 deferred items."
        ),
        regression_check=(
            f"after the fix, re-run `furqan check <directory>`; the "
            f"graph-level checker must produce zero G1 marads. "
            f"Verify the project still parses and that all "
            f"per-module checkers continue to pass."
        ),
    )


def _g2_cycle_marad(cycle: list[str], span: SourceSpan) -> Marad:
    chain = " -> ".join(cycle)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"cross-module dependency cycle detected: {chain}. Per "
            f"Furqan multi-module Case G2 (cross-module cycle), the "
            f"dependency graph must be acyclic so that a topological "
            f"build order exists. Each module in the cycle "
            f"transitively depends on itself, no module can be "
            f"compiled first. The single-module form of this rule "
            f"is tanzil T1 (self-dependency); G2 is its multi-module "
            f"generalization."
        ),
        location=span,
        minimal_fix=(
            f"break the cycle by removing one `depends_on:` edge "
            f"along the chain {chain}. Identify the module in the "
            f"cycle whose dependency on its successor is least "
            f"essential (or factor the shared logic into a new "
            f"module that all participants depend on, removing the "
            f"back-edge that closes the loop)."
        ),
        regression_check=(
            f"after the fix, re-run `furqan check <directory>`; the "
            f"graph-level checker must produce zero G2 marads and "
            f"`Project.topological_order()` must return a non-None "
            f"list covering every module in the project."
        ),
    )


def _g3_orphan_advisory(name: str, span: SourceSpan) -> Advisory:
    return Advisory(
        primitive=PRIMITIVE_NAME,
        message=(
            f"module {name!r} has no tanzil declarations and no "
            f"other module depends on it. It is disconnected from "
            f"the project's dependency graph (Case G3, orphan "
            f"module). This is informational, not a structural "
            f"violation: the module may legitimately be the project "
            f"entry point or a standalone utility."
        ),
        location=span,
        suggestion=(
            f"if {name!r} is the intended entry point, no action is "
            f"needed; this advisory is the developer's confirmation "
            f"that the orphan status is recognized. If {name!r} is "
            f"intended to be reachable from the rest of the project, "
            f"add a `tanzil {{ ... }}` block declaring its "
            f"dependencies, or have another module declare "
            f"`depends_on: {name}`."
        ),
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "GraphDiagnostic",
    "PRIMITIVE_NAME",
    "Project",
]
