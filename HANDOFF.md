# Furqan: Session Handoff

This is the rolling handoff record for the Phase-2 prototype
type-checker. The most recent verified state is at the top; prior
session-closing summaries are appended below for the isnad. The
next session begins by reading this file and the Furqan v1.0
thesis paper.

---

## Verified state at Session 1.10 close (D11 status-coverage shipped, v0.8.0)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 3 (post-Phase-2 polish + extensions; runtime not yet) |
| Sub-phase                         | D11, status-coverage (consumer-side scan-incomplete dual) (**SHIPPED**) |
| Primitives implemented            | **7 of 7 core** + D11 checker extension              |
| Test count                        | **366 passing in 0.47s** (v0.7.1 baseline: 334; net +32) |
| Test files                        | 13 (added `test_status_coverage`)                    |
| Public symbols on `furqan.parser` | 42 (unchanged, D11 adds no AST nodes)               |
| Public symbols on `furqan.checker`| 32 (was 29; +3 status-coverage entry points)         |
| Public symbols on `furqan.errors` | 4 (unchanged)                                        |
| Runtime dependencies              | **0** (Python stdlib only)                           |
| Reserved keywords                 | 28 (unchanged, D11 introduces no keywords)          |
| Fixtures                          | + status_coverage(4 valid + 3 invalid)               |
| Package version                   | `0.8.0` (minor bump for new public exports + new checker module) |
| Compliance state at handoff       | **COMPLIANT**, producer-side AND consumer-side scan-incomplete discipline now closed; capstone integration test still green |
| CI                                | GitHub Actions on Python 3.10-3.13; surface and version-sync gates green |

### What shipped in Session 1.10

* `furqan/checker/status_coverage.py` implementing S1, S2 (S3 is the no-diagnostic case)
* 7 paired `.furqan` fixtures (4 valid + 3 invalid in `tests/fixtures/status_coverage/`)
* 32 new tests (sweep + per-case + edge cases + strict variant + cross-primitive + render + surface)
* Public surface: `check_status_coverage`, `check_status_coverage_strict`, `STATUS_COVERAGE_PRIMITIVE_NAME`, plus the `StatusCoverageDiagnostic = Marad | Advisory` union type alias on the sub-module surface
* CHECKER.md §9 documenting the consumer-side discipline and the local-scope limitation
* CHANGELOG v0.8.0 entry registering D25 and D26 as deferred

### Closing register

**Test count delta (Tier 1):** 334 to 366 in 0.47s. Verified by `pytest --collect-only` and full-suite run.

**Tier-tagged claims:**

* **Tier 1 (implemented + tested):** S1 collapse detection on bare-TypePath callers; S1 detection on union returns whose arms are not exactly Integrity and Incomplete; per-call-site firing (multiple_collapses fixture: 2 separate marads); S2 advisory on no-return-type callers; recursive-producer S3 silence; cross-module call silence (external_call_only fixture); two mutually-calling producers both pass S3; strict variant raises only on Marads; producer-map empty short-circuit on no-producer modules; per-call-site location (call.span); diagnostic strings name both caller and producer; primitive name "status_coverage" stable; the seven-primitive integration capstone fixture still passes all eight checkers (six prior + ring-close + status-coverage) with zero marads.
* **Tier 2 (structural, designed, partially tested):** S1 inflicts one marad per call site; if a single function calls the producer twice with bare-Integrity return, the test suite asserts `len(marads) == 1` for the multi-caller case but does not pin per-call within a single function. Best-effort.
* **Tier 3 (hypothesis, deferred):** D25 transitive collapse; D26 branch-level exhaustiveness; D23 cross-module resolution.

**Honest null results:**

* D11 only resolves callees within the same module. A call to a function defined in another module silently passes (it cannot be proved or disproved as a producer at this layer). A future cross-module pass (D23) will close this gap.
* D11 detects collapse at the return-type level only; a caller that uses `if/else` to inspect both arms of the union (rather than propagating in the return type) is currently flagged because the return type still narrows. This is the D26 limitation: branch-level exhaustiveness needs control-flow analysis. Acknowledged at the diagnostic-text level (the minimal_fix says "branch-level exhaustiveness checking is registered as D26").
* `_is_integrity_incomplete_union` is replicated locally in status_coverage.py rather than imported from incomplete.py because the equivalent helper there is underscore-prefixed (private). The two implementations are textually identical; a future polish patch could promote the one in incomplete.py to public and have status_coverage import it. The string constants (`INTEGRITY_TYPE_NAME`, `INCOMPLETE_TYPE_NAME`) ARE imported from the public surface so the canonical names live in exactly one place.
* No fixtures failed to express their intent. No tests pass for the wrong reason.

**Demo readiness, status-collapse path:**

A novel inline module exercising the canonical S1 collapse:

```
fn deep_scan(f: Integrity) -> Integrity | Incomplete { ... }
fn report(f: Integrity) -> Integrity {
    deep_scan(f)
    return Integrity
}
```

`check_status_coverage(parse(src))` returns one Marad. Sub-millisecond on novel input.

### Open items for next session

* **D9 / D20 / D23**, multi-module / cross-module analysis (cycle detection, ring-close type resolution, status-coverage producer resolution). These three deferred items share the cross-module-graph machinery; a single Phase 3 module-loader pass closes all three.
* **D25 (NEW)**, transitive status-collapse detection.
* **D26 (NEW)**, branch-level exhaustiveness on union returns.
* **D11-D17** carryover items from earlier sessions (max_confidence range, mizan runtime, etc.).

**Next phase:** Phase 3 runtime evaluator OR cross-module pass (D9/D20/D23/D25 batch). Polish-patch protocol still applies.

---


## Verified state at Session 1.8 close (Phase 2.9 shipped, COMPLIANT, RING CLOSED)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 2 (Prototype Type-Checker): **COMPLETE**            |
| Sub-phase                         | 2.9, Ring-close (structural completion) (**SHIPPED**) |
| Primitives implemented            | **7 of 7**, Bismillah, zahir/batin, additive-only, scan-incomplete, mizan, tanzil, **ring-close** |
| Test count                        | **296 passing in 0.37s** (Session 1.7 baseline: 252; net +44) |
| Test files                        | 10 (added `test_ring_close`)                         |
| Public symbols on `furqan.parser` | 42 (unchanged, ring-close adds no AST nodes)        |
| Public symbols on `furqan.checker`| 29 (was 25; +4 ring-close entry points)              |
| Public symbols on `furqan.errors` | 4 (unchanged)                                        |
| Runtime dependencies              | **0** (Python stdlib only)                           |
| Reserved keywords                 | 27 (unchanged, ring-close adds NO new keywords)     |
| Fixtures                          | bismillah/zahir_batin/additive_only/scan_incomplete/mizan/tanzil unchanged + **ring_close(4 valid + 4 invalid)** |
| Package version                   | `0.7.0` (minor bump for new public exports; pinned-literal sync corrected from 0.5.0 → 0.7.0) |
| Compliance state at handoff       | **COMPLIANT**, seven-primitive ring closed; capstone integration test green |
| Demo readiness (June 9)           | **EXECUTABLE END-TO-END**, five primitives demoable + seven-primitive integration witness in <0.5ms |

### What shipped in Session 1.8

