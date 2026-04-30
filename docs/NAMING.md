# NAMING.md: Furqan Naming Discipline

Names are the first interface. A name that lies, that says one thing
and means another, is the language-design analog of the *zahir/batin*
divergence the language is built to detect. The conventions below are
the structural honesty discipline applied to the type-checker's own
identifiers.

This document is the second authority in the project's authority
hierarchy, after the Furqan v1.0 thesis paper itself.

---

## 1. Arabic terms are the canonical primitive names

The seven primitives of the language carry Arabic names from the
Quranic source. English aliases are first-class and accepted by the
type-checker on equal terms.

| Arabic (canonical) | English alias | Module             | Concept                                           |
|--------------------|---------------|--------------------|---------------------------------------------------|
| `bismillah`        | `scope_block` | `checker/bismillah`| Module-opening scope and not-scope declaration    |
| `zahir`            | `surface`     | `checker/zahir_batin` | Surface (visible) layer of a compound type     |
| `batin`            | `depth`       | `checker/zahir_batin` | Depth (internal) layer of a compound type      |
| `mizan`            | `calibration` | `checker/mizan`    | Three-valued bound on an optimization target      |
| `tanzil`           | `phased_build`| `checker/tanzil`   | Phased compilation with regression gates          |
| `marad`            | `diagnosis`   | `errors/marad`     | Structured diagnostic error type                  |
| `ring_close`       | `scope_verify`| `checker/ring_close`| Closing assertion matching the opening Bismillah |

The Arabic terms are the canonical syntax-level keywords. The English
aliases are equally accepted by the parser, a developer can write
`scope_block ScanService { ... }` and receive identical type-checker
verification to `bismillah ScanService { ... }`. **Both names map to
the same AST node and the same checker module.** The test suite
asserts behavioural identity for every alias pair.

This is the cultural-gatekeeping safeguard from Furqan thesis §7
(Failure mode 4) operationalized: the structural property is
independent of the terminology a developer uses to invoke it.

### 1.5, `verify` is a checker convention, not a keyword (Phase 2.4)

The zahir/batin primitive (thesis §3.2) gives `verify` a load-bearing
role: it is the only function permitted to take an unqualified
compound-type parameter. The natural design instinct is to promote
`verify` to a keyword so the type rule is enforceable lexically.

We **deliberately do not** promote `verify` to a keyword.

**Why.** Promoting `verify` to a keyword would prohibit every
non-type-verification use of the word across the entire language
surface, variable names, helper-function names, comment-adjacent
identifiers in unrelated domains. `verify` is a common English word
and the cost of reserving it dominates the benefit of lexical
enforcement. The zahir/batin checker compares function names at the
checker layer (`fn.name == "verify"`) rather than at the token layer.

**How to apply.** When implementing a primitive that depends on a
specific function name to grant special access, the rule lives in
the checker, not the tokenizer. Lexical promotion is reserved for
words whose only legitimate use in the language is the special
construct (`bismillah`, `zahir`, `batin`, `mizan`, `tanzil`,
`marad`, `ring_close`, `additive_only`, `type`).

### 1.6, Promoted keywords as of Phase 2.5

