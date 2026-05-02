# Changelog

All notable changes to the Furqan prototype type-checker are recorded
here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/spec/v2.0.0.html).

The Phase-2 prototype roadmap is the seven-primitive Tanzil ordering
declared in `HANDOFF.md`. Each session's deliverables land additively
on the prior session's surface, the additive-only invariant the
type-checker enforces on user code is enforced on the type-checker
itself (NAMING.md §6).

---

## [0.11.1] - 2026-05-02

### Added

- `MAX_NESTING_DEPTH` re-exported from `furqan.parser` (the public
  package surface), not only from `furqan.parser.parser`. A
  user-facing contract should be importable from the surface a user
  reaches for first. Added to `furqan.parser.__all__`. Closes the
  surface gap in Q10's first-step closure surfaced by the round-five
  audit.
- README "Resource limits" section documenting the parser's
  guaranteed minimum nesting depth (`MAX_NESTING_DEPTH = 200`), the
  exit code on overflow (`2` PARSE ERROR), and the importable
  constant. The one-line README addition Q10 said should land the
  day Q9 ships.
- `tests/test_parser_resource_limits.py` gains
  `test_max_nesting_depth_is_re_exported_at_package_surface` (+1
  test) pinning the package-level re-export and `__all__`
  membership.

### Fixed

- `QUESTIONS.md` discipline: Q9 moved from Open to Resolved with
  the version that closed it (`v0.11.0`), commit SHA, and the
  list of mechanisms that closed it. The empty `## Resolved`
  section that shipped in v0.11.0 was the exact failure mode
  QUESTIONS.md exists to prevent (surface and substrate out of
  sync). Q10's body updated with first-step status referencing
  the v0.11.1 surface fixes.
- `SECURITY.md` supported-versions table rephrased from
  enumerated minor versions (which would go stale on every
  release) to "latest minor on main" (additive-invariant
  applied to the security policy).
- README's "zero open findings" claim re-scoped to its actual
  protocol (LLM cross-collaborator audit) with a pointer to
  `QUESTIONS.md` for human-audit findings, including Q5's
  question about the limits of LLM cross-verification itself.
  The bracketed scope was technically accurate but read as a
  blanket claim to a reader who did not open QUESTIONS.md.

### Tests

- 538 -> 539 (+1). All v0.11.0 tests pass identically.

### Unchanged

- Parser, tokenizer, ten checker modules, public surface counts
  (parser 42 / checker 38 / errors 4), `furqan.Project`, G1/G2/G3,
  CLI directory mode, D23 cross-module type resolution.
- 28 keywords. Apache-2.0 license. SECURITY.md scope and reporting
  procedure (only the supported-versions row rephrased).

---

## [0.11.0] - 2026-05-02

### Added

- `check_status_coverage` and `check_status_coverage_strict` gain a
  keyword-only `producer_predicate` parameter (default `None`,
  resolves to the existing `_is_integrity_incomplete_union`). Enables
  furqan-lint and future language adapters to supply their own
  producer detection without monkey-patching. Threaded through
  `_check_calls` so every internal producer detection respects the
  caller's predicate, not just the producer-map build.
- QUESTIONS.md Q11 (minimal-fix-as-prose contract) and Q12 (advisory
  CLI visibility). Two additional structural-honesty questions
  surfaced by the round-3 audit.
- `MAX_NESTING_DEPTH = 200` constant exported from
  `furqan.parser.parser`. Surfaces the parser's nesting limit as an
  importable contract per Q10's first-step closure.
- `tests/fixtures/parse_errors/deep_nest.furqan` (depth-500 torture
  fixture) and `tests/test_parser_resource_limits.py` (6 new tests).

### Fixed

- Parser no longer crashes with a Python `RecursionError` on deeply
  nested input. Nesting beyond the parser's limit
  (`MAX_NESTING_DEPTH = 200`) now produces a structured `ParseError`
  with exit code `2` (PARSE ERROR) instead of exit code `1` (MARAD)
  and a 2,998-line Python traceback. Closes the discipline violation
  identified in the round-3 audit (QUESTIONS.md Q9).
  Belt-and-suspenders: the top-level `parse()` function also catches
  any `RecursionError` that escapes the depth-guard and converts it
  to `ParseError` with a `<file>:1:1` span.

### Changed

- `_parse_statement` and `_parse_if_statement` accept a keyword-only
  `depth: int = 0` parameter. Each nested if-body or else-body
  recurses at `depth + 1`, and the dispatch point in
  `_parse_statement` raises `ParseError` when depth exceeds
  `MAX_NESTING_DEPTH`. Internal API; default value preserves all
  pre-existing call sites.

### Tests

- 527 -> 538 (+11). All v0.10.x tests pass identically.

### Unchanged

- Seven core primitives. Parser, tokenizer, ten checker modules
  unchanged outside the parser-resource-limit fix.
- 28 keywords. Public surface: parser 42, checker 38, errors 4.
- `furqan.Project`, G1/G2/G3, CLI directory mode, D23 cross-module
  type resolution all unchanged from v0.10.1.

---


## [0.10.1] - 2026-04-30

**Phase 3 / Session 1.15: D23 cross-module type resolution
completion.** v0.10.0 already wired the `imported_types` parameter
through `Project.check_all` and shipped `valid/cross_module_type`.
v0.10.1 closes the gaps: the strict variant of ring-close now
forwards `imported_types`, two new invalid fixtures pin the
direct-only scoping rule, and a dedicated test module
(`test_cross_module_type.py`) pins the parameter contract
end-to-end.

A patch-level bump (0.10.0 to 0.10.1) reflects the strict-variant
fix and the new test surface; no behaviour change for callers using
the soft variant.

### Added

* `check_ring_close_strict` now accepts the keyword-only
  `imported_types` parameter and forwards it to `check_ring_close`.
  The fail-fast path agrees with the soft path on cross-module
  resolution.
* Two new invalid multi-module fixtures:
  - `tests/fixtures/multi_module/invalid/type_not_in_dep/` (A
    depends on B but references a type neither defines).
  - `tests/fixtures/multi_module/invalid/transitive_type/` (A
    depends on B, B depends on C; A references C's type without
    declaring depends_on: C - direct-only scoping fires R1).
* `tests/test_cross_module_type.py` (18 tests) covering the
  parameter contract: default empty, keyword-only, parameter +
  return + union-arm coverage, unknown-type still fires, builtins
  still exempt, R4 unaffected, strict-variant forwarding,
  cross-module fixture pass / fail behaviour, CLI directory mode
  integration, single-file backward compatibility.
* Sweep test in `test_multi_module.py` (`test_every_invalid_fixture
  _produces_a_marad`) updated to look for marads anywhere in
  `check_all()` output, not just `check_graph()`. The two new
  D23 invalid fixtures produce per-module R1 marads (graph is
  clean); the sweep now sees them via the unified view.

### Tests

* 507 -> 527 (+20). All v0.10.0 tests pass identically.

### Unchanged

* Seven core primitives. Parser, tokenizer, ten checker modules.
* 28 keywords. Public surface unchanged.
* `furqan.Project`, G1/G2/G3, CLI directory mode all unchanged
  from v0.10.0.

---

## [0.10.0] - 2026-04-30

**D9/D20 / Phase 1 multi-module support.** Furqan grows beyond
single files. A new `Project` class parses multiple `.furqan`
files, builds the dependency graph from each module's tanzil
declarations, and runs three new graph-level checks. The CLI
gains a directory mode: `furqan check src/` checks every
`.furqan` file in the directory, with optional `--graph-only`
for dependency-structure validation without per-module analysis.

A minor-version bump (0.9.x -> 0.10.0) reflects new architectural
capability. Per-module checkers are unchanged; the language now
composes across compilation units.

### Added
- **D9/D20: Multi-module graph analysis.**
  - New module: `src/furqan/project.py` with the `Project` class.
  - `Project.add_file` and `Project.add_directory` parse files
    and index them by bismillah name.
  - `Project.dependency_graph` returns the adjacency list built
    from each module's tanzil declarations.
  - `Project.topological_order` returns a deterministic dependency
    order via Kahn's algorithm (or `None` on cycle).
  - `Project.check_graph` runs the three graph-level cases:
    - **G1, missing dependency target (Marad).** A tanzil block
      declares `depends_on: X` but no module named `X` is in the
      project.
    - **G2, cross-module cycle (Marad).** The dependency graph
      contains a cycle. Each cycle is named in the diagnosis
      with an arrow chain (`A -> B -> C -> A`), canonicalized
      so the lexicographically-smallest member is the head.
    - **G3, orphan module (Advisory).** A multi-module project
      contains a module with no dependencies and no incoming
      edges. Informational, not a structural violation.
- **CLI directory mode.**
  - `furqan check <directory>` parses every `.furqan` file in
    the directory, runs graph-level checks, and runs the nine
    per-module checkers in topological order.
  - `furqan check <directory> --graph-only` skips per-module
    analysis and reports only graph-level diagnostics.
  - Single-file mode (`furqan check file.furqan`) is unchanged
    and continues to work exactly as in v0.9.0.
- **Multi-module fixtures.** Six new fixture directories under
  `tests/fixtures/multi_module/`: `valid/linear_chain`,
  `valid/diamond`, `valid/standalone`, `invalid/missing_target`,
  `invalid/cycle`, `invalid/long_cycle`.
- **42 new tests** in `tests/test_multi_module.py` (project
  construction, dependency graph, topological sort, G1/G2/G3,
  CLI directory mode, public-surface contract). Total suite:
  **495 tests** (453 baseline + 42 new).
- **Public surface.** `Project` is exported from `furqan` at the
  top level. The parser and checker surfaces are unchanged.

### Changed
- `pyproject.toml` and `src/furqan/__init__.py`: version bumped
  to `0.10.0`.

### Unchanged
- All 453 v0.9.0 tests pass identically. The nine per-module
  checkers (bismillah, zahir_batin, mizan, tanzil, ring_close,
  incomplete, status_coverage, return_type_match,
  all_paths_return) are not modified. 28 keywords. 7 primitives.

### Deferred (Phase 2 and 3 of multi-module support)
- **D23 (Phase 2): cross-module type resolution.** Ring-close R1
  still fires for any type not defined in the current module,
  even if the type is defined in a declared dependency. D23 will
  use the graph from this release to resolve type references
  across module boundaries.
- **Cross-module D11 (Phase 3): status-coverage propagation.**
  D11 still operates on a single module. Future work will follow
  function calls across module boundaries.
- **External-dependency declarations.** G1 currently fires on
  every dependency target not present in the project. There is
  no syntax yet for marking a dependency as external (vendored
  or from a registry). When that surface lands, G1 will gain an
  exception path.

---

## [0.9.0] - 2026-04-30

**Phase 3.1 / Session 1.13 - CLI entry point.** Furqan becomes a
tool, not just a library. A judge or end user can now clone the
repo, run `furqan check examples/clean_module.furqan`, and see the
checker in action on a real file. The demo moment is three
terminal commands: PASS on the clean module, MARAD on the status-
collapse example, MARAD on the missing-return-path example.

A minor-version bump (0.8.x -> 0.9.0) reflects new user-facing
capability. No checker changes, no parser changes, no tokenizer
changes; the CLI is a thin wrapper around the existing checker
modules.

### Added

* **CLI entry point.** `python -m furqan` and (after pip install)
  the standalone `furqan` command.
  - `furqan check <file.furqan>` runs all 9 checkers and reports
    Marad violations and Advisory notes.
  - `furqan check <file.furqan> --strict` exits with code 3 on
    any Marad.
  - `furqan version` prints the installed version.
  - `furqan help` (and bare invocation, `-h`, `--help`) prints
    usage.
* **Console script** registered in `pyproject.toml` under
  `[project.scripts]`: `furqan = "furqan.__main__:main"`.
* **Three example files** in `examples/`:
  - `clean_module.furqan` (PASS - canonical honest shape)
  - `status_collapse.furqan` (MARAD - D11 Case S1)
  - `missing_return_path.furqan` (MARAD - D24 Case P1)
* **18 new CLI tests** (`tests/test_cli.py`) covering exit codes,
  output formatting, help/version, error paths, strict mode.

### Exit code contract

