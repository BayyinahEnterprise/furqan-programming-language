"""
Ring-close (structural completion) checker — Furqan Phase 2.9 primitive #7.

The capstone of the seven-primitive program. Where the prior six
primitives each police a single discipline (bismillah scope, zahir/
batin layering, additive-only evolution, scan-incomplete honesty,
mizan three-valued calibration, tanzil build ordering), ring-close
verifies that the *whole module* coheres: every type referenced is
declared, every function with a declared output has a producing path,
every type declared finds a use, and a module that claims to exist
has something to say.

The thesis paper §6 names this *the closure of the ring*: a structure
in which each piece presupposes and is presupposed by the others.
Where a single primitive verifies a local invariant, ring-close
verifies the *whole-shape* invariant — the absence of which is the
defining failure mode of partial implementations across the
literature (a function returning ``Document`` with no ``Document``
type in scope; a type declared but unused; a function declaring
``-> T`` with no path that produces a ``T``).

This checker introduces NO new keywords, NO new AST nodes, and NO
parser changes. It is a pure whole-module pass over the AST surfaces
already established by Phases 2.3–2.8. The additive-only invariant is
preserved by construction: ring-close adds new public exports without
changing any existing one.

Four checker cases:

**Case R1 — Undefined type reference (Marad).**
A function signature (parameter or return type) names a type that is
neither (a) declared as a compound type elsewhere in the module, nor
(b) recognised as a builtin (``Integrity``, ``Incomplete``). The ring
is broken at the type-resolution edge: the function presupposes a
type that has nothing presupposing it.

**Case R2 — Empty module body (Advisory).**
A module declares zero functions and zero compound types. The
bismillah block alone (and any tanzil/mizan/additive_only metadata)
does not constitute a working module — there is nothing for the other
checkers to verify and nothing for the build pipeline to compile.
Advisory (not Marad): the module may legitimately exist as a stub
during development.

**Case R3 — Function declares a return type but has no return
statement (Marad).**
A function with ``-> T`` whose body lacks any ``ReturnStmt`` (walking
recursively into IfStmt bodies). The function promises an output it
has no path to produce. Phase 2.9 detection is *syntactic* — at least
one ``return`` anywhere in the body satisfies the gate. All-paths-
return analysis is registered as D24.

**Case R4 — Type declared but unreferenced (Advisory).**
A compound type that no function in the module references in its
parameter or return-type position. The type is structural dead code
*in this module*. Advisory (not Marad): the type may be intentionally
declared early for future use or exported for downstream modules to
consume.

Routing notes (M3-equivalent for ring-close):

* Type-name resolution is over (a) the names of declared compound
  types, plus (b) the two builtin names ``Integrity`` and
  ``Incomplete``. Parameter-type names that do not match either set
  trigger R1, EXCEPT for ones that arise inside a UnionType with a
  builtin partner — those are still resolved field-by-field.
* The Phase 2.9 checker does NOT verify that ``return`` expression
  types match the declared return type (registered as D22). It
  verifies only that *some* return statement is present.

What this checker does NOT do (deferred):

* **D22 — Return-expression type-vs-signature matching.** A function
  declared ``-> Document`` that returns ``Summary`` is not flagged.
  Phase 2.9 enforces presence; type matching requires expression
  type-inference that the checker layer does not yet implement.
* **D23 — Cross-module ring analysis.** R1's resolution is local: a
  type imported from another module would currently fire R1. Cross-
  module resolution requires the module-graph that D9 introduces.
* **D24 — All-paths-return analysis.** A function with ``if`` arms
  that each return but no else-branch syntactically satisfies R3 (at
  least one return is present), but at runtime falls through. Phase
  2.9 keeps R3 syntactic by design; control-flow analysis is a Phase
  3 concern.
"""

from __future__ import annotations

from typing import Iterable, Union

from furqan.checker.incomplete import (
    INCOMPLETE_TYPE_NAME,
    INTEGRITY_TYPE_NAME,
)
from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser.ast_nodes import (
    CompoundTypeDef,
    FunctionDef,
    IfStmt,
    Module,
    ReturnStmt,
    TypePath,
    UnionType,
)


PRIMITIVE_NAME: str = "ring_close"


