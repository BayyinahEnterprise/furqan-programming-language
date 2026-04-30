# CHECKER.md: Furqan checker layer design notes

This document records the checker-layer design decisions per primitive.
Decisions made once and recorded here should not be re-litigated
session-by-session.

---

## 1. Public surface (v0.8.2; seven-primitive ring + D11 + D22 + D24 extensions)

The `furqan.checker` package exports one entry-point family per
primitive. As of Phase 2.9 the seven-primitive ring is closed;
v0.8.0 added D11 status-coverage; v0.8.1 added D22 return-type
matching; v0.8.2 adds D24 all-paths-return analysis:

| Primitive               | Module                         | Entry points                                                                |
|-------------------------|--------------------------------|-----------------------------------------------------------------------------|
| Bismillah scope         | `checker/bismillah.py`         | `check_bismillah` / `check_bismillah_strict`                                |
| Zahir/batin             | `checker/zahir_batin.py`       | `check_zahir_batin` / `check_zahir_batin_strict`                            |
| Additive-only           | `checker/additive.py`          | `check_additive` / `check_additive_module` / `check_additive_module_strict` |
| Scan-incomplete         | `checker/incomplete.py`        | `check_incomplete` / `check_incomplete_strict`                              |
| Mizan calibration       | `checker/mizan.py`             | `check_mizan` / `check_mizan_strict`                                        |
| Tanzil build ordering   | `checker/tanzil.py`            | `check_tanzil` / `check_tanzil_strict`                                      |
| Ring-close completion   | `checker/ring_close.py`        | `check_ring_close` / `check_ring_close_strict`                              |
| Status-coverage (D11)   | `checker/status_coverage.py`   | `check_status_coverage` / `check_status_coverage_strict`                    |
| Return-type match (D22) | `checker/return_type_match.py` | `check_return_type_match` / `check_return_type_match_strict`                |
| All-paths-return (D24)  | `checker/all_paths_return.py`  | `check_all_paths_return` / `check_all_paths_return_strict`                  |

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

## 3. Additive-only checker (Phase 2.5), the four cases

### Case 1, Removed without bump

A symbol exported in the previous version is absent in the current
version, AND the current module's `major_version_bump` catalog does
not declare its removal. **Marad fires.**

### Case 2, Renamed without bump (two-tier handling)

The single conceptual rule "renames must be declared" is implemented
as two separate checks:

**Enforcement (marad fires).** The catalog declares
`renames: X -> Y`, but the catalog claim contradicts reality,
either `X` is still in `current.exports` OR `Y` is absent from
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

## 9. Status-coverage checker (D11, v0.8.0) - the consumer-side dual

The Phase 2.6 scan-incomplete checker is the producer-side primitive
of structural-honesty for incompleteness: a function declaring
`-> Integrity | Incomplete` must handle both arms in its body. The
v0.8.0 status-coverage checker is the consumer-side dual: a function
that CALLS a producer must propagate the union honestly in its own
return type. Together the two checkers close the loop on the
discipline. Incompleteness cannot be silently introduced (Phase 2.6
Case A guards bare-Integrity returns; Case B requires the literal's
required fields) AND it cannot be silently collapsed across a call
boundary (D11 Cases S1, S2).

### The three cases

* **S1 - Status collapse (Marad).** Caller's declared return type is
  not exactly `Integrity | Incomplete` despite calling a function
  whose return type IS that union. The caller has narrowed away the
  possibility of incompleteness; the caller's signature now lies
  about what the caller actually does. One Marad per offending call
  site (per-occurrence discipline matches Tanzil T1 self-dependency
  firing).
* **S2 - Status discard (Advisory).** Caller has no declared return
  type despite calling a producer. The producer's result is
  silently dropped. Advisory rather than Marad: the function may be
  intentionally effectful (a logger, a side-effect-only
  orchestrator). The diagnostic alerts the developer; the strict-
  variant gate does not fire on it.
* **S3 - Honest propagation (no diagnostic).** Caller is itself a
  producer. Union preserved end-to-end. Trivial pass.

### Local-scope only

The producer map is built from `module.functions` exclusively. A
call to a function defined in another module cannot be resolved
here - the same local-scope limitation as ring-close R1 and Phase
2.6 Case A's producer detection. Cross-module producer resolution
is registered as D23 alongside the cross-module ring analysis.

### Why this is not a new primitive

D11 sits inside the scan-incomplete primitive's discipline rather
than constituting an eighth primitive. The seven core primitives
(bismillah, zahir/batin, additive-only, scan-incomplete, mizan,
tanzil, ring-close) each express a distinct structural invariant.
Status-coverage is a checker EXTENSION of scan-incomplete: same
invariant (incompleteness must be honestly surfaced), enforced
across one more boundary (call sites in addition to function
bodies). Treating it as a new primitive would inflate the seven-
primitive count without adding a new structural rule.

### What this checker does NOT do

* **Branch-level exhaustiveness (D26).** Whether the caller
  inspects both arms of the union via if/else branching is not
  checked. Branch-level match checking requires control-flow
  analysis (D13) and pattern matching (future grammar).
* **Transitive collapse (D25).** A -> B -> C where C is a producer:
  D11 checks B's call to C and A's call to B independently. It
  does not verify the full chain preserves the union. Phase 3+
  work.
* **Effect tracking.** A future Phase-3 effect-system primitive
  may upgrade S2 from Advisory to Marad when the caller is purely
  functional (no side effects). For now, S2 stays informational.

---

## 10. Return-expression type matching (D22, v0.8.1)

