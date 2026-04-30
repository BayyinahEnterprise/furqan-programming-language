"""
Parser tests (Phase 2.2).

Each test pins a single property the parser must satisfy. Where the
property is a structural rule from the Furqan thesis paper (e.g.
"every Bismillah declares all four fields"), the test name names the
rule. Where the property is a mechanical grammar rule (e.g. arrow
return-type accepted), the test name names the grammar form.
"""

from __future__ import annotations

import pytest

from furqan.parser import (
    BismillahBlock,
    CallRef,
    FunctionDef,
    Module,
    ParseError,
    parse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_BISMILLAH = """
bismillah Demo {
    authority: NAMING_MD
    serves: purpose_hierarchy.truth_over_falsehood
    scope: scan, report
    not_scope: parse_files, render_output
}
"""


def _parse(src: str) -> Module:
    return parse(src, file="<test>")


# ---------------------------------------------------------------------------
# Bismillah block — happy path
# ---------------------------------------------------------------------------

def test_minimal_bismillah_block_parses_to_a_module() -> None:
    mod = _parse(MINIMAL_BISMILLAH)
    assert isinstance(mod, Module)
    assert isinstance(mod.bismillah, BismillahBlock)
    assert mod.bismillah.name == "Demo"
    assert mod.bismillah.alias_used == "bismillah"
    assert mod.functions == ()


def test_bismillah_authority_field_collects_identifiers() -> None:
    mod = _parse(MINIMAL_BISMILLAH)
    assert mod.bismillah.authority == ("NAMING_MD",)


def test_bismillah_serves_field_collects_qualified_names() -> None:
    mod = _parse(MINIMAL_BISMILLAH)
    assert mod.bismillah.serves == (
        ("purpose_hierarchy", "truth_over_falsehood"),
    )


def test_bismillah_scope_and_not_scope_fields_collect_identifiers() -> None:
    mod = _parse(MINIMAL_BISMILLAH)
    assert mod.bismillah.scope == ("scan", "report")
    assert mod.bismillah.not_scope == ("parse_files", "render_output")


def test_scope_block_alias_is_accepted_with_identical_semantics() -> None:
    """``scope_block`` is the English alias for ``bismillah`` per
    NAMING.md §1; both must parse to the same AST shape."""
    src = MINIMAL_BISMILLAH.replace("bismillah", "scope_block", 1)
    mod = _parse(src)
    assert mod.bismillah.alias_used == "scope_block"
    assert mod.bismillah.name == "Demo"


def test_bismillah_serves_can_carry_multiple_qualified_names() -> None:
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood,
                protect.artificial_systems
        scope: scan
        not_scope: render_output
    }
    """
    mod = _parse(src)
    assert mod.bismillah.serves == (
        ("purpose_hierarchy", "truth_over_falsehood"),
        ("protect", "artificial_systems"),
    )


# ---------------------------------------------------------------------------
# Bismillah block — required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["authority", "serves", "scope", "not_scope"])
def test_missing_required_field_is_a_parse_error(missing: str) -> None:
    """Per Furqan thesis §3.1 every Bismillah block declares all four
    fields. A missing field is a structural error, not a default."""
    fields = {
        "authority": "authority: NAMING_MD",
        "serves": "serves: purpose_hierarchy.truth_over_falsehood",
        "scope": "scope: scan",
        "not_scope": "not_scope: parse_files",
    }
    body = "\n".join(v for k, v in fields.items() if k != missing)
    src = f"bismillah Demo {{\n{body}\n}}"
    with pytest.raises(ParseError) as exc:
        _parse(src)
    # The diagnosis must name the missing field.
    assert missing in exc.value.message


def test_unknown_field_inside_bismillah_is_rejected() -> None:
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.truth_over_falsehood
        scope: scan
        not_scope: parse_files
        secret_clause: do_evil
    }
    """
    with pytest.raises(ParseError) as exc:
        _parse(src)
    assert "secret_clause" in str(exc.value)


# ---------------------------------------------------------------------------
# Bismillah block — uniqueness
# ---------------------------------------------------------------------------

def test_two_bismillah_blocks_per_module_is_a_parse_error() -> None:
    src = MINIMAL_BISMILLAH + "\n" + MINIMAL_BISMILLAH
    with pytest.raises(ParseError) as exc:
        _parse(src)
    assert "Only one Bismillah block" in exc.value.message


