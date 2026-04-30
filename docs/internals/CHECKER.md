# CHECKER.md: Furqan checker layer design notes

This document records the checker-layer design decisions per primitive.
Decisions made once and recorded here should not be re-litigated
session-by-session.

---

## 1. Public surface (Phase 2.9 complete)

The `furqan.checker` package exports one entry-point family per
primitive. As of Phase 2.9 the seven-primitive ring is closed:

| Primitive              | Module                     | Entry points                                                                |
|------------------------|----------------------------|-----------------------------------------------------------------------------|
| Bismillah scope        | `checker/bismillah.py`     | `check_bismillah` / `check_bismillah_strict`                                |
| Zahir/batin            | `checker/zahir_batin.py`   | `check_zahir_batin` / `check_zahir_batin_strict`                            |
| Additive-only          | `checker/additive.py`      | `check_additive` / `check_additive_module` / `check_additive_module_strict` |
| Scan-incomplete        | `checker/incomplete.py`    | `check_incomplete` / `check_incomplete_strict`                              |
| Mizan calibration      | `checker/mizan.py`         | `check_mizan` / `check_mizan_strict`                                        |
| Tanzil build ordering  | `checker/tanzil.py`        | `check_tanzil` / `check_tanzil_strict`                                      |
| Ring-close completion  | `checker/ring_close.py`    | `check_ring_close` / `check_ring_close_strict`                              |

Each primitive has a fail-soft variant (returns a list of marads, or
a `Result` bundle for additive-only) and a fail-fast `*_strict`
variant (raises `MaradError` on the first violation). The two-variant
shape is consistent across primitives so a Phase-3 multi-primitive
runner can compose them.

---

## 2. Marad versus Advisory (Phase 2.5)

Phase 2.5 lands the `Advisory` type (Session 1.1 deferred design D1).

| Type     | Semantics                                  | Causes type-check failure? |
|----------|--------------------------------------------|----------------------------|
| `Marad`  | Structural error, code does not type-check | YES                        |
| `Advisory` | Informational hint, code accepted, intent might be clearer | NO              |

The two types share a similar shape (primitive tag, location,
explanatory text, recovery suggestion) but are distinct dataclasses.
Conflating them on a single `tier` field would make every consumer
branch on the field; separate types give discrimination at the type
level for free.

A `Result(marads, advisories)` bundle separates the two so a Phase-3
reporter can render them differently:

* Marads emit the `[<primitive>]` tag and contribute to the
  type-check fail count.
* Advisories emit the `[advisory:<primitive>]` tag and are
  informational.

---

## 3. Additive-only checker (Phase 2.5): the four cases

### Case 1, Removed without bump

A symbol exported in the previous version is absent in the current
version, AND the current module's `major_version_bump` catalog does
not declare its removal. **Marad fires.**

### Case 2, Renamed without bump (two-tier handling)

The single conceptual rule "renames must be declared" is implemented
as two separate checks:

**Enforcement (marad fires).** The catalog declares
`renames: X -> Y`, but the catalog claim contradicts reality, either `X` is still in `current.exports` OR `Y` is absent from
`current.exports`. The catalog must not lie.

**Detection (advisory fires, marad does not).** The surface change
matches the pattern *exactly one removed name + exactly one added
name with matching type signature* AND the catalog has no rename
entry covering them. The checker emits an Advisory suggesting the
rename be declared explicitly.

The corresponding Case-1 marad still fires on the removed name; the
Advisory adds context, it does not suppress.

**Why the split.** The detection rule is a heuristic, a module that
removes one symbol and adds an unrelated symbol with a coincidentally
matching type signature would falsely look like a rename. Promoting
the detection to a marad would block legitimate work; demoting it to
silence would lose useful intent surfacing. The advisory is the
calibrated middle: visible evidence, no false-positive failure.

### Case 3, Type changed incompatibly

A symbol present in both current and previous with a non-equal
type-path AST. Phase 2.5 uses structural AST equality on `TypePath`
(same `base`, same `layer`); subtyping and variance are deferred to
Phase 3.

A type change has no dedicated catalog entry yet (`type_changes:`
deferred to D7); type changes must be expressed as a removes +
re-add OR a renames pair where the new name carries the new type.
**Marad fires.**

### Case 4, Catalog dishonest

The catalog declares `removes: X` but X is still present in
`current.exports`. **Marad fires.**

This is the reflexivity test: the escape valve cannot be abused.
Direct enforcement of thesis Section 7, Failure Mode 1 ("performed
alignment at the version-declaration layer") at the language level.

The check runs *before* Cases 1, 2, and 3 trust the catalog. A
catalog that lies cannot serve as evidence for the other cases.

---

## 4. Sidecar format (Phase 2.5)

The `<module>.furqan_history` sidecar is a regular `.furqan` file
containing a Bismillah block and one or more `additive_only module`
declarations at distinct versions. The sidecar parser is the standard
module parser; no special-case grammar.

Example:

```furqan
bismillah HistoryHolder {
    authority: NAMING_MD
    serves: archival.history
    scope: archive
    not_scope: nothing_excluded
}

additive_only module ScanRegistry v1.0 {
    export mechanism_registry: Registry
    export severity_weights: Weights
}

additive_only module ScanRegistry v1.1 {
    export mechanism_registry: Registry
    export severity_weights: Weights
    export scan_limits: ScanLimits
}
```

A current module at `v1.2` would be compared against the `v1.1`
entry (the adjacent prior). Resolution is by `_find_adjacent_prior`;
see `additive.py` for the rule.

---

## 5. Adjacent-version rule

For current `v<M>.<m>`:

* **Same major, prior is exactly `v<M>.<m-1>`** → adjacent.
* **Lower major (`current.major - 1`), any minor** → adjacent.
  If multiple priors qualify (e.g., sidecar contains v1.0, v1.5,
  and current is v2.0), the highest is selected (v1.5 in the
  example).
* **Otherwise** → not adjacent → marad.

The constraint exists to prevent skipping intermediate-version
evidence. Comparing v1.3 directly against v1.0 would miss any
removals or renames that happened in v1.1 or v1.2.

---

## 6. What this layer does NOT do (deferred)

* **Sidecar file discovery from disk.** The pure checker takes
  `sidecar_text: str | None` directly. Reading
  `<module>.furqan_history` from the filesystem is a CLI-layer
  concern (Phase 3+). The split mirrors Bayyinah's `ScanService`
  (pure orchestration) vs. CLI-layer file I/O.
* **Multi-module dependency graphs.** Phase 2.5 compares one
  current module against one prior module. Cross-module reasoning
  is a Phase 3+ surface.
* **Transitive multi-version comparison.** Phase 2.5 enforces
  *adjacent-only* comparison. Asking "does v1.3 still satisfy the
  v1.0 contract?" is out of scope for the prototype.
* **Structural subtyping on TypePath.** Phase 2.5 uses structural
  equality. A future phase may permit subtype substitution.
* **Behavioural verification.** The catalog must not lie about the
  *export list*; it cannot verify that a symbol's runtime behaviour
  is unchanged. That is the same Failure Mode 1 risk as the
  zahir/batin checker's `verify` discipline (NAMING.md §1.5):
  syntax-level verification cannot guarantee semantic intent.

---

*Bismillah.*
