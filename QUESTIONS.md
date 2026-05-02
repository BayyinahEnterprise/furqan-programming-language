# Open Questions

A live list of interpretive questions about Furqan's own design that the project has not yet resolved. Publishing it is the recursive application of the project's thesis: a checker that enforces structural honesty on Furqan source has to surface the gap between its own surface claims and its own substrate, or the checker is itself performing alignment.

This file is appended to, not rewritten. Questions move to a "Resolved" section with the version that resolved them. Questions are not bugs — they are interpretive issues whose right answer is not yet obvious.

## Maintainer

Bilal Syed Arfeen, project lead.

## Acknowledgement

This file was prompted by an external audit from Fraz Ashraf in May 2026. Several of the open questions below restate findings from that audit verbatim. The audit applied Furqan's own thesis to Furqan and found gaps the project had not surfaced internally; the appropriate response is to surface them publicly rather than absorb them silently.

## Open

### Q1. Rice's theorem applies, and the README does not engage with it

The seven structural primitives, however carefully chosen, approximate undecidable semantic properties of programs with decidable syntactic proxies. Rice's theorem says every non-trivial semantic property of programs is undecidable; the seven primitives are decidable proxies, and the gap between the proxy and the property is where false positives and false negatives live.

This is not a flaw to hide. It is a structural property the project should claim publicly, the way mathematics claims Gödel's theorem within its own discipline. Q1 is to identify and publish, in `KNOWN_LIMITS.md`, the function shape that the seven primitives provably cannot decide on — a Furqan source program whose honesty cannot be determined by any combination of the current checkers, with the construction method.

A note on framing: an earlier version of this question invoked Gödel's theorem. Gödel applies to formal systems that encode their own provability predicate. Furqan's checker does not (yet) — Rice is the right reference. If self-hosting lands (Q4), Gödel becomes the right reference at that point.

### Q2. The checker is implemented in unchecked Python

The Python implementation of the checker is not held to its own primitives. Python code can mutate, do I/O, throw exceptions on the success path, and shadow keywords — all things `.fqn` files cannot — without disciplinary friction from Furqan itself. Until the checker is self-hosting, or until the Python implementation has a formal semantics with a verified translation, the checker's claims about Furqan source are stronger than the checker's claims about itself.

Q2 is the bootstrap path. Self-hosting is multi-month. A formal semantics plus a verified Python translation is multi-year. A documented "Python translation discipline" — explicit rules the Python source must follow, audited the same way `.fqn` source is — is the smallest credible step and is the candidate for v0.11+.

### Q3. "Minimal fix" needs a metric

Diagnostics carry a `minimal_fix` field. "Minimal" is loaded — minimal in edit distance, in semantic perturbation, in the count of subsequent diagnostics it produces, in passing the checker that fired but possibly tripping a checker that did not? The README states the property; the metric is undefined.

The current operational definition is: the smallest edit that satisfies the checker that fired this diagnostic. Other checkers may fire on the result. v0.10.x states this explicitly in the README. Q3 is whether a stronger definition — for example, "minimal under AST node delta, with a proof that no other checker fires on the result" — is achievable across the seven primitives or only within a checker's local scope.

### Q4. Self-hosting is the bootstrap question

A type-checker that enforces structural honesty in Furqan source is itself implemented in Python. The path to a self-hosted checker (Furqan checking Furqan) is the path that closes the bootstrap. It also means re-implementing the parser, AST, checkers, and diagnostic infrastructure in Furqan, which requires Furqan to be expressive enough to express the checker — and that expressiveness has not been demonstrated yet.

Q4 is the staged plan. v1.0 might be a Furqan-source AST library used by a Python checker. v2.0 might be a Furqan-source single checker (e.g., bismillah scope) used in addition to the Python checker. v3.0 might be the parser. Self-hosting is years out. The question is which sub-component goes first and what success looks like for each stage.

### Q5. The cross-model audit shares failure modes

"Eight sessions, eight closing audits, zero open findings under the Munafiq Protocol cross-verification across three AI collaborators (Anthropic Claude, xAI Grok, Perplexity Computer)." The same observation as Bayyinah's Q9: three LLMs share substantial failure modes (sycophancy, anchoring, social pressure). Their joint null-finding rate is weak evidence against a narrow class of disagreement-based errors and is not strong evidence of correctness. Q5 is whether the project should claim audit-cleanness at all without a human audit by someone paid to find holes who does not accept the framework's premises.

### Q6. Furqan has no `INCOMPLETE` exit code

The CLI returns `0` (PASS), `1` (MARAD), `2` (PARSE ERROR), `3` (STRICT FAIL). There is no exit code for the case where a checker bailed: resource limit, unimplemented primitive on a new construct, cross-module unresolvable due to a missing module on the search path. Bayyinah, the sister project, has a prominent `scan_incomplete: bool` flag for exactly this case, and the asymmetry is silent.

Q6 is to add exit code `4` (INCOMPLETE) and document the parity with Bayyinah's flag. v0.11 candidate.

### Q7. The minimal subset tests a minimal subset of the thesis

The seven primitives are tested against fixtures designed to exercise them. The pressure on a type system comes from people writing programs the designer did not anticipate. Until a real program of non-trivial size is written in `.fqn` — something with the rough complexity of, say, the Bayyinah PDF analyzer — the primitives have not been tested against expressiveness gaps, false positives at scale, or missing primitives. Q7 is which real program is the first one to write in `.fqn`, and what Furqan needs to add (modules, generics, references, function types) to make it writable.

### Q8. Strategic coupling of framework and engineering

Same shape as Bayyinah's Q10. The Quranic vocabulary is load-bearing in the README. The engineering principles (decidable static checks, frozen AST, no I/O on success path, additive-only invariants, fixture-pinned tests) stand without the framework — the framework explains *why* these primitives were chosen, not *whether* they decide what they claim to decide. Q8 is whether a framework-free statement of the engineering principles should appear somewhere in `docs/`, alongside the framework-anchored README, for readers whose adoption is gated on it.

This is not a question about removing the framework. It is a question about whether the project's adoption ceiling is the framework's audience, and whether that is the intended ceiling.

## Resolved

(Empty. Resolved questions are appended here with the version that closed them.)
