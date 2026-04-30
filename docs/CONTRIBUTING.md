# CONTRIBUTING.md: Furqan

This is a Phase-2 prototype. Contributions follow the project's
governance protocol literally; there is no informal channel.

## 1. Authority hierarchy

When conventions conflict, resolve in this order:

1. **The Furqan v1.0 thesis paper**, absolute authority on primitive
   semantics. Disagreement with the paper is a paper-revision
   conversation, not a code-patch conversation.
2. **`docs/NAMING.md`**, authority on naming. Silent invention of a
   new convention is rejected.
3. **Observable codebase conventions**, the way existing modules are
   structured. New code matches existing patterns unless the deviation
   is justified in the PR description.
4. **Training priors / instinct**, last resort. If used, flag the
   choice explicitly in the PR.

## 2. Compliance state declaration

Every PR opens with one of three labels in the description:

* **COMPLIANT**, the change follows all conventions and preserves
  every existing test.
* **PARTIAL**, the change follows conventions but adds new public
  surface (a new module, AST node, or exported function). The PR
  description names the addition explicitly.
* **BLOCKED**, the change would violate primitive semantics or
  naming conventions and should not be merged. PRs labeled BLOCKED
  exist to record the design conversation, not to be merged.

A PR with no compliance label is rejected on contact.

## 3. The five-step workflow per change

Every change, no matter how small, goes through:

1. **Understand**, read the relevant section of the thesis paper and
   the relevant module's docstring before editing.
2. **Write**, make the change. One concept per commit.
3. **Verify**, run `pytest`. The full suite must pass.
4. **Integrate**, open the PR with the compliance label and a
   one-paragraph summary that names the primitive(s) affected.
5. **Close the ring**, the PR description ends with: which existing
   tests still pass, which new tests pin the new behavior, what
   future work is registered.

## 4. Test discipline

* Every primitive ships **paired fixtures**: at least one
  `tests/fixtures/valid/*.furqan` the checker must accept and at
  least one `tests/fixtures/invalid/*.furqan` the checker must
  reject with a specific error.
* No test is `skip`-ped or `xfail`-ed without a comment naming the
  blocking condition and a pointer to the future-work item that
  resolves it. Silent skips are rejected.
* The full test suite must run in under 5 seconds for the Phase-2
  prototype. If runtime exceeds that bound, optimize before adding
  features.

## 5. The additive-only invariant

The Phase-2 type-checker enforces this discipline on user code. The
type-checker is bound by the same discipline on its own surface:

* No public function or class is removed between versions.
* No AST node class is removed between versions.
* The exported `__all__` of every public module is monotonically
  growing.
* Renames require a deprecated alias for at least one minor version,
  documented in `CHANGELOG.md`.

CI enforces these by importing every name in `__all__` and asserting
the set is a superset of the previous version's set.

## 6. Dependency policy

The Phase-2 prototype is **standard-library-only at runtime**. New
runtime dependencies require:

* a one-paragraph justification in the PR description naming the
  specific failure that the dependency closes,
* an explicit upper version bound (`<2`, `<7`, etc.), the
  additive-only invariant extends to upstream parsers (the Bayyinah
  v1.1.1 lesson),
* approval from the lead author.

`pytest` in `[project.optional-dependencies].dev` is the only
exception, and it is dev-only.

## 7. The skip rule

If a single change consumes more than 20% of a session without
producing a passing test, the change is registered as BLOCKED with the
specific blocking condition named, and the session moves to the next
task. The Cow Episode (2:67–74) is the dominant failure mode of
ambitious refactors; the skip rule is its structural defence.

## 8. The Polish Patch Protocol

Two sessions of empirical evidence (1.1 and 1.4.1), and the
present registration (1.4.2), establish a named discipline for
absorbing small structural findings without disrupting the primitive-
shipping cadence. The protocol is documented here so future
contributors apply the same shape and so the discipline does not
drift.

### 8.1 Trigger

A polish patch fires when an independent cross-model audit
(Perplexity, Grok, or an external reviewer) identifies a
structural finding that is:

- small enough to fix in roughly ten lines of source change,
- additive on the rejection side (no previously-valid input is
  newly rejected),
- behaviorally non-breaking for any prior valid input (bit-for-bit
  output preservation on the existing fixture corpus),
- *not* gating downstream primitive work (the next phase can open
  cleanly with or without the fix).

If any of these four properties does not hold, the finding is *not*
a polish patch, see §9.5 below.

### 8.2 Shape of the patch

A polish patch ships in the same conversational round as the audit
that surfaced it. Its structural shape:

- **Source change**: typically one to three additions. New `except`
  clauses, new helper functions for diagnostic construction, new
  AST-field default values, never renames, never removals, never
  signature changes on existing exports.
- **Test change**: at minimum one new test pinning the new contract;
  for boundary-tightening fixes, additionally one negative-
  regression test asserting that the leak does *not* recur.
- **Documentation change**: a CHANGELOG entry under a fresh patch-
  level version (0.x.y → 0.x.(y+1)) with the audit finding cited
  by name and the worked-example shape recorded.
- **Inline source attribution**: a comment in the modified file
  citing the audit by name and session (e.g.
  `# Session 1.4.1 polish (Perplexity E2 finding)`). The audit
  trail lives in the source code, not just in the session log.