# Builtin type names recognised by the ring-close checker. These are
# the two scan-incomplete union arms (Phase 2.6) and the only types
# that may legitimately appear in a function signature without a
# corresponding compound-type declaration in the module.
BUILTIN_TYPE_NAMES: frozenset[str] = frozenset({
    INTEGRITY_TYPE_NAME,
    INCOMPLETE_TYPE_NAME,
})


# A ring-close diagnostic is either a Marad (R1 undefined type, R3
# missing return) or an Advisory (R2 empty body, R4 unreferenced
# type). The union is the checker's external return type.
RingCloseDiagnostic = Union[Marad, Advisory]


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_ring_close(
    module: Module,
    *,
    imported_types: frozenset[str] = frozenset(),
) -> list[RingCloseDiagnostic]:
    """Run the ring-close check over a parsed :class:`Module`.

    Returns a list of :class:`Marad` and/or :class:`Advisory` records.
    An empty list means the module's structural ring is closed: every
    type referenced is declared, every function with a declared
    return type has a return statement, and every declared type is
    used. Marads (R1, R3) are violations that fail the strict-variant
    gate; Advisories (R2, R4) are informational.

    D23 (cross-module type resolution): the optional
    ``imported_types`` keyword argument extends R1 resolution to type
    names defined in this module's direct dependencies. A multi-
    module driver (the future ``Project.check_all`` from D9/D20)
    builds the set of compound type names exported by each direct
    dependency and passes them in. R1 then accepts a referenced type
    iff it is declared locally OR is a builtin OR is in
    ``imported_types``. The default empty frozenset preserves the
    single-module behaviour: every existing call site continues to
    work unchanged. Direct-only scoping is a deliberate design
    choice (matches Python, Rust, Go): a module sees types from its
    direct dependencies only, not transitive deps.
    """
    diagnostics: list[RingCloseDiagnostic] = []

    declared_type_names: set[str] = {t.name for t in module.compound_types}
    resolvable_type_names: set[str] = (
        declared_type_names | BUILTIN_TYPE_NAMES | imported_types
    )

    # --- R2 — empty module body (Advisory) ---
    # Run before the per-function passes: an empty body has no
    # functions to walk, and the early advisory frames the rest of
    # the diagnostics for the developer.
    if not module.functions and not module.compound_types:
        diagnostics.append(_r2_empty_body_advisory(module))
        return diagnostics  # nothing else to inspect

    # --- R1 — undefined type references in function signatures ---
    # --- R3 — missing return statement when return type declared ---
    for fn in module.functions:
        diagnostics.extend(_r1_check_function(fn, resolvable_type_names))
        if fn.return_type is not None and not _has_return_statement(fn):
            diagnostics.append(_r3_missing_return_marad(fn))

    # --- R4 — unreferenced type declarations (Advisory) ---
    referenced_type_names = _collect_referenced_type_names(module)
    for type_def in module.compound_types:
        if type_def.name not in referenced_type_names:
            diagnostics.append(_r4_unreferenced_type_advisory(type_def))

    return diagnostics


