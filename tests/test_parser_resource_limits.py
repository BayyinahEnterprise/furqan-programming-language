"""
Parser resource-limit tests (v0.11.0 / Q9).

Closes the discipline violation flagged in QUESTIONS.md Q9: deeply
nested input previously produced a Python ``RecursionError`` traceback
to stderr with exit code ``1`` (MARAD per the README's exit-code
contract). v0.11.0 adds a static depth-guard at
``MAX_NESTING_DEPTH = 200`` plus a top-level ``try/except RecursionError``
in :func:`parse` that converts any leak past the guard into a structured
:class:`ParseError`. Both paths are pinned here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest

from furqan.parser import parse
from furqan.parser.parser import (
    MAX_NESTING_DEPTH,
    ParseError,
    _Parser,
)


FURQAN_CMD = [sys.executable, "-m", "furqan"]
DEEP_NEST_FIXTURE = (
    Path(__file__).parent / "fixtures" / "parse_errors" / "deep_nest.furqan"
)


def _module_with_nested_ifs(depth: int) -> str:
    """Build a syntactically valid module whose body has ``depth``
    levels of ``if not stop { ... }`` nesting around a single
    ``return Integrity``."""
    head = dedent("""\
        bismillah DeepNest {
            authority: NAMING_MD
            serves: purpose_hierarchy.balance_for_living_systems
            scope: torture
            not_scope: nothing_excluded
        }

        fn deep() -> Integrity {
        """)
    open_ifs = "    if not stop {\n" * depth
    body = "        return Integrity\n"
    close_ifs = "    }\n" * depth
    tail = "}\n"
    return head + open_ifs + body + close_ifs + tail


# ---------------------------------------------------------------------------
# Static depth-guard
# ---------------------------------------------------------------------------

def test_nesting_at_limit_parses_cleanly() -> None:
    """Depth strictly less than MAX_NESTING_DEPTH parses to a valid
    Module. Pin the boundary at MAX_NESTING_DEPTH - 1 so a future
    bump of the limit does not silently mask a regression."""
    src = _module_with_nested_ifs(MAX_NESTING_DEPTH - 1)
    module = parse(src, file="<inline>")
    assert module.bismillah.name == "DeepNest"
    assert len(module.functions) == 1


def test_nesting_above_limit_raises_parse_error() -> None:
    """Depth strictly above MAX_NESTING_DEPTH raises ParseError, NOT
    RecursionError. This is the v0.11.0 discipline-honouring path."""
    src = _module_with_nested_ifs(MAX_NESTING_DEPTH + 1)
    with pytest.raises(ParseError) as exc:
        parse(src, file="<inline>")
    # Diagnostic must name the limit so a developer reading the
    # message understands the contract.
    assert str(MAX_NESTING_DEPTH) in exc.value.message


def test_nesting_diagnostic_carries_line_number() -> None:
    """The raised ParseError's span.line is non-zero and points at
    a position inside the offending nested-if region (i.e., past the
    bismillah header)."""
    src = _module_with_nested_ifs(MAX_NESTING_DEPTH + 5)
    with pytest.raises(ParseError) as exc:
        parse(src, file="<inline>")
    span = exc.value.span
    assert span.line > 0
    # The bismillah block is the first 6 lines; nesting starts at
    # line 9 onward. The guard should fire well past the header.
    assert span.line >= 8
    assert span.file == "<inline>"


def test_recursion_error_at_parse_top_level_converted() -> None:
    """Belt-and-suspenders: even if the static guard misses a code
    path, the top-level try/except in parse() converts a stray
    RecursionError into a structured ParseError. Patches a parser
    internal to raise RecursionError and verifies the conversion."""
    src = _module_with_nested_ifs(1)  # short, valid input
    with patch.object(
        _Parser, "parse_module",
        side_effect=RecursionError("simulated stack exhaustion"),
    ):
        with pytest.raises(ParseError) as exc:
            parse(src, file="<inline>")
    assert "stack budget" in exc.value.message.lower()
    assert exc.value.span.file == "<inline>"


def test_max_nesting_depth_is_advertised_constant() -> None:
    """Pin that MAX_NESTING_DEPTH is importable from the parser
    module and is a positive integer. Surfacing the limit as an
    importable constant is part of Q10's closure (the contract is
    not silent)."""
    assert isinstance(MAX_NESTING_DEPTH, int)
    assert MAX_NESTING_DEPTH > 0


# ---------------------------------------------------------------------------
# CLI exit-code contract (Q9)
# ---------------------------------------------------------------------------

def test_cli_deeply_nested_input_exit_code_is_2() -> None:
    """The shipped deep_nest.furqan fixture (depth 500) must exit
    with code 2 (PARSE ERROR) and emit a structured "PARSE ERROR"
    line to stderr without a Python traceback."""
    assert DEEP_NEST_FIXTURE.is_file(), (
        f"deep-nest fixture missing at {DEEP_NEST_FIXTURE}"
    )
    result = subprocess.run(
        [*FURQAN_CMD, "check", str(DEEP_NEST_FIXTURE)],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode == 2, (
        f"expected exit 2 (PARSE ERROR), got {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "PARSE ERROR" in result.stderr
    assert "Traceback" not in result.stderr
    # Python traceback would render the type as a bare ``RecursionError:``
    # at column 0; the diagnostic prose may legitimately mention the
    # word in explanatory text. Pin the traceback-shape only.
    assert "RecursionError:" not in result.stderr