def test_module_without_a_bismillah_block_is_a_parse_error() -> None:
    src = "fn just_a_function() { do_thing() }"
    with pytest.raises(ParseError) as exc:
        _parse(src)
    assert "Bismillah" in exc.value.message


# ---------------------------------------------------------------------------
# Function definitions and call references
# ---------------------------------------------------------------------------

def test_function_with_no_calls_parses_with_empty_call_list() -> None:
    src = MINIMAL_BISMILLAH + """
    fn empty() {
    }
    """
    mod = _parse(src)
    assert len(mod.functions) == 1
    assert mod.functions[0].name == "empty"
    assert mod.functions[0].calls == ()


def test_function_call_sites_are_collected_in_source_order() -> None:
    src = MINIMAL_BISMILLAH + """
    fn run() {
        scan()
        report()
        scan()
    }
    """
    mod = _parse(src)
    calls = mod.functions[0].calls
    assert tuple(c.head for c in calls) == ("scan", "report", "scan")


def test_qualified_call_path_is_preserved() -> None:
    src = MINIMAL_BISMILLAH + """
    fn run() {
        stdlib.io.read()
    }
    """
    mod = _parse(src)
    call = mod.functions[0].calls[0]
    assert call.path == ("stdlib", "io", "read")
    assert call.head == "stdlib"
    assert call.qualified == "stdlib.io.read"


def test_function_signature_with_arrow_return_type_is_accepted() -> None:
    """The arrow + return-type tokens are tolerated but not type-checked
    in Phase 2.2. A future session adds zahir/batin and Incomplete
    return-type semantics."""
    src = MINIMAL_BISMILLAH + """
    fn produce() -> Integrity {
        scan()
    }
    """
    mod = _parse(src)
    assert mod.functions[0].name == "produce"
    assert tuple(c.head for c in mod.functions[0].calls) == ("scan",)


def test_function_parameters_are_tolerated_in_phase_2() -> None:
    """Parameter parsing is a Phase 3 surface; Phase 2 swallows the
    parameter list to avoid blocking on a grammar that has not been
    designed yet (do not over-specify, 2:67-74)."""
    src = MINIMAL_BISMILLAH + """
    fn run(input: Document) {
        scan()
    }
    """
    mod = _parse(src)
    assert mod.functions[0].name == "run"


def test_multiple_functions_after_bismillah_are_collected_in_source_order() -> None:
    src = MINIMAL_BISMILLAH + """
    fn one() { scan() }
    fn two() { report() }
    """
    mod = _parse(src)
    assert tuple(f.name for f in mod.functions) == ("one", "two")


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def test_bismillah_span_points_at_the_keyword() -> None:
    mod = _parse(MINIMAL_BISMILLAH)
    span = mod.bismillah.span
    # 'bismillah' starts on line 2 of the test source (line 1 is the
    # leading newline produced by the triple-quoted string), in
    # column 1 because the constant uses no indentation.
    assert span.line == 2
    assert span.column == 1


def test_call_span_points_at_the_call_head() -> None:
    src = MINIMAL_BISMILLAH + """
    fn run() {
        scan()
    }
    """
    mod = _parse(src)
    call = mod.functions[0].calls[0]
    assert call.span.line >= 9  # after the bismillah block
    assert call.span.column == 9   # 8 spaces of indentation + 1


# ---------------------------------------------------------------------------
# Trailing junk
# ---------------------------------------------------------------------------

def test_trailing_token_after_module_body_is_an_error() -> None:
    src = MINIMAL_BISMILLAH + "\nstray_token"
    with pytest.raises(ParseError):
        _parse(src)


# ---------------------------------------------------------------------------
# parse_invalid fixture sweep — Session 1.2 c.3 hardening
# ---------------------------------------------------------------------------
#
# Files under ``tests/fixtures/parse_invalid/`` are .furqan sources
# that must FAIL at the parser layer (not the checker layer). They
# exercise structural rejections — currently the c.3 brace-in-arg-list
# case from the Perplexity review. Every file in this directory is
# expected to raise :class:`ParseError`.
#
# This is a separate sweep from ``tests/fixtures/invalid/`` (which
# expects parse-then-checker rejection) because the two layers have
# different rejection contracts. Splitting them here keeps each test's
# error mode unambiguous.

