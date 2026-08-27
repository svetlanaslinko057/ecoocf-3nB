"""
Wave 11 — Deal360.

The operational "single pane of glass" for one deal. This module is purely
additive: it does not change any legacy /api/deals/* behaviour, it only adds
read-only aggregation endpoints under /api/deals/{deal_id}/360 (and friends).

Design rules (mirroring Wave 9 Lead360):

  * Single network round-trip for the page → /360 bundles everything the UI
    needs: deal doc, customer (light), lead (light), pipeline_stage, health,
    stage_progress, deposits, contracts, payments, shipments, timeline (last 30),
    financials snapshot, documents, counts.
  * Reuses existing Wave 6 modules (pipeline, timeline, health) — does NOT
    duplicate that logic.
  * All fan-out reads are wrapped in best-effort try/except so a single broken
    sub-source can never blow up Deal360 (auth + 404 still propagate).
"""

from .bundle import build_deal360_bundle, list_deal_documents
from .stage_progress import compute_stage_progress

__all__ = [
    "build_deal360_bundle",
    "list_deal_documents",
    "compute_stage_progress",
]
