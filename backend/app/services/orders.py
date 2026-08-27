"""
Orders domain service — Phase 5.5/C extraction
================================================

Owns the order-creation orchestration helper previously hosted as the
private ``server._create_order_from_invoice`` symbol.  Extracted on
2026-05-19 as part of Phase 5.5/C — the **first true orchestration
extraction** of the Phase 5 refactor cycle.

Mandate (verbatim, Phase 5.5/C kickoff)
─────────────────────────────────────────
  * Ownership target: ``app/services/orders.py``
  * Helper body moved 1:1 from server.py (no schema / payload / event
    drift).
  * ``db`` reads/writes route through ``app.core.db_runtime.get_db()``
    (the canonical accessor published in Phase 5.4 / C-4e/i).
  * ``sio`` access routes through ``app.core.socket_runtime.get_sio()``
    (the existing C-4c accessor — NO new accessor module is
    introduced; the C-4c precedent is reused).
  * ``logger`` is module-local: ``logging.getLogger("bibi.orders")``.
  * Public surface: ``create_order_from_invoice`` (renamed from the
    legacy ``_create_order_from_invoice`` private symbol).
  * Sibling pure-helper ``_build_order_steps_from_invoice`` moved with
    the orchestration and kept as a module-private function (still
    underscore-prefixed because its API is internal to the orders
    service).

Forbidden in this extraction (locked in the 5.5/C mandate)
──────────────────────────────────────────────────────────────
  * No order schema changes.
  * No invoice schema changes.
  * No Stripe logic changes.
  * No notification payload changes (events ``payment_confirmed`` +
    ``order_started`` fire with identical context dict shape).
  * No sio event changes (``order:created`` payload identical).
  * No customer / user lookup redesign.
  * No transaction semantics changes.
  * No retry / idempotency changes (the
    ``db.orders.find_one({"invoiceId": …})`` short-circuit is byte-
    identical to legacy).
  * No multi-currency additions.
  * No per-event split additions.

Invariants asserted by the golden suite
───────────────────────────────────────────
  * ``tests/test_phase5_5_c_order_creation_golden.py`` — 8 G-scenarios
    (G1 Stripe path, G2 manual mark-paid, G3 deposit auto-convert,
    G4 empty-items default workflow, G5 null IDs, G6 notification
    failure resilience, G7 sio failure resilience, G8 missing
    invoice.id early-return).  Same suite runs UNCHANGED pre and post
    extraction via the single ``_resolve_helper`` switch point.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

# Canonical runtime accessors — published by server.py at module-load
# time (db) and at sio-instance creation time (sio).  Reads call the
# accessor freshly each time so any in-process rebind remains visible
# (legacy semantics of ``from server import db`` / ``from server import
# sio`` were "read at call site"; the accessors preserve that exactly).
from app.core.db_runtime import get_db
from app.core.socket_runtime import get_sio

logger = logging.getLogger("bibi.orders")


__all__ = ["create_order_from_invoice"]


# ─────────────────────────────────────────────────────────────────────
# Internal helper — pure transform, no I/O.
# Translates ``invoice["items"]`` → linear list of workflow steps.
# Mirrors the legacy ``server._build_order_steps_from_invoice`` body
# byte-for-byte (UI labels included: "Очікує" / "В роботі" / "Готово").
# ─────────────────────────────────────────────────────────────────────


def _build_order_steps_from_invoice(invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Translate invoice line-items → linear list of workflow steps."""
    steps: List[Dict[str, Any]] = []
    for it in (invoice.get("items") or []):
        wf = it.get("workflow") or [
            {"key": "pending", "label": "Очікує"},
            {"key": "in_progress", "label": "В роботі"},
            {"key": "completed", "label": "Готово"},
        ]
        for s in wf:
            steps.append({
                "id": str(uuid.uuid4()),
                "service_item_id": it.get("id"),
                "service_id": it.get("service_id"),
                "service_name": it.get("name"),
                "key": s.get("key"),
                "label": s.get("label"),
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "note": None,
            })
    if not steps:
        steps = [
            {"id": str(uuid.uuid4()), "key": "pending",     "label": "Очікує",   "status": "pending"},
            {"id": str(uuid.uuid4()), "key": "in_progress", "label": "В роботі", "status": "pending"},
            {"id": str(uuid.uuid4()), "key": "completed",   "label": "Готово",   "status": "pending"},
        ]
    return steps


# ─────────────────────────────────────────────────────────────────────
# Public entry point — order-creation orchestration.
# Body is a 1:1 port of the legacy ``server._create_order_from_invoice``;
# the ONLY changes are:
#   * ``db`` references → ``get_db()`` (call-time resolution)
#   * ``sio`` references → ``get_sio()`` (call-time resolution, with
#     ``None``-safe best-effort emit semantics preserved)
#   * ``logger`` references → module-local ``bibi.orders`` namespace
# Everything else (id format, doc keys, ordering, idempotency guard,
# best-effort try/except wrappers, notification context dict shape)
# is byte-identical.
# ─────────────────────────────────────────────────────────────────────


