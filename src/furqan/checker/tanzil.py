"""
Tanzil build-ordering checker — Furqan Phase 2.8 primitive #6.

Per the Furqan thesis, tanzil governs the order in which modules
are compiled and verified. The Quran was revealed progressively
(*tanzilan*; Al-Isra 17:106 — *"And it is a Quran which We have
divided, that you might recite it to the people over a prolonged
period, and We have revealed it progressively"*); later revelations
depended on earlier ones being understood. In Furqan, a module
declares its build-order dependencies in a tanzil block, and the
checker verifies the declaration's well-formedness.

Three checker cases:

**Case T1 — Self-dependency.**
A tanzil block declares ``depends_on:`` referencing the module's
own bismillah name. The trivial cycle: the smallest possible
circular dependency. Multi-module cycles (A depends B depends A)
are D9 work; T1 catches the single-module case at compile time
without requiring a cross-module graph.

**Case T2 — Duplicate dependency.**
A tanzil block lists the same module path more than once. The
second declaration is either a redundant paste or an attempt to
declare two distinct dependencies that share a name — both shapes
deserve a loud diagnostic. First-occurrence-wins semantics: the
first entry is treated as canonical; subsequent occurrences fire
the marad. Same discipline as Mizan M2 and additive-only's
catalog-duplicate handling.

**Case T3 — Empty block (Advisory, not Marad).**
A tanzil block with zero dependency entries. This is not an error
— a module legitimately may have been evaluated for build
ordering and concluded it has no external dependencies. But the
empty declaration is structurally ambiguous (intentional zero or
left-as-stub), so the checker emits an :class:`Advisory`:
informational evidence the developer should review, not a
structural prohibition. Same pattern as the additive-only
checker's undeclared-rename Advisory.

Routing note (M3-equivalent for Tanzil). Unknown field heads in
the dependency position (anything other than the ``depends_on``
keyword) are enforced at the *parser* layer, not in this checker.
By the time a TanzilDecl reaches `check_tanzil`, every entry is
canonical by construction; an unknown-field guard inside this
function would be structurally unreachable. Honest layering: the
parser owns token-shape invariants; the checker owns semantic
invariants over a well-formed AST.

What this checker does NOT do (deferred to D9 / Phase 3+):

* Cross-module cycle detection (e.g., A → B → A across modules).
* Verification that depended-on modules actually exist somewhere
  in the compilation set.
* Topological sort computation over the dependency graph.
* Version-constraint declarations on dependencies (D21).
"""

from __future__ import annotations

from typing import Iterable, Union

from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser.ast_nodes import (
    DependencyEntry,
    Module,
    TanzilDecl,
)


PRIMITIVE_NAME: str = "tanzil_well_formed"


# A tanzil diagnostic is either a Marad (T1 self-dependency, T2
# duplicate) or an Advisory (T3 empty block). The union is the
# checker's external return type.
TanzilDiagnostic = Union[Marad, Advisory]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_tanzil(module: Module) -> list[TanzilDiagnostic]:
    """Run the Tanzil well-formedness check over a parsed
    :class:`Module`.

    Returns a list of :class:`Marad` and/or :class:`Advisory`
    records. An empty list means every tanzil block in the module
    is structurally well-formed (no self-dependency, no
    duplicates, no empty block). Marads are violations that fail
    the strict-variant gate; Advisories are informational and do
    not.
    """
    diagnostics: list[TanzilDiagnostic] = []
    for decl in module.tanzil_decls:
        diagnostics.extend(
            _check_tanzil_decl(decl, module.bismillah.name)
        )
    return diagnostics