The third leg of the return-type contract. Ring-close R3 (Phase 2.9)
verifies that a function with a declared return type contains at
least one return statement (presence). D11 status-coverage (v0.8.0)
verifies that callers of producers honestly propagate the union
(consumer-side exhaustiveness). D22 (this section) verifies that the
return statement's expression matches the declared return type
(producer-side type correctness on the value being returned).

### The single case

* **M1 - Return type mismatch (Marad).** A return expression's
  *statically-inferred* type is not a member of the declared return
  type's accepted set. Examples: function declares `-> Integrity`,
  body returns `Incomplete {...}`; function declares `-> CustomType`,
  body returns `Integrity`.

### Shallow inference is honest

Only `IntegrityLiteral` and `IncompleteLiteral` have statically-known
types in the AST. Every other expression (`IdentExpr`, `StringLiteral`,
`NumberLiteral`, `NotExpr`, `BinaryComparisonExpr`, `IdentList`) is
*uncheckable* and produces no diagnostic. This is the honest position:
the checker does not claim a verdict it cannot prove.

An M2-style "uncheckable expression" Advisory was considered and
deliberately omitted. It would fire on nearly every function that
returns a variable (`return result`), drowning the M1 signal in
noise. The trade-off favours signal density over warning coverage.

### Why this is not folded into ring-close

R1-R4 are about structural completion at the *module shape* level
(undefined types, empty body, missing return, unreferenced type).
D22 is about *value-level type matching*. Folding D22 into ring-close
would conflate two distinct invariants: structural presence and type
correctness. Keeping them separate matches the same architectural
choice that put D11 in its own module rather than extending
scan-incomplete's body.

### What this checker does NOT do

* **D27 - Type inference on `IdentExpr` returns.** `return result` -
  determining the type of `result` requires data-flow analysis
  (tracing assignments and call return types). Phase 3+ work.
* **D28 - Cross-function return-type resolution.**
  `return scan(file)` - what does `scan` return? Requires call-graph
  return-type propagation. Phase 3+ work; overlaps with the
  cross-module graph that D9/D20/D23 share.
* **Boolean inference.** `return not x` - the result is boolean, but
  Furqan has no boolean type in the type system yet. Future work.

### The three-leg return-type contract

Together, R3 / D22 / D11 form a complete return-type discipline
across function boundaries:

* **R3** - the function MUST return (structural presence).
* **D22** - the function MUST return the right TYPE (value-level
  correctness).
* **D11** - the function's CALLERS must propagate the type
  honestly (consumer-side exhaustiveness).

The compiler now does not let you lie about what you return at any
of the three levels: presence, type, or propagation.

---

## 11. All-paths-return analysis (D24, v0.8.2)

The fourth leg of the return-type contract. Ring-close R3 (Phase
2.9) checks that a return statement EXISTS somewhere in a typed
function's body. D24 checks that EVERY control-flow path through
the body reaches a return statement.

R3 catches the total absence ("you have no return at all"). D24
catches the partial absence ("you have a return on some paths but
not all"). The two compose: a function that fails R3 does not need
D24; a function that passes R3 but fails D24 has a silent fall-
through. The `_any_return_exists` short-circuit in D24 ensures no
double-reporting.

### The single case

* **P1 - Missing return path (Marad).** A function declares a
  return type, has at least one return statement (passes R3), but
  some control-flow path falls through without reaching a return.
  Common shapes: an `if` whose body returns but with no `else` and
  no trailing return; an `if`/`else` where one branch returns and
  the other runs only side-effect calls.

### The recurrence

A statement sequence all-paths-returns iff:
1. It contains a top-level `ReturnStmt`, OR
2. It contains an `IfStmt` with a non-empty `else_body` where BOTH
   the if-body and the else-body all-paths-return.

An `IfStmt` without an else cannot satisfy the gate on its own -
the missing-else path is an implicit fall-through. But a sequence
containing an else-less `IfStmt` followed by a bare return DOES
satisfy the gate, because the walker continues past the `IfStmt`
and finds the trailing return on the next iteration. This
preserves the canonical "early-return then default" pattern.

### Exact, not approximate

The analysis is exact for the current grammar. Furqan has exactly
one branching construct (`IfStmt` with optional else-arm, after
D15). There are no loops, no `switch`/`match`, no exceptions, no
early-exits other than `return`. Under these constraints,
structural recursion gives an exact verdict. When future grammar
adds loops or match expressions, D24 needs extension; that is
D29, registered as Phase 3+ work.

### Why this is not folded into ring-close

R3 (presence) is a first-order check: does any return exist?
D24 (path coverage) is a second-order check: do all paths reach
one? Folding D24 into ring-close would conflate two distinct
invariants. Keeping them separate matches the architectural
choice that put D11 in its own module rather than extending
scan-incomplete, and D22 in its own module rather than extending
ring-close.

### What this checker does NOT do

* **D29 - Full CFG analysis.** Loops, `switch`/`match`, exception
  paths require a control-flow graph rather than structural
  recursion. Phase 3+ work.
* **Unreachable-code detection.** A return statement followed by
  more statements is not flagged. Separate Phase 3 tooling.
* **Branch-level union exhaustiveness.** Whether each arm of a
  union return type is produced by some path is D26.

### The four-leg return-type contract

After D24, the return-type discipline has four legs:

| Leg | Checker | Question |
|---|---|---|
| Presence | Ring-close R3 | "Did you return at all?" |
| Path coverage | D24 all-paths-return | "Did every path return?" |
| Type correctness | D22 return-type-match | "Did you return the right thing?" |
| Consumer propagation | D11 status-coverage | "Do your callers preserve your type?" |

The compiler enforces return-type honesty from every angle: you
must return, on every path, with the right type, and your callers
must not hide it.