| Keyword              | Phase  | Where it appears                                  |
|----------------------|--------|---------------------------------------------------|
| `bismillah`          | 2.0    | module-opening declaration                        |
| `scope_block`        | 2.0    | English alias for `bismillah`                     |
| `authority`          | 2.0    | Bismillah field                                   |
| `serves`             | 2.0    | Bismillah field                                   |
| `scope`              | 2.0    | Bismillah field                                   |
| `not_scope`          | 2.0    | Bismillah field                                   |
| `fn`                 | 2.0    | function declaration                              |
| `type`               | 2.4    | compound-type declaration                         |
| `zahir`              | 2.4    | layer block + layer-qualified type path segment   |
| `surface`            | 2.4    | English alias for `zahir`                         |
| `batin`              | 2.4    | layer block + layer-qualified type path segment   |
| `depth`              | 2.4    | English alias for `batin`                         |
| `additive_only`      | 2.5    | additive-only module declaration head             |
| `module`             | 2.5    | additive-only module declaration head             |
| `export`             | 2.5    | export declaration inside additive_only module    |
| `major_version_bump` | 2.5    | breaking-change escape valve catalog              |
| `removes`            | 2.5    | major_version_bump catalog entry                  |
| `renames`            | 2.5    | major_version_bump catalog entry                  |
| `if`                 | 2.6    | conditional statement head                        |
| `not`                | 2.6    | unary negation in expressions                     |
| `return`             | 2.6    | return-statement head                             |
| `mizan`              | 2.7    | calibration block declaration head                |
| `la_tatghaw`         | 2.7    | "do not transgress", upper-bound field head      |
| `la_tukhsiru`        | 2.7    | "do not make deficient", lower-bound field head  |
| `bil_qist`           | 2.7    | "establish in justice", calibration field head   |
| `tanzil`             | 2.8    | build-ordering block declaration head             |
| `depends_on`         | 2.8    | dependency-entry field head inside tanzil block   |
| `else`               | 3.0    | else arm of an if statement                       |

