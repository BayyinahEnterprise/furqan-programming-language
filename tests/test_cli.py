"""
CLI entry point tests (Phase 3.1 / v0.9.0).

The tests are subprocess-based: each one invokes
``python -m furqan ...`` and asserts on the exit code and the
captured stdout/stderr. This pins the externally-visible contract
of the CLI - what a judge or end user actually sees when they
run the tool from the terminal.

Exit-code contract (see __main__.py docstring):

* 0   PASS - zero Marad diagnostics
* 1   MARAD - at least one violation
* 2   PARSE ERROR - file could not be parsed
* 3   STRICT MODE failure
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


FURQAN_CMD = [sys.executable, "-m", "furqan"]
EXAMPLES = Path(__file__).parent.parent / "examples"
PARSE_INVALID_FIXTURES = (
    Path(__file__).parent / "fixtures" / "parse_invalid"
)


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke the Furqan CLI with the given args."""
    return subprocess.run(
        [*FURQAN_CMD, *args],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=cwd or Path(__file__).parent.parent,
    )


# ---------------------------------------------------------------------------
# version + help + unknown command
# ---------------------------------------------------------------------------

def test_version_prints_version_string() -> None:
    result = _run("version")
    assert result.returncode == 0
    assert result.stdout.startswith("furqan ")
    # The version string should match a SemVer-shaped pattern.
    parts = result.stdout.strip().split()
    assert parts[0] == "furqan"
    assert parts[1].count(".") >= 2


def test_help_prints_usage() -> None:
    result = _run("help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "check" in result.stdout
    assert "version" in result.stdout


def test_no_args_prints_usage() -> None:
    result = _run()
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_dash_h_prints_usage() -> None:
    result = _run("-h")
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_double_dash_help_prints_usage() -> None:
    result = _run("--help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_unknown_command_exits_with_error() -> None:
    result = _run("badcommand")
    assert result.returncode == 1
    assert "Unknown command" in result.stderr


# ---------------------------------------------------------------------------
# check subcommand - happy path
# ---------------------------------------------------------------------------

def test_check_clean_module_passes() -> None:
    result = _run("check", str(EXAMPLES / "clean_module.furqan"))
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "9 checkers ran" in result.stdout
    assert "Zero diagnostics" in result.stdout


def test_check_clean_module_strict_passes() -> None:
    result = _run(
        "check", str(EXAMPLES / "clean_module.furqan"), "--strict"
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout


# ---------------------------------------------------------------------------
# check subcommand - Marad detection
# ---------------------------------------------------------------------------

def test_check_status_collapse_fires_marad() -> None:
    result = _run(
        "check", str(EXAMPLES / "status_collapse.furqan")
    )
    assert result.returncode == 1
    assert "MARAD" in result.stdout
    assert "[status_coverage]" in result.stdout
    assert "fix:" in result.stdout


def test_check_missing_return_path_fires_marad() -> None:
    result = _run(
        "check", str(EXAMPLES / "missing_return_path.furqan")
    )
    assert result.returncode == 1
    assert "MARAD" in result.stdout
    assert "[all_paths_return]" in result.stdout


# ---------------------------------------------------------------------------
# Strict mode - Marad becomes exit 3
# ---------------------------------------------------------------------------

def test_strict_mode_exit_3_on_marad() -> None:
    result = _run(
        "check", str(EXAMPLES / "status_collapse.furqan"),
        "--strict",
    )
    assert result.returncode == 3
    assert "STRICT MODE" in result.stderr


def test_strict_mode_passes_when_clean() -> None:
    """A clean file under --strict still exits 0 (no Marads)."""
    result = _run(
        "check", str(EXAMPLES / "clean_module.furqan"),
        "--strict",
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_check_nonexistent_file_exits_1() -> None:
    result = _run("check", "definitely-does-not-exist.furqan")
    assert result.returncode == 1
    assert "File not found" in result.stderr


def test_check_wrong_extension_exits_1() -> None:
    result = _run("check", "README.md")
    assert result.returncode == 1
    assert "Expected a .furqan file" in result.stderr


def test_check_with_no_args_exits_1() -> None:
    result = _run("check")
    assert result.returncode == 1
    assert "Usage" in result.stderr


def test_check_parse_error_exits_2() -> None:
    """A .furqan file that fails to parse exits with code 2."""
    parse_invalid = list(PARSE_INVALID_FIXTURES.glob("*.furqan"))
    if not parse_invalid:
        pytest.skip("no parse_invalid fixtures available")
    result = _run("check", str(parse_invalid[0]))
    assert result.returncode == 2
    assert "PARSE ERROR" in result.stderr


# ---------------------------------------------------------------------------
# Output formatting - checker name is bracketed
# ---------------------------------------------------------------------------

def test_marad_output_uses_bracketed_checker_name() -> None:
    result = _run(
        "check", str(EXAMPLES / "status_collapse.furqan")
    )
    # The diagnostic prefix is `    [<checker_name>] ...`
    assert "[status_coverage]" in result.stdout


def test_marad_output_includes_fix_line() -> None:
    result = _run(
        "check", str(EXAMPLES / "missing_return_path.furqan")
    )
    assert "fix:" in result.stdout
