"""
Scan-incomplete return-type checker — Furqan Phase 2.6 primitive #4.

Per the Furqan thesis paper §4 (Scan-Incomplete Honesty as a Return
Type, anchored on Al-Baqarah 2:286 — *"Allah does not burden a soul
beyond its capacity"*), a function whose declared return type is
``Integrity | Incomplete`` cannot return bare ``Integrity`` from a
path on which its own incompleteness signal was not syntactically
ruled out. The discipline is the language-level transposition of
Bayyinah's ``apply_scan_incomplete_clamp`` and the
``SCAN_INCOMPLETE_CLAMP = 0.5`` ceiling: a scanner that reports a
clean integrity score on a document it could not fully read is
producing a surface (the score) that diverges from the depth (the
scanner's epistemic state). Phase 2.6 catches the same divergence
at the function-signature level.

Two cases are enforced:

**Case A — Bare Integrity returned without ruling out incompleteness.**
A function with ``-> Integrity | Incomplete`` has at least one
``return Integrity`` whose enclosing path is not gated by an
``if not <expr>`` body. Phase 2.6 detection is *syntactic*: a path
"rules out incompleteness" iff its enclosing if-statement's
condition is a :class:`NotExpr`. The conservative rule produces
some false positives on legitimate code that uses unusual control-
flow shapes; those are registered as known limitations rather than
papered over (see `tests/fixtures/known_limitation/`).

**Case B — Incomplete literal missing required fields.**
An ``Incomplete { ... }`` constructor literal that omits any of the
three required fields (``reason``, ``max_confidence``,
``partial_findings``). The parser accepts any field set; the
checker (this layer) enforces required-field presence.

What this checker does NOT do (deferred to a later phase):

* **Consumer-side exhaustiveness checking.** A caller that ignores
  the ``Incomplete`` arm of a union return type is not flagged in
  Phase 2.6. The thesis paper §4 names this as the dual rule;
  implementing it requires control-flow analysis on call sites and
  is registered for Session 1.6 or Phase 3.
* **Numeric range validation on `max_confidence`.** The Phase-2.7
  Mizan primitive will check `0.0 <= max_confidence <= 1.0`. Phase
  2.6 accepts any numeric form.
* **Full control-flow analysis.** Phase 2.6 detection is syntactic
  on the enclosing if-statement only. Helper-extracted predicates,
  flag-variable guards, and other control-flow shapes outside the
  ``if not <expr>`` form will produce false-positive marads.
"""

from __future__ import annotations

from typing import Iterable

from furqan.errors.marad import Marad, MaradError
from furqan.parser.ast_nodes import (
    CallStmt,
    FunctionDef,
    IfStmt,
    IncompleteLiteral,
    IntegrityLiteral,
    Module,
    NotExpr,
    ReturnStmt,
    UnionType,
)


PRIMITIVE_NAME: str = "scan_incomplete"

# The required field set for an :class:`IncompleteLiteral`. The
# constructor must declare all three; absence of any is a Case B
# marad.
REQUIRED_INCOMPLETE_FIELDS: frozenset[str] = frozenset({
    "reason",
    "max_confidence",
    "partial_findings",
})

# Type names the checker recognises as the union arms. Phase 2.6
# does not promote these to keywords (NAMING.md §1.5 + LEXER.md §5);
# the checker recognises them by string-equality at the AST level.
INTEGRITY_TYPE_NAME: str = "Integrity"
INCOMPLETE_TYPE_NAME: str = "Incomplete"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_incomplete(module: Module) -> list[Marad]:
    """Run the scan-incomplete check over a parsed :class:`Module`.

    Returns a list of :class:`Marad` records, one per violation. An
    empty list means the module is structurally compliant with the
    thesis §4 producer-side discipline.
    """
    diagnostics: list[Marad] = []
    for fn in module.functions:
        diagnostics.extend(_check_function(fn))
    return diagnostics