* `0` PASS - zero Marad diagnostics
* `1` MARAD - at least one violation
* `2` PARSE ERROR - file could not be parsed
* `3` STRICT MODE failure - any Marad in --strict run

### Tests

* 435 -> 453 (+18). All Phase 2.x and earlier Phase 3 tests pass
  identically.

### Notes

* The additive-only checker is NOT run in single-file mode. It
  requires a prior-version module for comparison, which a single
  .furqan input cannot supply. Cross-version checks live in the
  test suite and the additive sidecar protocol; the CLI runs
  the other 9 checkers.

### Unchanged

* Seven core primitives unchanged. Parser and tokenizer untouched.
* 28 keywords (unchanged). 9 checker modules (unchanged from
  v0.8.2).
* Public surface 42 / 38 / 4 (parser / checker / errors).

---

## [0.8.2] - 2026-04-30

**Phase 3 / Session 1.12 - D24 all-paths-return analysis.** The
fourth leg of the return-type contract. Ring-close R3 (Phase 2.9)
checks that a return statement EXISTS somewhere in a typed
function's body. D24 (this release) checks that EVERY control-
flow path through the body reaches a return statement.

R3 catches the total absence ("you have no return at all").
D24 catches the partial absence ("you have a return on some
paths but not all"). The two compose: a function that fails R3
does not need D24; a function that passes R3 but fails D24 has
a silent fall-through.

The analysis is exact for the current grammar. Furqan has
exactly one branching construct (IfStmt with optional else, after
D15). There are no loops, no switch/match, no exceptions, no
early-exits other than return - so structural recursion is
sufficient and gives exact (not approximate) results. When future
grammar adds loops or match expressions, D24 needs extension; the
extension is registered as D29 (full CFG analysis).

A patch-level bump (0.8.1 -> 0.8.2) reflects new public exports
without behavioural changes to any pre-existing checker. No new
keywords, no new AST nodes, no parser changes.

### Added

* **D24 - All-paths-return analysis checker**
  (`checker/all_paths_return.py`).
  - **Case P1 (missing return path, Marad).** A function declares
    a return type, has at least one return statement (passes R3),
    but does NOT reach a return on every control-flow path.
  - **R3 delineation.** A function with zero returns triggers R3
    only; D24 stays silent on it via the `_any_return_exists`
    short-circuit. No double-reporting.
  - **Sequence-level path coverage.** An IfStmt without an else
    does not by itself cover all paths, but a sequence containing
    an else-less IfStmt followed by a bare return DOES - the
    walker continues past the IfStmt and finds the trailing
    return. Canonical "early-return then default" shape is
    preserved.
* Public surface additions on `furqan.checker`:
  - `check_all_paths_return(module) -> list[Marad]`
  - `check_all_paths_return_strict(module) -> Module`
  - `ALL_PATHS_RETURN_PRIMITIVE_NAME = "all_paths_return"`

### Fixture refactor (additive, not behavioural)

* `tests/fixtures/ring_close/valid/closed_ring_with_all_primitives.furqan`
  is updated to use `if/else` instead of two complementary `if`
  blocks. The two-if pattern was structurally fine for the older
  primitives but D24's exact path analysis (correctly) cannot
  prove that `not is_encrypted(file)` and `is_encrypted(file)`
  cover all paths without semantic information. Switching to
  if/else preserves the witness as honest under every checker
  including D24. The other two-if fixtures
  (`scan_handles_both_paths.furqan`, `if_only_no_else.furqan`)
  are left alone: their purpose is to test the no-else form
  itself, not to be all-checker witnesses.

### Tests

* 402 -> 435 (+33). All Phase 2.x and earlier Phase 3 tests pass
  identically.

### Deferred items registered

* **D29 - Full control-flow graph analysis.** When Furqan grammar
  adds loops, match/switch, or other branching constructs, D24's
  structural recursion is no longer sufficient. The extension is
  a Phase 3+ CFG pass.

### Unchanged

* Seven core primitives unchanged. Parser and tokenizer untouched.
* 28 keywords (unchanged).
* `IfStmt.else_body` semantics unchanged (D24 reuses the existing
  recursive descent shape).

---

## [0.8.1] - 2026-04-30

**Phase 3 / Session 1.11 - D22 return-expression type matching.**
The third leg of the return-type contract. Ring-close R3 (Phase
2.9) verifies that a function with a declared return type contains
at least one return statement. D11 status-coverage (v0.8.0)
verifies that callers of producers honestly propagate the union.
D22 (this release) verifies that the return statement's expression
matches the declared return type. Together: R3 catches the missing
return; D22 catches the wrong return; D11 catches the collapsed
return.

A patch-level bump (0.8.0 -> 0.8.1) reflects new public exports
without behavioural changes to any pre-existing checker. No new
keywords, no new AST nodes, no parser changes; D22 is a pure
whole-module checker over the existing AST.

### Added

* **D22 - Return-expression type matching checker**
  (`checker/return_type_match.py`).
  - **Case M1 (return type mismatch, Marad).** A return
    expression's statically-inferred type is not a member of the
    declared return type's accepted set. Examples: function
    declares `-> Integrity`, body returns `Incomplete {...}`;
    function declares `-> CustomType`, body returns `Integrity`.
  - **Inferrable expressions.** Only `IntegrityLiteral` and
    `IncompleteLiteral` have statically-known types. Every other
    expression (`IdentExpr`, `StringLiteral`, `NumberLiteral`,
    `NotExpr`, `BinaryComparisonExpr`, `IdentList`) is uncheckable
    and produces no diagnostic - the honest position when the
    checker cannot verify the match.
  - **Recurses into IfStmt body and else_body** (the Phase 3.0
    D15 additive extension): a mismatch in either arm fires its
    own M1, with per-occurrence discipline matching Tanzil T1 and
    status-coverage S1.
  - **No Advisory case.** An M2-style "uncheckable expression"
    Advisory was considered and deliberately omitted: it would
    fire on nearly every function that returns a variable,
    drowning the M1 signal in noise.
* Public surface additions on `furqan.checker`:
  - `check_return_type_match(module) -> list[Marad]`
  - `check_return_type_match_strict(module) -> Module`
  - `RETURN_TYPE_MATCH_PRIMITIVE_NAME = "return_type_match"`

### Tests

* 366 -> 402 (+36). All Phase 2.x and earlier Phase 3 tests pass
  identically; D22 is additive on the test surface.

### Deferred items registered

* **D27 - Type inference on `IdentExpr` returns.** Determining the
  type of `return result` requires data-flow analysis (tracing
  assignments and call return types). Phase 3+ work; overlaps with
  the cross-module graph that D9/D20/D23 share.
* **D28 - Cross-function return-type resolution.** `return scan(file)`
  - what does `scan` return? Requires call-graph return-type
  propagation. Phase 3+ work.

### Unchanged

* Seven core primitives unchanged. Parser and tokenizer untouched.
* 28 keywords (unchanged from v0.7.1 / v0.8.0).
* `IfStmt.else_body` semantics unchanged (D22 reuses the existing
  recursive descent pattern).
* CI workflow unchanged (still 3.10-3.13 matrix; the new tests
  are picked up automatically; surface-count assertion uses `>=`).

---

## [0.8.0] - 2026-04-30

**Phase 3 / Session 1.10 - D11 status-coverage checker.** The
consumer-side dual of the Phase 2.6 scan-incomplete primitive.
Where scan-incomplete polices the producer side (a function
declaring `-> Integrity | Incomplete` must handle both arms),
status-coverage polices the consumer side: a function that CALLS
a producer must propagate the union honestly in its own return
type. Together the two checkers close the loop on the structural-
honesty discipline for incompleteness: the possibility cannot be
silently introduced (Phase 2.6) AND cannot be silently collapsed
across a call boundary (D11).

A minor-version bump (0.7.x -> 0.8.0) reflects new public exports
and a new checker module. No new keywords, no new AST nodes, no
parser changes; D11 is a pure whole-module checker over the
existing AST. The seven core primitives stay closed; D11 is a
checker extension within the scan-incomplete family rather than
an eighth primitive.

### Added

* **D11 - Status-coverage checker** (`checker/status_coverage.py`).
  - **Case S1 (status collapse, Marad).** Caller returns a non-
    union type (or a union whose arms are not exactly Integrity
    and Incomplete) despite calling a producer. The possibility
    of incompleteness is silently narrowed away. One Marad per
    offending call site (per-occurrence discipline matches Tanzil
    T1).
  - **Case S2 (status discard, Advisory).** Caller has no
    declared return type despite calling a producer. The result
    is silently discarded; may be intentionally effectful.
    Advisory rather than Marad - the strict-variant gate does
    not fire.
  - **S3 (honest propagation).** Caller is itself a producer;
    union preserved end-to-end. Zero diagnostics.
  - Local-scope resolution only (same limitation as ring-close R1
    and Phase 2.6 producer detection). Cross-module producer
    resolution registered as D23.
* Public surface additions on `furqan.checker`:
  - `check_status_coverage(module) -> list[Marad | Advisory]`
  - `check_status_coverage_strict(module) -> Module`
  - `STATUS_COVERAGE_PRIMITIVE_NAME = "status_coverage"`

### Tests

* 334 -> 366 (+32). All Phase 2.x and Phase 3.0 tests pass
  identically; D11 is additive on the test surface.

### Deferred items registered

* **D25 - Transitive status-collapse detection.** A -> B -> C
  where C is a producer; D11 checks each call site
  independently and does not verify the full chain preserves the
  union. Phase 3+ work.
* **D26 - Branch-level exhaustiveness.** Whether the caller
  inspects both arms of the union via if/else (rather than just
  return-type propagation) requires control-flow analysis (D13)
  and pattern matching (future grammar).

### Unchanged

* Seven core primitives unchanged. Parser and tokenizer untouched.
* 28 keywords (unchanged from v0.7.1).
* `IfStmt.else_body` semantics unchanged (D11 does not interact
  with control-flow structure).
* CI workflow unchanged (still 3.10-3.13 matrix; the new tests
  are picked up automatically).

---

## [0.7.1] (2026-04-30)

**Phase 3.0 / Session 1.9.** Pre-push polish before the first
GitHub release. Three deferred items land plus a CI workflow; no
new primitives, no checker logic changes (apart from else-body
descent in two existing checkers), no new AST node classes. The
seven-primitive ring stays closed.

### Added

* **CI workflow.** `.github/workflows/ci.yml` runs `pytest` on
  Python 3.10, 3.11, 3.12, 3.13. Every job verifies the additive-
  only public-surface counts (`>= 42 / 29 / 4`) and re-runs the
  `test_version_sync` test as a named step so a version-bump PR
  that touches only one file gets a clearly labelled CI failure.
  README gains a CI badge.
* **D15: `else` arm of an if statement.** New keyword `else` (28
  total). `IfStmt` gains an `else_body` field with default empty
  tuple (additive on the dataclass surface). The parser optionally
  consumes `else { ... }` after the if-body. The ring-close R3
  return-presence walker descends into `else_body`. The scan-
  incomplete walker descends into `else_body` with FLIPPED guard
  polarity: an `else` arm of `if not <expr>` runs when `<expr>` is
  true (incompleteness NOT ruled out), so bare-Integrity returns
  there fire Case A. NAMING.md §1.6 gains the new keyword row.
* **D14: String escape sequences.** Four canonical escapes inside
  a string literal: `\n` (newline), `\t` (tab), `\\` (literal
  backslash), `\"` (literal double quote). The tokenizer validates
  escape shape at lex time and raises `TokenizeError` on any
  unknown escape. The parser unescapes the inner content via
  `_unescape_string` when constructing the `StringLiteral` AST node;
  the `Token.lexeme` preserves the raw source form for round-trip
  tooling. LEXER.md §4 documents the supported set.
* **D10: TokenizeError structured location.** `TokenizeError`
  exposes `line` / `column` integer attributes alongside the
  human-readable message. Both fields default to `0` so any caller
  that constructed the exception positionally still works. All
  three raise sites in the tokenizer (unrecognised character,
  unterminated string, escape-related rejections) populate the new
  fields. LEXER.md §6 documents the convention.

### Tests

* 297 → 334 (+37). All Phase 2.x tests pass identically (the
  additive-only invariant on the public surface is preserved at
  the test level too).

### Deferred items registered as next session work

* **D26: Empty if-body warning.** A future Advisory case for an
  if-body with no statements (currently silently accepted).
* **D27: `else if` chain syntactic sugar.** Currently a nested
  if inside an else-body works; a future polish patch may add
  shorthand syntax.

### Unchanged

* Seven primitives, zero new checker modules, parser's M3-equivalent
  routing discipline preserved (unknown tokens at field-head
  positions still raise ParseError, not checker cases).
* Public surface: parser 42, checker 29, errors 4 (unchanged at the
  module-level export count; AST surface gains the additive
  `IfStmt.else_body` field).

---

## [0.7.0] (2026-04-30)

**Phase 2.9 / Session 1.8.** The **ring-close** checker, Furqan's
seventh and final compile-time primitive, lands, completing the
Phase 2 program. Where the prior six primitives each police a single
discipline, ring-close verifies the *whole-shape* invariant: every
type referenced is declared, every function with a declared output
has a producing path, every type declared finds a use, and a module
that claims to exist has something to say. The thesis paper §6 names
this *the closure of the ring*: a structure in which each piece
presupposes and is presupposed by the others.

A minor-version bump (0.6.x → 0.7.0) reflects new public exports;
no new keywords, no new AST nodes, no parser changes, ring-close is
a pure whole-module checker over the Phase 2.3–2.8 AST surfaces. The
additive-only invariant is preserved by construction.

**Public-surface additions (additive on the export side).**

* `furqan.checker.check_ring_close(module) -> list[Marad | Advisory]`
* `furqan.checker.check_ring_close_strict(module) -> Module`
* `furqan.checker.RING_CLOSE_PRIMITIVE_NAME = "ring_close"`
* `furqan.checker.RING_CLOSE_BUILTIN_TYPE_NAMES = frozenset({"Integrity", "Incomplete"})`
* `furqan.checker.ring_close.PRIMITIVE_NAME` (sub-module surface)
* `furqan.checker.ring_close.BUILTIN_TYPE_NAMES` (sub-module surface)
* `furqan.checker.ring_close.RingCloseDiagnostic` (sub-module surface)

**Four checker cases.**

* **R1: undefined type reference (Marad).** A function signature
  (parameter or return type) names a type that is neither declared
  as a compound type in the module nor recognised as a builtin
  (`Integrity`, `Incomplete`).
* **R2: empty module body (Advisory).** A module declares zero
  functions and zero compound types. The bismillah block alone (and
  any tanzil/mizan/additive_only metadata) does not constitute a
  working module.
* **R3: missing return statement (Marad).** A function declares
  `-> T` but its body lacks any `ReturnStmt` (recursing into nested
  `IfStmt` bodies). All-paths-return analysis is registered as D24.
* **R4: unreferenced type declaration (Advisory).** A compound
  type that no function in the module references in parameter or
  return position.

**The seven-primitive integration capstone.** A new test pins that a
single `.furqan` module exercising every primitive (bismillah,
zahir/batin types, additive_only metadata, scan-incomplete return
types, mizan calibration, tanzil build ordering, ring-close) passes
all six prior checkers AND the new ring-close checker with zero
marads. This is the structural witness that the thesis mechanism
implements end-to-end.

**Test count.** 252 → 296 (+44). All Session 1.7 tests preserved
unchanged.

**Deferred items registered.**

* **D22: Return-expression type-vs-signature matching.** A function
  declared `-> Document` that returns `Summary` is not flagged.
  Phase 2.9 enforces presence; type matching requires expression
  type-inference that the checker layer does not yet implement.
* **D23: Cross-module ring analysis.** R1's resolution is local: a
  type imported from another module would currently fire R1. Cross-
  module resolution requires the module-graph that D9 introduces.
* **D24: All-paths-return analysis.** A function with `if` arms
  that each return but no else-branch syntactically satisfies R3.
  Control-flow analysis is a Phase 3 concern.

**Pinned-literal version sync.** The `furqan.__version__` literal in
`src/furqan/__init__.py` is updated to `"0.7.0"` to match
`pyproject.toml` (the v0.6.0 release left the literal at "0.5.0", a
silent drift caught and corrected here).

---

## [0.6.0] (2026-04-27)

**Phase 2.8 / Session 1.7.** The Tanzil build-ordering checker,
Furqan's sixth compile-time primitive, lands. The thesis
mechanism is implementable; this session demonstrates it. This is
the language-level transposition of build-ordering discipline
(Bayyinah's cost-class taxonomy A/B/C/D ordering, generalized to
inter-module dependencies declared explicitly).

A minor-version bump (0.5.x → 0.6.0) reflects the source-language
additions: two new keywords (`tanzil`, `depends_on`) and one new
module-level declaration form (`tanzil` block). Every Session-1.6
public symbol is preserved.

**Source-language additions (additive on the rejection side).** Pre-
2.8 .furqan source files that used either of the following words
as ordinary identifiers will fail to parse at the v0.6.0 flip:

* `tanzil`: block declaration head
* `depends_on`: dependency-entry field head

This is the **third session shipped under the polish-patch
protocol** formally documented in CONTRIBUTING.md §8 (registered
in v0.3.2). Cross-model audit null-finding rate at session open:
zero.

### Added

**Phase 2.8.0, paired fixtures (the surface contract).**

The grammar surface is defined as "what parses these eight
fixtures correctly" (Cow Episode anti-pattern check, 2:67-74).

- `tests/fixtures/tanzil/valid/single_module_no_deps.furqan`,
  simplest valid case; one dependency.
- `tests/fixtures/tanzil/valid/multiple_deps.furqan`,
  two distinct dependencies.
- `tests/fixtures/tanzil/valid/no_tanzil_block.furqan`,
  pre-2.8 baseline; no tanzil block at all.
- `tests/fixtures/tanzil/valid/tanzil_with_types_and_functions.furqan`
 , non-interference with mizan + functions.
- `tests/fixtures/tanzil/invalid/self_dependency.furqan`,
  Case T1: trivial cycle. **The load-bearing demo fixture.**
- `tests/fixtures/tanzil/invalid/duplicate_dependency.furqan`,
  Case T2: same module path declared twice.
- `tests/fixtures/tanzil/invalid/empty_block.furqan`,
  Case T3 (Advisory, not Marad): zero dependency entries.
- `tests/fixtures/tanzil/invalid/unknown_field.furqan`,
  parser-layer enforcement (NOT a checker case).

**Phase 2.8.1, tokenizer additions.**

- `TANZIL` and `DEPENDS_ON` keyword token kinds.
- Two lookup-table entries connecting source lexemes to token
  kinds.

Total reserved keywords across phases: **27** (was 25).

**Phase 2.8.2, AST nodes (two additions).**

- `DependencyEntry(module_path, span)`, single
  `depends_on: <ModulePath>` line inside a tanzil block.
- `TanzilDecl(name, dependencies, span)`, top-level tanzil
  build-ordering block. The `dependencies` tuple preserves source
  order (load-bearing for the T2 first-occurrence-wins discipline).

`Module` extended additively with `tanzil_decls: tuple = ()`.

**Phase 2.8.3, parser surgery.**

- `parse_module` extended to accept top-level `tanzil` declarations.
- `parse_tanzil_decl`: new strict parser for the tanzil block.
  Field-head position enforces the canonical `depends_on` keyword
  exclusively; an unknown field head raises ParseError (same M3-
  equivalent routing discipline as Mizan §6.4, parser owns
  token-shape invariants, checker owns semantic invariants over
  a well-formed AST).

F1/F2 discipline preserved. No opaque eaters in any new parser.

**Phase 2.8.4, checker (`furqan/checker/tanzil.py`).**

Public entry points:

- `check_tanzil(module: Module) -> list[TanzilDiagnostic]`,
  pure fail-soft check. Returns Marads (T1, T2) and Advisories
  (T3) intermixed in source order.
- `check_tanzil_strict(module: Module) -> Module`, fail-fast
  variant. Raises on the first Marad; **Advisories do NOT
  trigger the strict path** (informational by design, same as
  the additive-only checker's undeclared-rename Advisory).

Three diagnostic cases (parser owns the unknown-field case, see
routing rationale):

- **Case T1**, Self-dependency: a module declares
  `depends_on: <Self>` referencing its own bismillah name. Marad.
  Fires per occurrence (not gated by first-occurrence-wins).
- **Case T2**, Duplicate dependency: the same module path
  appears more than once. Marad. First-occurrence-wins
  semantics; subsequent occurrences fire.
- **Case T3**, Empty block: zero dependency entries. **Advisory,
  not Marad.** Informational evidence; does not fail strict
  check. Same pattern as the additive-only checker's
  undeclared-rename Advisory.

Public constant:

- `PRIMITIVE_NAME = "tanzil_well_formed"`
- `TanzilDiagnostic = Marad | Advisory` (the union type returned
  by `check_tanzil`)

**Phase 2.8.5, tests (33 additions).**

- `tests/test_tanzil.py`, 22 tests covering the parametrized
  fixture sweep (4 valid + 3 checker-eligible invalid; the
  unknown_field fixture is exercised by a parser test, not the
  tanzil-checker sweep), per-case named property tests (T1
  per-occurrence, T2 first-occurrence-wins, T3 advisory + short-
  circuit), strict-variant surface (Marad raises, Advisory does
  NOT), marad/advisory rendering, cross-primitive non-
  interference, and the §7 unreachable-branch reflexivity audit.
- 3 new tests in `tests/test_tokenizer.py` covering both new
  keyword promotions and a smoke test on the full tanzil block
  head.
- 3 new tests in `tests/test_parser.py` covering parser-level
  unknown-field enforcement, canonical-block round-trip, and
  tanzil+mizan composability.

**Phase 2.8.6, documentation.**

- `docs/NAMING.md` §1.6 expanded with two new keyword entries
  (total reserved keywords: 27).
- `docs/NAMING.md` §1.8, new section on Phase 2.8 keyword
  promotions; common-English-word test applied to each.

### Verified

- **Test suite: 252 passing in 0.38s** (Session 1.6 baseline:
  219; net +33). Distribution: tokenizer 53, parser 38,
  bismillah 19, marad 7, zahir_batin 22, additive 40,
  incomplete 24, mizan 22, tanzil 22 (approximate; pytest
  collects all parametrized cases independently).
- **Public surface, additive only.** `furqan.parser` grows from
  40 to 42 exports (+2 new AST nodes); `furqan.checker` grows
  from 22 to 25 exports (+3 tanzil-checker entry points and
  constants); `furqan.errors` unchanged. Every prior export
  preserved.
- **Keyword promotion executed.** Two new keywords are now
  reserved.
- **F1/F2 discipline preserved.** No opaque eaters in any new
  parser. Field-head position in tanzil blocks accepts only the
  canonical keyword token.
- **M3-equivalent routing reflexivity.** §7 unreachable-branch
  audit confirms `furqan/checker/tanzil.py` contains no
  defensive guard against unknown field names; the routing
  rationale is preserved structurally, not just by convention.
- **Polish-patch protocol applies.** Per CONTRIBUTING.md §8, if
  the post-2.8 cross-model audit identifies a small leak meeting
  §8.1 trigger, ship a Session 1.7.1 polish patch in the same
  shape as 1.4.1 before opening Phase 2.9.

### Demo readiness

The four-primitive demo path (additive-only marad + scan-incomplete
marad + mizan parse-and-validate + tanzil self-dependency marad)
is **executable end-to-end**. The Tanzil demo:

```python
from furqan.parser import parse
from furqan.checker.tanzil import check_tanzil

src = '''
bismillah CycleDemo {
    authority: NAMING_MD
    serves: purpose_hierarchy.balance_for_living_systems
    scope: compile
    not_scope: nothing_excluded
}

tanzil cycle_check {
    depends_on: CycleDemo
}
'''
module = parse(src, file="<demo>")
diagnostics = check_tanzil(module)
# → 1 Case-T1 marad in well under a millisecond
```

### Deferred, registered as Session-1.8+ items

- **D20: Multi-module tanzil graph analysis.** Topological sort
  across modules, cross-module cycle detection, existence
  verification of depended-on modules. Phase 3+ work; the
  single-module declaration surface is the Phase 2.8 contribution.
- **D21: Version constraints on dependencies.** A future
  grammar extension might permit `depends_on: CoreModule >= v0.3.0`.
  Requires extending the dependency-entry grammar with version
  comparisons. Future-fixture-driven.

---

## [0.5.0] (2026-04-25)

**Phase 2.7 / Session 1.6.** The Mizan three-valued calibration
block parser and syntactic well-formedness checker, Furqan's
fifth compile-time primitive, lands. The thesis paper §Primitive
4 mechanism is implementable; this session demonstrates it. This
is the language-level transposition of Bayyinah's detector
calibration discipline (every detector ships an upper bound,
lower bound, and calibration-function reference, calibrated
jointly per FRaZ non-monotonicity) into a three-valued
declaration, anchored on Ar-Rahman 55:7-9.

A minor-version bump (0.4.x → 0.5.0) reflects the source-language
additions: four new keywords (`mizan`, `la_tatghaw`,
`la_tukhsiru`, `bil_qist`), two new punctuation tokens (`<` and
`>`), one new module-level declaration form (`mizan` block), and
one new expression form (binary comparison, non-associative).
Every Session-1.5 public symbol is preserved.

**Source-language additions (additive on the rejection side).** Pre-
2.7 .furqan source files that used any of the following words as
ordinary identifiers will fail to parse at the v0.5.0 flip:

* `mizan`: block declaration head
* `la_tatghaw`: upper-bound field head
* `la_tukhsiru`: lower-bound field head
* `bil_qist`: calibration-function field head

The new punctuation tokens (`<` and `>`) cannot break previously-
valid input because no Phase-2.6 fixture used those character
sequences. **Chained comparisons (`a < b < c`) are a parse
error**, the grammar is non-associative; silent expansion to
`a < b AND b < c` would be exactly the kind of zahir/batin
divergence the framework is built to detect.

This is the **second session shipped under the polish-patch
protocol formally documented in CONTRIBUTING.md §8** (registered
in v0.3.2). Cross-model audit null-finding rate at session open:
zero.

### Added

**Phase 2.7.0, paired fixtures (the surface contract).**

The grammar surface is defined as "what parses these eight
fixtures correctly" (Cow Episode anti-pattern check, 2:67-74).

- `tests/fixtures/mizan/valid/detection_threshold.furqan`,
  thesis §Primitive 4 example 1 verbatim. **The load-bearing
  demo fixture.**
- `tests/fixtures/mizan/valid/compression_ratio.furqan`,
  thesis §Primitive 4 example 2 verbatim.
- `tests/fixtures/mizan/valid/with_string_calibration.furqan`,
  bil_qist with a string-literal argument.
- `tests/fixtures/mizan/valid/comparison_with_numbers.furqan`,
  reversed comparison orientation (`0.05 > false_positive_rate`).
- `tests/fixtures/mizan/invalid/missing_la_tatghaw.furqan`,
  Case M1: missing required field.
- `tests/fixtures/mizan/invalid/duplicate_field.furqan`,
  Case M2: duplicate field.
- `tests/fixtures/mizan/invalid/unknown_field.furqan`,
  M3 routed to **parser layer** (not checker). Parses to a
  ParseError with a pinned diagnostic text per §6.4 routing
  rationale.
- `tests/fixtures/mizan/invalid/out_of_order_fields.furqan`,
  Case M4: fields in non-canonical order.

Plus `tests/fixtures/parse_invalid/mizan_chained_comparison.furqan`
pinning the chained-comparison rejection rule.

**Phase 2.7.1, tokenizer additions.**

- `MIZAN`, `LA_TATGHAW`, `LA_TUKHSIRU`, `BIL_QIST` keyword token
  kinds.
- `LT` (`<`) and `GT` (`>`) punctuation token kinds.
- Six lookup-table entries connecting source lexemes to token
  kinds.

The Arabic-transliteration keywords use the snake_case-with-
underscore convention for multi-word phrases (NAMING.md §1.7).

**Phase 2.7.2, AST nodes (four additions).**

- `ComparisonOp`: enum with `LT` and `GT` members.
- `BinaryComparisonExpr(left, op, right, span)`, binary
  comparison expression. The grammar is non-associative; chained
  forms are rejected at parse time.
- `MizanField(name, value, span)`, single `name: value` line
  inside a mizan block; `name` is one of the three canonical
  Arabic strings.
- `MizanDecl(name, fields, span)`, top-level mizan calibration
  block. The `fields` tuple preserves source order (load-bearing
  for M4 out-of-order detection) and may contain duplicates
  (load-bearing for M2 duplicate detection).

`Module` extended additively with `mizan_decls: tuple = ()`.

**Phase 2.7.3, parser surgery.**

- `parse_module` extended to accept top-level `mizan` declarations.
- `parse_mizan_decl`: new strict parser for the mizan block.
  Field-head position enforces the three canonical keyword tokens
  exclusively; an unknown field-head raises ParseError (§6.4
  routing, M3 lives at the parser layer, not the checker).
- `_parse_expression` refactored into `_parse_expression` (the
  comparison-wrapping entry point) plus `_parse_primary_expression`
  (the Phase-2.6 expression body, renamed). Comparison form is
  non-associative: encountering a second comparison operator
  after the first raises ParseError.

F1/F2 discipline preserved. No opaque eaters in any new parser.

**Phase 2.7.4, checker (`furqan/checker/mizan.py`).**

Public entry points:

- `check_mizan(module: Module) -> list[Marad]`, pure fail-soft
  check.
- `check_mizan_strict(module: Module) -> Module`, fail-fast
  variant.

Three cases enforced (M3 lives in parser, see routing rationale):

- **Case M1**, Missing required field (one marad per missing
  field, all reported in a single pass).
- **Case M2**, Duplicate field (one marad per occurrence after
  the first; first occurrence treated as canonical).
- **Case M4**, Out-of-order fields (only fires when all three
  are present; M1 short-circuits M4 to avoid redundant
  diagnostics on partial blocks).

Public constants:

- `PRIMITIVE_NAME = "mizan_well_formed"`
- `REQUIRED_MIZAN_FIELDS = ("la_tatghaw", "la_tukhsiru", "bil_qist")`
  (tuple; canonical order pinned).

**Phase 2.7.5, tests (35 additions).**

- `tests/test_mizan.py`, 17 tests covering the parametrized
  fixture sweep (4 valid + 3 checker-eligible invalid; M3 fixture
  excluded, its test lives in test_parser.py per routing),
  per-case named property tests (M1 each-field-missing inline +
  M2 multi-occurrence + M4 short-circuit-on-M1 + canonical-order
  acceptance), strict-variant surface, marad rendering, cross-
  primitive non-interference, and the **§7 unreachable-branch
  audit** (grep-test confirming the checker contains no dead
  defensive code for M3).
- 8 new tests in `tests/test_tokenizer.py` covering the four new
  keyword promotions, LT/GT punctuation, and a smoke test on the
  full mizan block head.
- 5 new tests in `tests/test_parser.py` covering parser-level M3
  enforcement, chained-comparison rejection, canonical-block
  round-trip, reversed-orientation acceptance, and comparison-
  outside-mizan composability.
- 5 fixture sweep cases (4 valid + 1 invalid M2/M4/M1, the
  unknown_field fixture is exercised by a parser test, not the
  mizan-checker sweep).

**Phase 2.7.6, documentation.**

- `docs/NAMING.md` §1.6 expanded with four new keyword entries.
- `docs/NAMING.md` §1.7, new section on Phase 2.7 keyword
  promotions and the snake-case-with-underscore Arabic-
  transliteration convention.

### Verified

- **Test suite: 219 passing in 0.30s** (Session 1.5 baseline:
  184; net +35). Distribution: tokenizer 50, parser 35,
  bismillah 19, marad 7, zahir_batin 22, additive 40, incomplete
  24, mizan 22.
- **Public surface, additive only.** `furqan.parser` grows from
  36 to 40 exports (+4 new AST nodes); `furqan.checker` grows
  from 18 to 22 exports (+4 mizan-checker entry points and
  constants); `furqan.errors` unchanged. Every prior export
  preserved.
- **Keyword promotion executed.** Four new keywords are now
  reserved. Pre-Phase-2.7 source using any as identifiers will
  fail to tokenize.
- **F1/F2 discipline preserved.** No opaque eaters in any new
  parser. Field-head position in mizan blocks accepts only
  canonical keyword tokens.
- **M3 routing reflexivity.** §7 unreachable-branch audit
  confirms `furqan/checker/mizan.py` contains no defensive
  guard against unknown field names; the routing rationale
  (§6.6) is preserved structurally, not just by convention.
- **Polish-patch protocol applies.** Per CONTRIBUTING.md §8,
  if the post-2.7 cross-model audit identifies a small leak
  meeting §8.1 trigger, ship a Session 1.6.1 polish patch in the
  same shape as 1.4.1 before opening Phase 2.8.

### Demo readiness

The combined three-primitive demo path (additive-only marad +
scan-incomplete marad + mizan parse-and-validate) is **executable
end-to-end**:

```python
from furqan.parser import parse
from furqan.checker.mizan import check_mizan

# Thesis §Primitive 4 example 1, verbatim.
src = '''
bismillah CalibrationDemo {
    authority: NAMING_MD
    serves: purpose_hierarchy.balance_for_living_systems
    scope: calibrate
    not_scope: nothing_excluded
}

mizan detection_threshold {
    la_tatghaw:  false_positive_rate < 0.05
    la_tukhsiru: detection_rate > 0.90
    bil_qist:    calibrate(corpus, paired_fixtures)
}
'''
module = parse(src, file="demo.furqan")
result = check_mizan(module)
assert result == []  # zero marads, well-formed
```

A complementary marad-path proof: the same block with `la_tatghaw`
removed produces a single Case-M1 marad in well under a millisecond.

### Deferred, registered as Session-1.7+ items

- **D16: Runtime evaluation of bound expressions.** Phase 2.7
  parses `false_positive_rate < 0.05` as an AST node; runtime
  evaluation against a corpus is later-phase work.
- **D17: Non-monotonic interaction warning.** Multi-bound
  interaction analysis between `la_tatghaw` and `la_tukhsiru`
  is Phase 3.
- **D18: Trivial-bounds linter.** Flagging `< 1.0` ceilings or
  `> 0.0` floors as semantically vacuous is a linter concern,
  not a syntactic well-formedness check.
- **D19: English aliases.** A hypothetical `calibration {
  upper, lower, calibrate }` form is registered as future work
  per thesis Terminology Note.
- **Phase 2.8, Status-Coverage Checker.** Branch-coverage
  discipline over enum-typed values is a distinct primitive
  registered as the next phase, not absorbed into Mizan.

---

## [0.4.0] (2026-04-25)

**Phase 2.6 / Session 1.5.** The scan-incomplete return-type
checker, Furqan's fourth compile-time primitive, lands. The
thesis paper §4 mechanism is implementable; this session
demonstrates it. This is the language-level transposition of
Bayyinah's `apply_scan_incomplete_clamp`, the
`SCAN_INCOMPLETE_CLAMP = 0.5` ceiling, and the `mughlaq` verdict
into a producer-side return-type discipline.

A minor-version bump (0.3.x → 0.4.0) reflects the source-language
additions: three new flow-control keywords (`if`, `not`, `return`),
two new token kinds (`STRING`, `PIPE`), and twelve new AST node
classes for the statement-tree grammar. Every Session-1.4.2
public symbol is preserved.

This is the **first session shipped under the polish-patch protocol
formally documented in CONTRIBUTING.md §8** (registered in v0.3.2).
Cross-model audit null-finding rate at session open: zero.

**Source-language additions (additive on the rejection side).** Pre-
2.6 .furqan source files that used any of the following words as
ordinary identifiers will fail to parse at the v0.4.0 flip:

* `if`: conditional statement head
* `not`: unary negation in expressions
* `return`: return-statement head

The string-literal token (`"..."`) and pipe punctuation (`|`) are
new accepted forms; they cannot break previously-valid input
because no Phase-2.5 fixture used these character sequences.

**Deliberately NOT promoted to keywords:** `Integrity` and
`Incomplete`. Both remain ordinary identifiers in the type-name
namespace (NAMING.md §1.6 + LEXER.md §5). The scan-incomplete
checker recognises them by string-equality at the AST level,
mirroring the Phase 2.4 `verify` decision. The pattern across
phases: when a name plausibly collides with user identifiers, the
checker recognises it; when a name is a structural primitive with
no plausible identifier collision, the tokenizer promotes it.

### Added

**Phase 2.6.0, paired fixtures (the surface contract).**

The grammar surface is defined as "what parses these eight
fixtures correctly" (Cow Episode anti-pattern check, 2:67-74).

- `tests/fixtures/scan_incomplete/valid/scan_returns_only_integrity.furqan`
 , sanity case: no union return type.
- `tests/fixtures/scan_incomplete/valid/scan_handles_both_paths.furqan`
 , canonical honest shape (`if not is_encrypted(file)` gating
  the bare-Integrity branch).
- `tests/fixtures/scan_incomplete/valid/scan_only_incomplete_path.furqan`
 , conservative case: function always returns Incomplete.
- `tests/fixtures/scan_incomplete/valid/scan_with_partial_findings.furqan`
 , Incomplete with non-empty `partial_findings` ident-list.
- `tests/fixtures/scan_incomplete/invalid/scan_returns_integrity_unguarded.furqan`
 , Case A: bare Integrity, no enclosing if. **The load-bearing
  demo fixture.**
- `tests/fixtures/scan_incomplete/invalid/scan_returns_integrity_in_failure_branch.furqan`
 , Case A: guard polarity inverted (`if pred` not `if not pred`).
- `tests/fixtures/scan_incomplete/invalid/scan_incomplete_missing_reason.furqan`
 , Case B: Incomplete missing `reason`.
- `tests/fixtures/scan_incomplete/invalid/scan_incomplete_missing_max_confidence.furqan`
 , Case B: Incomplete missing `max_confidence`.

**Phase 2.6.1, tokenizer additions.**

- `STRING` token kind. Smallest sufficient form: `"..."` with no
  escape sequences and no embedded newlines. See
  `docs/internals/LEXER.md` §4 for the rationale.
- `PIPE` token kind for the `|` punctuation in union return types.
- Three keyword promotions: `if`, `not`, `return`. Promotion
  rationale in NAMING.md §1.6.

**Phase 2.6.2, AST nodes (twelve additions).**

- `StringLiteral(value, span)`, unwrapped string content.
- `NumberLiteral(lexeme, span)`, dotted-decimal numeric form
  preserved verbatim.
- `IdentExpr(name, span)`, bare identifier reference in
  expression position.
- `IdentList(items, span)`, comma-separated identifier list, used
  for `partial_findings:` field.
- `NotExpr(operand, span)`, unary negation in expressions.
- `IntegrityLiteral(span)`, bare `Integrity` reference (no
  structured form yet; deferred).
- `IncompleteField(name, value, span)`, single field inside an
  Incomplete literal.
- `IncompleteLiteral(fields, span)`, `Incomplete { ... }`
  constructor literal.
- `CallStmt(call, span)`, call statement at body scope.
- `ReturnStmt(value, span)`, `return <expression>` statement.
- `IfStmt(condition, body, span)`, `if <expression> { ... }`
  statement (no `else` arm in Phase 2.6).
- `UnionType(left, right, span)`, binary union return type.

`FunctionDef` extended additively with `statements: tuple = ()`.
`return_type` field's type extends from `TypePath | None` to
`TypePath | UnionType | None`.

**Phase 2.6.3, parser surgery.**

- `_parse_return_type`: new return-type parser accepts both
  single TypePath and binary union forms.
- Statement-tree body parser. The pre-2.6 call-only body parser
  is replaced with `_parse_statement` dispatching to `_parse_call`,
  `_parse_return_statement`, or `_parse_if_statement`. The
  pre-2.6 `fn.calls` and `fn.accesses` contracts are preserved by
  threading accumulator lists through the recursive walk; calls
  inside if-bodies are flattened to the function's top-level call
  list.
- `_parse_expression`: small expression grammar covering the
  six Phase-2.6 expression forms (NotExpr, StringLiteral,
  NumberLiteral, IntegrityLiteral, IncompleteLiteral, IdentExpr).
- `_parse_incomplete_literal`: Incomplete-constructor grammar
  with field-name-dispatched value parsing (reason → STRING;
  max_confidence → NumberLiteral; partial_findings → IdentList).

F1/F2 discipline preserved. No opaque eaters in any new parser.

**Phase 2.6.4, checker (`furqan/checker/incomplete.py`).**

Public entry points:

- `check_incomplete(module: Module) -> list[Marad]`, pure
  fail-soft check.
- `check_incomplete_strict(module: Module) -> Module`, fail-fast
  variant; raises on first marad, returns module unchanged on
  pass.

Two cases per thesis §4:

- **Case A**, Bare Integrity returned without ruling out
  incompleteness. Phase 2.6 detection is *syntactic*: a path
  "rules out incompleteness" iff its enclosing if-statement's
  condition is a `NotExpr`. Conservative rule; some legitimate
  control-flow shapes will produce false positives (registered as
  known limitation, see `docs/internals/CHECKER.md` §6, to be
  added in Session 1.6 when consumer-side ships).
- **Case B**, Incomplete literal missing required field. The
  parser accepts any field set; the checker enforces presence of
  `reason`, `max_confidence`, `partial_findings`. Each missing
  field produces an independent marad.

Public constants:

- `PRIMITIVE_NAME = "scan_incomplete"`
- `REQUIRED_INCOMPLETE_FIELDS = frozenset({"reason", "max_confidence", "partial_findings"})`
- `INTEGRITY_TYPE_NAME = "Integrity"`
- `INCOMPLETE_TYPE_NAME = "Incomplete"`

**Phase 2.6.5, tests (35 additions).**

- `tests/test_incomplete.py`, 18 tests covering the parametrized
  fixture sweep (4 valid + 4 invalid = 8 cases), per-case named
  property tests (Case A unguarded / inverted-guard / negated-
  guard / non-union / no-Integrity-return; Case B reason /
  max_confidence / complete / multi-missing), strict-variant
  surface, marad rendering, cross-primitive non-interference.
- 11 new tests in `tests/test_tokenizer.py` covering STRING
  (well-formed, empty, embedded punctuation, unterminated, with
  embedded newline), PIPE punctuation, three keyword promotions,
  Integrity/Incomplete-as-IDENT, and a full scan-incomplete
  function-signature smoke test.

**Phase 2.6.6, documentation.**

- `docs/internals/LEXER.md` §4, STRING token shape decision.
  No-escape minimal form. Rationale and future-work registration.
- `docs/internals/LEXER.md` §5, Why `Integrity` and `Incomplete`
  are not keywords. Pattern documented across phases.
- `docs/NAMING.md` §1.6, three new keywords added; promotion
  rationale block; deliberate non-promotion of Integrity/Incomplete
  documented.

### Verified

- **Test suite: 184 passing in 0.32s** (Session 1.4.2 baseline:
  149; net +35). Distribution: tokenizer 42, parser 30, bismillah
  19, marad 7, zahir_batin 22, additive 40, incomplete 24.
- **Public surface, additive only.** `furqan.parser` grows from 24
  to 36 exports (+12 new AST nodes); `furqan.checker` grows from
  12 to 18 exports (+6 scan-incomplete entry points and constants);
  `furqan.errors` unchanged. Every prior export preserved.
- **Keyword promotion executed.** Three new keywords (`if`, `not`,
  `return`) are now reserved. Pre-Phase-2.6 source using any of
  these as identifiers will fail to tokenize.
- **F1/F2 discipline preserved.** No opaque eaters in any new
  parser.
- **Polish-patch protocol applies.** If the post-2.6 cross-model
  audit identifies a small structural leak satisfying CONTRIBUTING.md
  §8.1 trigger, ship a Session 1.5.1 polish patch in the same shape
  as 1.4.1. The §8.5 boundary cases apply.

### Demo readiness

The combined two-primitive demo path (additive-only marad +
scan-incomplete marad) is **executable end-to-end** with this
session's artifact. The scan-incomplete demo:

```python
from furqan.parser import parse
from furqan.checker.incomplete import check_incomplete

# A function that silently claims Integrity on input it could
# not have fully processed:
src = '''
bismillah Demo {
    authority: NAMING_MD
    serves: purpose_hierarchy.truth_over_falsehood
    scope: scan
    not_scope: nothing_excluded
}

fn scan_pdf(file: File) -> Integrity | Incomplete {
    return Integrity
}
'''
module = parse(src, file="demo.furqan")
for marad in check_incomplete(module):
    print(marad.render())
```

The output is a Case-A marad naming the function, the unguarded
return path, the rule violated (thesis §4), and the minimal fix.
The demo runs in well under a millisecond on the existing
fixtures.

### Deferred, registered as Session-1.6+ items

- **D11: Consumer-side exhaustiveness checking.** A caller that
  ignores the `Incomplete` arm of a union return type is not
  flagged in Phase 2.6. Implementing this requires control-flow
  analysis on call sites; registered for Session 1.6 or Phase 3.
- **D12: Numeric range validation on `max_confidence`.** Phase
  2.7 Mizan primitive will check `0.0 <= max_confidence <= 1.0`.
  Phase 2.6 accepts any numeric form.
- **D13: Full control-flow analysis.** Phase 2.6 syntactic
  detection produces false positives on helper-extracted
  predicates and flag-variable guards. Phase 3 surface.
- **D14: Escape sequences in string literals.** Phase 2.6
  smallest-sufficient lexer rejects newlines and has no `\n`,
  `\"`, `\\` escapes. Future-fixture-driven addition.
- **D15: `else` arm in `if` statements.** Phase 2.6 has no
  `else`; the `if not <pred> { return Integrity }` pattern is the
  Phase-2.6 canonical form. Future-phase work if a fixture
  requires it.

---

## [0.3.2] (2026-04-25)

Session-1.4.2 polish patch, **documentation-only**.

**No source change. No test change. No behavior change.** The
version bump exists solely to register the formal documentation
of the polish-patch protocol in `docs/CONTRIBUTING.md` §8. Any
future maintainer who notices a v0.3.2 entry with no source delta
should find this CHANGELOG note pre-empting the question.

The polish-patch protocol, same-session ten-line additive fixes
in response to cross-model audit findings, has now been applied
twice (Session 1.1 absorbing the `MaradError` super-call finding;
Session 1.4.1 absorbing the `TokenizeError` leak in
`check_module`). Two data points are the right empirical
foundation for naming a discipline; one would be a coincidence,
three would be retrofit.

The first formal documentation of the protocol is itself a polish
patch. The reflexivity is deliberate (and recorded in
CONTRIBUTING.md §8.6): if the protocol were merely advisory it
could be documented at any session boundary, but landing it as a
documentation-only polish patch in the same shape it describes is
the framework eating its own dogfood.

### Added

- **`docs/CONTRIBUTING.md` §8, "The Polish Patch Protocol"**,
  ~150 lines of new prose. Six subsections: trigger (§8.1), shape
  of the patch (§8.2), discipline (§8.3), worked examples
  (§8.4, Session 1.1 and Session 1.4.1 with concrete
  marad/exception types named), what the protocol is NOT (§8.5
 , explicit boundary cases naming F1/F2 closure, keyword
  promotions, Tier-3 hypothesis failures, public-API renames),
  and the reflexivity check (§8.6).

### Changed

- **`docs/CONTRIBUTING.md`** numbering: the prior §8 "Closing"
  is now §9 "Closing". No content change to the closing section.

### Verified

- **Test suite: 149 passing in 0.20s**, identical to v0.3.1.
  No source change means no test surface change; the suite is
  re-run as a sanity check, not a substantive verification.
- **No public symbols added or removed.** `furqan.parser`,
  `furqan.checker`, `furqan.errors` exports unchanged.
- **Audit-streak preservation.** Phase 2.6 opens against a zero-
  finding baseline with the polish-patch protocol now durably
  documented rather than implicit in two prior sessions.

---

## [0.3.1] (2026-04-25)

Session-1.4.1 polish patch. One additive correction from the
post-Session-1.4 cross-model verification (Perplexity 31-probe
audit, finding E2). One bug closed; zero behavioural changes for
any well-formed input.

### Changed

- **`furqan/checker/additive.py::check_module`** now catches
  `TokenizeError` alongside `ParseError`. Pre-1.4.1 behaviour
  caught only `ParseError`, so a sidecar containing lexically-
  malformed bytes (characters the tokenizer cannot classify, e.g.
  `@#$%`) would raise `TokenizeError` uncaught from the checker.
  The leak was a Process-2 risk: a Python exception escaping a
  layer whose contract is "return a structured `Result`" violates
  the framework's structural-diagnostic discipline at exactly the
  load-bearing place, the version-history sidecar.

  The fix is the simplest correct version: a second `except`
  clause that translates `TokenizeError` to a uniform sidecar-
  parse-failed marad via the new `_lex_error_sidecar_marad`
  helper. The marad uses a synthetic `SourceSpan(file="<sidecar>",
  line=1, column=1)` because `TokenizeError` does not yet carry
  structured location fields; the exception's message string
  (which contains the offending line/column as text) is included
  verbatim in the diagnosis so the user can still locate the bad
  byte. Adding structured `line`/`column` to `TokenizeError` is
  registered as a Phase-3 surface change (D10 below).

  This is **non-breaking for every well-formed sidecar**: pre-1.4.1
  callers passing valid `.furqan_history` content see identical
  output. Only callers passing lexically-malformed sidecars see
  the new structured marad in place of the prior raised exception.

### Added

- **`tests/test_additive.py::test_check_module_with_lexically_malformed_sidecar_emits_marad`**
 , pins the new contract: lex-level garbage produces a structured
  marad with the additive-only primitive tag, the synthetic
  sidecar span, and the offending character quoted in the
  diagnosis.
- **`tests/test_additive.py::test_check_module_lex_error_does_not_leak_python_exception`**
 , negative-regression test asserting `check_module` returns
  rather than raises on lex-level garbage. Belt-and-braces; if a
  future refactor accidentally narrows the catch back to
  `ParseError` only, this test fires.

### Verified

- **Test suite: 149 passing in 0.20s** (Session 1.4 baseline:
  147; net +2). Zero removals; no Session-1.4 test changes.
- **Demo path unchanged.** The June 9 live-demo path uses well-
  formed sidecars; the existing fixture-driven sweep continues
  to pass identically.
- **Cross-model audit null-finding rate: zero.** Perplexity's E2
  was the only non-Tier-1 finding in the 31-probe report.
  Session 1.4.1 closes it.

### Deferred, registered for a later phase

- **D10: `TokenizeError` structured location fields.** Currently
  `TokenizeError` inherits `Exception` with a single message
  string; line/column are embedded as text. A Phase-3 surface
  change would add `.span: SourceSpan` to mirror `ParseError`'s
  shape. This patch's `_lex_error_sidecar_marad` synthesises a
  span at `<sidecar>:1:1`; once `TokenizeError` carries a real
  span, the synthetic anchor is replaced. Non-breaking via the
  same constructor signature.

---

## [0.3.0] (2026-04-25)

**Phase 2.5 / Session 1.4.** The additive-only module checker,
Furqan's third compile-time primitive, lands. The thesis paper §3.3
mechanism is implementable; this session demonstrates it. This is the
language-level transposition of Bayyinah's `MECHANISM_REGISTRY`
import-time coherence check into a type-system construct.

A minor-version bump (0.2.x → 0.3.0) reflects the source-language
breakage: six new keywords promoted, one new token kind (NUMBER),
two new checker entry points, six new AST node classes, fifty new
tests. Every Session 1.3 public symbol is preserved.

**Source-language breakage (additive-on-the-rejection-side).** Pre-2.5
.furqan source files that used any of the following words as ordinary
identifiers will fail to parse at the v0.3.0 flip:

* `additive_only`: declarator head
* `module`: declarator head pair-token
* `export`: symbol declarator
* `major_version_bump`: escape-valve catalog
* `removes`: catalog entry
* `renames`: catalog entry

The breakage is registered here (per NAMING.md §1.6) so downstream
authors are not surprised. **`verify` was not promoted** in any phase
and remains a free identifier (NAMING.md §1.5: the common-English-
word test).

### Added

**Phase 2.5.0, paired fixtures (the surface contract).**

The grammar surface for Phase 2.5 is defined as "what parses these
eight fixtures correctly" (Cow Episode anti-pattern check, 2:67-74).

- `tests/fixtures/additive_only/valid/module_v1.furqan`, baseline
  v1.0 with three exports, no sidecar.
- `tests/fixtures/additive_only/valid/module_v2_added_export.furqan`,
  v2.0 adding one export to v1.0; sidecar present.
- `tests/fixtures/additive_only/valid/module_v2_optional_major_bump.furqan`
 , v2.0 adding one export with empty `major_version_bump {}`.
- `tests/fixtures/additive_only/valid/module_v2_with_major_bump_removes_export.furqan`
 , v2.0 honestly declaring removal of `severity_weights`.
- `tests/fixtures/additive_only/invalid/module_v2_removed_export.furqan`
 , Case 1 violation (removed without bump).
- `tests/fixtures/additive_only/invalid/module_v2_renamed_export.furqan`
 , Case 2 enforcement violation (catalog claims rename, exports
  contradict).
- `tests/fixtures/additive_only/invalid/module_v2_type_changed_incompatibly.furqan`
 , Case 3 violation (type changed, no bump).
- `tests/fixtures/additive_only/invalid/module_v2_catalog_dishonest.furqan`
 , Case 4 violation (catalog claims removal, symbol still present,
  the reflexivity test).

Each fixture (except `module_v1`, which is the first version)
ships with its `.furqan_history` sidecar.

**Phase 2.5.1, tokenizer additions.**

- `NUMBER` token kind (integer-only digit run; multi-component
  numerics reconstructed at parser level via DOT separators). The
  lexer choice is documented in `docs/internals/LEXER.md` §1.
- Six keyword promotions: `additive_only`, `module`, `export`,
  `major_version_bump`, `removes`, `renames`. Promotion rationale
  in NAMING.md §1.6.

**Phase 2.5.2, AST nodes (six additions).**

- `VersionLiteral(components, span)`, semver-shaped version like
  `v1.0` or `v2.3.4`. `major` and `minor` properties; `render()`
  returns canonical text form.
- `ExportDecl(name, type_path, span)`, single `export name: TypePath`
  line.
- `RemovesEntry(name, span)`, single removed-symbol entry inside
  major_version_bump.
- `RenamesEntry(old_name, new_name, span)`, single rename entry.
- `MajorVersionBump(removes, renames, span)`, the escape-valve
  catalog. Empty catalog (`{}`) is benign.
- `AdditiveOnlyModuleDecl(name, version, exports, bump_catalog, span)`
 , the top-level declaration.

`Module` extended additively with `additive_only_modules:
tuple[AdditiveOnlyModuleDecl, ...] = ()`.

**Phase 2.5.3, parser surgery.**

- `parse_module` extended to accept top-level `additive_only`
  declarations.
- New strict parsers: `parse_additive_only_module_decl`,
  `_parse_version_literal`, `_parse_export_decl`,
  `_parse_major_version_bump`, `_parse_removes_entries`,
  `_parse_renames_entries`, `_parse_one_rename`. F1/F2 discipline
  applies, no opaque eaters in any of the new parsers.

**Phase 2.5.4, Advisory type (Session 1.1 D1 lands).**

`furqan/errors/marad.py` adds the `Advisory` dataclass alongside
`Marad`. An advisory is informational (does not cause type-check
failure); a marad is an error (does). The two-types-not-one-tier
decision was registered in Session 1.1 as a deferred design question
and lands now to support the Case 2 detection-vs-enforcement split.

**Phase 2.5.5, checker (`furqan/checker/additive.py`).**

Public entry points (pinned by NAMING.md §6):

- `check_additive(current: Module, previous: Module) -> Result`,
  pure two-module comparison, no I/O. The load-bearing primitive.
- `check_module(module: Module, sidecar_text: str | None) -> Result`
 , sidecar-aware wrapper. Resolves adjacent prior version,
  delegates to `check_additive`. Absent sidecar = trivial pass;
  malformed sidecar = marad; non-adjacent prior = marad.
- `check_module_strict(module: Module, sidecar_text: str | None) ->
  Module`, fail-fast variant.
- `Result(marads, advisories, passed)`, bundle separating errors
  from informational diagnostics.

Four enforcement cases per thesis §3.3:

- **Case 1**, Removed without bump.
- **Case 2**, Renamed without bump (enforcement marad + detection
  advisory split, see `docs/internals/CHECKER.md`).
- **Case 3**, Type changed incompatibly (structural AST equality
  on TypePath; subtyping deferred to Phase 3).
- **Case 4**, Catalog dishonest. The reflexivity test on the
  escape valve itself.

**Phase 2.5.6, tests (50 additions).**

- `tests/test_additive.py`, 38 tests covering parametrized fixture
  sweeps (4 valid + 4 invalid = 8 cases), Result type properties,
  per-case named property tests (Case 1, Case 2 enforcement, Case 2
  advisory positive + negative, Case 3, Case 4),
  check_additive / check_module / check_module_strict surface
  pinning, malformed sidecar, non-adjacent sidecar, version-literal
  parsing (1.0, 2.3.4, missing-minor rejection), empty bump catalog.
- 12 new tests in `tests/test_tokenizer.py` covering the NUMBER
  token (single digit, multi-digit, dotted, multi-dotted,
  v-prefix), each of the six new keywords, and a smoke test on the
  full additive_only header.

**Phase 2.5.7, documentation.**

- `docs/internals/LEXER.md`, new file. Documents the NUMBER token
  shape decision, version-literal lexing, keyword-promotion
  discipline, and the deliberate absence of string literals in
  Phase 2.5.
- `docs/NAMING.md` §1.6 updated with the six new keywords and a
  per-keyword promotion-rationale block.
- `docs/internals/CHECKER.md`, new file documenting the four
  cases, the public surface, the sidecar format, and the Case-2
  detection-vs-enforcement split.

### Verified

- **Test suite: 147 passing in 0.17s** (Session 1.3 baseline: 97;
  net +50). Distribution: tokenizer 31, parser 30, bismillah 19,
  marad 7, zahir_batin 22, additive 38.
- **Public surface, additive only.** `furqan.parser` grows from 18
  to 24 exports (+6 new AST node classes); `furqan.checker` grows
  from 7 to 12 exports (+5 additive-only entry points); `furqan.errors`
  grows from 3 to 4 (+1 `Advisory`). Every prior export is preserved
  with identical semantics.
- **Keyword promotion executed.** Six new keywords (`additive_only`,
  `module`, `export`, `major_version_bump`, `removes`, `renames`)
  are now reserved. Pre-Phase-2.5 source using any as identifiers
  will fail to tokenize.
- **F1/F2 discipline preserved.** No opaque eaters in any of the
  new Phase-2.5 parsers; every token is accounted for.
- **Bayyinah `MECHANISM_REGISTRY` parallel.** The same coherence-
  at-load-time discipline that Bayyinah enforces in Python via
  `assert` at module import is now expressible at language level
  via `additive_only module` + `major_version_bump`.

### Demo readiness

The June 9 Perplexity Billion Dollar Build live demo path,
*Bayyinah `MECHANISM_REGISTRY` → .furqan transcription → remove
export → run checker → show marad*, is **executable end-to-end**
with this session's artifact. Concretely:

```python
from furqan.parser import parse
from furqan.checker.additive import check_module

# v1.1 with severity_weights silently dropped:
v1_1_src = open("module_v1_1.furqan").read()
v1_0_history = open("module_v1_1.furqan_history").read()

current = parse(v1_1_src, file="module_v1_1.furqan")
result = check_module(current, v1_0_history)
for marad in result.marads:
    print(marad.render())
```

The output is a Case-1 marad naming `severity_weights`, the prior
version, and the minimal fix (`add removes: severity_weights to
major_version_bump`). The demo runs in under one second on the
existing fixtures.

### Deferred, registered as Phase-2.6+ items

- **D6: Sidecar file discovery.** The pure
  `check_additive(current, previous)` and the in-memory-text
  `check_module(module, sidecar_text)` ship in this session.
  Filesystem discovery (read `<module>.furqan_history` from disk
  next to the `.furqan` file) is a CLI-layer concern deferred to
  the Phase-3 CLI. The pure-checker / I/O separation mirrors the
  Bayyinah `ScanService` / CLI separation.
- **D7: `type_changes:` catalog entry.** Phase 2.5 has no syntax
  for declaring an intentional type change; type changes must be
  expressed as a `removes:` + add of the new-typed symbol, OR as a
  `renames:` pair (with the rename target carrying the new type).
  A `type_changes:` entry would streamline this. Deferred.
- **D8: Structural subtyping on TypePath.** Phase 2.5 uses
  structural equality. A future phase may introduce subtype
  compatibility (e.g., a derived type substituting for a base
  type). Phase 3 surface.
- **D9: Multi-module dependency graphs / transitive multi-version
  comparison.** Phase 2.5 does pair comparison only. Cross-module
  reasoning is a Phase 3+ surface.

---

## [0.2.0] (2026-04-25)

**Phase 2.4 / Session 1.3.** The zahir/batin type checker, Furqan's
second compile-time primitive, lands. The thesis paper §3.2
mechanism is implementable; this session demonstrates it.

A minor-version bump (0.1.x → 0.2.0) reflects the surface expansion:
five new keywords promoted, six new AST node classes, two new
checker entry points, twenty-two new tests. Every Session 1.2
public symbol is preserved; nothing on the previous surface was
renamed or removed.

### Added

**Phase 2.4.0, paired fixtures (the surface contract).**

- `tests/fixtures/zahir_batin/valid/document_compound.furqan`,
  literal port of thesis §3.2 Document example.
- `tests/fixtures/zahir_batin/valid/verify_reads_both.furqan`,
  `verify(doc: Document)` accessing both layers via
  `compare(doc.zahir, doc.batin)`. The canonical cross-layer
  construct.
- `tests/fixtures/zahir_batin/valid/verify_reads_one.furqan`,
  `verify(doc: Document)` accessing only one layer; verify is
  *permitted* both layers, not *required* both.
- `tests/fixtures/zahir_batin/invalid/zahir_reads_batin.furqan`,
  Case 1 violation (zahir-typed function reads batin field).
- `tests/fixtures/zahir_batin/invalid/batin_reads_zahir.furqan`,
  Case 2 violation (batin-typed function reads zahir field; the
  symmetric dual of Case 1).
- `tests/fixtures/zahir_batin/invalid/non_verify_unqualified_param.furqan`
 , Case 3 violation (non-verify function declares unqualified
  compound-type parameter).

The grammar surface for Phase 2.4 is defined as "what parses these
six fixtures correctly", the Cow Episode (2:67-74) anti-pattern
applied to grammar design.

**Phase 2.4.1, tokenizer keyword promotions.**

- `type`: compound-type declaration head.
- `zahir`, `surface`: zahir layer keyword + English alias.
- `batin`, `depth`: batin layer keyword + English alias.

The English aliases (`surface`, `depth`) carry first-class status
at the lexer level and are normalised to canonical Arabic form
(`zahir`, `batin`) at AST construction time, with the original
lexeme preserved on `layer_alias_used` for diagnostic quoting.

**Deliberate non-promotion, `verify` stays IDENT.** Promoting
`verify` to a keyword would prohibit every non-type-verification
use of the word across the entire language surface. The
zahir/batin checker recognises `verify` by function-name comparison
at the checker layer (`fn.name == "verify"`) rather than at the
token layer. Documented in `docs/NAMING.md` §1.5.

**Phase 2.4.2, AST nodes (six additions).**

- `TypePath(base, layer, span, layer_alias_used)`, parameter and
  return-type expression. Phase 2.4 forms: bare IDENT or
  `IDENT.zahir` / `IDENT.batin`.
- `FieldDecl(name, type_name, span)`, single field inside a layer
  block. Field types restricted to bare IDENT in Phase 2.4
  (generics deferred).
- `LayerBlock(layer, fields, span, alias_used)`, `zahir { ... }`
  or `batin { ... }` block inside a compound-type declaration.
- `CompoundTypeDef(name, zahir, batin, span)`, top-level
  `type Name { zahir { ... } batin { ... } }` block. Both layers
  required; order is fixed (zahir first, batin second).
- `ParamDecl(name, type_path, span)`, function parameter
  declaration. Untyped parameters are not accepted.
- `LayerAccess(param_name, layer, span, layer_alias_used)`,
  `param.zahir` / `param.batin` access pre-scanned from a function
  body's call-argument tokens. The input to the zahir/batin
  checker.

`FunctionDef` extended additively with three new fields
(`params`, `return_type`, `accesses`). Every existing v0.1.x
reader (`fn.name`, `fn.calls`, `fn.span`) returns identical values
to Session 1.2. `Module` extended additively with
`compound_types: tuple[CompoundTypeDef, ...] = ()`.

**Phase 2.4.3, parser surgery.**

- F1 (Session 1.2 deferred) **closed**: the opaque parameter-list
  eater is replaced with a real `_parse_param_list` /
  `_parse_param` / `_parse_type_path` chain. Untyped parameters are
  now a parse error; previously they were silently absorbed.
- F2 (Session 1.2 deferred) **closed**: the opaque return-type
  arrow eater is replaced with `_parse_type_path("return type")`.
  Empty-return-type forms (`fn r() -> {}`) are now a parse error;
  previously they parsed silently as `fn r() {}`.
- `_parse_qual_name` extended per the brief to accept
  `ZAHIR/SURFACE/BATIN/DEPTH` tokens as path segments after `.`.
- `parse_module` extended to accept top-level `type` declarations
  in addition to `fn` definitions.
- `_parse_call`'s argument-list consumer carries a non-invasive
  pre-scan that recognises the pattern
  `IDENT '.' (zahir|surface|batin|depth)` and emits `LayerAccess`
  records. The pre-scan does NOT change the rejection contract
  (the Session 1.2 c.3 brace-rejection is preserved unchanged); it
  only annotates the AST with structured access information that
  the zahir/batin checker reads.

**Phase 2.4.4, checker (`furqan/checker/zahir_batin.py`).**

Three rules per the thesis paper §3.2:

- **Case 1**: a zahir-typed function reading a batin field is a
  marad.
- **Case 2**: a batin-typed function reading a zahir field is a
  marad.
- **Case 3**: a non-verify function declaring an unqualified
  compound-type parameter is a marad.

Public entry points: `check_zahir_batin` (fail-soft, returns list
of marads) and `check_zahir_batin_strict` (fail-fast, raises on
first violation). Module-level constant `VERIFY_FUNCTION_NAME =
"verify"` pins the name the Case 3 rule trusts.

**Phase 2.4.5, tests (22 additions).**

- `tests/test_zahir_batin.py`, 22 tests:
  - 2 parametrized sweeps (3 valid + 3 invalid fixtures = 6 cases)
  - 1 directory-non-empty guard
  - 2 named tests for Case 1 (function/parameter/case naming +
    location pointing at the offending access)
  - 2 named tests for Case 2 (symmetric to Case 1 + dual layer
    naming)
  - 2 named tests for Case 3 (parameter-level marad +
    no-double-fire)
  - 3 verify-discipline tests
  - 1 compound-type-only smoke test
  - 2 strict-variant tests
  - 1 marad-rendering test
  - 2 AST extraction tests (pre-scan correctness + English alias
    normalisation)

### Verified

- **Test suite: 97 passing in 0.15s** (Session 1.2 baseline: 75; net
  +22). Distribution: tokenizer 19, parser 30, bismillah 19,
  marad 7, zahir_batin 22.
- **Public surface, additive only.** `furqan.parser` grows from 12
  to 18 exports (+6 new AST node classes); `furqan.checker` grows
  from 3 to 7 exports (+4 zahir/batin entry points and the
  `VERIFY_FUNCTION_NAME` constant); `furqan.errors` unchanged.
  Every prior export is preserved with identical semantics.
- **F1 and F2 deferred items closed.** The opaque parameter-list
  and return-type eaters from Session 1.2 are replaced with strict
  parsers. The forward-compatibility hazard registered in v0.1.2's
  CHANGELOG is now structurally impossible: a zahir/batin parameter
  annotation cannot be silently absorbed because the parser
  requires every parameter to be `IDENT : type_path`.
- **Keyword promotion executed.** `type`, `zahir`, `surface`,
  `batin`, `depth` are now reserved. Pre-Phase-2.4 source using any
  of these as ordinary identifiers will fail to tokenize at the
  v0.2.0 flip, the additive-on-the-rejection-side change
  registered in v0.1.2's forward-compatibility note. (`verify` was
  *not* promoted; see §1.5 of NAMING.md for why.)

### Deferred, registered as Phase-2.5+ items

- **D3: Field-level access checking.** Phase 2.4 verifies the
  layer of access (`doc.zahir` vs `doc.batin`) but does not verify
  that the trailing field name (e.g., `doc.zahir.x`) is actually
  declared in the layer. Field-level resolution requires a
  symbol-table infrastructure that Phase 2 does not yet have.
  Belongs to Phase 2.5+ where the additive-only module checker
  will introduce module-level symbol tracking.
- **D4: Behavioral verification of `verify`.** The thesis paper
  §7 reflexivity analysis names this Failure Mode 1 (dishonest
  declarations). Verifying that a function named `verify`
  *actually* performs cross-layer comparison is structural-honesty
  beyond what the type system can guarantee; the safeguard is
  human review, recorded here as a known limit rather than a
  future fix.
- **D5: Nested calls inside argument lists.** Currently
  `outer(inner())` extracts only `outer` as a CallRef; `inner` is
  inside the opaque arg-list region (modulo the layer-access
  pre-scan). The bismillah scope checker does not see `inner`. This
  was not load-bearing for Phase 2.3 or 2.4, but Phase 2.7's Mizan
  syntactic check may need per-call mechanism budgeting that
  depends on it. Flagged for Phase 2.7.

---

## [0.1.2] (2026-04-25)

Session-1.2 hardening patch. One load-bearing parser correction from
the Perplexity parser/tokenizer deep review. Additive on the
rejection side: every previously-accepted *structurally valid* input
still parses; only newly-rejected inputs are inputs that were silently
masking AST loss.

### Added

- **`tests/fixtures/parse_invalid/`**, new fixture directory for
  files that must fail at parser stage (distinct from
  `tests/fixtures/invalid/`, which expects parse-then-checker
  rejection). Three fixtures pin the c.3 drill-down cases from the
  Perplexity review:
  - `call_arg_stray_lbrace.furqan`, `x({)` → "Stray '{' inside call argument list"
  - `call_arg_stray_rbrace.furqan`, `x(})` → "Stray '}' inside call argument list"
  - `call_arg_braced_inner_call.furqan`, `x({ parse_files() })` → rejected
    (the load-bearing case: pre-patch this parsed as `x()` with the
    `parse_files()` call silently dropped, hiding a `not_scope`
    violation from the Bismillah scope checker)
- **`tests/fixtures/valid/call_arg_paren_only.furqan`**,
  negative-regression baseline. Confirms paren-only nesting at depth
  3 inside an arg list still parses as one CallRef on the outer
  head.
- **5 new tests in `tests/test_parser.py`**:
  - parametrized `test_every_parse_invalid_fixture_raises_parse_error`
    (3 fixtures = 3 cases)
  - `test_parse_invalid_directory_is_non_empty` (guard against silent
    test-surface vacuum)
  - 3 named direct tests pinning the lbrace, rbrace, and balanced-
    brace cases
  - `test_nested_paren_only_args_are_still_accepted`
    (negative-regression for the paren-only baseline)

### Changed

- **`src/furqan/parser/parser.py::_parse_call`**, the call-argument
  consumer now raises `ParseError` on any `{` or `}` token
  encountered while the arg list is open. Phase 2's surface syntax
  uses braces *only* as block delimiters (function bodies, type
  bodies, bismillah blocks); a brace inside an arg list is by
  definition a structural error, and silently absorbing it would
  drop nested CallRefs that the Bismillah scope checker depends on.

  This is the simplest correct version of the Perplexity-recommended
  fix (option A: reject any brace, vs. option B: track brace depth
  and recurse). Option A is sufficient for Phase 2 because the
  surface has no expression-shaped use of braces. If Phase 3
  introduces blocks-as-expressions or lambdas, the corresponding
  fixtures migrate from `parse_invalid/` to `valid/` and the parser
  grows real expression parsing, at which point this rejection is
  removed in an explicit Phase-3 commit, not silently.

### Verified

- **Test suite: 75 passing in 0.11s** (Session 1.1 baseline: 66; net
  +9). Net additions, verified by `pytest --collect-only`:
  - +3 parse_invalid sweep cases
  - +1 directory-non-empty guard
  - +4 named c.3 tests (lbrace, rbrace, balanced, paren-only baseline)
  - +1 new valid fixture in the bismillah sweep (`call_arg_paren_only`)
  - 0 removals, every Session-1.1 test still collects and passes.

### Deferred, registered as Phase-2.4 first-task replacements

The Perplexity review identified two other opaque-eater regions in
the parser. Both were *recommended for replacement, not incremental
hardening*. Both belong to Phase 2.4 because the type grammar that
replaces them is itself part of the 2.4 zahir/batin deliverable.
Recording them here so the next session opens with them as known
first-task work.

- **F1, Parameter-list parser (parser.py `parse_function_def`).**
  Currently swallows everything between `(` and `)` opaquely. Phase
  2.4 needs a real parameter-list parser so that
  `fn analyze(doc: Document.zahir) -> Integrity { ... }` checks
  that `doc` has type `Document.zahir` (and zahir/batin's cross-
  layer rule can fire). Replace, do not harden.

- **F2, Return-type arrow parser (parser.py `parse_function_def`).**
  Currently swallows everything between `->` and `{` opaquely. The
  empty-return-type case (`fn r() -> {}` parses as `fn r() {}` with
  no record of the arrow) becomes a silent loss of intent the moment
  zahir/batin annotations enter the return-type position. Replace
  with a real type-expression parser as the 2.4 sibling of F1.

### Forward-compatibility note, Phase 2.4 keyword promotion

Phase 2.4 will promote the following identifiers to reserved
keywords: `zahir`, `batin`, `verify`, `mizan`, `tanzil`, `marad`,
`ring_close`, `additive_only`. Existing Phase-2 source that uses any
of these as ordinary identifiers will fail to tokenize at the 2.4
flip.

Per NAMING.md §6, the additive-only invariant covers the public
*symbol* surface of the Python package, not the *keyword* set of
the .furqan language. New keywords are an explicit additive-on-the-
rejection-side change (pre-existing accepted source becomes rejected;
no previously-rejected source becomes accepted). The 2.4 release
must carry a CHANGELOG entry naming the promoted keywords explicitly
so downstream Furqan source authors are not surprised at flip-day.

---

## [0.1.1] (2026-04-25)

Session-1.1 polish patch. Four additive corrections from the
post-Session-1 review (Perplexity, three-model collaboration
architecture). All changes are additive; every Session-1 test still
passes; total test count grows from 57 to 60.

### Added

- **`tests/fixtures/known_limitation/`**, new fixture directory.
  Contains `scope_evasion_via_alias.furqan`, which pins the Phase-2
  Bismillah checker's documented head-only-resolution gap as
  executable behaviour. The Phase-2 checker passes the file by
  design; a future Phase-3 namespace-aware resolution will close the
  gap, at which point the fixture migrates to `tests/fixtures/invalid/`
  and the corresponding test inverts. Pinning the limitation as a
  fixture converts a docstring caveat into a structural promise the
  test suite signals on, rather than silent documentation drift.
- **`tests/test_marad.py`**, new test file. 7 tests pin the `Marad`
  data class's frozen contract, render format invariants, and the
  `MaradError` exception wrapper's session-1.1 access semantics (see
  Changed). Session-1.0 left Marad-rendering tested only indirectly
  inside `test_bismillah.py`; this file makes the contract first-class.
