"""
D23 imported_types parameter tests (partial - the additive ring-close
extension only).

The full D23 contract requires the v0.10.0 Project class with a
dependency graph (D9/D20) to drive cross-module type resolution.
That class does not exist in v0.9.0; this test module pins ONLY the
backward-compatible ring-close parameter that a future Project
driver will use. When D9/D20 ship, additional tests covering
Project.check_all and CLI directory mode will land in their own
files.
"""

from __future__ import annotations

import pytest

from furqan.checker.ring_close import check_ring_close
from furqan.errors.marad import Marad
from furqan.parser import parse


_BISMILLAH = """
bismillah ConsumerModule {
    authority: NAMING_MD
    serves: purpose_hierarchy.balance_for_living_systems
    scope: scan
    not_scope: nothing_excluded
}

fn process() -> Report {
    return Report
}
"""


def test_default_imported_types_is_empty_frozenset() -> None:
    """The default for the new parameter is an empty frozenset, so
    every pre-D23 caller behaves identically. R1 fires on the
    undeclared `Report` type."""
    module = parse(_BISMILLAH, file="<inline>")
    diagnostics = check_ring_close(module)
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "Report" in r1[0].diagnosis


def test_imported_type_does_not_fire_r1() -> None:
    """When the consumer's direct dependency exports `Report`, the
    Project driver passes it via imported_types and R1 is silent."""
    module = parse(_BISMILLAH, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"Report"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_imported_types_does_not_replace_builtin_set() -> None:
    """Integrity / Incomplete remain resolvable even when
    imported_types is empty - the builtin set is unioned, not
    overridden."""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> Integrity | Incomplete {
        if not missing {
            return Integrity
        } else {
            return Incomplete {
                reason: "missing",
                max_confidence: 0.5,
                partial_findings: empty_list
            }
        }
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(module, imported_types=frozenset())
    assert diagnostics == []


def test_imported_types_unions_with_local_compound_types() -> None:
    """A local compound type stays resolvable; an imported one is
    accepted alongside it."""
    src = """
    bismillah Mixed {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type LocalType {
        zahir { name: String }
        batin { id: ID }
    }

    fn one() -> LocalType {
        return LocalType
    }

    fn two() -> ImportedType {
        return ImportedType
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"ImportedType"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_imported_type_not_in_set_still_fires_r1() -> None:
    """Direct-only resolution: a type that is neither declared nor
    in the imported_types set fires R1, even when imported_types
    contains other names. (This pins the direct-only scoping
    decision: a future Project driver must include the type
    explicitly in imported_types - transitive resolution is opt-in
    only via re-declared dependencies.)"""
    src = """
    bismillah Demo {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn scan() -> NotImported {
        return NotImported
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"OtherType", "AnotherType"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert len(r1) == 1
    assert "NotImported" in r1[0].diagnosis


def test_imported_types_covers_parameter_position() -> None:
    """R1 covers parameter types as well as return types - the
    imported_types set must apply at both call sites."""
    src = """
    bismillah Param {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type Result {
        zahir { name: String }
        batin { id: ID }
    }

    fn process(input: ImportedType) -> Result {
        return Result
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"ImportedType"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_imported_types_covers_union_arms() -> None:
    """Both arms of a union return type are independently resolved
    against the imported_types set."""
    src = """
    bismillah Union {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    fn maybe() -> ImportedA | ImportedB {
        return ImportedA
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module,
        imported_types=frozenset({"ImportedA", "ImportedB"}),
    )
    r1 = [
        d for d in diagnostics
        if isinstance(d, Marad) and "Case R1" in d.diagnosis
    ]
    assert r1 == []


def test_imported_types_does_not_satisfy_r4_silence() -> None:
    """R4 fires on locally-declared types that no local function
    references. An imported type cannot be locally unreferenced
    because it is not locally declared - R4 only inspects local
    declarations. Pinning that imported_types does not interact
    with R4."""
    src = """
    bismillah HasLocalAndImported {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: declare
        not_scope: nothing_excluded
    }

    type LocalType {
        zahir { name: String }
        batin { id: ID }
    }

    fn use() -> ImportedType {
        return ImportedType
    }
    """
    module = parse(src, file="<inline>")
    diagnostics = check_ring_close(
        module, imported_types=frozenset({"ImportedType"}),
    )
    # LocalType is unreferenced - R4 advisory expected.
    r4 = [d for d in diagnostics if "Case R4" in getattr(d, "message", "")]
    assert len(r4) == 1
    assert "LocalType" in r4[0].message


def test_imported_types_keyword_only_argument() -> None:
    """The new parameter is keyword-only - positional invocation
    raises TypeError. Pins the deliberate keyword-only design."""
    src = """
    bismillah X {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: x
        not_scope: nothing_excluded
    }

    fn x() -> Local {
        return Local
    }

    type Local {
        zahir { name: String }
        batin { id: ID }
    }
    """
    module = parse(src, file="<inline>")
    with pytest.raises(TypeError):
        check_ring_close(module, frozenset({"X"}))  # type: ignore[misc]


def test_existing_single_module_callers_unaffected() -> None:
    """Every existing call to check_ring_close(module) without
    imported_types behaves identically to v0.9.0."""
    src = """
    bismillah Local {
        authority: NAMING_MD
        serves: purpose_hierarchy.balance_for_living_systems
        scope: scan
        not_scope: nothing_excluded
    }

    type Document {
        zahir { name: String }
        batin { id: ID }
    }

    fn parse_doc() -> Document {
        return Document
    }
    """
    module = parse(src, file="<inline>")
    assert check_ring_close(module) == []
