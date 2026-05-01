"""
Mizan well-formedness checker — Furqan Phase 2.7 primitive #5.

Per the Furqan thesis paper §Primitive 4 (*Mizan Constraints:
Three-Valued Calibration*, anchored on Ar-Rahman 55:7-9 — *"He has
set up the balance, that you may not transgress the balance. So
establish weight in justice and do not make the balance
deficient."*), every mizan calibration block declares three
canonical fields together: ``la_tatghaw`` (do not transgress),
``la_tukhsiru`` (do not make deficient), ``bil_qist`` (calibrate
fairly). The three are calibrated jointly because tightening one
typically loosens the others (FRaZ non-monotonicity, Underwood et
al. 2020).

This module is the language-level transposition of Bayyinah's
detector calibration discipline (every detector ships a triple of
upper bound, lower bound, calibration function) into a static
syntactic well-formedness check on `mizan` blocks.

Three checker cases are enforced (M3 lives in the parser layer,
see Phase 2.7 §6.4 routing rationale below):

**Case M1 — Missing required field.**
A `mizan` block omits one of the three canonical fields. One
marad per missing field, all reported in a single pass.

**Case M2 — Duplicate field.**
A `mizan` block contains the same canonical field name more than
once. Marad fires on every occurrence after the first; the first
is treated as the "intended" declaration.

**Case M4 — Out-of-order fields.**
All three canonical fields are present, no duplicates, but the
order of appearance does not match the canonical sequence
(la_tatghaw, then la_tukhsiru, then bil_qist — matching the thesis
example sequence and the underlying Quranic ordering at Ar-Rahman
55:7-9).

**Case M3 — Unknown field — NOT a checker case.**
Per Phase 2.7 §6.4, mizan field heads are *keyword* tokens, not
identifiers. The parser enforces field-head position by raising a
`ParseError` if any non-canonical token appears where a field
head is required. By the time a `MizanDecl` reaches this checker,
every field head is canonical by construction; an unknown-field
guard inside `check_mizan` would be structurally unreachable —
dead defensive code that produces a false signal of defence-in-
depth. Honest layering: the parser owns token-shape invariants;
the checker owns semantic invariants over a well-formed AST.

What this checker does NOT do (deferred to a later phase):

* **Runtime evaluation of bound expressions.** The checker parses
  ``false_positive_rate < 0.05`` as an AST node; it does not
  evaluate the comparison against any corpus.
* **Non-monotonic interaction warning.** Detecting interactions
  between bounds requires multi-bound analysis and is registered
  for a later phase.
* **Trivial-bounds linter.** Flagging ``< 1.0`` ceilings or
  ``> 0.0`` floors as semantically vacuous is a linter concern,
  not a syntactic well-formedness check (per thesis §Failure
  Mode 2 safeguard).
* **Type-checking of bound expressions.** The checker does not
  verify that ``la_tatghaw`` carries a numeric or comparison
  expression; the parser accepts any expression at the value
  position.
"""

from __future__ import annotations

from typing import Iterable

from furqan.errors.marad import Marad, MaradError
from furqan.parser.ast_nodes import (
    MizanDecl,
    MizanField,
    Module,
)


PRIMITIVE_NAME: str = "mizan_well_formed"

# The canonical field set and order. Phase 2.7 enforces:
# (M1) every block declares all three; (M2) no field appears
# twice; (M4) the source-order of fields matches this tuple.
REQUIRED_MIZAN_FIELDS: tuple[str, ...] = (
    "la_tatghaw",
    "la_tukhsiru",
    "bil_qist",
)

_FIELD_ROLE: dict[str, str] = {
    "la_tatghaw":  "the do-not-transgress upper bound",
    "la_tukhsiru": "the do-not-make-deficient lower bound",
    "bil_qist":    "the establish-in-justice calibration function",
}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_mizan(module: Module) -> list[Marad]:
    """Run the Mizan well-formedness check over a parsed
    :class:`Module`.

    Returns a list of :class:`Marad` records, one per violation.
    An empty list means every mizan block in the module is
    structurally well-formed (all three required fields present,
    no duplicates, in canonical order). The check is purely
    syntactic; runtime bound evaluation is a later-phase concern.
    """
    diagnostics: list[Marad] = []
    for decl in module.mizan_decls:
        diagnostics.extend(_check_mizan_decl(decl))
    return diagnostics


def check_mizan_strict(module: Module) -> Module:
    """Fail-fast variant: raise :class:`MaradError` on the first
    violation. Returns ``module`` unchanged on a clean check (for
    fluent-style call chaining)."""
    diagnostics = check_mizan(module)
    if diagnostics:
        raise MaradError(diagnostics[0])
    return module


# ---------------------------------------------------------------------------
# Per-decl checking
# ---------------------------------------------------------------------------

