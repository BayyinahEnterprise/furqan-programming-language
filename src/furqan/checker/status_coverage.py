"""
Status-coverage (consumer-side exhaustiveness) checker - Furqan D11.

The scan-incomplete checker (Phase 2.6) polices the PRODUCER side:
a function declaring ``-> Integrity | Incomplete`` must handle both
branches in its own body (Case A guards bare-Integrity returns,
Case B requires the literal's three required fields). This checker
polices the CONSUMER side: a function that CALLS a producer must
propagate the union honestly in its own return type.

The risk D11 catches is *status collapse*. Function A honestly
declares ``-> Integrity | Incomplete`` (the result might be
incomplete). Function B calls A but declares ``-> Integrity``
(bare, no union). B's callers never learn that the result might be
incomplete. The possibility is silently collapsed. B's signature
lies about what B actually does.

This is the Furqan equivalent of Rust's exhaustive match checking
on ``Result<T, E>``: if you call a function that returns a
``Result``, you must handle both ``Ok`` and ``Err``. In Furqan, if
you call a function that returns ``Integrity | Incomplete``, your
own return type must preserve the union or your signature is
structurally dishonest.

Two checker cases:

**Case S1 - Status collapse (Marad).**
Caller returns a non-union type (or a union whose arms are not
exactly ``Integrity | Incomplete``) despite calling a producer.
The possibility of incompleteness is silently hidden from the
caller's own consumers. One Marad per offending call site (per the
same per-occurrence discipline as Tanzil T1).

**Case S2 - Status discard (Advisory).**
Caller has no declared return type despite calling a producer. The
result is silently discarded. Advisory rather than Marad: the
function may be intentionally effectful (a logger, a side-effect-
only invocation). The diagnostic alerts the developer; the strict-
variant gate does not fire on it.

**S3 - Honest propagation (no diagnostic).**
Caller is itself a producer (returns ``Integrity | Incomplete``).
The union is preserved end-to-end. Zero diagnostics.

Routing notes:

* Producer detection is over the SAME module: ``producers`` is
  built from ``module.functions``. A call to a function defined in
  another module cannot be resolved here (same local-scope limit
  as ring-close R1; cross-module is D23).
* Recursion is fine: a producer that calls itself triggers S3,
  not S1 - the caller's own return type is the union, so the
  propagation invariant is preserved trivially.

What this checker does NOT do (deferred):

* **D25 - Transitive status-collapse detection.** If A calls B
  calls C and C is a producer, this checker verifies B's call to
  C and A's call to B independently. It does not verify that the
  full chain preserves the union end-to-end. Phase 3+ work.
* **D26 - Branch-level exhaustiveness.** Whether the caller
  inspects both arms of the union via if/else branching is not
  checked here. Branch-level match checking requires control-flow
  analysis (D13) and pattern matching (future grammar).
* **Cross-module producer resolution.** Calls to externally-defined
  functions are unresolvable; the checker neither flags them nor
  silently passes them - they are simply outside the scope of the
  local pass.
"""

from __future__ import annotations

from typing import Iterable, Union

from furqan.checker.incomplete import (
    INCOMPLETE_TYPE_NAME,
    INTEGRITY_TYPE_NAME,
)
from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser.ast_nodes import (
    CallRef,
    FunctionDef,
    Module,
    TypePath,
    UnionType,
)


PRIMITIVE_NAME: str = "status_coverage"


# A status-coverage diagnostic is either a Marad (S1 collapse) or
# an Advisory (S2 discard). The union is the checker's external
# return type.
StatusCoverageDiagnostic = Union[Marad, Advisory]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_integrity_incomplete_union(rt: UnionType) -> bool:
    """True iff the union's two arms are exactly Integrity and
    Incomplete, in either order.

    Replicated locally (rather than imported from
    ``checker.incomplete``) because the equivalent helper there is
    underscore-prefixed (private). The string constants
    ``INTEGRITY_TYPE_NAME`` and ``INCOMPLETE_TYPE_NAME`` ARE imported
    from the public surface so the canonical type names live in
    exactly one place.
    """
    arms = {rt.left.base, rt.right.base}
    return arms == {INTEGRITY_TYPE_NAME, INCOMPLETE_TYPE_NAME}


def _format_return_type(rt: Union[TypePath, UnionType, None]) -> str:
    """Render a return-type clause for use in diagnostic strings."""
    if rt is None:
        return "<none>"
    if isinstance(rt, TypePath):
        return rt.base
    return f"{rt.left.base} | {rt.right.base}"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_status_coverage(module: Module) -> list[StatusCoverageDiagnostic]:
    """Run the status-coverage check over a parsed :class:`Module`.

    Returns a list of :class:`Marad` (Case S1) and :class:`Advisory`
    (Case S2) records. An empty list means every consumer of a
    producer in this module honestly propagates (or intentionally
    discards via S3) the ``Integrity | Incomplete`` union.
    """
    diagnostics: list[StatusCoverageDiagnostic] = []

    # Build the producer map: functions in this module that return
    # Integrity | Incomplete. Anything else is not a producer for
    # the purposes of this check.
    producers: dict[str, FunctionDef] = {}
    for fn in module.functions:
        if (
            isinstance(fn.return_type, UnionType)
            and _is_integrity_incomplete_union(fn.return_type)
        ):
            producers[fn.name] = fn

    if not producers:
        # No producer in scope means there is nothing for any
        # caller to collapse or discard. Trivial pass.
        return diagnostics

    # Walk every function's call sites against the producer map.
    for fn in module.functions:
        diagnostics.extend(_check_calls(fn, producers))

    return diagnostics


