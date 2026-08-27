"""
Wave 6 — Deal Workspace + Pipeline Simplification + Timeline-first + Legal Policy.

Scoped, additive, non-destructive:
  * `stage_legacy` (original 20-stage truth) is preserved unchanged.
  * `pipeline_stage` (operational UX layer, 10 canonical stages) is derived
    on the fly OR written when stages advance.
  * Health is COMPUTED, never stored.
  * Timeline writes only key events (human-readable messages).
  * Legal policy is a small config doc (5 fields), separate from operational
    LegalWorkflowPage.

See plan.md (Wave 6) for the full architectural rationale.
"""

from .pipeline import (
    PIPELINE_STAGES,
    LEGACY_TO_PIPELINE,
    map_legacy_to_pipeline,
    derive_pipeline_stage,
    pipeline_stage_label,
)
from .timeline import write_event, list_events, TimelineEvent
from .health import compute_health, DealHealth

__all__ = [
    "PIPELINE_STAGES",
    "LEGACY_TO_PIPELINE",
    "map_legacy_to_pipeline",
    "derive_pipeline_stage",
    "pipeline_stage_label",
    "write_event",
    "list_events",
    "TimelineEvent",
    "compute_health",
    "DealHealth",
]