def check_ring_close_strict(
    module: Module,
    *,
    imported_types: frozenset[str] = frozenset(),
) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    Marad. Advisories (R2, R4) do NOT trigger the strict path - they
    are informational by design. Returns ``module`` unchanged on a
    clean check (for fluent-style call chaining).

    ``imported_types`` is forwarded to :func:`check_ring_close` for
    cross-module type resolution (D23). Default empty frozenset
    preserves single-module behaviour.
    """
    diagnostics = check_ring_close(module, imported_types=imported_types)
    for d in diagnostics:
        if isinstance(d, Marad):
            raise MaradError(d)
    return module


# ---------------------------------------------------------------------------
# Type-name extraction
# ---------------------------------------------------------------------------

def _extract_type_names(
    return_type: Union[TypePath, UnionType, None],
) -> tuple[tuple[str, object], ...]:
    """Return ``(name, span)`` pairs for every type referenced by a
    return-type clause.

    Handles the three return-type shapes Phase 2.x emits:
    * ``None`` — function has no declared return type (empty tuple).
    * :class:`TypePath` — single type; one pair.
    * :class:`UnionType` — two-arm union; two pairs (left, right).

    The ``span`` element of each pair is the source location of the
    *type-name occurrence*, not the surrounding signature — used for
    Marad ``location`` so the diagnostic points at the offending
    identifier itself.
    """
    if return_type is None:
        return ()
    if isinstance(return_type, TypePath):
        return ((return_type.base, return_type.span),)
    # UnionType: two TypePath arms.
    return (
        (return_type.left.base, return_type.left.span),
        (return_type.right.base, return_type.right.span),
    )


def _has_return_statement(fn: FunctionDef) -> bool:
    """True iff the function body contains at least one
    :class:`ReturnStmt`, recursing into :class:`IfStmt` bodies.

    Phase 2.9 detection is syntactic (D24 not yet implemented). A
    function with any single ``return`` anywhere in its statement
    tree satisfies the R3 gate; missing-else branches that
    syntactically permit fall-through are NOT flagged.
    """
    return _statements_contain_return(fn.statements)


def _statements_contain_return(statements: tuple) -> bool:
    """Recursive helper: True iff any ReturnStmt appears in this
    statement tuple or nested inside any IfStmt body or else-body.

    Phase 3.0 (D15) extended the recursion to descend into the
    optional ``else_body``. The else_body defaults to the empty
    tuple on pre-Phase-3.0 IfStmt constructions, so this loop is a
    no-op on those nodes — the additive-only invariant is preserved
    at the checker level.
    """
    for stmt in statements:
        if isinstance(stmt, ReturnStmt):
            return True
        if isinstance(stmt, IfStmt):
            if _statements_contain_return(stmt.body):
                return True
            if _statements_contain_return(stmt.else_body):
                return True
    return False


def _collect_referenced_type_names(module: Module) -> set[str]:
    """Return the set of type names referenced by *any* function in
    the module, in either parameter or return-type position.

    Used by R4 to identify declared types that no function consumes.
    Note: union-type arms are both counted as references — a type
    appearing only as an arm of a return-union is still referenced.
    """
    referenced: set[str] = set()
    for fn in module.functions:
        for param in fn.params:
            referenced.add(param.type_path.base)
        for name, _span in _extract_type_names(fn.return_type):
            referenced.add(name)
    return referenced


# ---------------------------------------------------------------------------
# R1 — undefined type reference
# ---------------------------------------------------------------------------

def _r1_check_function(
    fn: FunctionDef,
    resolvable_type_names: set[str],
) -> Iterable[Marad]:
    """Yield R1 marads for every type-name occurrence in the
    function's signature that does not resolve."""
    # Parameter types.
    for param in fn.params:
        if param.type_path.base not in resolvable_type_names:
            yield _r1_undefined_type_marad(
                type_name=param.type_path.base,
                location=param.type_path.span,
                context=f"parameter {param.name!r} of function {fn.name!r}",
            )
    # Return type (if declared).
    for name, span in _extract_type_names(fn.return_type):
        if name not in resolvable_type_names:
            yield _r1_undefined_type_marad(
                type_name=name,
                location=span,
                context=f"return type of function {fn.name!r}",
            )


def _r1_undefined_type_marad(
    type_name: str,
    location: object,
    context: str,
) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"the {context} references type {type_name!r}, but no "
            f"compound type with that name is declared in this "
            f"module and {type_name!r} is not a recognised builtin "
            f"({sorted(BUILTIN_TYPE_NAMES)}). Per Furqan thesis §6 "
            f"(Case R1 - undefined type reference), the structural "
            f"ring is broken at this edge: the signature presupposes "
            f"a type that has nothing presupposing it. A function "
            f"that declares an output of a type with no producing "
            f"declaration cannot be type-checked end-to-end."
        ),
        location=location,
        minimal_fix=(
            f"either declare a `type {type_name} {{ zahir {{ ... }} "
            f"batin {{ ... }} }}` block elsewhere in this module, or "
            f"change the {context} to use a type that is in scope "
            f"(a declared compound type or a builtin: "
            f"{sorted(BUILTIN_TYPE_NAMES)}). If {type_name!r} is "
            f"defined in another module, cross-module ring analysis "
            f"is registered as D23 (Phase 3+); for now, declare a "
            f"local type or import-equivalent."
        ),
        regression_check=(
            f"after the fix, re-run the ring-close check; this "
            f"function must produce zero R1 marads. Verify that all "
            f"other primitives' checks still pass, since changing a "
            f"signature can affect zahir/batin (Phase 2.4) and "
            f"additive-only (Phase 2.5) invariants."
        ),
    )


