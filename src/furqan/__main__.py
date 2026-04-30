"""
Furqan CLI - structural-honesty checker for .furqan modules.

Usage:
    python -m furqan check <file.furqan>
    python -m furqan check <file.furqan> --strict
    python -m furqan version
    python -m furqan help

Exit codes:
    0   PASS - zero Marad diagnostics
    1   MARAD - at least one violation
    2   PARSE ERROR - file could not be parsed
    3   STRICT MODE failure - any Marad in --strict run

The check subcommand runs nine checkers in order:

  1. bismillah
  2. zahir_batin
  3. mizan
  4. tanzil
  5. ring_close
  6. incomplete
  7. status_coverage   (D11)
  8. return_type_match (D22)
  9. all_paths_return  (D24)

The additive-only checker is NOT run in single-file mode: it
requires a prior-version module for comparison, which a single
.furqan input cannot supply. Cross-version checks live in the
test suite and the additive sidecar protocol.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple


def main() -> int:
    """Entry point for the Furqan CLI."""
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help", "help"):
        _print_usage()
        return 0

    if args[0] == "version":
        import furqan
        print(f"furqan {furqan.__version__}")
        return 0

    if args[0] == "check":
        return _cmd_check(args[1:])

    print(f"Unknown command: {args[0]}", file=sys.stderr)
    _print_usage()
    return 1


# ---------------------------------------------------------------------------
# `check` subcommand
# ---------------------------------------------------------------------------

def _cmd_check(args: List[str]) -> int:
    """Run all checkers on a single .furqan file."""
    if not args:
        print(
            "Usage: furqan check <file.furqan> [--strict]",
            file=sys.stderr,
        )
        return 1

    file_path = Path(args[0])
    strict = "--strict" in args

    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1

    if file_path.suffix != ".furqan":
        print(
            f"Expected a .furqan file, got: {file_path}",
            file=sys.stderr,
        )
        return 1

    source = file_path.read_text(encoding="utf-8")

    # Parse. A tokenize or parse error is a hard failure (exit 2)
    # before any checker runs - downstream checks all assume a
    # well-formed AST.
    from furqan.parser import parse
    from furqan.parser.parser import ParseError
    from furqan.parser.tokenizer import TokenizeError

    try:
        module = parse(source, file=str(file_path))
    except (TokenizeError, ParseError) as e:
        print(f"PARSE ERROR in {file_path}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        return 2

    # Collect diagnostics from every checker.
    from furqan.checker import (
        check_all_paths_return,
        check_bismillah,
        check_incomplete,
        check_mizan,
        check_return_type_match,
        check_ring_close,
        check_status_coverage,
        check_tanzil,
        check_zahir_batin,
    )
    from furqan.errors.marad import Advisory, Marad

    checkers = [
        ("bismillah", check_bismillah),
        ("zahir_batin", check_zahir_batin),
        ("mizan", check_mizan),
        ("tanzil", check_tanzil),
        ("ring_close", check_ring_close),
        ("incomplete", check_incomplete),
        ("status_coverage", check_status_coverage),
        ("return_type_match", check_return_type_match),
        ("all_paths_return", check_all_paths_return),
    ]

    all_diagnostics: List[Tuple[str, object]] = []
    for name, checker in checkers:
        try:
            results = checker(module)
        except Exception as e:  # pragma: no cover - defensive
            print(
                f"  INTERNAL ERROR in {name}: {e}",
                file=sys.stderr,
            )
            continue
        for d in results:
            all_diagnostics.append((name, d))

    marads = [
        (n, d) for n, d in all_diagnostics if isinstance(d, Marad)
    ]
    advisories = [
        (n, d) for n, d in all_diagnostics if isinstance(d, Advisory)
    ]

    if not all_diagnostics:
        print(f"PASS  {file_path}")
        print("  9 checkers ran. Zero diagnostics.")
        return 0

    if marads:
        print(f"MARAD  {file_path}")
        print(f"  {len(marads)} violation(s):")
        for name, m in marads:
            print(f"    [{name}] {m.diagnosis}")
            fix = getattr(m, "minimal_fix", None)
            if fix:
                print(f"      fix: {fix}")
        print()

    if advisories:
        print(f"ADVISORY  {file_path}")
        print(f"  {len(advisories)} note(s):")
        for name, a in advisories:
            msg = getattr(a, "message", None) or getattr(
                a, "diagnosis", str(a)
            )
            print(f"    [{name}] {msg}")
        print()

    if strict and marads:
        print(
            f"STRICT MODE: {len(marads)} Marad violation(s) found.",
            file=sys.stderr,
        )
        return 3

    return 1 if marads else 0


# ---------------------------------------------------------------------------
# Usage text
# ---------------------------------------------------------------------------

def _print_usage() -> None:
    print("Furqan - structural-honesty checker")
    print()
    print("Usage:")
    print("  furqan check <file.furqan>           Run all checkers")
    print("  furqan check <file.furqan> --strict  Fail on first Marad")
    print("  furqan version                       Show version")
    print("  furqan help                          Show this message")
    print()
    print("Exit codes:")
    print("  0  PASS (zero Marad diagnostics)")
    print("  1  MARAD (at least one violation)")
    print("  2  PARSE ERROR (file could not be parsed)")
    print("  3  STRICT MODE failure")


if __name__ == "__main__":
    sys.exit(main())