### 8.3 Discipline

- **Same-session shipping.** A polish patch is opened, executed,
  and closed in the same session as the audit that surfaced it.
  Deferral to a future session is acceptable only if the patch
  cannot fit in the remaining session budget; in that case the
  finding is registered as a deferred item in the closing HANDOFF
  rather than left unrecorded.
- **Audit re-run before next primitive opens.** After the patch
  ships, the verifier re-runs the same probe set that surfaced the
  finding. The next primitive opens against a zero-finding baseline
 , the audit streak is a first-class discipline.
- **Compliance state at handoff is COMPLIANT.** A polish patch
  that introduces any non-additive behavior is not a polish patch;
  see §9.5.

### 8.4 Worked examples

Two concrete cases form the empirical foundation. Future findings
should pattern-match to one of these shapes before being labeled a
polish patch.

**Session 1.1, `MaradError` super-call binding.**
Audit found that `MaradError.__init__` passed
`marad.render()` (a string) to `super().__init__`, leaving
`e.args[0]` bound to the rendered prose rather than the structured
:class:`Marad`. A future tool catching `Exception` and inspecting
`args[0]` would receive a string where a structured object was
expected.

The fix: pass `marad` directly to `super`; override `__str__` to
preserve the human-readable rendering on `str(e)`. Three lines of
source change. Two tests pinning that `e.args[0] is e.marad` and
`str(e) == e.marad.render()`. CHANGELOG v0.1.1 records the fix
and notes the contract is non-breaking for every Session-1.0
caller (no caller previously read `e.args[0]`).

**Session 1.4.1, `TokenizeError` leak in `check_module`.**
Audit found that `furqan.checker.additive.check_module` caught
only `ParseError`, so a sidecar containing lexically-malformed
bytes (characters the tokenizer cannot classify, e.g. `@#$%`)
would raise `TokenizeError` uncaught from a layer whose contract
is "return a structured `Result`". A Process-2 risk at the
version-history sidecar surface, exactly where structural honesty
is most load-bearing.

The fix: a second `except` clause that translates `TokenizeError`
to a uniform sidecar-parse-failed marad via a new
`_lex_error_sidecar_marad` helper. The marad uses a synthetic
`SourceSpan(file="<sidecar>", line=1, column=1)` because
`TokenizeError` does not yet carry structured location fields
(deferred to Phase 3 as D10). Three additive changes in
`additive.py`: one import, one `except` clause, one helper
function. Two tests: one positive (the new path emits a structured
marad with the offending character quoted in the diagnosis), one
negative-regression (the lex-error path does not raise). CHANGELOG
v0.3.1 records the fix and notes the demo path was unaffected
because the demo uses well-formed sidecars.

### 8.5 What the protocol is NOT

The polish patch is a narrow tool. The following kinds of findings
are *not* polish patches and require a full Session 1.x.x with a
fresh seven-step protocol open:

- **Multi-file semantically meaningful changes.** The Phase 2.4
  F1/F2 closure replaced opaque-eater parser logic with strict
  parsers for parameter lists and return types. This was the
  load-bearing parser surgery for zahir/batin and required a full
  session brief because it touched the parser, the AST, multiple
  test files, and changed the rejection contract on previously
  silently-accepted malformed input. Polish patches do not change
  rejection contracts on input that was previously *valid*; F1/F2
  did, by tightening the grammar.
- **Source-language breakage.** The Phase 2.5 keyword promotions
  (`additive_only`, `module`, `export`, `major_version_bump`,
  `removes`, `renames`) break any pre-2.5 source using these as
  identifiers. A breakage of this scope requires a full minor-
  version bump (v0.2.x → v0.3.0), CHANGELOG registration of the
  breakage with affected lexemes enumerated, and NAMING.md updates.
  Polish patches do not bump minor versions.
- **Tier-3 hypothesis failures.** If an audit finds that a claim
  the framework labelled Tier 3 (hypothesis, not implemented) does
  not hold under empirical pressure, for example, a proposed type
  rule produces false positives in development, that is a
  research finding requiring full retrospective analysis, not a
  ten-line fix. The retrospective belongs in its own session
  brief and may produce a thesis-paper revision rather than a
  source-code patch.
- **Public-API renames.** Renaming an exported symbol is forbidden
  by NAMING.md §6 (the additive-only invariant on the type-
  checker's own surface). Even a nominally cosmetic rename is a
  major-version-bump conversation, not a polish patch.

If a finding straddles the boundary, looks small but touches
something load-bearing, default to the full-session shape. The
five-minute cost of a deliberate session brief is small; the cost
of a polish patch that smuggled in a behavioral change is not.

### 8.6 The reflexivity check

This protocol's first formal documentation (Session 1.4.2,
CHANGELOG v0.3.2) is itself a polish patch. The protocol is
applied to its own registration: documentation-only change, no
source delta, no test delta, no behavior delta. If the protocol
were merely advisory it could be documented at any session
boundary; making the documentation itself follow the discipline is
the framework eating its own dogfood, and is the kind of structural
honesty the language is built to make habitual.

## 9. Closing

The protocol is a tool, not a wall. When it gets in the way of
shipping honest code, the protocol is the thing to revise, but the
revision is itself a proposal that goes through the same protocol.
