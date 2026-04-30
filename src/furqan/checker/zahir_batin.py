"""
Zahir/batin type checker — Furqan Phase 2.4 primitive #2.

Per the Furqan thesis paper §3.2, compound types declare distinct
``zahir`` (surface) and ``batin`` (depth) layers, and a function
declares which layer it is permitted to access through the layer
qualification on its parameter type. Cross-layer access without the
``verify`` discipline is a structural divergence between what the
function's signature claims (its zahir, its surface contract) and
what the function's body does (its batin, its depth behaviour). The
language is built to detect exactly this divergence.

Phase 2.4 implements three rules, each emitting a structured
:class:`Marad`:

**Case 1 — zahir-typed function reads a batin field.**
A function whose parameter is declared as ``Type.zahir`` must access
that parameter's zahir layer only. Any access of the form
``param.batin[...]`` is a violation; the function's signature
promises surface-only behaviour while the body reaches into the
depth.

**Case 2 — batin-typed function reads a zahir field.**
Symmetric to Case 1 in the other direction. A ``Type.batin``
parameter may not be accessed via ``param.zahir[...]``. The
batin-typed function is the analyst of the depth representation;
mixing surface access into it conflates two distinct reading
disciplines.

**Case 3 — non-verify function with an unqualified compound-type
parameter.**
Per the thesis paper §3.2, ``verify`` is the *only* construct
permitted to take an unqualified compound-type parameter, because
``verify`` is the cross-layer construct by design. Any other
function that declares ``param: ComplexType`` (without a layer
qualifier) is a structural error: it asks for both-layer access
without committing to the verification discipline that justifies
that access.

The checker is fail-soft: it returns a list of marads (possibly
multiple from one module) so a Phase-3 multi-error reporter can
aggregate diagnostics across primitives. A fail-fast variant
(:func:`check_module_strict`) is provided for callers that want to
abort on the first violation.

What this checker does NOT do (out of scope, deferred to later
phases):

* It does not verify field-level access (e.g., that ``doc.zahir.x``
  refers to a field ``x`` actually declared in the zahir layer of
  Document). Phase 2.4 stops at the layer level; field-level
  resolution is a Phase-3 surface that requires symbol-table
  infrastructure not yet built.
* It does not enforce that a ``verify``-named function actually
  performs cross-layer comparison. The thesis paper §7 reflexivity
  analysis names this Failure Mode 1 (dishonest declarations) and
  the safeguard is human review, not the compiler.
* It does not check return types. The Incomplete<T> return-type
  primitive is Phase 2.6 (Session 1.4+ work).
"""

from __future__ import annotations

from typing import Iterable

from furqan.errors.marad import Marad, MaradError
from furqan.parser.ast_nodes import (
    CompoundTypeDef,
    FunctionDef,
    LayerAccess,
    Module,
    ParamDecl,
)


PRIMITIVE_NAME: str = "zahir_batin"

# The function name that grants per-parameter cross-layer access. Per
# NAMING.md §1.5, ``verify`` is recognised at the checker layer (by
# name comparison) rather than at the lexer layer (by keyword token)
# — promoting it to a keyword would prohibit every non-type-
# verification use of the word across the entire language surface.
VERIFY_FUNCTION_NAME: str = "verify"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_module(module: Module) -> list[Marad]:
    """Run the zahir/batin check over a parsed :class:`Module`.

    Returns a list of :class:`Marad` records, one per violation. An
    empty list means the module is structurally compliant with the
    thesis §3.2 zahir/batin discipline.
    """
    compound_type_names = frozenset(ct.name for ct in module.compound_types)
    diagnostics: list[Marad] = []
    for fn in module.functions:
        diagnostics.extend(_check_function(fn, compound_type_names))
    return diagnostics


def check_module_strict(module: Module) -> None:
    """Fail-fast variant: raise :class:`MaradError` on the first
    violation. Returns ``None`` on a clean module."""
    diagnostics = check_module(module)
    if diagnostics:
        raise MaradError(diagnostics[0])


# ---------------------------------------------------------------------------
# Per-function checking
# ---------------------------------------------------------------------------