from pathlib import Path

PARSE_INVALID_DIR = Path(__file__).parent / "fixtures" / "parse_invalid"


@pytest.mark.parametrize(
    "fixture",
    sorted(PARSE_INVALID_DIR.glob("*.furqan")),
    ids=lambda p: p.name,
)
def test_every_parse_invalid_fixture_raises_parse_error(fixture: Path) -> None:
    """Each parse_invalid fixture is a .furqan file that the parser
    must reject. Catching the rejection at parser-stage (rather than
    letting it leak to checker-stage as a silent AST drop) is the
    structural guarantee Session 1.2 added.
    """
    with pytest.raises(ParseError):
        parse(fixture.read_text(), file=str(fixture))


def test_parse_invalid_directory_is_non_empty() -> None:
    """The directory must contain at least one fixture, otherwise
    the sweep above is silently vacuous (a Process-2 risk in the
    test surface itself)."""
    assert sorted(PARSE_INVALID_DIR.glob("*.furqan")), (
        "tests/fixtures/parse_invalid/ is empty; either remove this "
        "test along with the directory, or add a fixture pinning a "
        "documented parser-level rejection."
    )


# ---------------------------------------------------------------------------
# c.3 — direct, named tests for the brace-rejection contract
# ---------------------------------------------------------------------------

def test_lbrace_inside_call_arg_list_is_rejected() -> None:
    """The drill-down case 1 from the Perplexity review: a stray '{'
    inside an arg list. Before the patch this parsed silently."""
    src = MINIMAL_BISMILLAH + "\nfn run() { x({) }"
    with pytest.raises(ParseError) as exc:
        _parse(src)
    assert "'{'" in str(exc.value)


def test_rbrace_inside_call_arg_list_is_rejected() -> None:
    """Drill-down case 3: a stray '}' inside an arg list."""
    src = MINIMAL_BISMILLAH + "\nfn run() { x(}) }"
    with pytest.raises(ParseError) as exc:
        _parse(src)
    assert "'}'" in str(exc.value)


def test_balanced_brace_block_inside_call_arg_list_is_rejected() -> None:
    """Drill-down case 2 — the load-bearing one. A balanced brace pair
    containing a nested call inside the arg list is rejected. Before
    the patch the inner call was silently dropped from the AST."""
    src = MINIMAL_BISMILLAH + "\nfn run() { x({ parse_files() }) }"
    with pytest.raises(ParseError):
        _parse(src)


def test_nested_paren_only_args_are_still_accepted() -> None:
    """Negative-regression baseline. The c.3 patch must not break
    the existing paren-depth tracking — paren-only nesting at depth
    3 inside an arg list still parses as one CallRef on the outer
    head."""
    src = MINIMAL_BISMILLAH + "\nfn run() { x((a, b), c, ((d))) }"
    mod = _parse(src)
    assert len(mod.functions) == 1
    calls = mod.functions[0].calls
    assert len(calls) == 1
    assert calls[0].head == "x"


# ---------------------------------------------------------------------------
# Phase 2.7 (Session 1.6) — parser-level enforcement
# ---------------------------------------------------------------------------

def test_mizan_unknown_field_raises_parse_error_with_pinned_text() -> None:
    """Per Phase 2.7 §6.4, mizan field heads are keyword tokens.
    An IDENT in field-head position is a parse error, not a
    checker case (M3 is routed to the parser layer). The fixture
    ``invalid/unknown_field.furqan`` pins this behaviour; the
    diagnostic text is part of the v0.5.0 grammar contract."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "mizan" / "invalid"
        / "unknown_field.furqan"
    )
    with pytest.raises(ParseError) as exc:
        parse(fixture_path.read_text(), file=str(fixture_path))
    msg = exc.value.message
    assert "unexpected token in mizan field-head position" in msg
    assert "la_tatghaw" in msg
    assert "la_tukhsiru" in msg
    assert "bil_qist" in msg


def test_mizan_chained_comparison_raises_parse_error_with_pinned_text() -> None:
    """Phase 2.7 comparison expressions are non-associative.
    `a < b < c` is a parse error, not a silent expansion. The
    fixture ``parse_invalid/mizan_chained_comparison.furqan``
    pins this behaviour."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "parse_invalid"
        / "mizan_chained_comparison.furqan"
    )
    with pytest.raises(ParseError) as exc:
        parse(fixture_path.read_text(), file=str(fixture_path))
    msg = exc.value.message
    assert "Chained comparison" in msg
    assert "non-associative" in msg


