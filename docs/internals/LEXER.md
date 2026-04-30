# LEXER.md: Furqan tokenizer design notes

This document records the lexer-layer design decisions that the
`furqan/parser/tokenizer.py` implementation rests on. Decisions made
once and recorded here should not be re-litigated session-by-session.

---

## 1. NUMBER token shape (Phase 2.5)

**Decision:** A `NUMBER` token is a contiguous run of one or more ASCII
digits. Decimals, dotted-decimals, and version-literal multi-component
forms are reconstructed at the parser layer using `DOT` as a separator.

**Lexing examples:**

| Source           | Tokens                                              |
|------------------|-----------------------------------------------------|
| `1`              | `NUMBER('1')`                                       |
| `42`             | `NUMBER('42')`                                      |
| `1.0`            | `NUMBER('1') DOT NUMBER('0')`                       |
| `v1.0`           | `IDENT('v1') DOT NUMBER('0')`                       |
| `v2.3.4`         | `IDENT('v2') DOT NUMBER('3') DOT NUMBER('4')`       |
| `0.05`           | `NUMBER('0') DOT NUMBER('05')` (Phase-2.7 Mizan)    |

**Why integer-only?** The brief offered three lexer designs:

- (A) `NUMBER` = integer only (this choice). Multi-component literals
  reconstructed at the parser layer.
- (B) `NUMBER` = integer or single-decimal `\d+(\.\d+)?`. Pre-glues
  decimals at the lex layer.
- (C) Dedicated `VERSION` token kind that matches `v\d+(\.\d+)*` in
  one token.

We picked (A) for three reasons:

1. **Simplicity.** A single regex (`\d+`) covers every numeric literal
   the language will ever need; the parser's `DOT` handling is already
   present and exercised. No new lex rules, no greedy/non-greedy
   decisions.
2. **Phase-2.7 forward compatibility.** Mizan thresholds will use
   decimal forms like `0.05` and `0.95`. Option (B) would produce
   `NUMBER('0.05')`, which is fine; but Option (B) also has to
   special-case `1.2.3` (does it lex as one decimal `1.2` followed by
   `.3`, or two integers?). Option (A) sidesteps the ambiguity:
   every dot is a separator, period.
3. **Reusable parser machinery.** The `_parse_qual_name` family
   already handles dot-separated identifier paths; treating numeric
   versions the same way kept the new VersionLit grammar to a single
   helper function.

**Version literal lexing.** A version literal of the form `vN.M` (or
`vN.M.K`) is lexed as IDENT + (DOT NUMBER)+ because identifiers
permit digits in continuation positions. The parser layer recognises
the IDENT-with-`v\d+`-prefix pattern as a VersionLit head and treats
the trailing `(DOT NUMBER)+` as the component list. See
`_parse_version_literal` in `parser.py`.

**Cost paid.** Decimals like `0.05` will require the parser to
reconstruct the float from `NUMBER('0') DOT NUMBER('05')`. The
reconstruction is straightforward (string-concat the lexemes with
the DOT) and the only edge case is leading-zero preservation, which
the lexer hands to the parser unchanged.

---

## 2. Keyword promotion as additive-on-the-rejection-side change

The keyword set has grown across phases:

| Phase | Promotions                                                       |
|-------|------------------------------------------------------------------|
| 2.0   | `bismillah`, `scope_block`, `authority`, `serves`, `scope`, `not_scope`, `fn` |
| 2.4   | `type`, `zahir`, `surface`, `batin`, `depth`                     |
| 2.5   | `additive_only`, `module`, `export`, `major_version_bump`, `removes`, `renames` |