- 8 paired `.furqan` fixtures (4 valid + 4 invalid in `tests/fixtures/ring_close/`)
- **0 keyword promotions, 0 new AST nodes, 0 parser changes**, ring-close is a pure whole-module checker
- `furqan/checker/ring_close.py` implementing R1, R2, R3, R4 (R2 + R4 as Advisories; R1 + R3 as Marads)
- `RingCloseDiagnostic = Marad | Advisory` union as the public return type from `check_ring_close`
- `check_ring_close_strict` raises only on Marads (R1, R3); Advisories (R2, R4) are informational and do not fail the strict path
- 44 new tests (8 sweep + 6 R1 + 5 R2 + 5 R3 + 4 R4 + 5 strict + 2 render + 1 surface + 2 capstone + 1 reflexivity + others)
- **The seven-primitive integration capstone** (`closed_ring_with_all_primitives.furqan`): a single module passing every Phase 2.x checker
- Pinned-literal version sync correction: `furqan.__version__` advanced from "0.5.0" (drifted) to "0.7.0" matching `pyproject.toml`
- CHANGELOG v0.7.0 entry registering D22, D23, D24 as deferred

### Munafiq Protocol closing register

**Test count delta (Tier 1):** 252 → 296 in 0.37s. Verified by `pytest --collect-only` and full-suite run.

**Tier-tagged claims:**

- **Tier 1 (implemented + tested):** R1 undefined-type detection over both parameter and return positions; R1 per-arm firing on union return types; R1 silence on declared types and on the two builtins (`Integrity`, `Incomplete`); R2 empty-body advisory with body-non-emptiness defined as functions+types only (tanzil/mizan/additive_only metadata excluded); R2 short-circuits R1/R3/R4; R3 syntactic-presence detection recursing into IfStmt bodies; R3 silence on void functions; R4 unreferenced-type detection treating param-position references and union-arm references as referencing; strict variant raises on R1+R3 marads but NOT on R2+R4 advisories; **the seven-primitive integration capstone passes every Phase 2.x checker with zero marads**; pinned-literal version sync correction.
- **Tier 2 (structural, designed, partially tested):** R1 builtin set is hardcoded to `{Integrity, Incomplete}`: works under the Phase 2.x assumption that the language has no other primitive types; D23 cross-module resolution would extend this set.
- **Tier 3 (hypothesis, deferred):** D22 return-expression type-vs-signature matching; D23 cross-module ring analysis; D24 all-paths-return analysis.
- **N=1 acknowledgement:** the seven-primitive witness is a single module. The structural completion property generalizes; other multi-primitive .furqan modules following the same shape will demonstrate the same end-to-end coverage.

**Honest null results:**

- R3 detection is *syntactic*, the presence of any `return` statement anywhere in the body satisfies the gate. A function with `if A { return X } if B { return Y }` (no else) syntactically satisfies R3 but at runtime falls through. This is D24, intentionally deferred.
- R1 resolution is local to the module. A type imported from another module (cross-module-graph; D9/D23 territory) would currently fire R1 because no in-module declaration matches. Phase 3+ work.
- The pinned-literal `__version__` had drifted from "0.5.0" through Phases 2.7 and 2.8 (pyproject.toml was at 0.6.0). Caught and corrected in this session, now pinned at "0.7.0". Test suite did not catch this earlier because no test asserted equality with `pyproject.toml`. Registered as a quiet polish task for a future audit pass.
- The reflexivity audit (`test_ring_close_module_has_no_unreachable_branches`) is a public-symbol-set match, not a coverage-driven dead-code probe. Best-effort.
- No fixtures failed to express their intent. No tests pass for the wrong reason.

**Public-surface additions registered (verbatim CHANGELOG v0.7.0 quote):**

> `furqan.checker.check_ring_close(module) -> list[Marad | Advisory]`, `check_ring_close_strict`, `RING_CLOSE_PRIMITIVE_NAME = "ring_close"`, `RING_CLOSE_BUILTIN_TYPE_NAMES = frozenset({"Integrity", "Incomplete"})`.

**Demo readiness, combined seven-primitive path:**

| Demo | Path | Status |
|---|---|---|
| Phase 2.5, additive-only | silent removal → Case 1 marad | preserved |
| Phase 2.6, scan-incomplete | unguarded Integrity → Case A marad | preserved |
| Phase 2.7, mizan | thesis canonical example → 0 marads | preserved |
| Phase 2.8, tanzil | self-dependency → Case T1 | preserved |
| Phase 2.9, ring-close (R1) | undefined return-type ref → R1 marad | **<0.2 ms** |
| Phase 2.9, ring-close (R3) | function declaring -> Document with empty body → R3 marad | **<0.2 ms** |
| **Seven-primitive capstone** | full module exercising every primitive → 0 marads | **<0.5 ms** |

**Unreachable-branch audit verdict:** CLEAN. `furqan/checker/ring_close.py` contains no defensive guard against parser-routed invariants; its public symbol set matches `__all__` exactly (pinned by `test_ring_close_module_has_no_unreachable_branches`).

### Open items for Phase 3+

- **D11–D15** (Session 1.5 carryovers, scan-incomplete consumer-side, max_confidence range, control-flow, escapes, else)
- **D16–D19** (Session 1.6 carryovers, mizan runtime, non-monotonic interaction, trivial-bounds linter, English aliases)
- **D20**, Multi-module tanzil graph analysis (topological sort, cross-module cycle detection, existence verification)
- **D21**, Version constraints on dependencies (`depends_on: CoreModule >= v0.3.0`)
- **D22 (NEW)**, Return-expression type-vs-signature matching (e.g., `-> Document` returning `Summary`)
- **D23 (NEW)**, Cross-module ring analysis (R1 resolution across the module graph)
- **D24 (NEW)**, All-paths-return analysis (R3 promotion from syntactic to control-flow-driven)

**Next phase:** Phase 3, runtime evaluator + cross-module graph (D9, D20, D23). The seven-primitive compile-time ring is closed; what remains is the runtime layer that evaluates well-formed modules and the cross-module analyses that the local-only Phase 2 checks register.

Polish-patch protocol still applies. If post-2.9 cross-model audit identifies a structural leak satisfying CONTRIBUTING.md §8.1, ship a Session 1.8.1 polish patch before opening Phase 3.

---

## Verified state at Session 1.7 close (Phase 2.8 shipped, COMPLIANT)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 2 (Prototype Type-Checker)                           |
| Sub-phase                         | 2.8, Tanzil build-ordering checker (**SHIPPED**)    |
| Primitives implemented            | **6 of 7**, Bismillah, zahir/batin, additive-only, scan-incomplete, mizan, tanzil |
| Test count                        | **252 passing in 0.38s** (Session 1.6 baseline: 219; net +33) |
| Test files                        | 9 (`test_tokenizer`, `test_parser`, `test_bismillah`, `test_marad`, `test_zahir_batin`, `test_additive`, `test_incomplete`, `test_mizan`, `test_tanzil`) |
| Public symbols on `furqan.parser` | 42 (was 40; +2 AST nodes)                            |
| Public symbols on `furqan.checker`| 25 (was 22; +3 tanzil-checker entry points)         |
| Public symbols on `furqan.errors` | 4 (unchanged)                                        |
| Runtime dependencies              | **0** (Python stdlib only)                           |
| Reserved keywords                 | 27 (was 25; +2 from `tanzil`, `depends_on`)          |
| Fixtures                          | bismillah(4 valid + 3 invalid + 1 known_limitation), parse_invalid(4), zahir_batin(3 valid + 3 invalid), additive_only(4 valid + 4 invalid + 7 sidecars), scan_incomplete(4 valid + 4 invalid), mizan(4 valid + 4 invalid), tanzil(4 valid + 4 invalid) |
| Package version                   | `0.6.0` (minor bump for source-language additions: 2 keywords + tanzil block grammar) |
| Compliance state at handoff       | **COMPLIANT**, full primary path shipped; no fallback invoked |
| Demo readiness (June 9)           | **EXECUTABLE END-TO-END**, four primitives demoable in <0.5ms each |