def test_mizan_block_with_three_canonical_fields_parses_cleanly() -> None:
    """Round-trip smoke test: the canonical mizan block from the
    thesis §Primitive 4 example 1 parses without error."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    mizan detection_threshold {
        la_tatghaw:  false_positive_rate < 0.05
        la_tukhsiru: detection_rate > 0.90
        bil_qist:    calibrate(corpus, paired_fixtures)
    }
    """
    mod = parse(src, file="<inline>")
    assert len(mod.mizan_decls) == 1
    md = mod.mizan_decls[0]
    assert md.name == "detection_threshold"
    assert tuple(f.name for f in md.fields) == (
        "la_tatghaw", "la_tukhsiru", "bil_qist",
    )


def test_mizan_block_with_reversed_comparison_orientation_parses() -> None:
    """The grammar must accept `0.05 > false_positive_rate` (reversed
    operand orientation). Over-constraining operand order would be
    the Cow Episode applied to the parser."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    mizan reversed {
        la_tatghaw:  0.05 > false_positive_rate
        la_tukhsiru: detection_rate > 0.90
        bil_qist:    calibrate(corpus)
    }
    """
    mod = parse(src, file="<inline>")
    assert len(mod.mizan_decls) == 1
    from furqan.parser import BinaryComparisonExpr, ComparisonOp
    fields = mod.mizan_decls[0].fields
    la_tatghaw_value = fields[0].value
    assert isinstance(la_tatghaw_value, BinaryComparisonExpr)
    assert la_tatghaw_value.op == ComparisonOp.GT


def test_tanzil_unknown_field_raises_parse_error_with_pinned_text() -> None:
    """Per Phase 2.8 routing discipline (same as Mizan §6.4), tanzil
    field heads are keyword tokens. An IDENT (here `requires`) in
    the dependency-position is a parse error, not a checker case.
    The fixture ``tanzil/invalid/unknown_field.furqan`` pins this
    behaviour; the diagnostic text is part of the v0.6.0 grammar
    contract."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "tanzil" / "invalid"
        / "unknown_field.furqan"
    )
    with pytest.raises(ParseError) as exc:
        parse(fixture_path.read_text(), file=str(fixture_path))
    msg = exc.value.message
    assert "unexpected token in tanzil dependency position" in msg
    assert "depends_on" in msg


def test_tanzil_block_with_one_dependency_parses_cleanly() -> None:
    """Round-trip smoke test: the canonical tanzil block parses
    without error and produces a TanzilDecl with one
    DependencyEntry."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    tanzil build_order {
        depends_on: CoreModule
    }
    """
    mod = parse(src, file="<inline>")
    assert len(mod.tanzil_decls) == 1
    td = mod.tanzil_decls[0]
    assert td.name == "build_order"
    assert len(td.dependencies) == 1
    assert td.dependencies[0].module_path == "CoreModule"


def test_tanzil_block_can_coexist_with_mizan_block_in_one_module() -> None:
    """A module declaring both tanzil and mizan blocks parses
    cleanly; Phase 2.8 grammar composes additively with Phase 2.7
    grammar without interaction."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    tanzil deps {
        depends_on: Foundation
    }

    mizan threshold {
        la_tatghaw:  fp < 0.05
        la_tukhsiru: dr > 0.90
        bil_qist:    calibrate(c)
    }
    """
    mod = parse(src, file="<inline>")
    assert len(mod.tanzil_decls) == 1
    assert len(mod.mizan_decls) == 1


def test_lone_comparison_expression_parses_outside_mizan_block() -> None:
    """The comparison expression is part of the general expression
    grammar, not exclusive to mizan blocks. Confirm this composes
    with the existing function-body / return-statement context."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: cal
        not_scope: nothing
    }

    fn check(x: Number) -> Integrity | Incomplete {
        if not x < 0 {
            return Integrity
        }
        return Incomplete {
            reason: "negative input",
            max_confidence: 0.0,
            partial_findings: empty_list
        }
    }
    """
    mod = parse(src, file="<inline>")
    # The function parsed without error and produced one fn.
    assert len(mod.functions) == 1
