"""
Contract Execution Engine (ECO.NOVA)
====================================

Production contract engine built as an *extension* of the existing ECO Waste
domain (``app/waste``) — it does NOT duplicate models. It adds:

* Universal **Schedule** (period_type = quarter | month | custom | one_time)
  persisted in the new ``contract_periods`` collection.
* A **financial engine** exposing FIVE distinct values per contract:
    Contract Value  — frozen at signing (what the client agreed)
    Executed Value  — auto-computed from SIGNED acts (actual weight/price + extras)
    Invoiced Value  — sum of invoices linked to the contract
    Paid Value      — sum of PAID invoices
    Remaining Value — Contract Value − Paid Value
* **Extra works** as first-class, separate line items (transport, urgent visit,
  packaging, lab, sorting, other) — never silently merged into a grand total.
* **Auto-accumulation**: signing a utilization Act rebuilds the matching
  period actuals (idempotent — rebuilt from all signed acts every time).
* **Completion Wizard** checks + **Ecologist Report** aggregation entity.

Collections it owns / extends:
    waste_contracts   (extended — schedule_config / financial_terms / financials)
    contract_periods  (NEW — universal schedule)
    utilization_acts  (extended — contract_id / period_id / actual lines)
    invoices          (extended — contract_id / period_id / act_id / invoice_scope)
    ecologist_reports (NEW)
"""
