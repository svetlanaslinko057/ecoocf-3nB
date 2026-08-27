"""
Pure-utility serialization helpers (Phase 5.2 / Commit 1).
========================================================

This module owns the canonical `serialize_doc` helper that
converts a MongoDB document (or any dict-like object) into a
JSON-serializable shape: ObjectId → str, datetime → isoformat,
nested dicts recursed, list elements processed dict-by-dict.

Historical home:
    `server.py` lines 714-732 (since project inception).
Phase 5.2 / C-1 extraction (2026-05-18):
    function body moved verbatim to this module; `server.py`
    keeps a compatibility re-export so `from server import
    serialize_doc` still resolves to this exact function during
    the slice-by-slice router migration.

Guarantees (per Phase 5.2 / C-1 mandate):

  * Behaviour 1:1 with the legacy implementation.
  * Output shape unchanged for every existing caller.
  * ObjectId formatting unchanged (`str(_id)`).
  * datetime formatting unchanged (`value.isoformat()`).
  * List asymmetry preserved: lists recurse INTO dict items but
    do NOT unwrap ObjectId / datetime values directly contained
    in a list (legacy quirk — would break 58 call sites if changed).
  * `serialize_doc(None)` returns `None` (sentinel for absent docs).
  * No dependency on `server.py`, no Mongo handle, no global state.

Do NOT add new behaviour here without an explicit invariant
update. This file is part of the bridge-removal foundation —
breaking its contract breaks 58 read-paths simultaneously.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId


def serialize_doc(doc: Any) -> Any:
    """Convert MongoDB document to JSON-serializable dict.

    1:1 reimplementation of `server.serialize_doc` (legacy line 714).
    See module docstring for the preserved-behaviour contract.

    Parameters
    ----------
    doc : dict | None
        A Mongo document (motor coroutine return shape) or None.

    Returns
    -------
    dict | None
        A new dict with ObjectId stringified, datetime isoformat'd,
        nested dicts recursed, and lists processed dict-by-dict.
        Returns None if input is None.
    """
    if doc is None:
        return None

    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = serialize_doc(value)
        elif isinstance(value, list):
            result[key] = [
                serialize_doc(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


__all__ = ["serialize_doc"]
