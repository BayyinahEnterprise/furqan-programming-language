"""Furqan — a programming-language type-checker enforcing structural
honesty at compile time.

This top-level package is intentionally thin: the public surface
is exported from sub-packages (``furqan.parser``, ``furqan.checker``,
``furqan.errors``). Every name in those sub-packages' ``__all__`` is
covered by the additive-only invariant declared in ``docs/NAMING.md``
§6 — a Phase-2.x release that removes or renames any prior export
is forbidden.

The package version is exposed at module scope as
``furqan.__version__`` for tooling compatibility (e.g.,
``setup.cfg``, ``pyproject.toml``-aware introspection, IDE
tooltips). The value is read from the installed package metadata
(via :func:`importlib.metadata.version`); when the package is not
installed (e.g., running tests from a fresh checkout without
``pip install -e .``), the value falls back to the literal pinned
in this file. The two paths are kept in sync by the v0.5.0 polish
patch (P4 from Perplexity's pre-publish audit).
"""

from __future__ import annotations

# Pinned literal, mirrors the ``version = "..."`` line in
# ``pyproject.toml``. Kept here for the case where the package is
# imported from a source tree without an installed distribution.
# Version-bump procedure: change pyproject.toml AND this literal in
# the same commit; the post-bump audit confirms the two agree.
__version__: str = "0.10.0"

try:
    # When the package is installed (the normal case for end users),
    # prefer the metadata-driven value so a future release that
    # forgets to update the literal still reports correctly.
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    try:
        __version__ = _pkg_version("furqan")
    except PackageNotFoundError:
        # Source-tree-only checkout; keep the pinned literal above.
        pass
    finally:
        # Names imported strictly for the version-resolution logic
        # are not part of the public surface and are pruned here so
        # ``dir(furqan)`` stays minimal.
        del PackageNotFoundError
        del _pkg_version
except ImportError:  # pragma: no cover - importlib.metadata is stdlib >= 3.8
    pass


# Prune the ``from __future__ import annotations`` symbol that
# would otherwise leak into ``dir(furqan)`` as a public-looking name.
del annotations


from furqan.project import Project


__all__ = ["__version__", "Project"]
