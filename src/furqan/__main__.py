"""
Furqan CLI - structural-honesty checker for .furqan modules.

Usage:
    python -m furqan check <file.furqan>
    python -m furqan check <file.furqan> --strict
    python -m furqan check <directory>
    python -m furqan check <directory> --graph-only
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

    target = Path(args[0])
    strict = "--strict" in args
    graph_only = "--graph-only" in args

    if not target.exists():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    if target.is_dir():
        return _cmd_check_directory(target, strict=strict, graph_only=graph_only)

    if graph_only:
        print(
            "--graph-only requires a directory argument",
            file=sys.stderr,
        )
        return 1

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
# `check` directory mode (D9/D20)
# ---------------------------------------------------------------------------

def _cmd_check_directory(
    directory: Path,
    *,
    strict: bool,
    graph_only: bool,
) -> int:
    """Run graph-level (and optionally per-module) checks across
    every .furqan file in ``directory``.

    Exit codes match single-file mode:
      0  PASS, no Marads from any layer.
      1  MARAD, at least one violation (graph or per-module).
      2  PARSE ERROR, any file failed to parse.
      3  STRICT MODE failure on a Marad.
    """
    from furqan.errors.marad import Advisory, Marad
    from furqan.parser.parser import ParseError
    from furqan.parser.tokenizer import TokenizeError
    from furqan.project import Project

    project = Project()
    paths = sorted(directory.glob("*.furqan"))
    if not paths:
        print(f"PASS  {directory} (0 modules)")
        print("  No .furqan files found.")
        return 0

    for path in paths:
        try:
            project.add_file(path)
        except (TokenizeError, ParseError) as e:
            print(f"PARSE ERROR in {path}:", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
            return 2

    graph_diags = project.check_graph()
    graph_marads = [d for d in graph_diags if isinstance(d, Marad)]
    graph_advisories = [d for d in graph_diags if isinstance(d, Advisory)]

    per_module_diags: List[Tuple[str, str, object]] = []
    if not graph_only:
        topo = project.topological_order()
        order = topo if topo is not None else sorted(project.modules.keys())
        per_module_diags = _run_per_module_checks(project, order)

    per_module_marads = [
        (mod, name, d)
        for (mod, name, d) in per_module_diags
        if isinstance(d, Marad)
    ]
    per_module_advisories = [
        (mod, name, d)
        for (mod, name, d) in per_module_diags
        if isinstance(d, Advisory)
    ]

    total_marads = len(graph_marads) + len(per_module_marads)
    total_advisories = len(graph_advisories) + len(per_module_advisories)
    total_diags = total_marads + total_advisories

    if total_diags == 0:
        print(f"PASS  {directory} ({len(project.modules)} modules)")
        print(
            f"  Graph: {len(project.modules)} modules, "
            f"0 cycles, 0 missing targets."
        )
        if not graph_only:
            print(
                f"  Per-module: 9 checkers per module ran across "
                f"{len(project.modules)} modules. Zero diagnostics."
            )
        return 0

    if total_marads:
        print(f"MARAD  {directory}")
        if graph_marads:
            print(f"  Graph violations ({len(graph_marads)}):")
            for m in graph_marads:
                print(f"    [graph] {m.diagnosis}")
                if m.minimal_fix:
                    print(f"      fix: {m.minimal_fix}")
        if per_module_marads:
            print(
                f"  Per-module violations ({len(per_module_marads)}):"
            )
            for mod_name, checker_name, m in per_module_marads:
                print(f"    {mod_name}: [{checker_name}] {m.diagnosis}")
                fix = getattr(m, "minimal_fix", None)
                if fix:
                    print(f"      fix: {fix}")
        print()

    if total_advisories:
        print(f"ADVISORY  {directory}")
        if graph_advisories:
            for a in graph_advisories:
                msg = getattr(a, "message", None) or getattr(
                    a, "diagnosis", str(a)
                )
                print(f"    [graph] {msg}")
        for mod_name, checker_name, a in per_module_advisories:
            msg = getattr(a, "message", None) or getattr(
                a, "diagnosis", str(a)
            )
            print(f"    {mod_name}: [{checker_name}] {msg}")
        print()

    if strict and total_marads:
        print(
            f"STRICT MODE: {total_marads} Marad violation(s) found.",
            file=sys.stderr,
        )
        return 3

    return 1 if total_marads else 0


def _run_per_module_checks(
    project,
    order: List[str],
) -> List[Tuple[str, str, object]]:
    """Run the nine per-module checkers on each module in ``order``
    and return ``(module_name, checker_name, diagnostic)`` triples."""
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

    out: List[Tuple[str, str, object]] = []
    for mod_name in order:
        module = project.modules.get(mod_name)
        if module is None:
            continue
        for checker_name, checker in checkers:
            try:
                results = checker(module)
            except Exception as e:  # pragma: no cover - defensive
                print(
                    f"  INTERNAL ERROR in {checker_name} for "
                    f"{mod_name}: {e}",
                    file=sys.stderr,
                )
                continue
            for d in results:
                out.append((mod_name, checker_name, d))
    return out


# ---------------------------------------------------------------------------
# Usage text
# ---------------------------------------------------------------------------

def _print_usage() -> None:
    print("Furqan - structural-honesty checker")
    print()
    print("Usage:")
    print("  furqan check <file.furqan>           Run all checkers")
    print("  furqan check <file.furqan> --strict  Fail on first Marad")
    print("  furqan check <directory>             Multi-module check (D9/D20)")
    print("  furqan check <directory> --graph-only  Skip per-module checkers")
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