async def create_order_from_invoice(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Idempotently create an order document from a paid invoice.

    Args:
        invoice: invoice doc as persisted in ``db.invoices``. Must
            carry at least an ``id`` field; everything else is
            optional and defaults to legacy fallbacks.

    Returns:
        the created order doc (or the pre-existing one if an order
        for this invoice was already created — legacy idempotency
        semantics).  Returns ``{}`` if ``invoice`` is falsy or has no
        ``id``.
    """
    if not invoice or not invoice.get("id"):
        return {}

    db = get_db()
    existing = await db.orders.find_one({"invoiceId": invoice["id"]}, {"_id": 0})
    if existing:
        return existing

    items = invoice.get("items") or []
    summary_items = [{
        "service_item_id": it.get("id"),
        "service_id": it.get("service_id"),
        "name": it.get("name"),
        "category": it.get("category"),
        "qty": it.get("qty", 1),
        "price": it.get("price", 0),
        "line_total": it.get("line_total", 0),
        # Phase Final / Block 1 — keep workflow_template_id binding visible
        # on the order summary for audit / Customer Cabinet trace.
        "workflow_template_id": it.get("workflow_template_id"),
    } for it in items]

    order_id = f"ord_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"
    doc = {
        "id": order_id,
        "invoiceId": invoice.get("id"),
        "paymentIntentId": invoice.get("paymentIntentId"),
        "customerId": invoice.get("customerId"),
        "managerId": invoice.get("managerId"),
        "managerEmail": invoice.get("managerEmail"),
        "status": "in_progress",
        "items": summary_items,
        "steps": _build_order_steps_from_invoice(invoice),
        "amount": invoice.get("total") or invoice.get("amount") or 0,
        "currency": invoice.get("currency") or "USD",
        "notes": [],
        "assignedAt": datetime.now(timezone.utc).isoformat(),
        "startedAt":  None,
        "completedAt": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Sprint 1.5 / Finance Core Closeout — propagate UTM from invoice to
    # order so downstream analytics (Team Lead dashboard, marketing
    # attribution, etc.) can group orders by source/campaign without
    # needing to back-join through invoices.
    try:
        from app.services.utm_propagation import pick_utm, stamp_utm
        stamp_utm(doc, pick_utm(invoice))
    except Exception:
        logger.exception("[order] utm stamping failed (non-fatal)")

    await db.orders.insert_one(doc)
    doc.pop("_id", None)

    # Best-effort socket notification — legacy semantics preserved
    # (silent swallow on any failure, including a pre-startup sio of
    # None which the legacy code never hit but we defensively handle
    # via try/except pass).
    try:
        sio = get_sio()
        if sio is not None:
            await sio.emit(
                "order:created",
                {
                    "orderId": order_id,
                    "invoiceId": invoice["id"],
                    "customerId": invoice.get("customerId"),
                    "managerId": invoice.get("managerId"),
                },
            )
    except Exception:
        pass

    # Fire business events: payment_confirmed + order_started.
    # Notifications module is imported lazily — matches legacy
    # ``import notifications as _notif`` shape inside the helper body
    # (kept lazy because notifications imports are heavyweight in the
    # test path).
    try:
        import notifications as _notif  # noqa: WPS433 (lazy by design)
        customer = await db.customers.find_one(
            {"id": invoice.get("customerId")}, {"_id": 0}
        ) or {}
        manager = None
        if invoice.get("managerId"):
            manager = await db.users.find_one(
                {"id": invoice.get("managerId")}, {"_id": 0}
            )
        manager = manager or {
            "id": invoice.get("managerId"),
            "email": invoice.get("managerEmail"),
        }
        ctx = {"invoice": invoice, "order": doc, "customer": customer, "manager": manager}
        await _notif.emit(_notif.EVENT_PAYMENT_CONFIRMED, dict(ctx))
        await _notif.emit(_notif.EVENT_ORDER_STARTED, dict(ctx))
    except Exception:
        logger.exception("[notif] emit payment_confirmed/order_started failed")

    # Sprint 3 / PDF Engine — auto-generate Contract PDF on invoice payment
    # so the customer immediately has the signed document in their
    # File Manager. Failure here MUST NOT block order creation; the
    # document can always be regenerated manually from the UI.
    try:
        if invoice.get("customerId"):
            from app.services import pdf_engine
            await pdf_engine.generate(
                doc_type="contract",
                customer_id=invoice["customerId"],
                invoice_id=invoice.get("id"),
                language="en",
                generated_by="system",
                generated_by_email="system@bibi.cars",
            )
            logger.info("[pdf_engine] auto-generated contract for invoice %s", invoice.get("id"))
    except Exception:
        logger.exception("[pdf_engine] auto-generate contract failed (non-fatal)")

    # Sprint 3.5 / Customer Roadmap — auto-spawn the 7-stage client journey
    # so the cabinet can immediately render the "where is my car" view.
    # Idempotent: a second call for the same order short-circuits inside
    # the service helper.
    try:
        if invoice.get("customerId"):
            from app.services import customer_roadmap as _roadmap
            await _roadmap.auto_create_from_order(
                customer_id=invoice["customerId"],
                order=doc,
                invoice=invoice,
            )
            logger.info("[customer_roadmap] auto-spawned for order %s", order_id)
    except Exception:
        logger.exception("[customer_roadmap] auto-spawn failed (non-fatal)")

    # Sprint 4 / Customer Timeline — fire invoice_paid + order_created
    try:
        if invoice.get("customerId"):
            from app.services import customer_timeline
            await customer_timeline.record_event(
                customer_id=invoice["customerId"],
                kind="invoice_paid",
                title=f"Invoice paid: #{(invoice.get('number') or invoice.get('id') or '')[-8:]}",
                ref={"collection": "invoices", "id": invoice.get("id")},
                meta={
                    "amount": invoice.get("amount") or invoice.get("total"),
                    "currency": invoice.get("currency"),
                },
            )
            await customer_timeline.record_event(
                customer_id=invoice["customerId"],
                kind="order_created",
                title=f"Order #{order_id[-8:]} created",
                ref={"collection": "orders", "id": order_id},
                meta={"items_count": len(doc.get("items") or [])},
            )
    except Exception:
        logger.exception("[customer_timeline] order_created/invoice_paid emit failed (non-fatal)")

    return doc