### What shipped in Session 1.7

- 8 paired `.furqan` fixtures (4 valid + 4 invalid; the unknown_field fixture is parser-routed, not checker-routed)
- 2 keyword promotions: `tanzil`, `depends_on` (total 27 reserved)
- 2 new AST node classes: `DependencyEntry`, `TanzilDecl`
- Top-level `tanzil` block parser with §6.4-equivalent field-head position enforcement (unknown field → parse error, not checker case)
- `furqan/checker/tanzil.py` implementing T1, T2, T3 (T3 as Advisory, not Marad, same pattern as additive-only's undeclared-rename Advisory)
- `TanzilDiagnostic = Marad | Advisory` union as the public return type from `check_tanzil`
- `check_tanzil_strict` raises only on Marads; Advisories are informational and do not fail the strict path
- 33 new tests (22 tanzil + 3 tokenizer + 3 parser + 5 inline-property)
- NAMING.md §1.6 expanded with two new keyword rows; §1.8 documents Phase 2.8 promotion rationale

### Munafiq Protocol closing register

**Test count delta (Tier 1):** 219 → 252 in 0.38s. Verified by `pytest --collect-only` and full-suite run.

**Tier-tagged claims:**

- **Tier 1 (implemented + tested):** 2 keyword promotions; tanzil block grammar; T1 self-dependency (per-occurrence firing, with inline test for triple-self confirming non-first-occurrence-wins semantics); T2 duplicate (first-occurrence-wins, with inline test for triple-duplicate confirming N-1 fires); T3 empty block (Advisory, NOT Marad, confirmed by isinstance check); short-circuit on T3 empty block; strict variant raises on Marad but NOT on Advisory; parser-level unknown-field routing with pinned diagnostic; reflexivity audit (no dead defensive code in `tanzil.py`); tanzil + mizan composability.
- **Tier 2 (structural, designed, partially tested):** the M3-equivalent routing reflexivity (grep-based audit catches obvious dead-code additions; not a formal proof).
- **Tier 3 (hypothesis, deferred):** D20 multi-module graph analysis, D21 version constraints on dependencies.
- **N=1 acknowledgement:** the demo-path execution was tested with one freshly-constructed novel input; other Bayyinah-pattern transcriptions would follow the same path.

**Honest null results:**

- T1 fires per-occurrence (NOT first-occurrence-wins). Three `depends_on: Self` lines produce three T1 marads. T2 in contrast IS first-occurrence-wins (three duplicates produce two T2 marads, not three). The asymmetry is deliberate: T1 is a unary property of each entry; T2 is a binary relation requiring a prior occurrence. Documented in inline tests.
- T3 short-circuits T1 and T2 on empty blocks (no entries to inspect). Deliberate diagnostic-quality choice; not a structural rule.
- The `Advisory` class fields are `(primitive, message, location, suggestion)`: different from the prompt's §11.4 description (`primitive, diagnosis, location`). I preserved the existing class shape per additive-only invariant; the prompt's description was outdated relative to the deployed Advisory class.
- The reflexivity audit is a string-match grep, not static analysis; subtle defensive guards (e.g., `if module_path != REQUIRED_VALUE`) would evade it. Best-effort, not formal proof.
- No fixtures failed to express their intent. No tests pass for the wrong reason.

**Source-language additions registered (verbatim CHANGELOG v0.6.0 quote):**

> Pre-2.8 .furqan source files that used either of the following words as ordinary identifiers will fail to parse at the v0.6.0 flip: `tanzil`, `depends_on`.

**NAMING.md §1.6 quote (first new row of v0.6.0 promotion block):**

> | `tanzil`             | 2.8    | build-ordering block declaration head             |

**Demo readiness, combined four-primitive path:**

All four primitives demo end-to-end on novel input in well under a millisecond:

| Demo | Path | Runtime |
|---|---|---|
| Phase 2.5, additive-only | silent removal → Case 1 marad | 0.13–0.45 ms |
| Phase 2.6, scan-incomplete | unguarded Integrity → Case A marad | 0.139 ms |
| Phase 2.7, mizan (pass) | thesis canonical example → 0 marads | 0.173 ms |
| Phase 2.7, mizan (marad) | la_tatghaw removed → Case M1 | 0.103 ms |
| Phase 2.8, tanzil (marad) | self-dependency → Case T1 | **0.097 ms** |
| Phase 2.8, tanzil (clean) | three distinct deps → 0 marads | **0.077 ms** |

**Unreachable-branch audit verdict:** CLEAN. The M3-equivalent routing rationale is preserved structurally, `furqan/checker/tanzil.py` contains no defensive guard against unknown field heads. The test `test_check_tanzil_module_has_no_unknown_field_branch` pins this for future contributors.

### Open items for Session 1.8+

- **D11–D15** (Session 1.5 carryovers, scan-incomplete consumer-side, max_confidence range, control-flow, escapes, else)
- **D16–D19** (Session 1.6 carryovers, mizan runtime, non-monotonic interaction, trivial-bounds linter, English aliases)
- **D20**, Multi-module tanzil graph analysis (topological sort, cross-module cycle detection, existence verification)
- **D21**, Version constraints on dependencies (`depends_on: CoreModule >= v0.3.0`)

**Next phase:** Phase 2.9, Ring-close (the seventh and final core primitive). Distinct primitive from Tanzil; closes the seven-primitive program.

Polish-patch protocol applies. If post-2.8 cross-model audit identifies a small structural leak satisfying CONTRIBUTING.md §8.1, ship a Session 1.7.1 polish patch in the same shape as 1.4.1 before opening Phase 2.9.

---

## Verified state at Session 1.6 close (Phase 2.7 shipped, COMPLIANT)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 2 (Prototype Type-Checker)                           |
| Sub-phase                         | 2.7, Mizan three-valued calibration block (**SHIPPED**) |
| Primitives implemented            | **5 of 7**, Bismillah, zahir/batin, additive-only, scan-incomplete, mizan |
| Test count                        | **219 passing in 0.30s** (Session 1.5 baseline: 184; net +35) |
| Test files                        | 8 (`test_tokenizer`, `test_parser`, `test_bismillah`, `test_marad`, `test_zahir_batin`, `test_additive`, `test_incomplete`, `test_mizan`) |
| Distribution                      | tokenizer 50, parser 35, bismillah 19, marad 7, zahir_batin 22, additive 40, incomplete 24, mizan 22 |
| Public symbols on `furqan.parser` | 40 (was 36; +4 AST nodes)                            |
| Public symbols on `furqan.checker`| 22 (was 18; +4 mizan-checker entry points)           |
| Public symbols on `furqan.errors` | 4 (unchanged)                                        |
| Runtime dependencies              | **0** (Python stdlib only)                           |
| Fixtures                          | bismillah(4 valid + 3 invalid + 1 known_limitation), parse_invalid(4), zahir_batin(3 valid + 3 invalid), additive_only(4 valid + 4 invalid + 7 sidecars), scan_incomplete(4 valid + 4 invalid), mizan(4 valid + 4 invalid) |
| Package version                   | `0.5.0` (minor bump for source-language additions: 4 keywords + LT/GT + comparison grammar + mizan block) |
| Compliance state at handoff       | **COMPLIANT**, full primary path shipped; no fallback invoked |
| Demo readiness (June 9)           | **EXECUTABLE END-TO-END**, three demos in <0.5ms each |

### What shipped in Session 1.6

- 8 paired `.furqan` fixtures + 1 parse_invalid fixture (chained-comparison)
- 4 keyword promotions: `mizan`, `la_tatghaw`, `la_tukhsiru`, `bil_qist`
- 2 new punctuation tokens: `LT` (`<`), `GT` (`>`)
- 4 new AST node classes: `ComparisonOp`, `BinaryComparisonExpr`, `MizanField`, `MizanDecl`
- Top-level `mizan` block parser with §6.4 field-head position enforcement (M3 routed to parser)
- Non-associative comparison-expression parser (chained `a < b < c` is a parse error)
- `furqan/checker/mizan.py` implementing Cases M1, M2, M4 (NOT M3, routed to parser per §6.6)
- 35 new tests (22 mizan + 8 tokenizer + 5 parser)
- NAMING.md §1.6 expanded with four new keywords; §1.7 documents snake_case Arabic-transliteration convention
- CHANGELOG v0.5.0 entry

### Munafiq Protocol closing register

**Test count delta (Tier 1):** 184 → 219 in 0.30s. Verified by `pytest --collect-only` and full-suite run.

**Tier-tagged claims:**

- **Tier 1 (implemented + tested):** 4 keyword promotions + 2 punctuation tokens + binary comparison expression (non-associative) + mizan block grammar + Case M1 (with per-field inline test confirming all three canonical fields fire correctly when missing) + Case M2 (with multi-occurrence test) + Case M4 (with M1-short-circuit test) + parser-level M3 (with pinned diagnostic text) + chained-comparison rejection (with pinned diagnostic text) + canonical-order acceptance + reversed-orientation acceptance + comparison-outside-mizan composability + unreachable-branch reflexivity audit.
- **Tier 2 (structural, designed, partially tested):** the M3-routing reflexivity claim (the unreachable-branch audit is a grep-style check; it confirms no dead code exists today but cannot prevent a future contributor from adding it, the test would catch the addition, but the discipline lives in CONTRIBUTING.md §8 boundaries).
- **Tier 3 (hypothesis, not implemented):** D16 runtime evaluation, D17 non-monotonic interaction warning, D18 trivial-bounds linter, D19 English aliases, Phase 2.8 status-coverage checker.
- **N=1 acknowledgement:** the demo-path execution was tested with the thesis §Primitive 4 example 1 and one inline marad variant; other Bayyinah-pattern transcriptions follow the same path.

**Honest null results:**

- The M4 out-of-order check short-circuits when M1 fires. This is a deliberate diagnostic-quality choice (avoid double signal on partial blocks), not a structural rule, a future audit that wanted M1 + M4 to both fire on the same partial block could justify the change. Documented in checker source.
- The M2 duplicate check uses first-occurrence-wins semantics. This is documented in the marad text and pinned by the multi-occurrence test.
- The §7 unreachable-branch audit is a grep test, not a static analysis; it catches obvious dead-code patterns by string match. A subtle defensive guard (e.g., spelled differently) could evade it. The audit is best-effort reflexive verification, not a formal proof.
- No fixtures failed to express what was intended. No tests pass for the wrong reason.

**Source-language additions registered (verbatim CHANGELOG v0.5.0 quote):**

> Pre-2.7 .furqan source files that used any of the following words as ordinary identifiers will fail to parse at the v0.5.0 flip: `mizan`, `la_tatghaw`, `la_tukhsiru`, `bil_qist`.

**NAMING.md §1.6 quote (first new row of v0.5.0 promotion block):**

> | `mizan`              | 2.7    | calibration block declaration head                |

**Demo readiness, combined three-primitive June 9 path:**

All three demos execute end-to-end on novel input in well under a millisecond:

- **Phase 2.5 demo** (additive-only): silent removal → Case 1 marad in 0.13–0.45 ms.
- **Phase 2.6 demo** (scan-incomplete): unguarded Integrity → Case A marad in 0.139 ms.
- **Phase 2.7 demo** (mizan): pass-path 0.173 ms; marad-path (la_tatghaw missing) 0.103 ms.

Three primitives, three marads, three minimal-fix recovery paths, one framework discipline. The Mizan demo is the simplest of the three to film: zero runtime dependencies, fully comprehensible from source-text alone, the canonical example matches thesis §Primitive 4 example 1 verbatim.

**Unreachable-branch audit verdict:** CLEAN. The M3 routing rationale (§6.6) is preserved structurally, `furqan/checker/mizan.py` contains no dead defensive code against unknown field names. The test `test_check_mizan_module_has_no_unknown_field_branch` pins this for future contributors.

### Open items for Session 1.7+

- **D11**, Consumer-side exhaustiveness (Session 1.6 deferred or Phase 3)
- **D12**, Numeric range validation on `max_confidence` (scan-incomplete follow-up, NOT mizan)
- **D13**, Full control-flow analysis (Phase 3)
- **D14**, String escape sequences (future-fixture-driven)
- **D15**, `else` arm in `if` statements (future-phase work)
- **D16**, Runtime evaluation of mizan bound expressions (Phase 3+)
- **D17**, Non-monotonic interaction warning (Phase 3)
- **D18**, Trivial-bounds linter (post-Phase-3 tooling)
- **D19**, English aliases for mizan (`calibration { upper, lower, calibrate }`)

**Next phase:** Phase 2.8, Status-Coverage Checker. Branch-coverage discipline over enum-typed values (covers all variants OR declares uncovered variants explicitly). Distinct primitive from Mizan; the natural home for the payment-refund status-collapse demo originally proposed. NOT absorbed into 2.7.

Polish-patch protocol applies. If Perplexity's post-2.7 audit identifies a small structural leak satisfying CONTRIBUTING.md §8.1, ship a Session 1.6.1 polish patch in the same shape as 1.4.1 before opening Phase 2.8.

---

## Verified state at Session 1.6 open (Phase 2.7 begin)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 2 (Prototype Type-Checker)                           |
| Sub-phase                         | 2.7, Mizan three-valued calibration block (in progress) |
| Primitives implemented            | 4 of 7 (Bismillah, zahir/batin, additive-only, scan-incomplete) |
| Test count at session open        | **184 passing** (Session 1.5 baseline)               |
| Public symbols on `furqan.parser` | 36                                                   |
| Public symbols on `furqan.checker`| 18                                                   |
| Public symbols on `furqan.errors` | 4                                                    |
| Package version                   | `0.4.0` → bumping to `0.5.0` this session for source-language additions (4 keywords + LT/GT punctuation + comparison grammar + mizan block grammar) |
| Polish-patch protocol             | First-class (CONTRIBUTING.md §8): applied twice (Sessions 1.1, 1.4.1) |
| Cross-model audit null-finding rate | Zero open findings at session open                 |

### Sync probes confirming Session 1.5 state at this open

- `pytest --collect-only`: 184 tests across 7 files (tokenizer 42, parser 30, bismillah 19, marad 7, zahir_batin 22, additive 40, incomplete 24).
- 8 scan_incomplete fixtures present (4 valid + 4 invalid).
- `furqan.checker.incomplete` exports confirmed (PRIMITIVE_NAME, REQUIRED_INCOMPLETE_FIELDS, INTEGRITY_TYPE_NAME, INCOMPLETE_TYPE_NAME, check_incomplete, check_incomplete_strict).
- `Integrity` and `Incomplete` lex as IDENT (deliberate non-promotion, NAMING.md §1.6).
- STRING, PIPE, IF, NOT, RETURN tokens present.
- Statement-tree body parser landed (`fn.statements` field populated).
- Public surface 36/18/4.
- CHANGELOG v0.4.0 entry present; NAMING.md §1.6 documents `if`/`not`/`return` promotion; LEXER.md §4 (STRING) and §5 (Integrity-not-keyword) present; CONTRIBUTING.md §8 polish-patch protocol intact.

---

## Verified state at Session 1.5 close (Phase 2.6 shipped, COMPLIANT)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 2 (Prototype Type-Checker)                           |
| Sub-phase                         | 2.6, scan-incomplete return-type checker (**SHIPPED**) |
| Primitives implemented            | **4 of 7**, Bismillah, zahir/batin, additive-only, scan-incomplete |
| Test count                        | **184 passing in 0.32s** (Session 1.4.2 baseline: 149; net +35) |
| Test files                        | 7 (`test_tokenizer`, `test_parser`, `test_bismillah`, `test_marad`, `test_zahir_batin`, `test_additive`, `test_incomplete`) |
| Distribution                      | tokenizer 42, parser 30, bismillah 19, marad 7, zahir_batin 22, additive 40, incomplete 24 |
| Public symbols on `furqan.parser` | 36 (was 24; +12 AST nodes)                           |
| Public symbols on `furqan.checker`| 18 (was 12; +6 scan-incomplete entry points)         |
| Public symbols on `furqan.errors` | 4 (unchanged)                                        |
| Runtime dependencies              | **0** (Python stdlib only)                           |
| Fixtures                          | bismillah(4 valid + 3 invalid + 1 known_limitation), parse_invalid(3), zahir_batin(3 valid + 3 invalid), additive_only(4 valid + 4 invalid + 7 sidecars), scan_incomplete(4 valid + 4 invalid) |
| Package version                   | `0.4.0` (minor bump for source-language additions: STRING token, PIPE punctuation, three new keywords) |
| Compliance state at handoff       | **COMPLIANT**, full primary path shipped; no fallback invoked |
| Demo readiness (June 9)           | **EXECUTABLE END-TO-END**, Phase 2.5 (additive-only) + Phase 2.6 (scan-incomplete) demos both run on novel input in well under a millisecond |

### What shipped in Session 1.5

- 8 paired `.furqan` fixtures + the canonical demo (`scan_returns_integrity_unguarded`)
- 3 keyword promotions: `if`, `not`, `return`
- 2 new token kinds: `STRING` (no-escape v1), `PIPE` (`|`)
- 12 new AST node classes for the statement-tree grammar
- Statement-tree body parser (replaces call-only loop) with calls/accesses accumulator threading
- `_parse_return_type` accepting binary unions
- `furqan/checker/incomplete.py` implementing both thesis §4 cases
- 35 new tests (18 incomplete + 11 tokenizer + others)
- `docs/internals/LEXER.md` §4 (STRING) and §5 (Integrity/Incomplete-not-keywords)
- NAMING.md §1.6 expanded with three new keywords + Phase 2.6 promotion rationale
- CHANGELOG v0.4.0 entry

### Munafiq Protocol closing register

**Test count delta (Tier 1):** 149 → 184 in 0.32s. Verified by `pytest --collect-only` and full-suite run.

**Tier-tagged claims:**

- **Tier 1 (implemented + tested):** Case A producer-side check (unguarded, inverted-guard, negated-guard, non-union, no-Integrity-return); Case B literal-shape check (per-field positive + negative + multi-missing); STRING tokenization (well-formed, empty, with-punctuation, unterminated, with-newline-rejection); PIPE punctuation; three keyword promotions; binary union return type; Incomplete literal grammar with field-name-dispatched value parsing; 8 paired fixtures + 1 demo path proof outside fixtures.
- **Tier 2 (structural, designed, partially tested):** the syntactic incompleteness-check detection rule (tested with two-branch shapes; helper-extracted predicates and flag-variable guards not tested but acknowledged as known limitations).
- **Tier 3 (hypothesis, not implemented):** D11 consumer-side exhaustiveness, D12 numeric range validation on max_confidence, D13 full control-flow analysis, D14 string escape sequences, D15 `else` arm in if-statements.
- **N=1 acknowledgement:** the demo-path execution was tested with one freshly-constructed novel input (`scan_pdf(file: File) -> Integrity | Incomplete { return Integrity }`); other Bayyinah-pattern transcriptions would follow the same path.

**Honest null results:**

- The Phase 2.6 syntactic incompleteness-check rule is conservative. It accepts ONLY `if not <expr>` enclosing forms; legitimate code using helper functions for predicates (e.g., `let safe = is_safe(file); if safe { ... }`) would produce false-positive Case A marads. This is acknowledged in the checker docstring and registered as D13 for Phase 3.
- Calls inside expressions (e.g., `is_encrypted(file)` in an `if` condition) are NOT extracted into `fn.calls` for the bismillah checker. A function could place a not_scope-violating call inside an if-condition and silently pass bismillah. This is a Phase-3 plumbing item not load-bearing for any current fixture.
- No fixtures failed to express what was intended. No tests pass for the wrong reason (each named-property test asserts on specific case-number strings or specific field names).

**Source-language additions registered (verbatim CHANGELOG v0.4.0 quote):**

> Pre-2.6 .furqan source files that used any of the following words as ordinary identifiers will fail to parse at the v0.4.0 flip: `if`, `not`, `return`.

**NAMING.md §1.6 quote (first new row of v0.4.0 promotion block):**

> | `if`                 | 2.6    | conditional statement head                        |

**Demo readiness (June 9 path):**

The combined two-primitive demo runs end-to-end in well under a millisecond on novel input:

- **Phase 2.5 demo** (additive-only): `module ScanRegistry v2.0` silently dropping `severity_weights` → Case 1 marad in 0.13–0.45 ms.
- **Phase 2.6 demo** (scan-incomplete): `fn scan_pdf(file: File) -> Integrity | Incomplete { return Integrity }` → Case A marad in **0.139 ms**. The honest fix (`if not is_encrypted(file) { return Integrity } return Incomplete { ... }`) passes cleanly in 0.401 ms.

Both demos execute on freshly-constructed inputs, not fixture replays. Together they form a 10-minute live-demonstration core: two primitives, two marads, two minimal-fix recovery paths, all from the same framework discipline.

### Open items for Session 1.6+

- **D11**, Consumer-side exhaustiveness checking (Session 1.6 or Phase 3)
- **D12**, Numeric range validation on `max_confidence` (Phase 2.7 Mizan)
- **D13**, Full control-flow analysis (Phase 3)
- **D14**, String escape sequences (future-fixture-driven)
- **D15**, `else` arm in `if` statements (future-phase work)

**Next primitive (Tanzil):** Phase 2.7, Mizan three-valued bound checker (thesis §3.4). Numeric bounds calibration for optimization targets: `la_tatghaw` (do not overfit), `la_tukhsiru` (do not underfit), `bil_qist` (calibrate fairly). Phase 2.7 contribution is parsing the `mizan { ... }` block and verifying syntactic well-formedness; the runtime calibration aspect belongs to a later phase.

Polish-patch protocol applies. If Perplexity's post-2.6 audit identifies a small structural leak satisfying CONTRIBUTING.md §8.1, ship a Session 1.5.1 polish patch in the same shape as 1.4.1 before opening Phase 2.7.

---

## Verified state at Session 1.5 open (Phase 2.6 begin)

| Metric                            | Value                                                |
|-----------------------------------|------------------------------------------------------|
| Phase                             | 2 (Prototype Type-Checker)                           |
| Sub-phase                         | 2.6, scan-incomplete return-type checker (in progress) |
| Primitives implemented            | 3 of 7 (Bismillah, zahir/batin, additive-only)       |
| Test count at session open        | **149 passing** (Session 1.4.2 baseline)             |
| Public symbols on `furqan.parser` | 24                                                   |
| Public symbols on `furqan.checker`| 12                                                   |
| Public symbols on `furqan.errors` | 4                                                    |
| Package version                   | `0.3.2` → bumping to `0.4.0` this session for source-language additions (STRING token + Integrity/Incomplete type names) |
| Polish-patch protocol             | **First-class**, formally documented in CONTRIBUTING.md §8; applied twice (Sessions 1.1, 1.4.1) |
| Cross-model audit null-finding rate | Zero open findings at session open                 |

### Sync probes confirming Session 1.4.2 state at this open

- `pytest --collect-only`: 149 tests across 6 files (tokenizer 31, parser 30, bismillah 19, marad 7, zahir_batin 22, additive 40).
- 8 additive_only fixtures + 7 sidecars present.
- `furqan.checker.additive` exports `check_additive`, `check_module`, `check_module_strict`, `PRIMITIVE_NAME`, `Result`.
- `_lex_error_sidecar_marad` helper present (line 584).
- `verify` lexes as `IDENT` (NAMING.md §1.5 holds).
- `NUMBER` token in place (Phase 2.5 lex addition).
- CHANGELOG v0.3.1 cites "Session 1.4.1 polish (Perplexity E2 finding)"; v0.3.2 entry documents-only contract.
- CONTRIBUTING.md §8 contains all six subsections; §9 is renumbered Closing.

---

## Verified state at Session 1.4 close (Phase 2.5 shipped, COMPLIANT)

| Metric                              | Value                                                |
|-------------------------------------|------------------------------------------------------|
| Phase                               | 2 (Prototype Type-Checker)                           |
| Sub-phase                           | 2.5, additive-only module checker (**SHIPPED**)     |
| Primitives implemented              | **3 of 7**, Bismillah scope + zahir/batin + additive-only |
| Test count                          | **147 passing in 0.17s** (Session 1.3 baseline: 97; net +50) |
| Test files                          | 6 (`test_tokenizer`, `test_parser`, `test_bismillah`, `test_marad`, `test_zahir_batin`, `test_additive`) |
| Distribution                        | tokenizer 31, parser 30, bismillah 19, marad 7, zahir_batin 22, additive 38 |
| Public symbols on `furqan.parser`   | 24 (was 18; +6 AST nodes)                            |
| Public symbols on `furqan.checker`  | 12 (was 7; +5 additive entry points)                 |
| Public symbols on `furqan.errors`   | 4 (was 3; +1 `Advisory`)                             |
| Runtime dependencies                | **0** (Python stdlib only)                           |
| Fixtures                            | bismillah(4 valid + 3 invalid + 1 known_limitation), parse_invalid(3), zahir_batin(3 valid + 3 invalid), additive_only(4 valid + 4 invalid + 7 sidecars) |
| Package version                     | `0.3.0` (minor bump for Phase 2.5 source-language breakage) |
| Compliance state at handoff         | **COMPLIANT**, full primary path shipped; no fallback invoked |
| F1 / F2 status                      | **CLOSED** since Session 1.3                         |
| Demo readiness (June 9 live demo)   | **EXECUTABLE END-TO-END** with current artifact      |

### What shipped in Session 1.4

- 8 paired `.furqan` fixtures with 7 sidecars (the surface contract)
- 6 keyword promotions: `additive_only`, `module`, `export`, `major_version_bump`, `removes`, `renames`
- 1 new token kind: `NUMBER` (integer-only; multi-component decimals reconstructed at parser layer)
- 6 new AST node classes (VersionLiteral, ExportDecl, RemovesEntry, RenamesEntry, MajorVersionBump, AdditiveOnlyModuleDecl)
- New `Advisory` type (Session 1.1 D1 lands)
- `furqan/checker/additive.py` implementing the four thesis §3.3 cases
- `check_additive` (pure, in-memory) AND `check_module` (sidecar-aware): both shipped, no fallback invoked
- 38 new additive-only tests + 12 new tokenizer tests (50 total)
- `docs/internals/LEXER.md` (new) and `docs/internals/CHECKER.md` (new)
- Updated NAMING.md §1.6 with six new keyword entries + per-keyword promotion rationale
- CHANGELOG v0.3.0 entry registering the source-language breakage

### Munafiq Protocol closing register

**Test count delta (Tier 1):** 97 → 147 in 0.17s. Verified by `pytest --collect-only` and full-suite run.

**Tier-tagged claims:**

- Tier 1 (implemented + tested): all four cases (1, 2-enforcement, 2-advisory, 3, 4); pure `check_additive`; sidecar-aware `check_module`; malformed-sidecar handling; non-adjacent-prior detection; empty-bump-catalog acceptance; numeric-literal lexing; six keyword promotions; `Advisory` type and rendering.
- Tier 2 (structural, designed, partially tested): the adjacency rule across major bumps (tested with v2.0 → v1.5; v3.0 → v1.x not tested but follows the same pattern).
- Tier 3 (hypothesis, not implemented): D7 `type_changes:` catalog entry, D8 structural subtyping, D9 multi-module dependency graphs.
- N=1 acknowledgement: the demo readiness path was tested end-to-end with one fixture (`module_v2_removed_export`); other Bayyinah-style transcriptions would follow the same path.

**Honest null results:**

- The Case 2 advisory's positive-fire test was added inline (not as a fixture file), because the advisory requires a sidecar with matching type signatures, adding it as a fixture file would have required a separate fixture pair. Inline test confirms behaviour; the fixture absence is documented as an acceptable shortcut.
- The Case 2 advisory does NOT fire on the `module_v2_renamed_export.furqan` invalid fixture, the catalog entry is present (and dishonest), so the advisory's "no catalog entry" precondition is not met. This is the correct behaviour but is *not* tested by the fixture sweep alone; the inline `test_case_2_advisory_fires_on_undeclared_rename_with_matching_types` covers it explicitly.
- No fixtures failed in development. No tests passed for the wrong reason (each named-property test pins a specific case-number string, ensuring the expected case fired and not a different one).

**v0.3.0 source-language breakage, verbatim CHANGELOG quote:**

> Pre-2.5 .furqan source files that used any of the following words as ordinary identifiers will fail to parse at the v0.3.0 flip: `additive_only`, `module`, `export`, `major_version_bump`, `removes`, `renames`.

**v0.3.0, verbatim NAMING.md §1.6 entry quote (first row of the v2.5 promotion block):**

> | `additive_only`      | 2.5    | additive-only module declaration head             |

**Demo readiness, June 9 path executable:**

The pipeline `Bayyinah MECHANISM_REGISTRY → .furqan transcription → remove export → run checker → show marad` runs end-to-end in under 0.2 seconds on existing fixtures and produces a structured marad with diagnosis + minimal_fix + regression_check naming the rule violated. Verified by behavioural spot-check.

### Next session, Phase 2.6 (scan-incomplete): open items

- D6, sidecar file discovery (CLI-layer concern; deferrable to Phase 3)
- D7, `type_changes:` catalog entry (Phase 2.5+ design)
- D8, structural subtyping on TypePath (Phase 3)
- D9, multi-module dependency graphs (Phase 3+)

The natural next primitive (per Tanzil order) is **Phase 2.6, scan-incomplete return type** (thesis §4): `Integrity | Incomplete<T>` union return types where a function returning `Integrity` while a path of its body could not fully process the input is a marad. Requires extending the parser to recognise return-type unions.

---

## Verified state at Session 1.4 open (Phase 2.5 begin)

| Metric                           | Value                                                |
|----------------------------------|------------------------------------------------------|
| Phase                            | 2 (Prototype Type-Checker)                           |
| Sub-phase                        | 2.5, additive-only module checker (in progress)     |
| Primitives implemented           | 2 of 7 (Bismillah scope, zahir/batin)                |
| Test count at session open       | **97 passing** (Session 1.3 baseline)                |
| Public symbols on `furqan.parser`| 18                                                   |
| Public symbols on `furqan.checker`| 7                                                   |
| Public symbols on `furqan.errors`| 3                                                    |
| Package version                  | `0.2.0` → bumping to `0.3.0` this session for source-language breakage (six new keywords) |
| F1 / F2 status                   | **CLOSED** in Session 1.3, strict parsers in place  |

### Sync probes confirming Session 1.3 state at this open

- `pytest --collect-only` reports 97 tests across 5 files (19 + 7 + 30 + 19 + 22).
- 6 zahir/batin fixtures present (3 valid + 3 invalid).
- `VERIFY_FUNCTION_NAME = "verify"` constant at module level in `src/furqan/checker/zahir_batin.py`.
- `verify` tokenizes to `TokenKind.IDENT` (deliberately not promoted, NAMING.md §1.5).
- `type`, `zahir`, `surface`, `batin`, `depth` all in the `KEYWORDS` table.
- Zero opaque-eater patterns in `parse_function_def`; `_parse_param_list` and `_parse_type_path` are in place.

---

## Verified state at Session 1.3 close (Phase 2.4 shipped)

| Metric                         | Value                                                |
|--------------------------------|------------------------------------------------------|
| Phase                          | 2 (Prototype Type-Checker)                           |
| Sub-phase                      | 2.4, zahir/batin type checker (**SHIPPED**)         |
| Primitives implemented         | **2 of 7**, Bismillah scope + zahir/batin           |
| Test count                     | **97 passing in 0.15s** (Session 1.2 baseline: 75)   |
| Test files                     | 5 (`test_tokenizer`, `test_parser`, `test_bismillah`, `test_marad`, `test_zahir_batin`) |
| Distribution                   | tokenizer 19, parser 30, bismillah 19, marad 7, zahir_batin 22 |
| Public symbols on `furqan.parser` | 18 (was 12; +6 AST nodes)                         |
| Public symbols on `furqan.checker`| 7 (was 3; +4 zahir/batin entry points + constant) |
| Public symbols on `furqan.errors` | 3 (unchanged)                                     |
| Runtime dependencies           | **0** (Python stdlib only)                           |
| Fixtures                       | 4 valid + 3 invalid + 3 parse_invalid + 1 known_limitation + 6 zahir_batin (3 valid + 3 invalid) |
| Package version                | `0.2.0` (minor bump for Phase 2.4 surface expansion) |
| Compliance state at handoff    | **COMPLIANT**, every declared deliverable shipped, additive-only invariant held, every prior test passes unmodified |

### What shipped in Session 1.3

- 6 paired `.furqan` fixtures pinning the Phase 2.4 grammar surface (the surface contract)
- 5 keyword promotions (`type`, `zahir`, `surface`, `batin`, `depth`); `verify` deliberately stays IDENT (NAMING.md §1.5)
- 6 new AST node classes for compound types, layer blocks, fields, parameters, type paths, layer accesses
- F1 (parameter-list parser) and F2 (return-type parser) closed, opaque eaters replaced with strict parsers
- Layer-access pre-scan in `_parse_call`'s argument-list consumer
- Top-level compound-type declaration grammar in `parse_module`
- `furqan/checker/zahir_batin.py` implementing the three thesis §3.2 cases
- 22 tests, including 6 fixture-sweep parametrizations + 16 named-property tests

### Phase-2.4 deferred items registered for next session

- **D3, Field-level access checking.** Phase 2.4 verifies layer access (`doc.zahir` vs `doc.batin`) but not field-name resolution. Belongs to Phase 2.5+ where module-level symbol tables enter.
- **D4, Behavioral verification of `verify`.** Thesis §7 Failure Mode 1, verifying that a function named `verify` actually performs cross-layer comparison is beyond what a type system can guarantee. Recorded as a known limit, not a future fix.
- **D5, Nested calls inside argument lists.** Bismillah scope checker doesn't see them. Flagged for Phase 2.7.

### Next session, proposed scope

**Phase 2.5, additive-only module checker** (thesis §3.3). Compare a module's exported symbols at version N+1 against version N. Removed or renamed exports without explicit `major_version_bump` is a marad. The pattern transposes from Bayyinah's `MECHANISM_REGISTRY` import-time coherence assertion. This primitive will require introducing the version-history surface (proposed: `// @version N.M` annotation + sibling `.furqan_history` reference module). Design conversation about which form of version history to adopt is a Phase-2.5 prerequisite.

The Cow Episode warning continues: do not pre-build a multi-module type system before Phase 2.5's fixtures require it.

---

## Verified state at Session 1.3 open (Phase 2.4 begin)

| Metric                         | Value                                                |
|--------------------------------|------------------------------------------------------|
| Phase                          | 2 (Prototype Type-Checker)                           |
| Sub-phase                      | 2.4, zahir/batin type checker (begun)               |
| Primitives implemented         | 1 of 7, Bismillah scope (Sessions 1.0-1.2 shipped)  |
| Test count                     | **75 passing in 0.11s** (Session 1.2 baseline)       |
| Test files                     | 4 (`test_tokenizer`, `test_parser`, `test_bismillah`, `test_marad`) |
| Distribution                   | tokenizer 19, parser 30, bismillah 19, marad 7       |
| Public symbols on `furqan.parser` | 12                                                |
| Public symbols on `furqan.checker`| 3                                                 |
| Public symbols on `furqan.errors` | 3                                                 |
| Runtime dependencies           | **0** (Python stdlib only)                           |
| Fixtures                       | 4 valid + 3 invalid + 3 parse_invalid + 1 known_limitation |
| Reference modules              | none yet (Session 1.x is single-version)             |
| Phase 2.4 first-task surface   | F1 (param-list parser), F2 (return-type parser): both replace, not harden |

### Sync probes confirming Session 1.2 state at this open

- `pytest --collect-only` reports 75 tests across 4 files.
- `tests/fixtures/parse_invalid/` exists with 3 fixtures
  (`call_arg_stray_lbrace`, `call_arg_stray_rbrace`,
  `call_arg_braced_inner_call`).
- `tests/fixtures/valid/call_arg_paren_only.furqan` is present.
- `pytest` runs 75/75 green in 0.11s.

---

## Verified state at end of Session 1.2 (Phase 2.3 close + hardening)

| Metric                         | Value                                                |
|--------------------------------|------------------------------------------------------|
| Phase                          | 2 (Prototype Type-Checker)                           |
| Sub-phase                      | 2.0–2.3 complete + 1.2 hardening                     |
| Primitives implemented         | 1 of 7 (Bismillah scope)                             |
| Test count                     | **75 passing in 0.11s**                              |
| Test files                     | 3 (`test_tokenizer`, `test_parser`, `test_bismillah`)|
| Source files                   | tokenizer, parser, AST nodes, marad error type, bismillah checker |
| Public symbols on `furqan.parser` | 12 (tokenizer + AST + parse entry point)         |
| Public symbols on `furqan.checker`| 3 (`check_bismillah`, `check_bismillah_strict`, primitive name) |
| Public symbols on `furqan.errors` | 3 (`Marad`, `MaradError`, `raise_marad`)         |
| Runtime dependencies           | **0** (Python stdlib only)                           |
| `.furqan` test fixtures        | 6 (3 valid + 3 invalid; paired discipline holds)     |

---

## What shipped

### Phase 2.0, scaffolding

- `pyproject.toml` (src-layout, zero runtime deps, dev-only pytest)
- `docs/NAMING.md`: naming discipline (Arabic + English alias rule,
  marad field structure, additive-only invariant)
- `docs/CONTRIBUTING.md`: governance protocol
  (COMPLIANT/PARTIAL/BLOCKED, five-step workflow, skip rule,
  dependency policy)
- `README.md`: surface description + primitive roadmap

### Phase 2.1, tokenizer

- `src/furqan/parser/tokenizer.py`: hand-written single-pass
  tokenizer. Recognises 7 keywords (`bismillah`, `scope_block`,
  `authority`, `serves`, `scope`, `not_scope`, `fn`), identifiers,
  the punctuation `{ } ( ) : , .`, the multi-char `->`, and `//` line
  comments. Tracks line/column. Raises `TokenizeError` on unknown
  characters with a marad-style message that lists what is accepted.
- `tests/test_tokenizer.py`: 19 tests pinning EOF behavior,
  identifier rules, every keyword's lex kind, the
  bismillah/scope_block alias distinction at the lex level, line and
  column tracking, comment elision, and unknown-character errors.

### Phase 2.2, AST + parser

- `src/furqan/parser/ast_nodes.py`: `SourceSpan`, `CallRef`,
  `BismillahBlock`, `FunctionDef`, `Module`. All frozen dataclasses;
  the AST is immutable.
- `src/furqan/parser/parser.py`: recursive-descent parser. Enforces
  exactly-one-Bismillah-per-module, all four required Bismillah
  fields, accepts both Arabic and English aliases identically (with
  `alias_used` recorded), parses qualified-name lists, parses
  function bodies as call-reference sets (no expression grammar yet).
  First parse error raises `ParseError` with a precise SourceSpan.
- `tests/test_parser.py`: 22 tests pinning each grammar rule, all
  four required-field error cases (parametrized), uniqueness of the
  Bismillah block, alias equivalence, multi-function modules,
  trailing-token rejection, and span correctness.

### Phase 2.3, Bismillah scope checker + paired fixtures

- `src/furqan/errors/marad.py`: diagnosis-structured error type per
  thesis §3.7. `Marad` is a frozen dataclass with the four required
  fields (`diagnosis`, `location`, `minimal_fix`, `regression_check`)
  plus a `primitive` tag. `MaradError` wraps it for raise-and-catch.
  `Marad.render()` produces the human-readable form.
- `src/furqan/checker/bismillah.py`: the scope checker. Two entry
  points: `check_module` (returns list of marads, fail-soft) and
  `check_module_strict` (raises on first marad, fail-fast). Walks
  every function's call references; flags any call whose head
  identifier appears in `not_scope`.
- `tests/fixtures/valid/`: 3 paired-fixture files (a full module
  that respects scope, a degenerate empty module, the
  `scope_block` alias variant).
- `tests/fixtures/invalid/`: 3 paired-fixture files (direct
  violation, qualified-call violation, violation in the second
  function only).
- `tests/test_bismillah.py`: 13 tests. Two are parametrized fixture
  sweeps (every valid file produces zero diagnostics; every invalid
  file produces ≥1). Eleven are named-property tests pinning
  diagnostic content, alias preservation in error messages, location
  pointing at the call (not the Bismillah), strict-variant raising
  semantics, and the `Marad.render()` format.

---

## What was attempted and not shipped

Nothing was attempted and abandoned in this session. The scope set in
Step 4 was held: tokenizer → parser → Bismillah checker → fixtures →
verification. The skip rule was not invoked.

One unplanned but ~5-minute setup detour: the initial pyproject
`package-dir = { "furqan" = "src" }` directive plus
`packages.find` did not produce an importable `furqan` namespace, setuptools instead exposed each subpackage as a top-level module.
Resolved by switching to the standard `src/furqan/` src-layout. The
intermediate state was caught by the first pytest run, not by review.

---

## Next session, proposed scope

Tanzil order within Phase 2:

1. **Phase 2.4, zahir/batin type checker** (thesis §3.2).
   Compound types declaring `zahir { ... }` and `batin { ... }`
   field blocks. Functions annotate which layer they access via
   `Type.zahir` or `Type.batin` parameter types. Cross-layer access
   without a `verify(...)`-typed function is a marad. This is the
   second cleanest primitive after Bismillah and the one the thesis
   gives the most formal-sketch attention (§6.5 has the type rules
   in judgment-style notation, port them directly).

2. **Phase 2.5, additive-only module checker** (thesis §3.3).
   Compare a module's exported symbols at version N+1 against
   version N (read from a sibling `.furqan_history` file or an
   inline `// @version N.M` annotation; design decision pending).
   Removed or renamed exports without `major_version_bump` is a
   marad. This is structurally most similar to Bayyinah's
   `MECHANISM_REGISTRY` import-time coherence assertion, the
   pattern transposes directly.

3. **Phase 2.6, scan-incomplete return type** (thesis §4).
   `Integrity | Incomplete<T>` union return types. A function that
   returns `Integrity` while a path of its body could not fully
   process the input is a marad. Requires extending the parser to
   recognise return-type unions.

4. **Phase 2.7, Mizan three-valued bound checker** (thesis §3.4).
   Lowest priority for the prototype: the runtime-calibration aspect
   makes most of the work belong to a future evaluator, not the
   static checker. Phase 2 contribution is parsing the `mizan { ... }`
   block and verifying syntactic well-formedness (all three of
   `la_tatghaw`, `la_tukhsiru`, `bil_qist` present).

The ring-close primitive (§3.6), tanzil build ordering (§3.5), and
marad's deeper integration with caller-side `regression_check`
verification (§3.7) are Phase-3 concerns: they require either a
build system (tanzil) or whole-program analysis (ring-close,
caller-side regression-check) that Phase 2's per-module surface does
not yet have.

### Anti-patterns to avoid in the next session

- **The Cow Episode (2:67–74):** do not pre-specify a full type
  grammar before observing what the next primitive needs. Extend the
  parser only as far as the Phase-2.4 fixtures require. The current
  parser's deliberate gaps (no expressions, no parameter types) are
  features.
- **Do not rebuild what works.** The `Marad` infrastructure is
  general-purpose; the next checker uses it as-is. Adding fields to
  `Marad` is a Process-2 risk, it means existing diagnostics
  silently lose information. Extend by adding new fields with safe
  defaults, never mutating the contract.
- **Do not introduce dependencies.** stdlib-only is the discipline.
  If a parser-generator looks tempting, the answer is the same as in
  Session 1: hand-write it, the surface stays auditable.
- **Run `pytest` after every primitive's fixtures land**, before
  moving to the next. The Bayyinah-style additive-only invariant is
  cheap to maintain when it is checked at every step.

---

## Compliance state at handoff

**COMPLIANT.** All declared session deliverables shipped. Every
existing test passes. No silent additions to the public surface; the
57 tests pin the surface that exists. The marad rendering format is
stable; the Bismillah primitive's checker entry points are pinned in
`furqan/checker/__init__.py`. NAMING.md §6 (additive-only on the
type-checker's own surface) is satisfied as of this writing.

---

## How to run

```bash
cd <repo>
pip install -e '.[dev]'
pytest                 # all 57 tests, ~0.1s
```

End-to-end check on a single file (no CLI yet, Phase 3):

```python
from pathlib import Path
from furqan.parser import parse
from furqan.checker.bismillah import check_module

src_path = Path("path/to/your.furqan")
module = parse(src_path.read_text(), file=str(src_path))
for marad in check_module(module):
    print(marad.render())
```