Each promotion is **additive on the rejection side**: previously-
accepted source that used the word as an ordinary identifier becomes
rejected at the lexer. NAMING.md §6 (the additive-only invariant on
the type-checker's *public Python surface*) covers the package's
exported names; it does not cover the .furqan language's keyword
set. New keywords are explicit additive-on-the-rejection-side
changes and require a CHANGELOG version bump.

**Common-English-word test (NAMING.md §1.5).** A word is *not*
promoted to a keyword if its non-language uses are likely to collide
with user identifiers. The canonical example is `verify`, which is
recognised by the zahir/batin checker as a function-name comparison
(`fn.name == "verify"`) rather than as a token kind, so user code
remains free to define `verify_inputs`, `verify_signature`, etc.

---

## 3. Why no string literals yet (Phase 2.5, superseded by §4 below)

Phase 2.5 had no use for string literals. The deferral was the Cow
Episode (2:67-74) anti-pattern check: do not pre-specify before
observing what the next primitive needs.

Phase 2.6 (the scan-incomplete primitive, thesis §4) is where
strings actually arrive. The Incomplete literal's `reason:` field
carries free-form text, naming why the scan was incomplete in
language a downstream consumer (or a logging system) can read. See
§4 below.

## 4. STRING token shape (Phase 2.6)

**Decision:** A `STRING` token is the source span between matching
double-quote characters (`"..."`), inclusive. No escape sequences.
Newlines inside the literal are a tokenize error.

**Lexing examples:**

| Source                 | Tokens                                  |
|------------------------|-----------------------------------------|
| `"hello"`              | `STRING('"hello"')`                     |
| `"a, b, c"`            | `STRING('"a, b, c"')`                   |
| `""`                   | `STRING('""')` (empty content)          |
| `"unterminated`        | `TokenizeError`                         |
| `"with\nnewline"`      | `TokenizeError` (no multi-line in v1)   |

**Why this minimal shape?** Phase 2.6 needs strings only for the
`reason:` field of the Incomplete literal. The smallest sufficient
lexer accepts every `reason` form the eight canonical fixtures
require. Escape sequences (``\n``, ``\"``, ``\\``, etc.) are not
needed because no fixture's `reason` text contains a backslash, a
newline, or an embedded quote. Adding escape support now would be
the Cow Episode applied to lexing, pre-specifying before observing
which escapes the language actually needs.

**Future-work registration.** Escape-sequence-aware string lexing
is registered for a later phase (likely Phase 2.7 Mizan, or whenever
a fixture surfaces a `reason` text containing the disallowed
characters). The future expansion is additive on the rejection side:
every `STRING` lexeme that is currently accepted continues to lex
identically; only previously-rejected forms (escape-bearing strings)
become accepted.

**Phase 3.0 (D14) - escape sequences land.** The deferred future-
work item is delivered as an additive-on-the-rejection-side change.
Four escapes are now recognised inside a string literal:

| Escape | Resulting character        |
|--------|----------------------------|
| `\n`   | newline (U+000A)           |
| `\t`   | horizontal tab (U+0009)    |
| `\\`   | literal backslash          |
| `\"`   | literal double-quote       |

Every pre-Phase-3.0 string lexeme without a backslash continues to
lex identically; only previously-rejected forms (an embedded quote,
a newline-bearing reason text, an explicit tab) now become accepted
through the escape mechanism. An unknown escape character (for
example `\q`) raises `TokenizeError` with the escape's exact line
and column reported via the structured fields documented in §6
below; this is not a silent acceptance, not a fall-through to the literal
two-character sequence.

**Where the unescape happens.** The `Token.lexeme` captured by the
tokenizer preserves the **raw** source form (including the
surrounding quotes and the escape backslashes). The parser, when
constructing the `StringLiteral` AST node, strips the surrounding
quotes and runs the inner content through `_unescape_string` so the
node's `value` field carries the resolved text. Two-stage handling
keeps the round-trip property of the token stream: a future
formatter can reconstruct exact source text from the lexeme without
having to re-escape.

**Lexeme content includes the quotes.** The lexer hands the parser
the full lexeme `"..."` rather than the unwrapped content. The
parser strips the surrounding quotes when constructing a
`StringLiteral` AST node. The lexeme-includes-quotes choice keeps
the token's source-text round-trip exact (a future formatter can
reconstruct the source from the token stream without ambiguity
about which strings were quoted) and matches how `NUMBER` works
(NUMBER lexemes preserve the digit run as text, not as parsed
integer).

---

## 5. Why no `Integrity` / `Incomplete` keyword promotions (Phase 2.6)

The Phase 2.6 brief considered whether `Integrity` and `Incomplete`
should be promoted to keywords. **They were not promoted.** Both
remain ordinary identifiers in the type-name namespace alongside
`Registry`, `Weights`, `ScanLimits`.

**Why.** Both are domain concepts the caller may want to read about
as types in IDE tooltips, autocomplete suggestions, and source
documentation. Keyword promotion would force a v0.4.0 source-
language breakage on every existing identifier collision, and
because `Integrity` and `Incomplete` are common-noun-shaped
PascalCase names, those collisions are plausible.

The Phase 2.6 checker (`furqan/checker/incomplete.py`) recognises
both names by string-equality on the AST identifier (e.g.,
`type_path.base == "Incomplete"`). The checker is the layer that
attaches semantics to these identifiers; the lexer remains
oblivious. This mirrors the `verify` decision (NAMING.md §1.5):
domain semantics that depend on a name belong in the checker, not
the tokenizer, when the name is plausibly a user identifier.

**Compare to the Phase 2.5 keyword set** (`additive_only`, `module`,
`export`, `major_version_bump`, `removes`, `renames`). Those are
structural primitives, `additive_only` and `major_version_bump`
are compound declarators with no user-identifier collision risk;
`removes` and `renames` are catalog-entry verbs whose grammatical
position uniquely identifies them. The Phase 2.6 type names
(`Integrity`, `Incomplete`) and Phase 2.4's `verify` are different,
they could plausibly appear as user identifiers in unrelated code,
so they live in their respective checker layers, not the keyword
table.

---

## 6. TokenizeError carries structured location (Phase 3.0 - D10)

**Decision:** `TokenizeError` exposes the source location as
structured `line` and `column` integer attributes alongside the
human-readable message. The historical message-prose still names
the location, so any consumer that previously parsed the message
continues to work; the new fields are an additive convenience.

**Constructor signature:**

```python
class TokenizeError(Exception):
    def __init__(self, message: str, *, line: int = 0, column: int = 0): ...
```

Both fields default to `0` so any pre-Phase-3.0 raise site that has
not yet been updated continues to construct without error. The
three raise sites in the tokenizer (unrecognised character,
unterminated string, escape-related rejections) all pass concrete
values.

**Why.** The additive-only sidecar load path in
`checker/additive.py` (and any future higher-level diagnostic
that wraps a lex-time failure into a `Marad`) wants the location
without parsing the message string. Phase-2.x consumers parsed the
prose; Phase-3.0 makes the structured access point explicit.

**Reflexivity register.** The escape-sequence raise sites added in
§4 above use the same structured-location convention: an unknown
escape reports the column of the offending escape character, not
the column of the surrounding string literal. The two raise sites
on the unterminated-string path report the START location of the
literal (where the unterminated quote opened), since that is the
position the developer needs to find the typo.
