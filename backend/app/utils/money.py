"""
Pure money / currency helpers (Phase 5.2 / Commit 2).
=====================================================

This module owns `_round_money`, the canonical helper that rounds
a numeric value to 2 decimal places with permissive coercion.

Historical home:
    `server.py` line 14440 (since project inception).
Phase 5.2 / C-2 extraction (2026-05-18):
    function body moved verbatim to this module; `server.py`
    keeps a compatibility re-export so any direct call site still
    resolves to this exact function.

Guarantees (per Phase 5.2 / C-2 mandate):

  * Behaviour 1:1 with the legacy implementation.
  * Floats are rounded to 2 decimals via `round(float(x), 2)`.
  * Any conversion error (string that does not parse, None, etc.)
    returns `0.0` — never raises.  This permissive contract is
    relied on by callers that pass user-supplied JSON values
    without prior validation.
  * Return type is ALWAYS `float`.  Even on failure path.
  * No dependency on `server.py`, no Mongo handle, no global state.

Do NOT add new behaviour here without an explicit invariant
update.  This file is part of the bridge-removal foundation —
breaking its contract may produce silent off-by-one cents in
financial breakdowns / invoice totals / deposit reconciliation.
"""
from __future__ import annotations

from typing import Any


def _round_money(x: Any) -> float:
    """Round a numeric value to 2 decimal places with permissive coercion.

    1:1 reimplementation of `server._round_money` (legacy line 14440).
    See module docstring for the preserved-behaviour contract.

    Parameters
    ----------
    x : Any
        A value that *should* be coercible to ``float``. In practice
        callers pass: ``int``, ``float``, numeric ``str``, ``None``,
        or occasionally a Decimal-shaped string from Mongo.

    Returns
    -------
    float
        Rounded to 2 decimal places. ``0.0`` on any conversion error
        (legacy permissive contract — DO NOT change without an
        invariant update; ~4 financial call sites in server.py and
        ``legal_workflow.py`` rely on this never-raises semantic).
    """
    try:
        return round(float(x), 2)
    except Exception:
        return 0.0


__all__ = ["_round_money"]