# ---------------------------------------------------------------------------
# R2 — empty module body (Advisory)
# ---------------------------------------------------------------------------

def _r2_empty_body_advisory(module: Module) -> Advisory:
    return Advisory(
        primitive=PRIMITIVE_NAME,
        message=(
            f"module {module.bismillah.name!r} declares zero "
            f"functions and zero compound types. Per Furqan thesis "
            f"§6 (Case R2 - empty module body), this is not an "
            f"error: a module may legitimately exist as a stub "
            f"during development, or as a build-order placeholder "
            f"that other modules depend on. But the empty body is "
            f"structurally ambiguous - the module's bismillah "
            f"declares a scope it has no shape to fulfill."
        ),
        location=module.bismillah.span,
        suggestion=(
            f"if the module is intentionally a stub, document this "
            f"in a comment or remove the module entirely until it "
            f"has structural content. If functions or types are "
            f"intended but not yet declared, add at least one "
            f"`type ... {{ zahir/batin }}` declaration or one "
            f"`fn ...` definition. A tanzil/mizan/additive_only "
            f"block alone does not satisfy the body-non-emptiness "
            f"criterion (those declare metadata, not structure)."
        ),
    )


# ---------------------------------------------------------------------------
# R3 — missing return statement
# ---------------------------------------------------------------------------

def _r3_missing_return_marad(fn: FunctionDef) -> Marad:
    return_type_repr = _format_return_type(fn.return_type)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} declares return type "
            f"{return_type_repr} but its body contains no `return` "
            f"statement (recursing into any nested if-blocks). Per "
            f"Furqan thesis §6 (Case R3 - missing return), the ring "
            f"is broken at the function level: the function "
            f"promises an output its control-flow has no path to "
            f"produce. Phase 2.9 detection is syntactic; all-paths-"
            f"return analysis is registered as D24."
        ),
        location=fn.span,
        minimal_fix=(
            f"either add a `return <expr>` statement to the function "
            f"body that produces a {return_type_repr} value, or "
            f"remove the `-> {return_type_repr}` clause from the "
            f"signature if the function is intentionally void. If "
            f"the function returns conditionally and you intended "
            f"each branch to terminate, ensure at least one "
            f"`return` is reachable syntactically (full all-paths "
            f"verification is D24, Phase 3+)."
        ),
        regression_check=(
            f"after the fix, re-run the ring-close check; the "
            f"function must produce zero R3 marads. Verify that "
            f"scan-incomplete (Phase 2.6) Case A still passes if "
            f"the return type is `Integrity | Incomplete` - the "
            f"two checkers compose, not collide."
        ),
    )


def _format_return_type(rt: Union[TypePath, UnionType, None]) -> str:
    """Render a return-type clause for use in diagnostic strings."""
    if rt is None:
        return "<none>"
    if isinstance(rt, TypePath):
        return rt.base
    return f"{rt.left.base} | {rt.right.base}"


# ---------------------------------------------------------------------------
# R4 — unreferenced type declaration (Advisory)
# ---------------------------------------------------------------------------

def _r4_unreferenced_type_advisory(type_def: CompoundTypeDef) -> Advisory:
    return Advisory(
        primitive=PRIMITIVE_NAME,
        message=(
            f"compound type {type_def.name!r} is declared but no "
            f"function in this module references it (neither as a "
            f"parameter type nor as a return type). Per Furqan "
            f"thesis §6 (Case R4 - unreferenced type), this is not "
            f"an error: the type may be intentionally declared "
            f"early for future use, or exported for downstream "
            f"modules to consume. But within the current module the "
            f"declaration is structural dead code, and the developer "
            f"should be aware."
        ),
        location=type_def.span,
        suggestion=(
            f"if {type_def.name!r} is intended for future use within "
            f"this module, add the function(s) that will reference "
            f"it. If the type is exported for downstream consumption "
            f"only, declare it explicitly via an `additive_only "
            f"module` `export` clause so the intent is structural "
            f"rather than implicit. Otherwise, remove the type "
            f"declaration to keep the module surface honest."
        ),
    )


__all__ = [
    "BUILTIN_TYPE_NAMES",
    "PRIMITIVE_NAME",
    "RingCloseDiagnostic",
    "check_ring_close",
    "check_ring_close_strict",
]
