"""
ECO Analytics — unified ECO-domain aggregation layer for the restored "wave"
dashboards (Finance360 / Operations360 / Executive Center / Contract360 /
Deal360).

Replaces the legacy BiBi-Cars car-import aggregations (auction stages, EUR,
deposits/shipments) with the ECO waste-recycling model:

    deal      = db.deals       (ECO funnel: new→negotiation→contract→pickup→
                                utilization→won/lost, UAH, wasteType)
    contract  = db.contracts   (draft→pending_approval→sent→signed→active→archived)
    payment   = db.payments    (income / expense, UAH)
    pickup    = waste_pickups   (operations SLA / in-transit)

Scope model: admin = all, manager = own (managerId). NO team_lead.
"""
from app.eco_analytics.router import (
    finance_router,
    operations_router,
    executive_router,
    contracts_router,
    deals_router,
)

__all__ = [
    "finance_router",
    "operations_router",
    "executive_router",
    "contracts_router",
    "deals_router",
]