Each keyword promotion is additive on the rejection side: previously-
accepted source that used the word as an ordinary identifier becomes
rejected at the lexer. NAMING.md §6 (the additive-only invariant on
the type-checker's *public Python surface*) covers the package's
exported names; it does not cover the .furqan language's keyword
set. New keywords are explicit additive-on-the-rejection-side
changes, recorded in CHANGELOG with the promotion phase.

#### Phase 2.5 promotion rationale (per the common-English-word test)

The six new keywords are each structural primitives of the module/
versioning system, not runtime concepts that might collide with
ordinary user identifiers:

- **`additive_only`**, a compound declarator unique to Phase 2.5.
  No legitimate non-Furqan use of this exact snake-case form.
- **`module`**, narrowly used in the additive-only declaration head.
  Although `module` is a common English word, it appears in Furqan
  *only* paired with `additive_only` at the head of a module
  declaration. The pairing makes accidental collision unlikely;
  `module` is still reserved to keep the parser unambiguous.
- **`export`**, declarator for surface symbols. `export` appears in
  many languages (TypeScript, ES modules, Rust) as a keyword; the
  promotion is consistent with established practice.
- **`major_version_bump`**, a compound declarator unique to Phase
  2.5. No reasonable user-code collision.
- **`removes`** / **`renames`**, third-person-singular verbs
  declarating catalog entries. These could collide with method names
  in user code (a future release surface, Phase 3+, may introduce
  method declarations), but inside the major_version_bump catalog
  the syntactic position is unambiguous. Phase 2.5 promotes them
  conservatively; if a future phase needs them as ordinary
  identifiers, they could be context-sensitive (parsed as keywords
  only inside the catalog).

Compare these to `verify` (NAMING.md §1.5), which was *not* promoted
because its non-language uses are pervasive (`verify_input`,
`verify_signature`, etc.). The six Phase-2.5 promotions all pass the
test that `verify` failed.

#### Phase 2.6 promotion rationale (per the common-English-word test)

The three new keywords (`if`, `not`, `return`) are flow-control
primitives. Every mainstream programming language reserves these
because their grammatical position is universal and their non-
language uses as identifiers are vanishingly rare:

- **`if`**, conditional statement head. No legitimate user-
  identifier use; even in domain-specific contexts (a function named
  `if_holds`?) the conditional sense dominates.
- **`not`**, unary negation. Could collide with predicate names
  (`is_not_empty`?) but never as a bare identifier in expression
  position; inside a Furqan expression `not <expr>` is always the
  negation operator, never a name reference.
- **`return`**, return-statement head. Universal across languages;
  the position-after-statement-start is unambiguously the keyword.

#### Phase 2.6 deliberate non-promotions: `Integrity` and `Incomplete`

The Phase 2.6 brief explicitly considered whether to promote
`Integrity` and `Incomplete` to keywords. **Both were left as
ordinary identifiers** in the type-name namespace, alongside
`Registry`, `Weights`, `ScanLimits`, and other PascalCase type
references.

**Why.** Both names describe domain concepts the caller may want
to read about as types in IDE tooltips, autocomplete suggestions,
and source documentation. Promoting them to keywords would force a
v0.4.0 source-language breakage on every existing identifier
collision, and because both are common-noun-shaped PascalCase
names, those collisions are plausible. The Phase 2.6 checker
(`furqan/checker/incomplete.py`) recognises both names by string-
equality on the AST identifier; semantic recognition lives in the
checker, not the lexer.

This pattern (semantic checker + identifier-namespace token) is
the same one applied to `verify` in Phase 2.4 (NAMING.md §1.5).
The rule that emerges across phases: when a name plausibly
collides with user identifiers, the checker recognises it; when a
name is a structural primitive with no plausible identifier
collision, the tokenizer promotes it.

### 1.7, Phase 2.7 keyword promotions and the snake-case Arabic-transliteration convention

Phase 2.7 promotes four new keywords for the Mizan three-valued
calibration block:

- **`mizan`**, block declaration head. Arabic for "balance"; not
  a common English word; no identifier collision risk.
- **`la_tatghaw`**, "do not transgress" (Ar-Rahman 55:8). The
  upper-bound field head.
- **`la_tukhsiru`**, "do not make deficient" (Ar-Rahman 55:9).
  The lower-bound field head.
- **`bil_qist`**, "in justice" (Ar-Rahman 55:9). The calibration-
  function field head.

All four pass the common-English-word test (none are common
English words; none plausibly collide with user identifiers).
Promotion is safe.

#### The snake-case-with-underscore convention for Arabic transliterations

Arabic phrases that span multiple English words (after
transliteration) use the underscore as a word separator:

- `la_tatghaw` rather than `latatghaw` (the original Arabic is
  two words: لَا تَطْغَوْا‎)
- `la_tukhsiru` rather than `latukhsiru`
- `bil_qist` rather than `bilqist`

The underscore convention has two structural effects:

1. **Readability.** A reader unfamiliar with Arabic can recognise
   the word boundaries from the underscore, which aids
   pronunciation and learning.
2. **Identifier-namespace separation.** A user identifier like
   `latatghaw` (no underscore) would not collide with the keyword
   `la_tatghaw`. This relaxes the common-English-word test on
   transliterations: even if a user happens to use the
   transliterated phrase as an identifier, the underscore form is
   distinct.

Future Arabic-transliteration keywords will follow the same
convention. English aliases (e.g., a hypothetical
`calibration { upper, lower, calibrate }` form for the mizan
block) are deferred per the thesis paper's Terminology Note;
when they land, they will follow the same snake_case convention
as Phase 2.0–2.6 English-alias precedents (`scope_block`,
`surface`, `depth`).

### 1.8, Phase 2.8 keyword promotions

Phase 2.8 promotes two keywords for the Tanzil build-ordering
block:

- **`tanzil`**, block declaration head. Arabic for "revelation"
  / "progressive descent" (Al-Isra 17:106). Not a common English
  word; no identifier collision risk.
- **`depends_on`**, single canonical field-head keyword inside
  a tanzil block. The snake_case form is consistent with both the
  Phase-2.7 Arabic-transliteration convention (§1.7) and the
  English-keyword precedents (`scope_block`, `not_scope`,
  `additive_only`, `major_version_bump`); the underscore makes
  the two-word phrase syntactically distinct from any plausible
  user identifier (`dependson` would not collide).

Both pass the common-English-word test. `tanzil` is unfamiliar
outside Quranic context. `depends_on` is a structural primitive of
the build-ordering grammar with no plausible non-language use as
an identifier (a dependent variable in user code would be named
`dependency`, `dep`, `depended_on_by`, etc., not the imperative
`depends_on`).

## 2. Python module names

* **snake_case** for module names: `checker/bismillah.py`,
  `checker/zahir_batin.py`, `parser/tokenizer.py`.
* The module name is the Arabic term (when one applies), `bismillah.py`
  not `scope_block.py`, so the import path tracks the canonical name.
  The English alias is implemented inside the module as a function or
  attribute alias.
* No abbreviations in module names. `tokenizer`, not `tok`. `parser`,
  not `prs`.

## 3. Python type and class names

* **PascalCase** for classes, dataclasses, exception types, and named
  tuples: `BismillahBlock`, `ZahirBatinType`, `MizanConstraint`,
  `MaradError`, `Token`, `TokenKind`.
* Exception types end in `Error`: `ParseError`, `BismillahScopeError`,
  `MaradMissingFieldError`. Never `Exception` on its own; never a bare
  string-typed message.
* Dataclass field names follow the same Arabic-canonical /
  English-alias rule as primitive names: a `BismillahBlock` carries
  fields `authority`, `serves`, `scope`, `not_scope`: the Arabic
  source-syntax keywords are the field names, because the English
  aliases (e.g. `scope_block` for `bismillah`) apply at the
  language-keyword level, not at the AST-field level.

## 4. Test naming

* Test files mirror source files exactly:
  `src/checker/bismillah.py` → `tests/test_bismillah.py`.
* Test functions name the property they pin, not the function they
  exercise: `test_violates_not_scope_is_rejected_with_specific_error`,
  not `test_check_module`. The reader of a test failure should be able
  to name the contract that broke from the test name alone.
* Test fixtures live in `tests/fixtures/valid/` and
  `tests/fixtures/invalid/` and use the `.furqan` extension. Each
  primitive ships paired fixtures: at least one valid file the checker
  must accept and at least one invalid file the checker must reject
  with a specific error. This is the Bayyinah `paired_fixtures`
  discipline applied to the type-checker's own surface.

## 5. Error messages

Every type error produced by the checker is a *marad*, a diagnosis,
not a verdict. From the `errors/marad.py` contract, every error
carries:

| Field             | Meaning                                                      |
|-------------------|--------------------------------------------------------------|
| `diagnosis`       | What went wrong, in one sentence (no jargon)                 |
| `location`        | Source file + line/column (or `None` if not yet wired)        |
| `minimal_fix`     | The smallest change that would make the program type-check   |
| `regression_check`| What test would verify the fix did not break adjacent rules  |

Error messages name the violated *constraint* explicitly, by the
constraint's canonical name. A `bismillah` `not_scope` violation
mentions the word `not_scope` and quotes the offending symbol. A user
who reads the error should be able to find the relevant section of
the Furqan thesis paper from the wording alone.

## 6. The additive-only invariant on this type-checker

The type-checker is itself bound by the additive-only invariant it
enforces on user code. **Every public function or class exported by
`furqan/__init__.py` at version N must be present at version N+1 with
a compatible signature.** Removal or renaming requires an explicit
major-version bump (1.0 → 2.0) and a documented deprecation.

A second canonical surface is the *AST node set*: removing or renaming
an AST node class is treated the same as removing a public function.
Tests pin this in the same way Bayyinah's `MECHANISM_REGISTRY` pins
its mechanism set, by importing the registry and asserting on its
contents, so a future version cannot silently change the surface.

## 7. What this document does not cover

* Runtime / interpreter naming conventions, Phase 2 is static
  verification only; there is no runtime yet.
* Formal language grammar, that lives in the thesis paper and (when
  written) `docs/GRAMMAR.md`.
* Editor / IDE plugin naming, Phase 4 work, not in scope here.

## 8. Authority

When a naming question is not resolved by this document or by the
thesis paper, the resolution goes to the lead author (Bilal Syed
Arfeen) before code is written. **Silent invention of a new
convention is the worst failure mode** (Ashraf, M1 principle). A loud
question is acceptable; a guess that ships is not.
