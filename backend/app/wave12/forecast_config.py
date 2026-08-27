"""
BIBI Cars — Wave 12C — Forecasting 360 configuration

*Deterministic* probability tables for the stage-conversion model. Default
values live here so that we can later promote them to an admin surface
(`/admin/settings/forecast`) without touching every aggregator.

The contract is intentionally tiny:

    from app.wave12.forecast_config import stage_probability, HORIZONS
    p = stage_probability("awaiting_deposit")    # → 0.35

Unknown stages fall back to ``DEFAULT_UNKNOWN`` so that brand-new stages
added by the team don't silently break the forecast.
"""
from __future__ import annotations
from typing import Dict, Tuple

# Probabilities are read as the chance an *open* deal at this stage will
# eventually generate revenue. They are *not* the chance of moving to the
# next stage. (A deal at "contract" has a 75% chance of closing as paid
# revenue.)
STAGE_PROBABILITY: Dict[str, float] = {
    "new":                  0.10,
    "lead":                 0.10,
    "qualification":        0.15,
    "contacted":            0.15,
    "negotiation":          0.25,
    "awaiting_deposit":     0.35,
    "deposit":              0.55,
    "deposit_paid":         0.60,
    "contract":             0.75,
    "contract_signed":      0.80,
    "payment":              0.85,
    "payment_received":     0.88,
    "in_transit":           0.85,
    "shipping":             0.85,
    "customs":              0.90,
    "ready_for_delivery":   0.95,
    "delivery":             0.95,
    "delivered":            1.00,
    # terminal/negative — explicit zeros so the forecaster never counts them
    "cancelled":            0.00,
    "refunded":             0.00,
    "closed_won":           1.00,
    "closed_lost":          0.00,
    "lost":                 0.00,
}

DEFAULT_UNKNOWN: float = 0.30  # safe middle if we see an unknown stage

# Forecast horizons (in days). The Overview tab uses 30/60/90; Cash Flow
# uses weeks; Pipeline + Capacity use months.
HORIZONS: Tuple[int, ...] = (30, 60, 90)
MAX_HORIZON: int = 90

# Cash-flow projection assumes a payment lands by ETA. If a deal has no
# ETA, we fall back to created_at + DEFAULT_PAYMENT_LAG_DAYS so the
# revenue is at least visible somewhere on the timeline.
DEFAULT_PAYMENT_LAG_DAYS: int = 30

# Capacity model — a single manager can comfortably run this many open
# deals at once. The capacity tab compares load_today vs this number to
# generate the utilisation %.
MANAGER_TARGET_OPEN_DEALS: int = 8

# Carrier capacity — same idea, for the Delivery side.
CARRIER_TARGET_OPEN_LOADS: int = 12

# Risk weights — used by /api/forecast/risk. Higher = more revenue at risk.
RISK_WEIGHT_BY_SEGMENT: Dict[str, float] = {
    "healthy":  0.00,
    "on_track": 0.00,
    "warning":  0.25,
    "delay_risk": 0.30,
    "at_risk":  0.60,
    "delayed":  0.55,
    "critical": 0.90,
}


def stage_probability(stage: str | None) -> float:
    """Return the close-probability for a given pipeline stage.

    Falls back to ``DEFAULT_UNKNOWN`` for unknown stages so we never
    silently drop revenue out of the forecast.
    """
    if not stage:
        return DEFAULT_UNKNOWN
    return STAGE_PROBABILITY.get(stage.lower(), DEFAULT_UNKNOWN)


__all__ = [
    "STAGE_PROBABILITY",
    "DEFAULT_UNKNOWN",
    "HORIZONS",
    "MAX_HORIZON",
    "DEFAULT_PAYMENT_LAG_DAYS",
    "MANAGER_TARGET_OPEN_DEALS",
    "CARRIER_TARGET_OPEN_LOADS",
    "RISK_WEIGHT_BY_SEGMENT",
    "stage_probability",
]
