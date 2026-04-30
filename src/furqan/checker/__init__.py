"""Furqan checker layer — public entry points for each primitive's checker."""

from .bismillah import (
    PRIMITIVE_NAME as BISMILLAH_PRIMITIVE_NAME,
    check_module as check_bismillah,
    check_module_strict as check_bismillah_strict,
)
from .zahir_batin import (
    PRIMITIVE_NAME as ZAHIR_BATIN_PRIMITIVE_NAME,
    VERIFY_FUNCTION_NAME,
    check_module as check_zahir_batin,
    check_module_strict as check_zahir_batin_strict,
)
from .additive import (
    PRIMITIVE_NAME as ADDITIVE_ONLY_PRIMITIVE_NAME,
    Result as AdditiveOnlyResult,
    check_additive,
    check_module as check_additive_module,
    check_module_strict as check_additive_module_strict,
)
from .incomplete import (
    PRIMITIVE_NAME as SCAN_INCOMPLETE_PRIMITIVE_NAME,
    REQUIRED_INCOMPLETE_FIELDS,
    INTEGRITY_TYPE_NAME,
    INCOMPLETE_TYPE_NAME,
    check_incomplete,
    check_incomplete_strict,
)
from .mizan import (
    PRIMITIVE_NAME as MIZAN_PRIMITIVE_NAME,
    REQUIRED_MIZAN_FIELDS,
    check_mizan,
    check_mizan_strict,
)
from .tanzil import (
    PRIMITIVE_NAME as TANZIL_PRIMITIVE_NAME,
    check_tanzil,
    check_tanzil_strict,
)
from .ring_close import (
    BUILTIN_TYPE_NAMES as RING_CLOSE_BUILTIN_TYPE_NAMES,
    PRIMITIVE_NAME as RING_CLOSE_PRIMITIVE_NAME,
    check_ring_close,
    check_ring_close_strict,
)
from .status_coverage import (
    PRIMITIVE_NAME as STATUS_COVERAGE_PRIMITIVE_NAME,
    check_status_coverage,
    check_status_coverage_strict,
)
from .return_type_match import (
    PRIMITIVE_NAME as RETURN_TYPE_MATCH_PRIMITIVE_NAME,
    check_return_type_match,
    check_return_type_match_strict,
)
from .all_paths_return import (
    PRIMITIVE_NAME as ALL_PATHS_RETURN_PRIMITIVE_NAME,
    check_all_paths_return,
    check_all_paths_return_strict,
)

__all__ = [
    # Bismillah scope (Phase 2.3)
    "BISMILLAH_PRIMITIVE_NAME",
    "check_bismillah",
    "check_bismillah_strict",
    # Zahir/batin (Phase 2.4)
    "ZAHIR_BATIN_PRIMITIVE_NAME",
    "VERIFY_FUNCTION_NAME",
    "check_zahir_batin",
    "check_zahir_batin_strict",
    # Additive-only module (Phase 2.5)
    "ADDITIVE_ONLY_PRIMITIVE_NAME",
    "AdditiveOnlyResult",
    "check_additive",
    "check_additive_module",
    "check_additive_module_strict",
    # Scan-incomplete (Phase 2.6)
    "SCAN_INCOMPLETE_PRIMITIVE_NAME",
    "REQUIRED_INCOMPLETE_FIELDS",
    "INTEGRITY_TYPE_NAME",
    "INCOMPLETE_TYPE_NAME",
    "check_incomplete",
    "check_incomplete_strict",
    # Mizan well-formedness (Phase 2.7)
    "MIZAN_PRIMITIVE_NAME",
    "REQUIRED_MIZAN_FIELDS",
    "check_mizan",
    "check_mizan_strict",
    # Tanzil build-ordering (Phase 2.8)
    "TANZIL_PRIMITIVE_NAME",
    "check_tanzil",
    "check_tanzil_strict",
    # Ring-close structural completion (Phase 2.9)
    "RING_CLOSE_PRIMITIVE_NAME",
    "RING_CLOSE_BUILTIN_TYPE_NAMES",
    "check_ring_close",
    "check_ring_close_strict",
    # Status-coverage / consumer-side exhaustiveness (D11, v0.8.0)
    "STATUS_COVERAGE_PRIMITIVE_NAME",
    "check_status_coverage",
    "check_status_coverage_strict",
    # Return-expression type matching (D22, v0.8.1)
    "RETURN_TYPE_MATCH_PRIMITIVE_NAME",
    "check_return_type_match",
    "check_return_type_match_strict",
    # All-paths-return analysis (D24, v0.8.2)
    "ALL_PATHS_RETURN_PRIMITIVE_NAME",
    "check_all_paths_return",
    "check_all_paths_return_strict",
]
