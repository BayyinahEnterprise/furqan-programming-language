"""
Additive-only module checker — Furqan Phase 2.5 primitive #3.

Per the Furqan thesis paper §3.3, an additive-only module's exported
surface is monotonically growing across versions. Symbols exported at
version N must remain exported at version N+1 with a compatible type
signature. The escape valve is the explicit ``major_version_bump``
catalog: a developer who needs to break the additive-only invariant
declares the breakage in the catalog, making it visible to every
downstream consumer at compile time.

This module is the language-level transposition of Bayyinah's
``MECHANISM_REGISTRY`` import-time coherence check (CHANGELOG v1.1.1).
There the discipline was a Python ``assert`` at module import; here it
is a compile-time type rule. The structural property — public surface
must not silently shrink — is identical.

The checker enforces four cases:

**Case 1 — Removed without bump.**
A symbol exported in the previous version is absent in the current
version, AND the current module's bump catalog does not declare its
removal. This is the canonical Process-2 risk: every downstream
caller of the removed symbol breaks at the version-flip moment, and
the language is built to make the break loud at compile time.

**Case 2 — Renamed without bump.**
Two-tier handling separates *enforcement* (a marad that fires) from
*detection* (an advisory that informs):

* **Enforcement (marad):** the bump catalog declares
  ``renames: X -> Y`` but the catalog claim contradicts reality —
  either ``X`` is still in current.exports OR ``Y`` is absent from
  current.exports. The catalog must not lie.

* **Detection (advisory only, not a marad):** the surface change
  pattern matches "exactly one removed name and exactly one added
  name with matching type signature" AND the bump catalog has no
  rename entry covering them. The checker emits an
  :class:`Advisory` suggesting the rename be declared explicitly.
  The corresponding Case 1 marad still fires on the removed name;
  the advisory adds context, it does not suppress.

This split prevents false-positive marads on modules where unrelated
symbols happen to share a type signature, while still surfacing
likely intent.

**Case 3 — Type changed incompatibly.**
A symbol present in both current and previous with a non-equal
type-path AST. Phase 2.5 uses structural AST equality on
:class:`TypePath` (same ``base``, same ``layer``); subtyping and
variance are deferred to Phase 3. Type changes require either a
``removes:`` + add of the new-typed symbol or a ``renames:`` pair —
there is no ``type_changes:`` catalog entry yet (a Phase-2.5+
deferred design).

**Case 4 — Catalog dishonest.**
The bump catalog declares ``removes: X`` but X is still present in
current.exports. The reflexivity test: the escape valve itself
cannot be abused. Direct enforcement of thesis Section 7, Failure
Mode 1 at the version-declaration layer.

What this checker does NOT do (deferred):

* Multi-module dependency graphs.
* Transitive multi-version comparison (only adjacent-version
  comparison; v1.2 must compare against v1.1, never against v1.0).
* Structural subtyping or variance on :class:`TypePath`.
* Sidecar file discovery from the filesystem (the pure
  :func:`check_additive` is the load-bearing primitive; the
  :func:`check_module` sidecar wrapper is a convenience around it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from furqan.errors.marad import Advisory, Marad, MaradError
from furqan.parser import (
    AdditiveOnlyModuleDecl,
    ExportDecl,
    Module,
    ParseError,
    SourceSpan,
    TokenizeError,
    TypePath,
    parse,
)


PRIMITIVE_NAME: str = "additive_only"


# ---------------------------------------------------------------------------
# Result — checker output bundle
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Result:
    """Outcome of the additive-only check.

    A :class:`Marad` is an error: the program does not type-check.
    An :class:`Advisory` is informational: the program is accepted
    but the developer might want to declare intent more explicitly.
    Separating the two lets a Phase-3 multi-error reporter render
    them differently while keeping the structural distinction
    visible at the type level.
    """

    marads: tuple[Marad, ...] = ()
    advisories: tuple[Advisory, ...] = ()

    @property
    def passed(self) -> bool:
        """True iff zero marads were emitted (advisories do not fail
        the check)."""
        return len(self.marads) == 0


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_additive(current: Module, previous: Module) -> Result:
    """Pure two-module comparison — the load-bearing primitive.

    No I/O. The test harness passes :class:`Module` objects directly.
    Returns a :class:`Result` carrying every marad and advisory the
    checker emits. The four checker cases are applied to every pair
    of matching-named additive_only module declarations across the
    two modules.

    A current module with no additive-only declarations produces an
    empty :class:`Result` (nothing to check). A previous module with
    no additive-only declarations means "first version" for whatever
    the current declares — a trivial pass.
    """
    marads: list[Marad] = []
    advisories: list[Advisory] = []

    current_decls = {m.name: m for m in current.additive_only_modules}
    previous_decls = {m.name: m for m in previous.additive_only_modules}

    for name, current_decl in current_decls.items():
        if name not in previous_decls:
            # No prior version of this module to compare against.
            # First-version-trivial-pass behaviour.
            continue
        previous_decl = previous_decls[name]
        m, a = _compare_module_decls(current_decl, previous_decl)
        marads.extend(m)
        advisories.extend(a)

    return Result(marads=tuple(marads), advisories=tuple(advisories))


def check_module(
    module: Module,
    sidecar_text: str | None,
) -> Result:
    """Sidecar-aware wrapper around :func:`check_additive`.

    Parses ``sidecar_text`` as a regular .furqan module (the sidecar
    format is just .furqan with one Bismillah and zero or more
    additive-only module declarations at varying versions). Resolves
    the adjacent prior version via the sidecar and delegates to
    :func:`check_additive`.

    Resolution rules:

    * ``sidecar_text is None`` → first version, trivial pass
      (returns an empty :class:`Result`).
    * Sidecar parses cleanly and contains an adjacent prior version
      → compare via :func:`check_additive`.
    * Sidecar parses cleanly but contains no adjacent prior version
      (gap) → marad: non-adjacent comparison.
    * Sidecar fails to parse → marad: malformed sidecar.

    Adjacency rule (Phase 2.5):

    * Same major, prior is exactly ``v<M>.<m-1>``  → adjacent.
    * Lower major (``current.major - 1``), any minor  → adjacent.
    * Otherwise  → not adjacent.
    """
    if sidecar_text is None:
        return Result()

    # Session 1.4.1 polish (Perplexity E2 finding): catch BOTH lex-
    # level and parse-level failures and translate them to a uniform
    # sidecar-parse-failed marad. Pre-1.4.1 behaviour caught only
    # ParseError, so a sidecar containing lexically-malformed bytes
    # (e.g. ``@#$%`` — characters the tokenizer cannot classify)
    # would raise TokenizeError uncaught from the checker. The leak
    # was a Process-2 risk: the user would see a Python exception
    # instead of a structured marad, and the "structured diagnostic"
    # contract of the framework would be violated at exactly the
    # place where structural honesty is most load-bearing — the
    # version-history sidecar.
    try:
        sidecar_module = parse(sidecar_text, file="<sidecar>")
    except ParseError as exc:
        return Result(
            marads=(_malformed_sidecar_marad(exc),),
            advisories=(),
        )
    except TokenizeError as exc:
        return Result(
            marads=(_lex_error_sidecar_marad(exc),),
            advisories=(),
        )

    # If the current module declares no additive_only blocks, there
    # is nothing to compare; sidecar is irrelevant.
    if not module.additive_only_modules:
        return Result()

    marads: list[Marad] = []
    advisories: list[Advisory] = []

    sidecar_priors_by_name: dict[str, list[AdditiveOnlyModuleDecl]] = {}
    for prior in sidecar_module.additive_only_modules:
        sidecar_priors_by_name.setdefault(prior.name, []).append(prior)

    for current_decl in module.additive_only_modules:
        priors = sidecar_priors_by_name.get(current_decl.name, [])
        adjacent = _find_adjacent_prior(current_decl, priors)
        if priors and adjacent is None:
            marads.append(_non_adjacent_marad(current_decl, priors))
            continue
        if adjacent is None:
            # No prior versions at all — first version, trivial pass.
            continue
        m, a = _compare_module_decls(current_decl, adjacent)
        marads.extend(m)
        advisories.extend(a)

    return Result(marads=tuple(marads), advisories=tuple(advisories))


def check_module_strict(
    module: Module,
    sidecar_text: str | None,
) -> Module:
    """Fail-fast variant: raises :class:`MaradError` on the first
    marad. Returns ``module`` unchanged on a clean check (for
    fluent-style call chaining)."""
    result = check_module(module, sidecar_text)
    if result.marads:
        raise MaradError(result.marads[0])
    return module


# ---------------------------------------------------------------------------
# Adjacent prior version resolution
# ---------------------------------------------------------------------------

def _find_adjacent_prior(
    current: AdditiveOnlyModuleDecl,
    priors: list[AdditiveOnlyModuleDecl],
) -> AdditiveOnlyModuleDecl | None:
    """Return the prior version adjacent to ``current``, or None.

    See :func:`check_module` for the adjacency rule. If multiple
    priors qualify, the highest by ``(major, minor)`` ordering is
    returned (favours the most recent).
    """
    candidates: list[AdditiveOnlyModuleDecl] = []
    cur_major = current.version.major
    cur_minor = current.version.minor
    for p in priors:
        p_major = p.version.major
        p_minor = p.version.minor
        if p_major == cur_major and p_minor == cur_minor - 1:
            candidates.append(p)
        elif p_major == cur_major - 1:
            candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda m: (m.version.major, m.version.minor))


# ---------------------------------------------------------------------------
# Module-pair comparison — the four checker cases
# ---------------------------------------------------------------------------

def _compare_module_decls(
    current: AdditiveOnlyModuleDecl,
    previous: AdditiveOnlyModuleDecl,
) -> tuple[list[Marad], list[Advisory]]:
    marads: list[Marad] = []
    advisories: list[Advisory] = []

    current_exports = {e.name: e for e in current.exports}
    previous_exports = {e.name: e for e in previous.exports}

    bump_removes: dict[str, "RemovesEntry"] = {}
    bump_renames: list["RenamesEntry"] = []
    if current.bump_catalog is not None:
        bump_removes = {r.name: r for r in current.bump_catalog.removes}
        bump_renames = list(current.bump_catalog.renames)

    rename_old_to_new = {r.old_name: r for r in bump_renames}
    rename_new_names = {r.new_name for r in bump_renames}

    # --- Case 4: catalog dishonesty (check first; the catalog must
    # not lie before we trust it for the other cases) ---
    for removed_name, removes_entry in bump_removes.items():
        if removed_name in current_exports:
            marads.append(_case4_marad(current, removed_name, removes_entry.span))

    for rename_entry in bump_renames:
        old_present = rename_entry.old_name in current_exports
        new_absent = rename_entry.new_name not in current_exports
        if old_present or new_absent:
            marads.append(
                _case2_enforcement_marad(current, rename_entry, old_present, new_absent)
            )

    # --- Case 1: removed without bump ---
    for prev_name in previous_exports:
        if prev_name in current_exports:
            continue
        # Symbol absent from current.
        if prev_name in bump_removes:
            continue  # honestly declared as removed
        if prev_name in rename_old_to_new:
            # Declared as a rename. The Case 2 enforcement above
            # handles dishonest declarations; if the declaration was
            # honest (new name present, old name absent), the
            # removal of the old name is justified.
            entry = rename_old_to_new[prev_name]
            if (
                prev_name not in current_exports
                and entry.new_name in current_exports
            ):
                continue
            # Otherwise the enforcement marad already fired; do not
            # double-fire Case 1 here.
            continue
        marads.append(_case1_marad(current, previous_exports[prev_name]))

    # --- Case 3: type changed incompatibly ---
    for name, current_export in current_exports.items():
        if name not in previous_exports:
            continue
        previous_export = previous_exports[name]
        if not _types_equal(current_export.type_path, previous_export.type_path):
            marads.append(
                _case3_marad(current, current_export, previous_export)
            )

    # --- Case 2: detection (advisory only) ---
    # The advisory surfaces a likely undeclared rename. We DO NOT
    # filter on whether Case 1 fired; the advisory adds context.
    removed_names = (
        set(previous_exports.keys())
        - set(current_exports.keys())
        - set(bump_removes.keys())
        - set(rename_old_to_new.keys())
    )
    added_names = (
        set(current_exports.keys())
        - set(previous_exports.keys())
        - rename_new_names
    )
    if len(removed_names) == 1 and len(added_names) == 1:
        removed = next(iter(removed_names))
        added = next(iter(added_names))
        if _types_equal(
            previous_exports[removed].type_path,
            current_exports[added].type_path,
        ):
            advisories.append(
                _case2_advisory(current, removed, added, current_exports[added].span)
            )

    return marads, advisories


def _types_equal(a: TypePath, b: TypePath) -> bool:
    """Structural equality on type paths (Phase 2.5 rule).

    Same base name AND same layer. Subtyping and variance deferred
    to Phase 3.
    """
    return a.base == b.base and a.layer == b.layer


# ---------------------------------------------------------------------------
# Marad / Advisory construction
# ---------------------------------------------------------------------------

def _case1_marad(
    current: AdditiveOnlyModuleDecl,
    previous_export: ExportDecl,
) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"module {current.name!r} at version "
            f"{current.version.render()} has removed export "
            f"{previous_export.name!r} from its public surface, but "
            f"the major_version_bump catalog does not declare the "
            f"removal. Per Furqan thesis §3.3 (Case 1 — removed "
            f"without bump), every removal must be declared in the "
            f"catalog so downstream consumers can see the breaking "
            f"change at compile time."
        ),
        location=current.span,
        minimal_fix=(
            f"add `removes: {previous_export.name}` to a "
            f"`major_version_bump {{ ... }}` catalog inside "
            f"{current.name!r}'s body."
        ),
        regression_check=(
            f"after the fix, re-run the additive-only check; the "
            f"module must produce zero marads. Verify that every "
            f"caller previously using {previous_export.name!r} has "
            f"been migrated."
        ),
    )


def _case2_enforcement_marad(
    current: AdditiveOnlyModuleDecl,
    rename: "RenamesEntry",
    old_present: bool,
    new_absent: bool,
) -> Marad:
    contradictions: list[str] = []
    if old_present:
        contradictions.append(
            f"the old name {rename.old_name!r} is still in the exports list"
        )
    if new_absent:
        contradictions.append(
            f"the new name {rename.new_name!r} is missing from the exports list"
        )
    detail = " AND ".join(contradictions)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"module {current.name!r} at version "
            f"{current.version.render()} declares "
            f"`renames: {rename.old_name} -> {rename.new_name}` in "
            f"its major_version_bump catalog, but {detail}. The "
            f"catalog claim contradicts the actual exports. Per "
            f"Furqan thesis §3.3 (Case 2 enforcement), the escape "
            f"valve must be a truthful enumeration of the surface "
            f"change."
        ),
        location=rename.span,
        minimal_fix=(
            f"either remove the old name {rename.old_name!r} from "
            f"the exports list AND add the new name "
            f"{rename.new_name!r} (matching the catalog claim), or "
            f"remove the rename entry from the catalog (if the "
            f"rename did not actually happen)."
        ),
        regression_check=(
            f"after the fix, re-run the additive-only check; verify "
            f"that the catalog accurately describes the diff "
            f"between this version and its predecessor."
        ),
    )


def _case2_advisory(
    current: AdditiveOnlyModuleDecl,
    removed: str,
    added: str,
    location: SourceSpan,
) -> Advisory:
    return Advisory(
        primitive=PRIMITIVE_NAME,
        message=(
            f"module {current.name!r} removed {removed!r} and added "
            f"{added!r} with the same type signature; this looks "
            f"like an undeclared rename."
        ),
        location=location,
        suggestion=(
            f"if intentional, declare it in the major_version_bump "
            f"catalog: `renames: {removed} -> {added}`. The "
            f"declaration makes the intent visible to downstream "
            f"consumers and suppresses this advisory on the next "
            f"check."
        ),
    )


def _case3_marad(
    current: AdditiveOnlyModuleDecl,
    current_export: ExportDecl,
    previous_export: ExportDecl,
) -> Marad:
    prev_type = _format_type_path(previous_export.type_path)
    curr_type = _format_type_path(current_export.type_path)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"module {current.name!r} at version "
            f"{current.version.render()} keeps the export "
            f"{current_export.name!r} but its type changed from "
            f"{prev_type!r} (previous version) to {curr_type!r} "
            f"(current version). Per Furqan thesis §3.3 (Case 3 — "
            f"type changed incompatibly), the additive-only "
            f"invariant requires structural type equality across "
            f"versions; subtyping and variance are deferred to "
            f"Phase 3."
        ),
        location=current_export.span,
        minimal_fix=(
            f"either revert the type to {prev_type!r}, or remove "
            f"the export and re-add it under a new name (declaring "
            f"both via removes + a fresh export, OR via a renames "
            f"entry)."
        ),
        regression_check=(
            f"after the fix, re-run the additive-only check; verify "
            f"that callers expecting the prior type continue to "
            f"compile."
        ),
    )


def _case4_marad(
    current: AdditiveOnlyModuleDecl,
    removed_name: str,
    span: SourceSpan,
) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"module {current.name!r} at version "
            f"{current.version.render()} declares "
            f"`removes: {removed_name}` in its major_version_bump "
            f"catalog, but {removed_name!r} is still present in "
            f"the exports list. Per Furqan thesis §3.3 (Case 4 — "
            f"catalog dishonest), the escape valve cannot be "
            f"abused: the catalog must truthfully describe what was "
            f"removed. This is the reflexivity rule applied to the "
            f"version-declaration layer."
        ),
        location=span,
        minimal_fix=(
            f"either remove the {removed_name!r} export from the "
            f"exports list (if removal was actually intended), or "
            f"remove the `removes: {removed_name}` entry from the "
            f"catalog (if the symbol is meant to remain)."
        ),
        regression_check=(
            f"after the fix, re-run the additive-only check; the "
            f"catalog must agree with the actual surface."
        ),
    )


def _malformed_sidecar_marad(exc: ParseError) -> Marad:
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"the sidecar history file failed to parse: "
            f"{exc.message}. Per Furqan thesis §3.3, an unreadable "
            f"sidecar is a structural error: the additive-only "
            f"check cannot proceed without a verifiable prior-"
            f"version surface."
        ),
        location=exc.span,
        minimal_fix=(
            "fix the parse error in the .furqan_history sidecar "
            "(see the parser diagnostic above for the specific "
            "syntax issue), or remove the sidecar entirely if this "
            "is the first version of the module."
        ),
        regression_check=(
            "after the fix, re-run the additive-only check; the "
            "sidecar must parse cleanly."
        ),
    )


def _lex_error_sidecar_marad(exc: TokenizeError) -> Marad:
    """Marad for lex-level sidecar failures (Session 1.4.1, E2).

    ``TokenizeError`` does not yet carry structured ``line``/``column``
    fields (it inherits Exception with a single message string). Until
    Phase 3 promotes it to a fully structured exception, the marad
    uses a synthetic ``SourceSpan`` anchored at line 1, column 1 of
    the sidecar — sufficient to identify the file the error came
    from. The exception's message string carries the actual line/
    column embedded as text and is included verbatim in the diagnosis
    so the user can locate the offending byte.
    """
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"the sidecar history file failed to tokenize: "
            f"{str(exc)}. Per Furqan thesis §3.3, an unreadable "
            f"sidecar is a structural error: the additive-only "
            f"check cannot proceed without a verifiable prior-"
            f"version surface. The lex-level failure means the "
            f"sidecar contains bytes the language does not "
            f"recognise — most often a stray character outside "
            f"the accepted alphabet."
        ),
        location=SourceSpan(file="<sidecar>", line=1, column=1),
        minimal_fix=(
            "fix the lex error in the .furqan_history sidecar "
            "(remove or replace the offending character), or "
            "remove the sidecar entirely if this is the first "
            "version of the module."
        ),
        regression_check=(
            "after the fix, re-run the additive-only check; the "
            "sidecar must tokenize and parse cleanly."
        ),
    )


def _non_adjacent_marad(
    current: AdditiveOnlyModuleDecl,
    priors: list[AdditiveOnlyModuleDecl],
) -> Marad:
    prior_versions = ", ".join(p.version.render() for p in priors)
    return Marad(
        primitive=PRIMITIVE_NAME,
        diagnosis=(
            f"module {current.name!r} at version "
            f"{current.version.render()} has no adjacent prior "
            f"version in the sidecar history. Available prior "
            f"versions: {prior_versions}. Phase 2.5 enforces "
            f"adjacent-only comparison: v<M>.<m> must be checked "
            f"against v<M>.<m-1> (same major) or against any minor "
            f"of v<M-1> (prior major). A gap in the version chain "
            f"would skip surface-change evidence and undermine the "
            f"additive-only guarantee."
        ),
        location=current.version.span,
        minimal_fix=(
            "add the adjacent prior version to the .furqan_history "
            "sidecar so the chain has no gap. The sidecar should "
            "record every version the module has shipped at, not "
            "only selected ones."
        ),
        regression_check=(
            "after the fix, re-run the additive-only check; the "
            "sidecar must contain the adjacent prior version."
        ),
    )


def _format_type_path(tp: TypePath) -> str:
    if tp.layer is None:
        return tp.base
    return f"{tp.base}.{tp.layer}"


__all__ = [
    "PRIMITIVE_NAME",
    "Result",
    "check_additive",
    "check_module",
    "check_module_strict",
]
