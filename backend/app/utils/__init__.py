"""Pure helpers — Phase 5.2 utility extraction target.

As of Phase 5.2 / C-2, this package owns:

  * `serialize_doc`  (C-1) — Mongo BSON → JSON-safe shape
  * `_round_money`   (C-2) — permissive 2-decimal money rounder

Future commits will land:

  * Domain-coupled helpers (eta smoothing, GPS movement validation)
    will go into `app/utils/shipments.py` in Phase 5.5 together
    with their owning domain (per `PHASE5_1_OWNERSHIP_MAP.md`).
  * `_STATIC_DIR` will move to `app/core/paths.py` in Phase 5.8
    after lifespan-driven static-mount migration.
"""

from app.utils.serialization import serialize_doc
from app.utils.money import _round_money

__all__ = ["serialize_doc", "_round_money"]