- **`CHANGELOG.md`**, this file. The Bayyinah CHANGELOG-as-isnad
  pattern (every phase named, what was added, what was preserved,
  what was deferred) is started early so it scales across Phases
  2.4 through 2.7 without retrofitting.

### Changed

- **`MaradError.args[0]` is now the structured `Marad`, not its
  rendered string.** Previously `MaradError.__init__` called
  `super().__init__(marad.render())`, binding `args[0]` to prose.
  Tooling that catches a generic `Exception` and inspects `args[0]`
  expecting structure would have received a string. The new
  `__init__` passes the `Marad` itself; an overridden `__str__`
  preserves the human-readable form on `str(e)`. Both
  `e.args[0] is e.marad` and `str(e) == e.marad.render()` are now
  pinned by tests.

  This is a **non-breaking change** for every current caller: no
  Session-1 code or test reads `e.args[0]`; `e.marad` and `str(e)`
  remain identical.

- **`README.md`**, removed the dead reference to
  `./papers/Furqan_Thesis_v1_0_Academic.docx` (the file does not
  exist in the repo). Replaced with a Zenodo-DOI placeholder. Repo
  README is now zahir/batin-aligned with the file system.

### Verified

- **Test suite: 66 passing in 0.10s** (Session 1.0 baseline: 57).
  Net additions, verified by `pytest --collect-only`:
  - +7 from `test_marad.py` (new file)
  - +2 from `test_bismillah.py`
    (`test_known_limitation_passes_by_design[scope_evasion_via_alias.furqan]`,
    `test_known_limitation_directory_is_non_empty`)
  - 0 removals, every Session-1.0 test still collects and passes.

  Net: +9 tests. No test was renamed or relocated.
