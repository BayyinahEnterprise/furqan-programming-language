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
    """Run all checkers on a single .furqan file or, in directory
    mode, build a Project across every .furqan file in the directory
    and run cross-module analysis (D9/D20/D23).
    """
    if not args:
        print(
            "Usage: furqan check <file-or-dir> [--strict] [--graph-only]",
            file=sys.stderr,
        )
        return 1

    target = Path(args[0])
    strict = "--strict" in args
    graph_only = "--graph-only" in args

    if not target.exists():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    if target.is_dir():
        return _cmd_check_directory(target, strict=strict, graph_only=graph_only)

    file_path = target

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
# Directory mode (D9/D20/D23)
# ---------------------------------------------------------------------------

def _cmd_check_directory(
    directory: Path,
    *,
    strict: bool,
    graph_only: bool,
) -> int:
    """Build a Project from every .furqan file in ``directory`` and
    run cross-module analysis. Per-module diagnostics use the D23
    cross-module type-resolution path (each module's ring-close R1
    accepts compound type names exported by its direct dependencies).
    """
    from furqan import Project
    from furqan.errors.marad import Advisory, Marad
    from furqan.parser.parser import ParseError
    from furqan.parser.tokenizer import TokenizeError

    project = Project()
    try:
        project.add_directory(directory)
    except (TokenizeError, ParseError) as e:
        print(f"PARSE ERROR in directory {directory}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"PROJECT ERROR in {directory}:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        return 1

    if not project.modules:
        print(f"PASS  {directory} (0 modules)")
        print("  No .furqan files found in directory.")
        return 0

    # Graph-only mode skips per-module checks.
    if graph_only:
        graph_diags = project.check_graph()
        return _report_directory_results(
            directory,
            project,
            results={"__graph__": graph_diags} if graph_diags else {},
            strict=strict,
        )

    results = project.check_all()
    return _report_directory_results(
        directory, project, results=results, strict=strict,
    )


def _report_directory_results(
    directory: Path,
    project,
    *,
    results: dict,
    strict: bool,
) -> int:
    """Render directory-mode output and pick the right exit code."""
    from furqan.errors.marad import Advisory, Marad

    total_marads = 0
    total_advisories = 0

    # Graph-level block (G1, G2, G3) printed first.
    graph_diags = results.get("__graph__", [])
    graph_marads = [d for d in graph_diags if isinstance(d, Marad)]
    graph_advisories = [d for d in graph_diags if isinstance(d, Advisory)]
    total_marads += len(graph_marads)
    total_advisories += len(graph_advisories)

    # Per-module diagnostics (everything except __graph__).
    per_module = {k: v for k, v in results.items() if k != "__graph__"}

    if not graph_marads and not graph_advisories and all(
        not v for v in per_module.values()
    ):
        print(f"PASS  {directory} ({len(project.modules)} modules)")
        graph = project.dependency_graph()
        cycle_count = 0  # we already know there are none if marads==0
        missing_count = 0
        print(
            f"  Graph: {len(project.modules)} modules, "
            f"{cycle_count} cycles, {missing_count} missing targets."
        )
        if per_module:
            checker_count = 9 * len(per_module)
            print(
                f"  Per-module: {checker_count} checkers ran. "
                f"Zero diagnostics."
            )
        return 0

    if graph_marads or graph_advisories:
        print(f"GRAPH  {directory}")
        if graph_marads:
            print(f"  {len(graph_marads)} graph violation(s):")
            for m in graph_marads:
                print(f"    [graph] {m.diagnosis}")
                fix = getattr(m, "minimal_fix", None)
                if fix:
                    print(f"      fix: {fix}")
        if graph_advisories:
            print(f"  {len(graph_advisories)} graph advisory/ies:")
            for a in graph_advisories:
                msg = getattr(a, "message", None) or getattr(
                    a, "diagnosis", str(a)
                )
                print(f"    [graph] {msg}")
        print()

    for module_name in sorted(per_module):
        diags = per_module[module_name]
        if not diags:
            continue
        marads = [d for d in diags if isinstance(d, Marad)]
        advisories = [d for d in diags if isinstance(d, Advisory)]
        total_marads += len(marads)
        total_advisories += len(advisories)
        if marads:
            print(f"MARAD  module {module_name!r}")
            for m in marads:
                print(f"    [{m.primitive}] {m.diagnosis}")
                fix = getattr(m, "minimal_fix", None)
                if fix:
                    print(f"      fix: {fix}")
            print()
        if advisories:
            print(f"ADVISORY  module {module_name!r}")
            for a in advisories:
                msg = getattr(a, "message", None) or getattr(
                    a, "diagnosis", str(a)
                )
                print(f"    [{a.primitive}] {msg}")
            print()

    if strict and total_marads > 0:
        print(
            f"STRICT MODE: {total_marads} Marad violation(s) found.",
            file=sys.stderr,
        )
        return 3

    return 1 if total_marads > 0 else 0


# ---------------------------------------------------------------------------
# Usage text
# ---------------------------------------------------------------------------

def _print_usage() -> None:
    print("Furqan - structural-honesty checker")
    print()
    print("Usage:")
    print("  furqan check <file.furqan>           Run all checkers on a file")
    print("  furqan check <directory>             Project mode: graph + per-module")
    print("  furqan check <target> --strict       Fail on first Marad")
    print("  furqan check <directory> --graph-only  Run only graph checks (G1/G2/G3)")
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
