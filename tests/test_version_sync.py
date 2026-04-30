"""
Version-sync assertion (Phase 2.9 polish patch).

Catches the ``furqan.__version__`` drift that occurred across Phases
2.7 to 2.9 where the pinned literal in ``src/furqan/__init__.py``
silently fell behind ``pyproject.toml``. The test suite did not
catch this earlier because no test asserted equality between the
two sources of truth.

This single test fails loudly on any future version bump that
touches one file but not the other. Zero dependencies (regex over
the toml file rather than `tomllib`/`tomli`); works on every
supported Python version (3.10+).
"""

from __future__ import annotations

import re
from pathlib import Path

import furqan


PYPROJECT_PATH = Path(__file__).parent.parent / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    """``furqan.__version__`` must equal the ``[project] version``
    field in ``pyproject.toml``. Update both files on every bump.

    A path-resolution sanity guard is folded into the same test so
    a future repo-layout change that moves ``pyproject.toml`` cannot
    silently make this test trivially pass.
    """
    assert PYPROJECT_PATH.is_file(), (
        f"pyproject.toml not found at expected location "
        f"{PYPROJECT_PATH}. The test_version_sync module assumes "
        f"the standard repo layout (pyproject.toml at the repo "
        f"root, tests/ as a sibling)."
    )
    text = PYPROJECT_PATH.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, (
        f"Could not find a version line in {PYPROJECT_PATH}. "
        f"This test expected `version = \"<x.y.z>\"` somewhere "
        f"in the file."
    )
    pyproject_version = match.group(1)
    assert furqan.__version__ == pyproject_version, (
        f"furqan.__version__ is {furqan.__version__!r} but "
        f"pyproject.toml says {pyproject_version!r}. Update both "
        f"files on every version bump (see CHANGELOG.md and the "
        f"Phase 2.9 closing register for the historical drift "
        f"this test was added to prevent)."
    )