- **Public surface:** zero removals; one informational addition
  (the `known_limitation/` directory). The `furqan` package's
  `__all__` is unchanged.

### Deferred, registered as Phase-2.4 prerequisite design questions

The post-Session-1 review identified two items that warrant design
conversation before Phase 2.4 (zahir/batin) lands rather than
unilateral implementation. Both are recorded here so the next
session opens with them visible.

- **D1: `Marad` tier field, or separate `Advisory` type?** The
  Bismillah checker currently treats a module declaring an empty
  `not_scope:` as a silent pass. Per thesis §7 Failure Mode 1
  (dishonest Bismillah declarations), this is a Process-2 risk,
  technically compliant, structurally vacuous. The fix is an
  informational diagnostic. The design question is whether this
  belongs as a `tier: "advisory" | "error"` field on the existing
  `Marad`, or as a separate `Advisory` type alongside `Marad`. Lean:
  separate type, no dataclass mutation. Awaits Fraz/Bilal sign-off
  before Phase 2.4.
- **D2: Phase-3 `regression_check` should be a templatable shell
  command, not prose.** When the checker is exposed externally
  (`furqan check path/to/file.furqan`), the marad's
  `regression_check` field should be the actual command the user
  types. Open question: how is the template configured,
  environment variable, project config file, CLI flag? Phase-3
  surface; flagged here so Phase-3 design begins from a known
  requirement rather than discovering it mid-implementation.