def check_tanzil_strict(module: Module) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    Marad. Advisories do NOT trigger the strict path (they are
    informational by design). Returns ``module`` unchanged on a
    clean check (for fluent-style call chaining)."""
    diagnostics = check_tanzil(module)
    for d in diagnostics:
        if isinstance(d, Marad):
            raise MaradError(d)
    return module


# ---------------------------------------------------------------------------
# Per-decl checking
# ---------------------------------------------------------------------------

def _check_tanzil_decl(
    decl: TanzilDecl,
    self_module_name: str,
) -> Iterable[TanzilDiagnostic]:
    """Yield well-formedness diagnostics for a single TanzilDecl.

    Rule order (T3 → T1 → T2): T3 short-circuits on empty blocks
    because the other rules have nothing to inspect when the
    dependency list is empty. T1 (self-dependency) and T2
    (duplicate) are independent and fire in source order over
    the dependency tuple.
    """
    # --- T3 — empty block (Advisory) ---
    if not decl.dependencies:
        yield _t3_empty_advisory(decl)
        return  # no further checks on an empty block

    # --- T1 — self-dependency ---
    for dep in decl.dependencies:
        if dep.module_path == self_module_name:
            yield _t1_self_dependency_marad(decl, dep, self_module_name)

    # --- T2 — duplicate dependency ---
    seen: dict[str, DependencyEntry] = {}
    for dep in decl.dependencies:
        if dep.module_path in seen:
            yield _t2_duplicate_marad(decl, dep)
        else:
            seen[dep.module_path] = dep


# ---------------------------------------------------------------------------
# Marad / Advisory construction
# ---------------------------------------------------------------------------

def _t1_self_dependency_marad(
    decl: TanzilDecl,
    dep: DependencyEntry,
    self_module_name: str,
) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"tanzil block {decl.name!r} declares a self-dependency: "
            f"`depends_on: {dep.module_path}` references the module's "
            f"own bismillah name {self_module_name!r}. Per Furqan "
            f"thesis (Case T1 — self-dependency), this is the trivial "
            f"cycle — the smallest possible circular dependency. The "
            f"order of revelation matters precisely because later "
            f"depends on earlier; a module depending on itself has no "
            f"place in the build sequence. Multi-module cycles are "
            f"caught by Phase 3+ graph analysis (D9); T1 catches the "
            f"single-module case at compile time."
        ),
        location=dep.span,
        minimal_fix=(
            f"remove the `depends_on: {dep.module_path}` line from "
            f"the tanzil block. If the dependency was intended to "
            f"reference a different module that happens to share the "
            f"name {self_module_name!r}, rename one of the two "
            f"modules so the dependency is unambiguous."
        ),
        regression_check=(
            f"after the fix, re-run the tanzil well-formedness "
            f"check; the block must produce zero marads. Verify that "
            f"the build ordering still expresses the developer's "
            f"actual dependency graph."
        ),
    )


def _t2_duplicate_marad(
    decl: TanzilDecl,
    dep: DependencyEntry,
) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"tanzil block {decl.name!r} contains duplicate "
            f"dependency {dep.module_path!r}. Per Furqan thesis "
            f"(Case T2 — duplicate dependency), each depended-on "
            f"module appears exactly once. The second declaration "
            f"would be silently redundant under any 'last write "
            f"wins' convention; the duplication is either a paste "
            f"error or two distinct dependencies that happen to "
            f"share a name — both shapes deserve a loud diagnostic."
        ),
        location=dep.span,
        minimal_fix=(
            f"remove the duplicate `depends_on: {dep.module_path}` "
            f"line, or if the two intended distinct dependencies, "
            f"rename one of the depended-on modules so the names "
            f"are unambiguous."
        ),
        regression_check=(
            f"after the fix, re-run the tanzil well-formedness "
            f"check; the block must produce zero marads."
        ),
    )


def _t3_empty_advisory(decl: TanzilDecl) -> Advisory:
    return Advisory(
        primitive=PRIMITIVE_NAME,
        message=(
            f"tanzil block {decl.name!r} declares zero dependencies. "
            f"Per Furqan thesis (Case T3 — empty block), this is not "
            f"an error: a module may legitimately have no build-order "
            f"dependencies. But the empty block is structurally "
            f"ambiguous — did the developer intend zero dependencies, "
            f"or leave the block as a stub for later population?"
        ),
        location=decl.span,
        suggestion=(
            f"if the module genuinely has no build-order "
            f"dependencies, consider removing the empty tanzil "
            f"block entirely (its absence carries the same "
            f"semantics, with one less surface to maintain). If "
            f"dependencies are intended but not yet declared, add "
            f"the `depends_on: <ModuleName>` lines."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "TanzilDiagnostic",
    "check_tanzil",
    "check_tanzil_strict",
]