def check_incomplete_strict(module: Module) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    marad. Returns ``module`` unchanged on a clean module."""
    diagnostics = check_incomplete(module)
    if diagnostics:
        raise MaradError(diagnostics[0])
    return module


# ---------------------------------------------------------------------------
# Per-function checking
# ---------------------------------------------------------------------------

def _check_function(fn: FunctionDef) -> Iterable[Marad]:
    """Yield scan-incomplete marads for a single function definition.

    The two cases are independent: Case A applies only to functions
    with a union return type; Case B applies to every Incomplete
    literal anywhere in the body, regardless of the function's
    declared return type. Both are emitted in a single body walk.
    """
    # Case A applies only to union-typed returns.
    is_union_typed = (
        isinstance(fn.return_type, UnionType)
        and _is_integrity_incomplete_union(fn.return_type)
    )

    # Walk every statement, tracking the enclosing-if-condition stack.
    yield from _walk_statements(
        statements=fn.statements,
        guard_stack=(),
        fn=fn,
        check_case_a=is_union_typed,
    )


def _walk_statements(
    *,
    statements: tuple,
    guard_stack: tuple,
    fn: FunctionDef,
    check_case_a: bool,
) -> Iterable[Marad]:
    """Recursive walk over a statement tree.

    ``guard_stack`` is a tuple of conditions guarding the current
    path: each entry is either ``"negated"`` (an ``if not <expr>``
    body) or ``"non-negated"`` (an ``if <expr>`` body where the
    condition is not a :class:`NotExpr`). A return-Integrity is
    accepted iff at least one ``"negated"`` guard is in the stack.
    """
    for stmt in statements:
        if isinstance(stmt, ReturnStmt):
            yield from _check_return(
                stmt=stmt,
                guard_stack=guard_stack,
                fn=fn,
                check_case_a=check_case_a,
            )
            continue
        if isinstance(stmt, IfStmt):
            entry = "negated" if stmt.negated else "non-negated"
            yield from _walk_statements(
                statements=stmt.body,
                guard_stack=guard_stack + (entry,),
                fn=fn,
                check_case_a=check_case_a,
            )
            # Phase 3.0 (D15) — descend into the else-body when
            # present. The else-body's effective guard is the
            # OPPOSITE polarity of the if-body's guard: if the
            # if-condition is `not <expr>` (negated, ruling out
            # incompleteness on the if-path), the else-body executes
            # exactly when `<expr>` is true (non-negated). The flip
            # is essential — without it, an `else { return Integrity }`
            # arm following an `if not encrypted` would be wrongly
            # treated as guarded, when in fact the else runs when
            # `encrypted` is true and bare Integrity in that arm is
            # exactly the producer-side dishonesty Case A detects.
            if stmt.else_body:
                else_entry = (
                    "non-negated" if stmt.negated else "negated"
                )
                yield from _walk_statements(
                    statements=stmt.else_body,
                    guard_stack=guard_stack + (else_entry,),
                    fn=fn,
                    check_case_a=check_case_a,
                )
            continue
        if isinstance(stmt, CallStmt):
            # Call statements do not produce return values, so neither
            # Case A nor Case B fires on them. They may carry
            # Incomplete literals as nested expressions in a future
            # extension, but Phase 2.6 grammar only places Incomplete
            # literals in return-statement value positions.
            continue


def _check_return(
    *,
    stmt: ReturnStmt,
    guard_stack: tuple,
    fn: FunctionDef,
    check_case_a: bool,
) -> Iterable[Marad]:
    """Check a single return statement for Case A and Case B
    violations."""
    value = stmt.value
    # Case A — bare Integrity return on a union-typed function
    # whose enclosing path does not negate an incompleteness
    # predicate.
    if check_case_a and isinstance(value, IntegrityLiteral):
        if "negated" not in guard_stack:
            yield _case_a_marad(fn=fn, stmt=stmt, guard_stack=guard_stack)
    # Case B — Incomplete literal missing required fields. This
    # check applies regardless of the function's return type: an
    # Incomplete literal is always a structured diagnostic and must
    # always carry the three required fields.
    if isinstance(value, IncompleteLiteral):
        missing = REQUIRED_INCOMPLETE_FIELDS - {f.name for f in value.fields}
        for field_name in sorted(missing):
            yield _case_b_marad(
                fn=fn,
                literal=value,
                missing_field=field_name,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_integrity_incomplete_union(rt: UnionType) -> bool:
    """True iff the union's two arms are exactly Integrity and
    Incomplete (in either order)."""
    arms = {rt.left.base, rt.right.base}
    return arms == {INTEGRITY_TYPE_NAME, INCOMPLETE_TYPE_NAME}


# ---------------------------------------------------------------------------
# Marad construction
# ---------------------------------------------------------------------------

def _case_a_marad(
    *,
    fn: FunctionDef,
    stmt: ReturnStmt,
    guard_stack: tuple,
) -> Marad:
    """Construct the diagnostic for a Case A violation."""
    if not guard_stack:
        guard_description = (
            "the return statement is not enclosed by any `if` body"
        )
        recovery = (
            f"either wrap the return in `if not <incompleteness_predicate>"
            f"(...) {{ ... }}` so the predicate is explicitly ruled out, "
            f"or change {fn.name!r}'s declared return type from "
            f"`Integrity | Incomplete` to bare `Integrity` (and accept "
            f"that the function commits to always-complete processing)."
        )
    else:
        guard_description = (
            f"the return statement is enclosed by an `if` body, but the "
            f"condition is not negated (Phase 2.6 syntactic detection "
            f"requires the form `if not <expr>` for a path to count as "
            f"having ruled out incompleteness)."
        )
        recovery = (
            f"either invert the enclosing `if` condition to `if not "
            f"<predicate>(...)` (so the path is reached when the "
            f"incompleteness predicate is FALSE), or restructure the "
            f"function so the bare-Integrity return lives in the "
            f"negated branch instead of the predicate-holds branch."
        )
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} declares return type "
            f"`Integrity | Incomplete` but a return path produces "
            f"bare `Integrity` without first ruling out "
            f"incompleteness: {guard_description}. Per Furqan thesis "
            f"§4 (Case A - producer-side honesty), every "
            f"`return Integrity` on a union-typed function must be "
            f"guarded by an explicit incompleteness check. The rule "
            f"is the language-level form of Bayyinah's "
            f"`apply_scan_incomplete_clamp`: a scanner that reports "
            f"clean output on input it could not fully read is the "
            f"same shape of dishonesty this checker prevents at "
            f"compile time."
        ),
        location=stmt.span,
        minimal_fix=recovery,
        regression_check=(
            f"after the fix, re-run the scan-incomplete check; the "
            f"function must produce zero diagnostics. Verify that "
            f"every caller relying on the previous semantics is "
            f"updated to the new return-type contract."
        ),
    )


def _case_b_marad(
    *,
    fn: FunctionDef,
    literal: IncompleteLiteral,
    missing_field: str,
) -> Marad:
    """Construct the diagnostic for a Case B violation
    (Incomplete literal missing a required field)."""
    role_description = {
        "reason":           "describes WHY the scan was incomplete",
        "max_confidence":   "caps the confidence ceiling so downstream "
                            "consumers can apply the SCAN_INCOMPLETE_CLAMP "
                            "discipline",
        "partial_findings": "carries whatever was found before the scan "
                            "halted, so the diagnostic is actionable",
    }.get(missing_field, "is a required field of the Incomplete literal")
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"`Incomplete` literal in function {fn.name!r} is missing "
            f"required field {missing_field!r}, which "
            f"{role_description}. Per Furqan thesis §4 (Case B - "
            f"literal-shape honesty), every `Incomplete` value must "
            f"declare reason, max_confidence, and partial_findings. "
            f"An `Incomplete` value missing any of these is a "
            f"degenerate diagnostic - it signals incompleteness "
            f"without naming the cause, the bound, or the partial "
            f"results."
        ),
        location=literal.span,
        minimal_fix=(
            f"add the missing `{missing_field}: <value>` field to the "
            f"`Incomplete {{ ... }}` literal. If the value is not yet "
            f"known at the call site, use a placeholder identifier "
            f"(e.g. `partial_findings: empty_list`) and revisit when "
            f"the surrounding logic produces real content."
        ),
        regression_check=(
            f"after the fix, re-run the scan-incomplete check; the "
            f"function must produce zero diagnostics. Verify that "
            f"the new field's value matches the function's actual "
            f"epistemic state at the return site."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "REQUIRED_INCOMPLETE_FIELDS",
    "INTEGRITY_TYPE_NAME",
    "INCOMPLETE_TYPE_NAME",
    "check_incomplete",
    "check_incomplete_strict",
]