---

## [0.1.0] (2026-04-25)

**Phase 2, Session 1.** First running prototype. The Furqan thesis
paper said "no compiler exists." This session demonstrates that the
cleanest of the seven primitives is mechanically implementable.

### Added

**Phase 2.0, scaffolding**

- `pyproject.toml` (src-layout, zero runtime dependencies,
  pytest in `[project.optional-dependencies].dev`).
- `docs/NAMING.md`, the second authority in the project's
  authority hierarchy (after the thesis paper). Pins the
  Arabic/English alias rule, the Marad field structure, and the
  additive-only invariant on the type-checker's own surface.
- `docs/CONTRIBUTING.md`, governance protocol
  (COMPLIANT/PARTIAL/BLOCKED labels, the five-step workflow,
  the 20% skip rule, the dependency policy).
- `README.md`, public-facing surface description and
  per-primitive roadmap.

**Phase 2.1, tokenizer**

- `src/furqan/parser/tokenizer.py`, hand-written single-pass
  tokenizer. Recognises 7 keywords (the canonical `bismillah` plus
  English alias `scope_block`, the four Bismillah-block fields, and
  `fn`), identifiers, the punctuation `{ } ( ) : , .`, the
  multi-character `->`, and `//` line comments. 1-indexed line and
  column tracking. `TokenizeError` on unknown characters with a
  marad-style message listing what is accepted.
