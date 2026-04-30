"""
Return-expression type matching checker - Furqan D22.

Ring-close R3 (Phase 2.9) verifies that a function with a declared
return type contains at least one return statement. D22 is the
second half of that contract: it verifies that the return
statement's EXPRESSION matches the declared return type.

The check is deliberately shallow. Furqan has no runtime type
inference engine. The only expressions whose types are statically
knowable from the AST are the two scan-incomplete singletons:

* :class:`IntegrityLiteral` -> type name "Integrity"
* :class:`IncompleteLiteral` -> type name "Incomplete"

Every other expression shape (``IdentExpr``, ``StringLiteral``,
``NumberLiteral``, ``NotExpr``, ``BinaryComparisonExpr``,
``IdentList``) has no statically-determinable type at this phase.
D22 skips these. No diagnostic is emitted for an uncheckable
return expression. The checker is honest about what it can and
cannot verify; an Advisory case (M2) for uncheckable expressions
was considered and deliberately omitted because it would fire on
nearly every function that returns a variable, drowning the signal
in noise.

One checker case:

**Case M1 - Return type mismatch (Marad).**
A return expression's *inferred* type is a member of the inferrable
set ({Integrity, Incomplete}) but is NOT a member of the declared
return type's accepted set. The body contradicts the signature.
Examples:

* Function declares ``-> Integrity``, returns ``Incomplete {...}``.
* Function declares ``-> CustomType``, returns ``Integrity``.
* Function declares ``-> Document``, returns ``Incomplete {...}``.

Cases that are NOT M1:

* Function declares ``-> Integrity | Incomplete``, returns either
  arm. Both arms are members of the accepted set.
* Function declares any return type and returns ``some_variable``
  (an IdentExpr). The expression's type is not statically known;
  no diagnostic.

What this checker does NOT do (deferred):

* **Type inference on IdentExpr.** ``return result`` - what type
  is ``result``? Determining this requires data-flow analysis
  (tracing assignments and call return types). Phase 3+ work.
* **Cross-function return-type resolution.** ``return scan(file)``
  - what does ``scan`` return? Requires call-graph return-type
  propagation. Phase 3+ work (overlaps with D11/D23 cross-module
  graph).
* **Nested expression type inference.** ``return not x`` - what
  type is ``not x``? Boolean, but Furqan has no boolean type in
  the type system yet. Future work.

Together with ring-close R3 (presence) and D11 (consumer-side
propagation), D22 (return-type correctness) closes the return-type
contract across function boundaries:

* R3: you must return something (structural presence)
* D22: you must return the right type (type correctness)
* D11: your callers must propagate your type honestly (consumer
  exhaustiveness)
"""

from __future__ import annotations

from typing import Optional, Union

from furqan.checker.incomplete import (
    INCOMPLETE_TYPE_NAME,
    INTEGRITY_TYPE_NAME,
)
from furqan.errors.marad import Marad, MaradError
from furqan.parser.ast_nodes import (
    Expression,
    FunctionDef,
    IfStmt,
    IncompleteLiteral,
    IntegrityLiteral,
    Module,
    ReturnStmt,
    TypePath,
    UnionType,
)


PRIMITIVE_NAME: str = "return_type_match"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_return_type_match(module: Module) -> list[Marad]:
    """Run the return-type-match check over a parsed :class:`Module`.

    Returns a list of :class:`Marad` records, one per return
    statement whose statically-inferred expression type does not
    match the function's declared return type. An empty list means
    every checkable return expression matches its function's
    declared return type. Uncheckable expressions (anything that is
    not an IntegrityLiteral or IncompleteLiteral) produce no
    diagnostic.
    """
    diagnostics: list[Marad] = []
    for fn in module.functions:
        if fn.return_type is None:
            # No declared return type - ring-close R3 is responsible
            # for whether a return is required at all; D22 has no
            # contract to enforce here.
            continue
        accepted = _declared_type_names(fn.return_type)
        if not accepted:
            # Unknown return-type shape (defensive fallback - the
            # parser does not produce these today, but a future
            # additive return-type kind would land here without
            # firing spurious M1s).
            continue
        _check_statements(fn, fn.statements, accepted, diagnostics)
    return diagnostics


