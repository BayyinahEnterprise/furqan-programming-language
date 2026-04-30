"""
Marad error type — diagnosis-structured errors (Furqan thesis §3.7).

Per the thesis, an error in Furqan is not a thrown exception with a
free-form string. It is a structured *diagnosis* with four required
fields. The discipline derives from Al-Baqarah 2:10: performed
alignment is treated as a disease (marad), not a betrayal (khiyana).
A disease is diagnosed, treated minimally, and verified as recovered.
A betrayal is punished with a rewrite. Ninety-nine percent of bugs
are diseases; the rewrite-on-error reflex causes more regressions
than it prevents.

The four required fields per thesis §3.7 and NAMING.md §5:

* ``diagnosis``       — what specifically went wrong (one sentence,
                        no jargon)
* ``location``        — where in the source the failure was detected
* ``minimal_fix``     — the smallest change that would resolve it
* ``regression_check``— what the user should run to verify the fix
                        did not break adjacent rules

Phase 2 implements ``Marad`` as a frozen dataclass that the
checker layers wrap around their findings. A ``Marad`` is *raised*
through the :class:`MaradError` exception, which carries the marad
record on its ``.marad`` attribute. The two-layer split (data class +
exception wrapper) lets a checker either return a list of marads (for
multi-error reporting in a future phase) or raise the first one (for
fail-fast Phase-2 behavior) without changing the marad's shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from furqan.parser.ast_nodes import SourceSpan


# ---------------------------------------------------------------------------
# Marad
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Marad:
    """A diagnosis-structured Furqan error.

    The four fields are required at the dataclass level — a ``Marad``
    cannot be constructed without all four. This is the language-level
    structural form of the discipline; a checker that wants to skip
    any field has to construct an entirely different value, which
    itself is a Process-2 risk that future-session code review will
    notice.

    The ``primitive`` field names which Furqan primitive the diagnosis
    belongs to (e.g. ``"bismillah"``, ``"zahir_batin"``,
    ``"additive_only"``). Diagnostics aggregate by primitive in the
    Phase-3 reporter; pinning the primitive at construction time
    prevents misclassification later.
    """

    primitive: str
    diagnosis: str
    location: SourceSpan
    minimal_fix: str
    regression_check: str

    def render(self) -> str:
        """Human-readable rendering of the diagnosis.

        The format is stable across versions (additive-only on the
        rendering surface): a leading ``[primitive]`` tag, the
        diagnosis sentence, the location, the minimal fix, and the
        regression check on separate lines. A reader who reads only
        the first line should already know what went wrong; the
        following lines are the recovery instructions.
        """
        return (
            f"[{self.primitive}] {self.diagnosis}\n"
            f"  location:         {self.location.file}:"
            f"{self.location.line}:{self.location.column}\n"
            f"  minimal_fix:      {self.minimal_fix}\n"
            f"  regression_check: {self.regression_check}"
        )


# ---------------------------------------------------------------------------
# MaradError — the exception wrapper
# ---------------------------------------------------------------------------

class MaradError(Exception):
    """Exception form of a :class:`Marad`.

    Use :func:`raise_marad` to raise; the exception's string form is
    the marad's ``render()``, so an uncaught MaradError prints a
    diagnostic the user can act on directly.

    The structured :class:`Marad` is bound to BOTH ``self.marad`` and
    ``self.args[0]``. The double binding is deliberate (session-1.1
    polish, Perplexity review item #2): Python tooling that catches
    a generic ``Exception`` and inspects ``e.args[0]`` should receive
    the structured object, not its prose rendering. ``str(e)`` still
    returns the rendered text via the inherited ``__str__``, so
    uncaught-exception printing remains human-readable.
    """

    def __init__(self, marad: Marad) -> None:
        # NOTE: passing ``marad`` (not ``marad.render()``) to super.
        # The inherited ``__str__`` is overridden below so the
        # human-readable form survives unchanged.
        super().__init__(marad)
        self.marad = marad

    def __str__(self) -> str:
        # Preserve the v0.1.0 Session-1 prose-rendering on str(); the
        # structured object lives on ``self.args[0]`` and ``self.marad``.
        return self.marad.render()


def raise_marad(
    *,
    primitive: str,
    diagnosis: str,
    location: SourceSpan,
    minimal_fix: str,
    regression_check: str,
) -> "Marad":
    """Construct and raise a :class:`MaradError`.

    Returns ``Marad`` only as a typing hint; the function never
    returns normally. Inline it where a fail-fast checker wants to
    abort with a structured diagnosis.
    """
    marad = Marad(
        primitive=primitive,
        diagnosis=diagnosis,
        location=location,
        minimal_fix=minimal_fix,
        regression_check=regression_check,
    )
    raise MaradError(marad)


__all__: Final[list[str]] = [
    "Marad",
    "MaradError",
    "raise_marad",
    "Advisory",
]


# ---------------------------------------------------------------------------
# Advisory — informational diagnostic, distinct from Marad
# ---------------------------------------------------------------------------
#
# Session 1.1 (D1) registered the design question: should the Marad
# class grow a tier field, or should we model an informational
# diagnostic as a separate type? Phase 2.5 (Session 1.4) lands the
# decision: a separate ``Advisory`` type alongside ``Marad``.
#
# Rationale:
#
#   * Clean separation. A ``Marad`` is an error — the program does not
#     type-check. An ``Advisory`` is a hint — the program is structurally
#     accepted, but the developer might want to reconsider. Conflating
#     the two on a single ``tier`` field would make every consumer
#     branch on the field; separate types give us the discrimination
#     for free at the type level.
#
#   * Additive-only safety. ``Marad``'s shape is unchanged across
#     versions; existing diagnostics retain their contract. The
#     advisory surface is purely additive — Phase-2.4 callers that
#     read marads only continue to work.
#
#   * Reflexivity. The framework's own thesis says: do not mix levels
#     of evidence (§7 reflexivity). A type-level error and a
#     heuristic suggestion are different evidence; separate types
#     make the difference structural.

@dataclass(frozen=True, slots=True)
class Advisory:
    """A non-fatal informational diagnostic.

    Distinct from :class:`Marad`: an Advisory does NOT cause type-
    check failure. It is emitted alongside marads (or in their
    absence) to flag structural patterns that *might* indicate
    developer intent the language should know about.

    The canonical Phase-2.5 use is the additive-only checker's
    "possible undeclared rename" advisory: if the surface change
    looks like a rename (one symbol removed, one symbol added with
    matching type signature) and the developer did not declare it
    in a major_version_bump catalog, the checker emits an Advisory
    suggesting the rename be declared explicitly. The corresponding
    Case 1 marad still fires on the removed name; the Advisory
    does not suppress it, only adds context.

    Fields mirror :class:`Marad` for diagnostic uniformity, but the
    semantic load is informational.
    """

    primitive: str
    message: str
    location: SourceSpan
    suggestion: str

    def render(self) -> str:
        """Human-readable rendering. The leading tag is
        ``[advisory:<primitive>]`` so the reader can distinguish
        advisories from marads at a glance."""
        return (
            f"[advisory:{self.primitive}] {self.message}\n"
            f"  location:   {self.location.file}:"
            f"{self.location.line}:{self.location.column}\n"
            f"  suggestion: {self.suggestion}"
        )
