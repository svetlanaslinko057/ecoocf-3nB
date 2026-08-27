"""
Wave 12 — Finance360.

Finance360 is *not* another payments table. It's the operational money
control center for the whole company:

  * Aggregates 4 entities (deposits / payments / refunds / outstanding)
    across all deals in scope.
  * Three tabs in 12A: Overview, Transactions journal, Outstanding.
  * Returns scope-aware data (admin sees all, team_lead sees own + team,
    manager sees only own).

Wave 12B (planned): Manager Finance, Financial Health, Revenue at risk.
Wave 12C (planned): Forecasting / Cash flow projection.
"""

from .aggregations import (
    build_finance_overview,
    list_finance_transactions,
    list_outstanding_deals,
    finance_scope_for_user,
)

__all__ = [
    "build_finance_overview",
    "list_finance_transactions",
    "list_outstanding_deals",
    "finance_scope_for_user",
]