def check_status_coverage_strict(module: Module) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    Marad. Advisories (Case S2) do NOT trigger the strict path -
    they are informational by design. Returns ``module`` unchanged
    on a clean check (for fluent-style call chaining).
    """
    diagnostics = check_status_coverage(module)
    for d in diagnostics:
        if isinstance(d, Marad):
            raise MaradError(d)
    return module


# ---------------------------------------------------------------------------
# Per-function checking
# ---------------------------------------------------------------------------

def _check_calls(
    fn: FunctionDef,
    producers: dict[str, FunctionDef],
) -> Iterable[StatusCoverageDiagnostic]:
    """Yield S1/S2 diagnostics for every call in ``fn`` that targets
    a producer in the same module.

    Per-call-site firing: if ``fn`` calls the same producer twice
    and ``fn``'s return type is bare-Integrity, S1 fires twice
    (once per call site), so the developer sees every offending
    location. Same discipline as Tanzil T1.
    """
    for call in fn.calls:
        if call.head not in producers:
            # Not a producer call (or a call to a function defined
            # outside this module). Out of scope for this checker.
            continue
        producer = producers[call.head]

        if fn.return_type is None:
            # S2: no return type, the producer's result is silently
            # discarded. Advisory rather than Marad - the function
            # may be intentionally effectful.
            yield _s2_discard_advisory(fn, call, producer)
            continue

        if isinstance(fn.return_type, UnionType):
            if _is_integrity_incomplete_union(fn.return_type):
                # S3: honest propagation. No diagnostic.
                continue
            # A union whose arms are not exactly Integrity and
            # Incomplete is still a collapse - the caller has
            # narrowed away the possibility of the producer's
            # incompleteness.
            yield _s1_collapse_marad(fn, call, producer)
            continue

        # TypePath (bare type) - the canonical S1 collapse.
        yield _s1_collapse_marad(fn, call, producer)


# ---------------------------------------------------------------------------
# Marad / Advisory construction
# ---------------------------------------------------------------------------

def _s1_collapse_marad(
    fn: FunctionDef,
    call: CallRef,
    producer: FunctionDef,
) -> Marad:
    caller_rt = _format_return_type(fn.return_type)
    producer_rt = _format_return_type(producer.return_type)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} calls {producer.name!r} (which "
            f"returns {producer_rt}) but {fn.name!r}'s declared "
            f"return type is {caller_rt}. Per Furqan D11 (Case S1 - "
            f"status collapse), the caller has silently narrowed "
            f"away the possibility of incompleteness that "
            f"{producer.name!r} explicitly declared. {fn.name!r}'s "
            f"signature now lies about what {fn.name!r} actually "
            f"does: a result that might be Incomplete is presented "
            f"to {fn.name!r}'s callers as if it were always "
            f"Integrity. The producer-side honesty discipline (Phase "
            f"2.6) requires every Integrity-returning path to rule "
            f"out incompleteness; the consumer-side discipline (D11) "
            f"requires every caller to propagate the union the "
            f"producer declared."
        ),
        location=call.span,
        minimal_fix=(
            f"change {fn.name!r}'s return type to "
            f"`Integrity | Incomplete` so the union is honestly "
            f"propagated. If {fn.name!r} legitimately wants to "
            f"narrow the union (for example, by raising on the "
            f"Incomplete arm), the narrowing must be explicit at "
            f"the call site - branch-level exhaustiveness checking "
            f"is registered as D26 (Phase 3+). For now, propagate."
        ),
        regression_check=(
            f"after the fix, re-run the status-coverage check; "
            f"{fn.name!r} must produce zero S1 marads. Verify that "
            f"every caller of {fn.name!r} also propagates the union "
            f"or is itself flagged - the discipline is recursive "
            f"by design."
        ),
    )


def _s2_discard_advisory(
    fn: FunctionDef,
    call: CallRef,
    producer: FunctionDef,
) -> Advisory:
    producer_rt = _format_return_type(producer.return_type)
    return Advisory(
        primitive=PRIMITIVE_NAME,
        message=(
            f"function {fn.name!r} calls {producer.name!r} (which "
            f"returns {producer_rt}) but {fn.name!r} declares no "
            f"return type. Per Furqan D11 (Case S2 - status "
            f"discard), the producer's result is silently dropped. "
            f"This is not necessarily an error: {fn.name!r} may be "
            f"intentionally effectful (a logger, a side-effect-only "
            f"orchestrator). But the discard is structurally "
            f"ambiguous - a consumer reading {fn.name!r}'s signature "
            f"cannot tell from the type alone whether the producer's "
            f"incompleteness was handled or simply ignored."
        ),
        location=call.span,
        suggestion=(
            f"if {fn.name!r} legitimately consumes the producer's "
            f"result for side effects only, document the intent in "
            f"a comment so the discard is explicit. If the result "
            f"should propagate, declare {fn.name!r}'s return type "
            f"as `Integrity | Incomplete` and have the body return "
            f"the appropriate arm. A future Phase 3 effect-system "
            f"primitive may promote this to a structural-honesty "
            f"obligation; for now, the discard is informational."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "StatusCoverageDiagnostic",
    "check_status_coverage",
    "check_status_coverage_strict",
]