def _check_mizan_decl(decl: MizanDecl) -> Iterable[Marad]:
    """Yield well-formedness marads for a single MizanDecl.

    The three rules are evaluated in a fixed order (M2 → M1 → M4)
    because each later rule presupposes the earlier rules' shape:

    * M2 (duplicates) is detected by walking the field list and
      tracking name occurrence counts. Fires on every occurrence
      *after the first* of any duplicated name. Independent of
      M1 and M4.
    * M1 (missing) is detected by computing the set difference
      between the canonical names and the names actually present.
      Independent of M2 and M4. Reports one marad per missing
      field.
    * M4 (order) compares the source-order sequence of canonical-
      named fields against the canonical sequence. Only fires
      when ALL three canonical fields are present (otherwise the
      M1 marad is the load-bearing diagnostic; firing M4 on a
      partial block would produce a confusing dual diagnostic).
      Duplicates are filtered to first-occurrence only for the
      order check, so M4 and M2 do not double-fire on the same
      offence.

    The three rules are independent in the sense that each is
    individually false (or true) regardless of the others; the
    short-circuit on M4 is purely a diagnostic-quality choice.
    """
    # --- M2 — duplicate field detection ---
    seen: dict[str, MizanField] = {}
    duplicates: list[MizanField] = []
    for field in decl.fields:
        if field.name in seen:
            duplicates.append(field)
        else:
            seen[field.name] = field
    for dup in duplicates:
        yield _m2_duplicate_marad(decl, dup)

    # --- M1 — missing field detection ---
    present_names = set(seen.keys())
    missing = [
        name for name in REQUIRED_MIZAN_FIELDS
        if name not in present_names
    ]
    for name in missing:
        yield _m1_missing_marad(decl, name)

    # --- M4 — out-of-order detection ---
    # Only run if every canonical field is present (otherwise
    # M1 is the load-bearing diagnostic; M4 would be redundant).
    # Duplicates are filtered to first-occurrence only.
    if not missing:
        first_occurrence_order = [
            field.name for field in decl.fields
            if field is seen[field.name]
        ]
        if tuple(first_occurrence_order) != REQUIRED_MIZAN_FIELDS:
            yield _m4_out_of_order_marad(decl, first_occurrence_order)


# ---------------------------------------------------------------------------
# Marad construction
# ---------------------------------------------------------------------------

def _m1_missing_marad(decl: MizanDecl, missing_field: str) -> Marad:
    role = _FIELD_ROLE.get(missing_field, "a required calibration command")
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"mizan block {decl.name!r} is missing required field "
            f"{missing_field!r}, which is {role}. Per Furqan thesis "
            f"§Primitive 4 (Case M1 - missing required field), every "
            f"mizan block must declare all three calibration "
            f"commands: la_tatghaw (do not transgress), la_tukhsiru "
            f"(do not make deficient), bil_qist (calibrate fairly). "
            f"The three commands are calibrated jointly; declaring "
            f"only two is the canonical Process-2 risk for this "
            f"primitive - the block syntactically exists but one "
            f"balance-point is silently absent."
        ),
        location=decl.span,
        minimal_fix=(
            f"add the missing `{missing_field}: <bound>` line to the "
            f"mizan block in canonical position (la_tatghaw first, "
            f"then la_tukhsiru, then bil_qist). If this calibration "
            f"command is genuinely not applicable to this block, "
            f"document the reasoning in a comment and supply a "
            f"placeholder bound that the runtime will reject."
        ),
        regression_check=(
            f"after the fix, re-run the mizan well-formedness "
            f"check; the block must produce zero marads. Confirm "
            f"the new field's bound expression matches the actual "
            f"calibration discipline you intend to enforce."
        ),
    )


def _m2_duplicate_marad(decl: MizanDecl, dup_field: MizanField) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"mizan block {decl.name!r} contains duplicate field "
            f"{dup_field.name!r}. Per Furqan thesis §Primitive 4 "
            f"(Case M2 - duplicate field), each calibration "
            f"command appears exactly once. The second declaration "
            f"would silently override the first under any 'last "
            f"write wins' convention, making one of the two bound "
            f"declarations disappear without a diagnostic."
        ),
        location=dup_field.span,
        minimal_fix=(
            f"remove the duplicate `{dup_field.name}` line, or "
            f"merge the two bound expressions into a single line "
            f"if both bounds are intended to apply (use a compound "
            f"bound expression in a future Phase-3 grammar; Phase "
            f"2.7 has only single-comparison bounds)."
        ),
        regression_check=(
            f"after the fix, re-run the mizan well-formedness "
            f"check; the block must produce zero marads."
        ),
    )


def _m4_out_of_order_marad(
    decl: MizanDecl,
    actual_order: list[str],
) -> Marad:
    canonical = ", ".join(REQUIRED_MIZAN_FIELDS)
    actual = ", ".join(actual_order)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"mizan block {decl.name!r} has fields in non-canonical "
            f"order. Canonical order: {canonical} (per thesis "
            f"§Primitive 4 example 1, matching the textual sequence "
            f"of Ar-Rahman 55:7-9). Actual order in the block: "
            f"{actual}. Per Furqan thesis §Primitive 4 (Case M4 - "
            f"out-of-order fields), pinning the order in the "
            f"language preserves the textual sequence the "
            f"discipline derives from."
        ),
        location=decl.span,
        minimal_fix=(
            f"reorder the mizan block fields to match the canonical "
            f"sequence: la_tatghaw first (the do-not-transgress "
            f"upper bound), then la_tukhsiru (the do-not-make-"
            f"deficient lower bound), then bil_qist (the establish-"
            f"in-justice calibration function)."
        ),
        regression_check=(
            f"after the fix, re-run the mizan well-formedness "
            f"check; the block must produce zero marads. Field "
            f"semantics are unchanged by the reordering."
        ),
    )


__all__ = [
    "PRIMITIVE_NAME",
    "REQUIRED_MIZAN_FIELDS",
    "check_mizan",
    "check_mizan_strict",
]
