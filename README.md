# Furqan

[![CI](https://github.com/BayyinahEnterprise/furqan/actions/workflows/ci.yml/badge.svg)](https://github.com/BayyinahEnterprise/furqan/actions/workflows/ci.yml)

A programming-language type-checker that enforces structural honesty
at compile time. Furqan rejects code shapes that promise more than
the program can actually deliver, before the program ever runs.

## What this repository is

A standalone Python type-checker that verifies a minimal subset of
the Furqan surface syntax against the paper's structural-honesty
primitives. Phase 2 (this repository) is the prototype type-checker
, not a full compiler, not a runtime, not an LLM. It demonstrates
that the Furqan thesis paper's compile-time rules are mechanically
implementable.

The thesis claim under test: a meaningful fraction of code-level
"AI hallucination" is the same shape as a long-known software
defect, promising a complete answer about an input the program
cannot fully process. That shape can be made *structurally
uncompilable* by the type system, in milliseconds, with no model
in the loop.

## Why this matters

When a function declares it returns a complete answer (`Integrity`)
but the input may be unreadable (an encrypted PDF, a partial scan,
a missing field), the function should be required to either rule
out the unreadability before promising completeness, or return a
populated incomplete result with a reason and a confidence bound.
Most languages do not enforce this. Furqan does.

The discipline is a static, syntactic check. It runs in
sub-millisecond time. It produces diagnostics that name the rule
violated, the line it occurred on, and the minimal fix. It has
zero runtime dependencies and no model in the loop.

## Status

| # | Primitive             | Module                       | Status                                       |
|---|-----------------------|------------------------------|----------------------------------------------|
| 1 | Bismillah scope       | `checker/bismillah.py`       | **Shipped** (Session 1.0, v0.1.0)           |
| 2 | Zahir / batin         | `checker/zahir_batin.py`     | **Shipped** (Session 1.3, v0.2.0)           |
| 3 | Additive-only modules | `checker/additive.py`        | **Shipped** (Session 1.4, v0.3.0)           |
| 4 | Scan-incomplete       | `checker/incomplete.py`      | **Shipped** (Session 1.5, v0.4.0)           |
| 5 | Mizan calibration     | `checker/mizan.py`           | **Shipped** (Session 1.6, v0.5.0)           |
| 6 | Tanzil build ordering | `checker/tanzil.py`          | **Shipped** (Session 1.7, v0.6.0)           |
| 7 | Ring-close            | `checker/ring_close.py`      | **Shipped** (Session 1.8, v0.7.0)           |

**Seven of seven primitives shipped, the ring is closed.** Each row corresponds to a single
closing `HANDOFF.md` block; each version corresponds to a
`CHANGELOG.md` minor-version bump that registers the source-language
additions.

## Verified state

* 453 tests passing in ~0.7 seconds on Python 3.10+
* Zero runtime dependencies, Python standard library only
* Public surface 42 / 38 / 4 (parser / checker / errors), additive-only invariant held since v0.1.0
* Eight sessions, eight closing audits, zero open findings under the Munafiq Protocol cross-verification across three AI collaborators (Anthropic Claude, xAI Grok, Perplexity Computer)

## Quickstart

```bash
git clone https://github.com/BayyinahEnterprise/furqan.git
cd furqan
pip install -e .
python -m pytest        # 453 passing in ~0.7s
```

The library:

```python
from furqan.parser import parse
from furqan.checker import check_incomplete

source = open("scan_pdf.fqn").read()
module = parse(source)
diagnostics = check_incomplete(module)

for d in diagnostics:
    print(d.diagnosis)
    print(d.location)
    print(d.minimal_fix)
```

## CLI usage

After `pip install -e .`, the `furqan` command is on your PATH.

```bash
# Check a single file (runs 9 checkers)
furqan check examples/clean_module.furqan

# Strict mode (exit 3 on any Marad)
furqan check examples/status_collapse.furqan --strict

# Show version
furqan version
```

Three example files demonstrate the contract:

```bash
$ furqan check examples/clean_module.furqan
PASS  examples/clean_module.furqan
  9 checkers ran. Zero diagnostics.

$ furqan check examples/status_collapse.furqan
MARAD  examples/status_collapse.furqan
  1 violation(s):
    [status_coverage] function 'summarize' calls 'deep_scan' ...

$ furqan check examples/missing_return_path.furqan
MARAD  examples/missing_return_path.furqan
  1 violation(s):
    [all_paths_return] function 'scan' declares a return type ...
```

Exit codes: `0` PASS, `1` MARAD, `2` PARSE ERROR, `3` STRICT MODE failure.

The additive-only checker is NOT run in single-file mode; it
requires a prior-version module for comparison. Cross-version
checks live in the test suite via the additive sidecar protocol.

## What "structural honesty" means in code

The repository ships a self-contained demonstration in `demo/`.
Three frontier LLMs (ChatGPT, Claude, Gemini) were each handed the
same encrypted PDF and asked to summarise its contents. Their
behaviour diverged: one named the encryption explicitly, one blamed
the file ("unsupported or corrupted", it was neither), one implied
user error ("check the file for any issues", there were none).

The Furqan compile-time scan-incomplete primitive rejects the
function shape that would promise a complete answer about such a
file, in 0.162 ms, with a diagnostic that names the missing
incompleteness guard, the offending line, and the minimal fix. The
guarantee holds for every function that compiles, not just for the
one file the demo tested.

The point is not that the LLMs failed. ChatGPT was honest. The
point is that runtime behaviour, even when correct, is not a
structural guarantee. The same model on a different file, account
tier, or version may behave differently. A compile-time check
cannot.

Run the demo on a fresh clone:

```bash
bash demo/runner.sh
```

Four assertions, all passing: encrypted PDF regenerated and
verified rejecting open, after-column checker accepts the honest
shape and rejects the unguarded shape (both sub-millisecond), all
three captured before-column responses classified.

## Architecture

```text
src/furqan/
├── parser/
│   ├── tokenizer.py       hand-written lexer; keyword-promotion discipline
│   ├── parser.py          strict recursive-descent; F1/F2 (no opaque eaters)
│   └── ast_nodes.py       frozen dataclasses for every parsed shape
├── checker/
│   ├── bismillah.py       Primitive 1, purpose-hierarchy / scope discipline
│   ├── zahir_batin.py     Primitive 2, surface vs depth layer separation
│   ├── additive.py        Primitive 3, module evolution; sidecar history
│   ├── incomplete.py      Primitive 4, scan-incomplete; the demo target
│   └── mizan.py           Primitive 5, three-valued calibration blocks
└── errors/
    └── marad.py           diagnostic record: diagnosis, location, fix, regression check
```

Every checker is a pure function over a parsed `Module` AST. Every
diagnostic is a `Marad` record with a structured payload (diagnosis
text, source span, minimal fix, regression check). No mutation, no
I/O, no exceptions on the success path.

## Documentation

* `HANDOFF.md`, rolling session-close audit log; the most recent verified state is at the top, prior sessions are appended below as isnad.
* `CHANGELOG.md`, every minor-version bump registers the source-language additions and breaking-change boundary.
* `docs/NAMING.md`, naming-convention discipline; common-English-word reservation policy; additive-only invariant.
* `docs/CONTRIBUTING.md`, session-close protocol; polish-patch protocol §8.
* `docs/internals/CHECKER.md`, per-primitive checker semantics, scope, and limits.
* `docs/internals/LEXER.md`, tokenizer extensions per phase.

## The thesis paper

The compile-time primitives implemented here are derived from
*Furqan: A Programming Language for Structural Honesty*, published
on Zenodo:

* DOI: [10.5281/zenodo.19750529](https://doi.org/10.5281/zenodo.19750529)

Companion papers establishing the surrounding architecture (Bayyinah
input-layer defense, Bilal honest-autonomous LLM architecture, the
Munafiq Protocol for cross-verification) are linked from the thesis
paper's references section.

## What this repository is not

* Not a full compiler. This is a type-checker over a minimal surface syntax. Code generation, runtime, and FFI are out of scope for Phase 2.
* Not a static analyzer for an existing language. Furqan is a new source language with its own grammar; the checker operates on `.fqn` files, not on Python or any other host language.
* Not an LLM, not an LLM wrapper, not a prompt-engineering toolkit. No model is invoked at any point in the parser or checker. The thesis claim is about language design, not model behaviour.
* Not a finished system. The seven Phase 2 compile-time primitives are shipped, sub-millisecond, audit-clean, and demo-ready; what remains is the Phase 3 runtime evaluator and cross-module graph (D9, D20, D23). The full thesis is not yet executable end-to-end at runtime.

## Honest registers

* Test count is N=334 paired fixtures + property tests + named-rule tests + a seven-primitive integration capstone + Phase 3.0 polish (else arm, string escapes, structured tokenize errors); not a formal proof. Falsifying a primitive requires a fixture that escapes the rule's intent. The known limitations for each checker are documented in `docs/internals/CHECKER.md`.
* The cross-model audit's null-finding rate has held at zero across seven sessions and seven primitives. This is N=1 in the program's own hands; whether the methodology generalizes is a future-work question.
* The demo's three-vendor capture is N=1 per vendor at fixed timestamps on free-tier UI. Vendor behaviour drifts across model versions and account tiers; the captures are pinned to the timestamps recorded in `demo/before/responses/*.md`.

## Authors

* **Bilal Syed Arfeen**, product, architecture, research lead
* **Fraz Ashraf**, co-architect, governance protocol, first author on the Furqan thesis paper

With AI collaborators (acknowledged contributors, not co-founders):
Anthropic Claude, xAI Grok, Perplexity Computer.

## License

Apache License 2.0, see [LICENSE](./LICENSE).

## Citation

If you use Furqan in academic work:

```text
@software{furqan_2026,
  author    = {Arfeen, Bilal Syed and Ashraf, Fraz},
  title     = {Furqan: A Programming-Language Type-Checker for Structural Honesty},
  year      = {2026},
  version   = {0.9.0},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19750529},
  url       = {https://github.com/BayyinahEnterprise/furqan}
}
```