def check_return_type_match_strict(module: Module) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    M1 mismatch. Returns ``module`` unchanged on a clean check
    (for fluent-style call chaining)."""
    diagnostics = check_return_type_match(module)
    if diagnostics:
        raise MaradError(diagnostics[0])
    return module


# ---------------------------------------------------------------------------
# Recursive descent
# ---------------------------------------------------------------------------

def _check_statements(
    fn: FunctionDef,
    statements: tuple,
    accepted: frozenset[str],
    diagnostics: list[Marad],
) -> None:
    """Walk the statement tree, checking every ReturnStmt against
    the accepted type set. Recurses into IfStmt body AND else_body
    (the Phase 3.0 D15 additive extension - the empty-tuple default
    on else_body keeps this loop a no-op for pre-D15 IfStmts).
    """
    for stmt in statements:
        if isinstance(stmt, ReturnStmt):
            inferred = _infer_return_type(stmt.value)
            if inferred is not None and inferred not in accepted:
                diagnostics.append(
                    _m1_mismatch_marad(fn, stmt, inferred, accepted)
                )
        elif isinstance(stmt, IfStmt):
            _check_statements(fn, stmt.body, accepted, diagnostics)
            _check_statements(fn, stmt.else_body, accepted, diagnostics)


# ---------------------------------------------------------------------------
# Type inference and declared-type extraction
# ---------------------------------------------------------------------------

def _infer_return_type(expr: Expression) -> Optional[str]:
    """Infer the type name of a return expression, if statically
    determinable. Returns ``None`` for uncheckable expressions.

    Two cases are statically inferrable today:

    * :class:`IntegrityLiteral` -> "Integrity"
    * :class:`IncompleteLiteral` -> "Incomplete"

    Every other expression returns ``None``. The walker treats
    ``None`` as a no-op (no diagnostic emitted), which is the
    honest position when the checker cannot verify the match.
    """
    if isinstance(expr, IntegrityLiteral):
        return INTEGRITY_TYPE_NAME
    if isinstance(expr, IncompleteLiteral):
        return INCOMPLETE_TYPE_NAME
    return None


def _declared_type_names(
    return_type: Union[TypePath, UnionType, None],
) -> frozenset[str]:
    """Extract the set of type names a declared return type accepts.

    * ``TypePath("X")`` -> ``{"X"}`` (single accepted type)
    * ``UnionType(TypePath("A"), TypePath("B"))`` -> ``{"A", "B"}``
      (either arm accepted)
    * Anything else (including ``None``) -> ``frozenset()``

    The empty result is the signal "I cannot extract a type set;
    skip the function" - the public entry point honours it by
    short-circuiting before walking the body, so an unknown return-
    type kind never produces a spurious mismatch.
    """
    if isinstance(return_type, TypePath):
        return frozenset({return_type.base})
    if isinstance(return_type, UnionType):
        names: set[str] = set()
        if isinstance(return_type.left, TypePath):
            names.add(return_type.left.base)
        if isinstance(return_type.right, TypePath):
            names.add(return_type.right.base)
        return frozenset(names)
    return frozenset()


# ---------------------------------------------------------------------------
# Marad construction
# ---------------------------------------------------------------------------

def _m1_mismatch_marad(
    fn: FunctionDef,
    stmt: ReturnStmt,
    inferred: str,
    accepted: frozenset[str],
) -> Marad:
    accepted_repr = (
        next(iter(accepted)) if len(accepted) == 1
        else " | ".join(sorted(accepted))
    )
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} declares return type "
            f"{accepted_repr} but a return statement in its body "
            f"returns a {inferred} value. Per Furqan D22 (Case M1 - "
            f"return type mismatch), the body's return expression "
            f"contradicts the signature: the function promises a "
            f"value of type {accepted_repr} to its callers but "
            f"actually produces a {inferred}. Ring-close R3 (Phase "
            f"2.9) caught the missing-return failure mode; D22 "
            f"catches the wrong-return failure mode. Together they "
            f"make the return-type contract enforceable."
        ),
        location=stmt.span,
        minimal_fix=(
            f"either widen {fn.name!r}'s return type to include "
            f"{inferred} (for example, change "
            f"`-> {accepted_repr}` to `-> "
            f"{accepted_repr} | {inferred}` if the union shape "
            f"is honest about the function's behaviour), or "
            f"change this return statement to produce a value of "
            f"type {accepted_repr}. The two repair paths reflect "
            f"the same diagnostic question: is the signature "
            f"wrong, or is the body wrong? Pick the one that "
            f"matches what the function should actually do."
        ),
        regression_check=(
            f"after the fix, re-run the return-type-match check; "
            f"function {fn.name!r} must produce zero M1 marads. "
            f"Verify that ring-close R3 (Phase 2.9) and the scan-"
            f"incomplete checker (Phase 2.6) still pass - widening "
            f"a return type to a union may activate Case A guards "
            f"on bare-Integrity returns elsewhere in the body."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "check_return_type_match",
    "check_return_type_match_strict",
]
