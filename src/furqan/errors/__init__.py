"""Furqan error surface — public Marad type and exception wrapper.

Phase 2.5 (Session 1.4) adds the :class:`Advisory` type — informational
diagnostics distinct from :class:`Marad` errors. See marad.py for the
design rationale (Session 1.1 D1 lands here).
"""

from .marad import Advisory, Marad, MaradError, raise_marad

__all__ = ["Advisory", "Marad", "MaradError", "raise_marad"]
