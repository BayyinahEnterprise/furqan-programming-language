"""
All-paths-return analysis - Furqan D24.

Ring-close R3 (Phase 2.9) checks that a return statement EXISTS
somewhere in a typed function's body. D24 checks that EVERY
control-flow path through the function reaches a return statement.
The two are deliberately separate: R3 catches the total absence
("you have no return at all"), D24 catches the partial absence
("you have a return on some paths but not all").

The analysis is exact for the current grammar. Furqan has exactly
one branching construct: :class:`IfStmt` with an optional else-arm
(D15, v0.7.1). There are no loops, no switch/match, no exceptions,
no early exits other than ``return``. Under these constraints,
all-paths-return can be computed without a control-flow graph - a
direct structural recursion suffices and gives exact (not
approximate) results.

The recurrence:

* A statement sequence all-paths-returns iff
  - it contains a top-level :class:`ReturnStmt`, OR
  - it contains an :class:`IfStmt` with a non-empty ``else_body``
    where BOTH the if-body and the else-body all-paths-return.
* An :class:`IfStmt` WITHOUT an else-arm cannot satisfy the gate
  on its own: the missing-else path is an implicit fall-through.
  However, a sequence containing an else-less IfStmt followed by a
  bare return DOES satisfy the gate, because the loop that walks
  the sequence continues past the IfStmt and finds the return.
* A :class:`CallStmt` never returns a value. It does not contribute
  to path coverage.

When future grammar adds loops, match/switch, or early-exit forms,
D24 needs extension. For Phase 3+, that is D29 (full CFG). For
now, exact within the current grammar is the right discipline.

One checker case:

**Case P1 - Missing return path (Marad).**
A function declares a return type, has at least one return
statement in its body (passes ring-close R3), but does NOT all-
paths-return. Some control-flow path falls through with no return.

What this checker does NOT do (deferred):

* **Unreachable-code detection.** A return statement followed by
  more statements is not flagged. Unreachable-code analysis is a
  separate Phase 3 tool.
* **Loop-based control flow.** Furqan has no loops yet.
* **Exception/error paths.** Furqan has no exceptions.
* **Branch-level exhaustiveness on union types.** Whether each
  arm of the union is produced by some path is D26.
"""

from __future__ import annotations

from furqan.errors.marad import Marad, MaradError
from furqan.parser.ast_nodes import (
    FunctionDef,
    IfStmt,
    Module,
    ReturnStmt,
)


PRIMITIVE_NAME: str = "all_paths_return"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_all_paths_return(module: Module) -> list[Marad]:
    """Run the all-paths-return check over a parsed :class:`Module`.

    Returns one :class:`Marad` per function where a return type is
    declared, at least one return statement exists, but not every
    control-flow path reaches a return. Functions with no declared
    return type are skipped (D24 has no contract). Functions with
    zero returns are also skipped - that case is ring-close R3's
    territory; surfacing both R3 and P1 on the same function would
    be a double diagnostic.
    """
    diagnostics: list[Marad] = []
    for fn in module.functions:
        if fn.return_type is None:
            continue
        if not _any_return_exists(fn.statements):
            # R3 territory. Skip to avoid double-reporting.
            continue
        if not _all_paths_return(fn.statements):
            diagnostics.append(_p1_missing_path_marad(fn))
    return diagnostics


def check_all_paths_return_strict(module: Module) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    P1 marad. Returns ``module`` unchanged on a clean check
    (for fluent-style call chaining)."""
    diagnostics = check_all_paths_return(module)
    if diagnostics:
        raise MaradError(diagnostics[0])
    return module


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _all_paths_return(statements: tuple) -> bool:
    """True iff every control-flow path through this statement
    sequence reaches a :class:`ReturnStmt`.

    The walk is order-sensitive: when we encounter an IfStmt with a
    qualifying both-branches-return shape, the sequence terminates
    on it and we return True. Otherwise we keep walking, looking
    for a top-level return that covers any earlier else-less
    fall-through. If the loop exhausts the sequence without finding
    either, the sequence has at least one path with no return.
    """
    for stmt in statements:
        if isinstance(stmt, ReturnStmt):
            return True
        if isinstance(stmt, IfStmt):
            if (
                stmt.else_body
                and _all_paths_return(stmt.body)
                and _all_paths_return(stmt.else_body)
            ):
                return True
            # IfStmt without else, OR with else but at least one
            # branch lacking return: the IfStmt does not by itself
            # cover all paths. Fall through to the next statement
            # in the sequence and let a later top-level return
            # close the gap if one exists.
    return False


def _any_return_exists(statements: tuple) -> bool:
    """True iff any :class:`ReturnStmt` appears anywhere in the
    statement tree (recursing into IfStmt body and else_body).

    Mirrors ring-close's ``_statements_contain_return``. Replicated
    locally rather than imported because the ring-close helper is
    underscore-prefixed (private). The behaviour is identical and
    pinned by tests against the other implementation.
    """
    for stmt in statements:
        if isinstance(stmt, ReturnStmt):
            return True
        if isinstance(stmt, IfStmt):
            if _any_return_exists(stmt.body):
                return True
            if _any_return_exists(stmt.else_body):
                return True
    return False


# ---------------------------------------------------------------------------
# Marad construction
# ---------------------------------------------------------------------------

def _p1_missing_path_marad(fn: FunctionDef) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} declares a return type and has "
            f"at least one `return` statement in its body, but not "
            f"every control-flow path reaches a return. Per Furqan "
            f"D24 (Case P1 - missing return path), the function "
            f"falls through silently on at least one path. Common "
            f"shapes: an `if` block whose body returns but with no "
            f"`else` branch and no trailing return after the `if`; "
            f"an `if`/`else` where one branch returns and the other "
            f"runs a side-effect call without returning. The "
            f"signature promises a value on every invocation; the "
            f"body does not deliver one on every path."
        ),
        location=fn.span,
        minimal_fix=(
            f"either add an `else` branch to the offending `if` "
            f"with a `return` statement, or add a `return` after "
            f"the `if` block to cover the fall-through path. If "
            f"the function should not always return (for example, "
            f"a logger or side-effect orchestrator), remove the "
            f"declared return type instead - a void function is "
            f"not subject to D24. Note: this differs from "
            f"ring-close R3, which fires on ZERO returns; D24 "
            f"fires on PARTIAL return coverage."
        ),
        regression_check=(
            f"after the fix, re-run the all-paths-return check; "
            f"function {fn.name!r} must produce zero P1 marads. "
            f"Verify that ring-close R3 (presence) and D22 "
            f"(return-type matching) still pass on the function - "
            f"adding an else branch may activate scan-incomplete "
            f"Case A guards on bare-Integrity returns under the "
            f"flipped polarity (D15)."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "check_all_paths_return",
    "check_all_paths_return_strict",
]