- `tests/test_tokenizer.py`, 19 tests pinning EOF behaviour,
  identifier rules, every keyword's lex kind, the
  bismillah/scope_block alias distinction at the lex level, line
  and column tracking, comment elision, and unknown-character
  errors.

**Phase 2.2, AST + parser**

- `src/furqan/parser/ast_nodes.py`, `SourceSpan`, `CallRef`,
  `BismillahBlock`, `FunctionDef`, `Module`. All frozen dataclasses;
  the AST is immutable.
- `src/furqan/parser/parser.py`, recursive-descent parser. Enforces
  exactly-one-Bismillah-per-module, all four required Bismillah
  fields, accepts both Arabic and English aliases identically (with
  `alias_used` recorded), parses qualified-name lists, parses
  function bodies as call-reference sets. The first parse error
  raises `ParseError` with a precise SourceSpan. No expression
  grammar yet, deliberate Phase-2 gap.
- `tests/test_parser.py`, 22 tests pinning each grammar rule, all
  four required-field error cases (parametrized), uniqueness of the
  Bismillah block, alias equivalence, multi-function modules,
  trailing-token rejection, and span correctness.

**Phase 2.3, Bismillah scope checker + paired fixtures**

- `src/furqan/errors/marad.py`, diagnosis-structured error type per
  thesis §3.7. `Marad` is a frozen dataclass with the four required
  fields (`diagnosis`, `location`, `minimal_fix`, `regression_check`)
  plus a `primitive` tag. `MaradError` wraps it for raise-and-catch.
  `Marad.render()` produces the human-readable form.
