"""Phase 4 / C-5 — make `tests/` a regular Python package so the
invariant helpers can be imported from the shell smoke script as
``from tests._invariants_helpers import ...``.

pytest discovery already worked without this file (uses rootdir
+ ini-based collection), so adding it is non-disruptive.
"""
