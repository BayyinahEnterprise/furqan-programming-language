"""
Tests for the Marad error type and MaradError exception wrapper.

These tests pin the structural contract so future tooling that catches
``MaradError`` and inspects either ``e.args[0]`` or ``e.marad`` gets
identical access to the structured diagnosis. Session 1.1 polish:
``e.args[0]`` is the Marad object itself, not its prose rendering.
"""

from __future__ import annotations

import pytest

from furqan.errors.marad import Marad, MaradError, raise_marad
from furqan.parser.ast_nodes import SourceSpan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_marad() -> Marad:
    return Marad(
        primitive="bismillah",
        diagnosis="example diagnosis",
        location=SourceSpan(file="<test>", line=3, column=5),
        minimal_fix="example fix",
        regression_check="rerun the bismillah check",
    )


# ---------------------------------------------------------------------------
# Marad data class
# ---------------------------------------------------------------------------

def test_marad_is_frozen() -> None:
    m = _sample_marad()
    with pytest.raises(Exception):
        m.diagnosis = "mutated"  # type: ignore[misc]


def test_marad_render_starts_with_primitive_tag() -> None:
    m = _sample_marad()
    assert m.render().startswith("[bismillah] ")


def test_marad_render_contains_all_four_required_fields() -> None:
    """The render format is the human surface; pin its load-bearing
    pieces so a future format change is a structural decision, not an
    accidental drift."""
    rendered = _sample_marad().render()
    assert "example diagnosis" in rendered
    assert "<test>:3:5" in rendered
    assert "example fix" in rendered
    assert "rerun the bismillah check" in rendered


# ---------------------------------------------------------------------------
# MaradError exception wrapper — session-1.1 polish
# ---------------------------------------------------------------------------

def test_marad_error_str_returns_rendered_form() -> None:
    """An uncaught ``MaradError`` printed by Python's default handler
    must remain human-readable. The Session-1.0 contract is
    preserved."""
    m = _sample_marad()
    err = MaradError(m)
    assert str(err) == m.render()


def test_marad_error_args_zero_is_the_structured_marad() -> None:
    """Session 1.1 polish (Perplexity review item #2): a caller who
    catches a generic ``Exception`` and inspects ``e.args[0]`` should
    receive the structured Marad, not its prose form. This pins the
    contract so future tooling can rely on it."""
    m = _sample_marad()
    err = MaradError(m)
    assert err.args[0] is m


def test_marad_error_marad_attribute_matches_args_zero() -> None:
    """Both access paths to the structured object must agree —
    otherwise a Process-2 risk (one path drifts from the other) opens
    up between session 1.1 and any future session that adds fields."""
    m = _sample_marad()
    err = MaradError(m)
    assert err.marad is err.args[0]


def test_raise_marad_constructs_and_raises() -> None:
    with pytest.raises(MaradError) as exc_info:
        raise_marad(
            primitive="bismillah",
            diagnosis="d",
            location=SourceSpan(file="<test>", line=1, column=1),
            minimal_fix="f",
            regression_check="r",
        )
    assert exc_info.value.marad.primitive == "bismillah"
    assert exc_info.value.args[0] is exc_info.value.marad