def _check_function(
    fn: FunctionDef,
    compound_type_names: frozenset[str],
) -> Iterable[Marad]:
    """Yield zahir/batin marads for a single function definition.

    Phase 2.4 walks the function's :class:`ParamDecl` set to determine
    each parameter's declared layer, then walks the
    :class:`LayerAccess` records pre-scanned from the body to verify
    each access against the rule that applies to its parameter.
    """
    is_verify = fn.name == VERIFY_FUNCTION_NAME
    # Map param-name -> (layer | None | "non-compound").
    # ``layer`` is "zahir" or "batin" if the param is layer-qualified;
    # ``None`` if the param is an unqualified compound type
    # (Document, not Document.zahir / Document.batin); "non-compound"
    # if the param's type is not a declared compound type at all
    # (e.g., the parameter is a ``String`` or ``Bytes`` — the
    # zahir/batin checker has nothing to say about such parameters).
    param_layers: dict[str, str | None] = {}
    for param in fn.params:
        if param.type_path.base not in compound_type_names:
            # Non-compound-typed parameters are out of scope for this
            # checker. Phase 2.4 only verifies access discipline on
            # compound types declared in the same module.
            continue
        # Case 3 check happens here: a non-verify function declaring
        # an unqualified compound-type parameter is a marad. We yield
        # the diagnostic but still register the param so subsequent
        # body-access checks have the layer info they need.
        if param.type_path.layer is None and not is_verify:
            yield _case3_marad(fn, param)
        param_layers[param.name] = param.type_path.layer

    # Walk every access pre-scanned from the body. For each, check
    # the access layer against the parameter's declared layer.
    for access in fn.accesses:
        if access.param_name not in param_layers:
            # The access references a name that is not a compound-
            # typed parameter. This may be a free variable, a closure
            # capture, or a field on something the checker has no
            # type info about. Phase 2.4 does not flag these — the
            # zahir/batin rule is about *parameters declared as
            # compound types*, and we do not have whole-program name
            # resolution to determine the type of arbitrary names.
            continue
        declared_layer = param_layers[access.param_name]
        if declared_layer is None:
            # Unqualified compound-type parameter. For ``verify``
            # functions this is permitted (the per-parameter rule
            # grants both-layer access). For non-verify functions
            # the Case 3 marad has already been emitted above; we
            # do not double-fire the body-access marad.
            continue
        if declared_layer != access.layer:
            yield _case_1_or_2_marad(fn, access, declared_layer)


# ---------------------------------------------------------------------------
# Marad construction
# ---------------------------------------------------------------------------

def _case_1_or_2_marad(
    fn: FunctionDef,
    access: LayerAccess,
    declared_layer: str,
) -> Marad:
    """Construct the diagnostic for a Case 1 or Case 2 violation.

    The two cases are structurally symmetric — ``declared_layer``
    determines which one we emit and the resulting message names the
    rule by case number for cross-reference with the thesis paper
    §3.2.
    """
    case = "Case 1" if declared_layer == "zahir" else "Case 2"
    other_layer = "batin" if declared_layer == "zahir" else "zahir"
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} declares parameter "
            f"{access.param_name!r} with layer "
            f"{declared_layer!r}, but its body accesses "
            f"{access.param_name}.{access.layer_alias_used} "
            f"({access.layer!r} layer). Per Furqan thesis §3.2 "
            f"({case}), a {declared_layer}-typed function may "
            f"only access {declared_layer} fields; reaching into "
            f"the {other_layer} layer is a surface/depth divergence "
            f"the language is built to make loud."
        ),
        location=access.span,
        minimal_fix=(
            f"either change the parameter declaration to the "
            f"unqualified compound type and rename the function to "
            f"'verify' (the only construct permitted to take both "
            f"layers), or remove the {access.param_name}."
            f"{access.layer_alias_used} access from the body."
        ),
        regression_check=(
            f"after the fix, re-run the zahir/batin check; the "
            f"function must produce zero diagnostics. Verify that "
            f"the function's signature still matches the body's "
            f"actual reading discipline."
        ),
    )


def _case3_marad(fn: FunctionDef, param: ParamDecl) -> Marad:
    """Construct the diagnostic for a Case 3 violation (non-verify
    function declaring an unqualified compound-type parameter)."""
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"function {fn.name!r} declares parameter "
            f"{param.name!r} with the unqualified compound type "
            f"{param.type_path.base!r}, but only a function named "
            f"{VERIFY_FUNCTION_NAME!r} may take an unqualified "
            f"compound-type parameter (Furqan thesis §3.2, Case 3). "
            f"The unqualified form grants both-layer access; that "
            f"access is reserved for the verify discipline so the "
            f"reader of the call site can trust the access pattern."
        ),
        location=param.span,
        minimal_fix=(
            f"either rename {fn.name!r} to {VERIFY_FUNCTION_NAME!r} "
            f"(if cross-layer access is the function's actual "
            f"purpose), or qualify the parameter type as "
            f"{param.type_path.base}.zahir or "
            f"{param.type_path.base}.batin to commit to a "
            f"single-layer reading discipline."
        ),
        regression_check=(
            f"after the fix, re-run the zahir/batin check; the "
            f"function must produce zero diagnostics, and any "
            f"caller that relied on the prior signature must "
            f"continue to type-check."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "VERIFY_FUNCTION_NAME",
    "check_module",
    "check_module_strict",
]