- `src/furqan/checker/bismillah.py`, the scope checker. Two entry
  points: `check_module` (returns list of marads, fail-soft) and
  `check_module_strict` (raises on first marad, fail-fast). Walks
  every function's call references; flags any call whose head
  identifier appears in the module's `not_scope`.
- `tests/fixtures/valid/`, 3 `.furqan` fixtures the checker accepts
  (full module, degenerate empty module, scope_block alias variant).
- `tests/fixtures/invalid/`, 3 `.furqan` fixtures the checker
  rejects (direct violation, qualified-call violation, violation in
  the second function only).
- `tests/test_bismillah.py`, 13 tests. 2 parametrized fixture
  sweeps (every valid fixture produces zero diagnostics; every
  invalid fixture produces ≥1). 11 named-property tests pinning
  diagnostic content, alias preservation, location accuracy, strict-
  variant raising semantics, and `Marad.render()` format.

### Verified

- **Test suite: 57 passing in 0.10s** across 3 test files.
- **Runtime dependencies: 0.** Python stdlib only.
- **Public surface stable:** every name exported from
  `furqan.parser`, `furqan.checker`, `furqan.errors` is in its
  module's `__all__`.

### Future-work registered (Tanzil order for Phase 2)

1. **Phase 2.4, zahir/batin type checker** (thesis §3.2). Compound
   types declaring `zahir { ... }` and `batin { ... }` field blocks.
   Cross-layer access without `verify(...)` is a marad. The judgment-
   style type rules are already in thesis §6.5, port them directly.
2. **Phase 2.5, additive-only module checker** (thesis §3.3).
   Compare exported symbols at version N+1 against version N.
   Removed or renamed exports without `major_version_bump` is a
   marad. Pattern transposes from Bayyinah's
   `MECHANISM_REGISTRY` import-time coherence assertion.
3. **Phase 2.6, scan-incomplete return type** (thesis §4).
   `Integrity | Incomplete<T>` union return types.
4. **Phase 2.7, Mizan three-valued bound checker, syntactic only**
   (thesis §3.4). Phase-2 contribution is the parser surface plus
   a well-formedness check; the calibration-runtime aspect is a
   later phase.

The ring-close primitive (§3.6), tanzil build ordering (§3.5), and
deeper marad caller-side regression-check verification (§3.7) are
Phase-3 concerns: each requires either a build system or whole-
program analysis that the per-module Phase-2 surface does not yet
have.
