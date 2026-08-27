"""
Phase 5.5 / C — Order Creation Orchestration Golden Suite
==========================================================

This suite **pins legacy behaviour** of ``_create_order_from_invoice``
(the last remaining qualified-access bridge in
``QUALIFIED_USAGE_BRIDGES`` after Phase 5.5/F) BEFORE its extraction
to ``app/services/orders.py``.

Mandate (verbatim from user kick-off):
  * Step 1 — golden tests FIRST
  * Coverage — G1 … G8 only (no multi-currency / per-event splits)
  * Cover: Stripe webhook path, manual mark-paid, deposit auto-convert,
    empty-items, null-id robustness, notification failure, sio failure,
    missing invoice.id early-return

Suite contract (8 scenarios):

  G1. Order auto-create after Stripe-confirmed invoice payment
      (call shape used by ``app/routers/payments.py:658``).
  G2. Order auto-create after manual ``PATCH /api/invoices/{id}/mark-paid``
      (call shape used by ``server.py:14469``).
  G3. Order auto-create after deposit approve auto-convert
      (call shape used by ``backend/legal_workflow.py:2209``).
  G4. Invoice without ``items`` produces a 3-step default workflow.
  G5. Invoice with missing customerId / managerId still creates order
      (notification ctx has empty customer dict + manager stub).
  G6. ``notifications.emit`` raising does NOT abort order creation.
  G7. ``sio.emit`` raising does NOT abort order creation.
  G8. Missing ``invoice["id"]`` returns ``{}`` early — no DB write.

Discipline notes
─────────────────
* Suite uses SYNC test functions with ``asyncio.run`` wrappers — matches
  the rest of the test suite's convention (no ``pytest-asyncio`` is
  installed in this codebase; the ``asyncio_mode = auto`` ini key is
  inert).
* The helper is resolved through a single switch point
  (``_resolve_helper``) so the SAME suite runs UNCHANGED before AND
  after the 5.5/C extraction:
    - Pre-extraction  : ``server._create_order_from_invoice``
    - Post-extraction : ``app.services.orders.create_order_from_invoice``

Run:
    cd /app/backend && python -m pytest \\
        tests/test_phase5_5_c_order_creation_golden.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "bibi_test_phase5_5_c")


# ─────────────────────────────────────────────────────────────────────
# Helper-resolver — single switch point for pre/post extraction.
# ─────────────────────────────────────────────────────────────────────


def _resolve_helper() -> Tuple[Any, str]:
    """Return ``(helper_callable, label)``.

    Post-extraction shape wins if present.  The lookup order makes
    the suite resilient across the cutover commit — both shapes are
    accepted, assertions are identical.
    """
    try:
        from app.services.orders import create_order_from_invoice  # type: ignore
        return create_order_from_invoice, "post-5.5/C"
    except Exception:
        pass
    import server  # noqa: WPS433
    return server._create_order_from_invoice, "pre-5.5/C"


# ─────────────────────────────────────────────────────────────────────
# Side-effect recorder + sio stub.
# ─────────────────────────────────────────────────────────────────────


class SideEffectRecorder:
    """Records every notification + sio.emit call for assertions."""

    def __init__(self) -> None:
        self.sio_emissions: List[Dict[str, Any]] = []
        self.notification_emissions: List[Dict[str, Any]] = []
        self.notification_should_raise: bool = False
        self.sio_should_raise: bool = False

    async def sio_emit(self, event: str, payload: Dict[str, Any], *args, **kwargs) -> None:
        if self.sio_should_raise:
            raise RuntimeError("[stub] sio.emit forced failure")
        self.sio_emissions.append({"event": event, "payload": payload})

    async def notify_emit(self, event: str, payload: Dict[str, Any]) -> None:
        if self.notification_should_raise:
            raise RuntimeError("[stub] notifications.emit forced failure")
        self.notification_emissions.append({"event": event, "payload": payload})


class _SioStub:
    def __init__(self, recorder: SideEffectRecorder) -> None:
        self._recorder = recorder

    async def emit(self, event: str, payload: Dict[str, Any], *args, **kwargs):
        await self._recorder.sio_emit(event, payload, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────
# Async runner — sets up isolated DB, patches deps, executes coro,
# always tears down.  Returns whatever the coro returned + recorder.
# ─────────────────────────────────────────────────────────────────────


async def _setup_and_run(coro_factory):
    """Boot an isolated test DB, patch ``server.db``, ``server.sio``,
    ``notifications.emit``, and (post-extraction) the runtime accessors,
    then await ``coro_factory(db, helper, recorder)``.

    Cleans the database collections before AND after.
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    import server  # noqa: WPS433
    import notifications as notif  # noqa: WPS433

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Clean slate
    await db.orders.delete_many({})
    await db.customers.delete_many({})
    await db.users.delete_many({})

    helper, label = _resolve_helper()
    recorder = SideEffectRecorder()
    sio_stub = _SioStub(recorder)

    patches: List[Any] = [
        mock.patch.object(server, "db", db),
        mock.patch.object(server, "sio", sio_stub),
        mock.patch.object(notif, "emit", recorder.notify_emit),
    ]

    # Post-extraction surfaces (best-effort — only if they exist).
    try:
        from app.core import db_runtime  # type: ignore
        patches.append(mock.patch.object(db_runtime, "_db_ref", db, create=True))
    except Exception:
        pass
    try:
        from app.core import socket_runtime  # type: ignore
        patches.append(mock.patch.object(socket_runtime, "_sio_ref", sio_stub, create=True))
    except Exception:
        pass

    for p in patches:
        p.start()
    try:
        return await coro_factory(db, helper, recorder, label)
    finally:
        for p in reversed(patches):
            try:
                p.stop()
            except Exception:
                pass
        try:
            await db.orders.delete_many({})
            await db.customers.delete_many({})
            await db.users.delete_many({})
        finally:
            client.close()


def _run(coro_factory):
    """Synchronous wrapper around ``asyncio.run`` — used by every test."""
    return asyncio.run(_setup_and_run(coro_factory))


# ─────────────────────────────────────────────────────────────────────
# Invoice factory.
# ─────────────────────────────────────────────────────────────────────


def _make_invoice(
    *,
    invoice_id: str = "inv_test_001",
    items: List[Dict[str, Any]] | None = None,
    customer_id: str | None = "cust_001",
    manager_id: str | None = "mgr_001",
    manager_email: str | None = "mgr@example.com",
    payment_intent_id: str | None = "pi_test_001",
    total: float = 100.0,
    currency: str = "USD",
) -> Dict[str, Any]:
    if items is None:
        items = [
            {
                "id": "li_001",
                "service_id": "svc_inspect",
                "name": "VIN inspection",
                "category": "inspection",
                "qty": 1,
                "price": 100.0,
                "line_total": 100.0,
                "workflow": [
                    {"key": "pending", "label": "Очікує"},
                    {"key": "completed", "label": "Готово"},
                ],
            }
        ]
    return {
        "id": invoice_id,
        "items": items,
        "customerId": customer_id,
        "managerId": manager_id,
        "managerEmail": manager_email,
        "paymentIntentId": payment_intent_id,
        "total": total,
        "amount": total,
        "currency": currency,
    }


# ─────────────────────────────────────────────────────────────────────
# G1 — Stripe-webhook path.
# ─────────────────────────────────────────────────────────────────────


def test_g1_stripe_webhook_order_auto_create():
    """G1: Helper called from the Stripe webhook recompute branch
    (``app/routers/payments.py:658``) auto-creates an order
    for the paid invoice.  Behavioural pin: doc shape, notification
    events, sio broadcast, idempotency."""
    async def scenario(db, helper, recorder, label):
        inv = _make_invoice(invoice_id="inv_g1_stripe")
        order = await helper(inv)

        # — Order doc shape
        assert order, f"[G1 / {label}] helper returned empty doc"
        assert order["invoiceId"] == "inv_g1_stripe"
        assert order["customerId"] == "cust_001"
        assert order["managerId"] == "mgr_001"
        assert order["managerEmail"] == "mgr@example.com"
        assert order["paymentIntentId"] == "pi_test_001"
        assert order["status"] == "in_progress"
        assert order["amount"] == 100.0
        assert order["currency"] == "USD"
        # 2 workflow stages × 1 item
        assert len(order["steps"]) == 2
        assert order["id"].startswith("ord_"), (
            f"[G1] id must follow legacy `ord_<ts>_<6hex>` prefix; got {order['id']!r}"
        )
        for k in ("assignedAt", "created_at", "updated_at"):
            assert k in order, f"[G1] missing timestamp field {k!r}"

        # — Side-effects
        assert any(e["event"] == "order:created" for e in recorder.sio_emissions), (
            f"[G1] expected sio.emit('order:created'); got {recorder.sio_emissions!r}"
        )
        events = [e["event"] for e in recorder.notification_emissions]
        import notifications as notif  # noqa: WPS433
        assert notif.EVENT_PAYMENT_CONFIRMED in events, (
            f"[G1] payment_confirmed event missing — got {events!r}"
        )
        assert notif.EVENT_ORDER_STARTED in events, (
            f"[G1] order_started event missing — got {events!r}"
        )

        # — Idempotency: re-invoke returns the same (existing) order
        again = await helper(inv)
        assert again["id"] == order["id"], (
            f"[G1] idempotency broken: 2nd call id={again['id']!r} vs 1st={order['id']!r}"
        )
        # — Exactly one orders document persisted
        count = await db.orders.count_documents({"invoiceId": "inv_g1_stripe"})
        assert count == 1, f"[G1] idempotency broken: {count} orders for one invoice"

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G2 — Manual PATCH /api/invoices/{id}/mark-paid path.
# ─────────────────────────────────────────────────────────────────────


def test_g2_manual_mark_paid_order_auto_create():
    """G2: Same helper invoked from the in-file ``invoice_mark_paid``
    endpoint (``server.py:14469``).  Identical doc shape, identical
    events as G1.  Idempotency parity required."""
    async def scenario(db, helper, recorder, label):
        inv = _make_invoice(invoice_id="inv_g2_manual")
        order = await helper(inv)

        assert order["invoiceId"] == "inv_g2_manual"
        assert order["status"] == "in_progress"
        events = [e["event"] for e in recorder.notification_emissions]
        import notifications as notif
        assert notif.EVENT_PAYMENT_CONFIRMED in events
        assert notif.EVENT_ORDER_STARTED in events

        # Idempotency
        again = await helper(inv)
        assert again["id"] == order["id"]
        count = await db.orders.count_documents({"invoiceId": "inv_g2_manual"})
        assert count == 1

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G3 — Deposit auto-convert.
# ─────────────────────────────────────────────────────────────────────


def test_g3_deposit_auto_convert_order_auto_create():
    """G3: Helper invoked from ``backend/legal_workflow.py:2209``
    immediately after the deposit→invoice synthesis.  The deposit-
    driven invoice has ``sourceDepositId`` set and a single
    ``deposit``-category line item.  Helper must still produce a
    valid order with the deposit's 2-stage workflow."""
    async def scenario(db, helper, recorder, label):
        inv = _make_invoice(
            invoice_id="inv_g3_deposit",
            items=[
                {
                    "id": "li_dep_001",
                    "service_id": None,
                    "service_code": None,
                    "name": "Депозит · manual",
                    "description": "",
                    "category": "deposit",
                    "price": 250.0,
                    "qty": 1,
                    "line_total": 250.0,
                    "workflow": [
                        {"key": "received", "label": "Депозит отримано"},
                        {"key": "applied", "label": "Зарахований у замовлення"},
                    ],
                }
            ],
            total=250.0,
        )
        inv["sourceDepositId"] = "dep_g3"

        order = await helper(inv)

        assert order["invoiceId"] == "inv_g3_deposit"
        assert order["amount"] == 250.0
        assert order["status"] == "in_progress"
        assert len(order["steps"]) == 2
        assert order["steps"][0]["key"] == "received"
        assert order["steps"][1]["key"] == "applied"

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G4 — Empty invoice.items → default 3-step workflow.
# ─────────────────────────────────────────────────────────────────────


def test_g4_empty_items_default_three_step_workflow():
    """G4: Invoice with no ``items`` must produce the legacy 3-step
    fallback workflow: pending → in_progress → completed."""
    async def scenario(db, helper, recorder, label):
        inv = _make_invoice(invoice_id="inv_g4_empty", items=[])
        order = await helper(inv)

        keys = [s["key"] for s in order["steps"]]
        assert keys == ["pending", "in_progress", "completed"], (
            f"[G4 / {label}] default 3-step workflow broken; got {keys!r}"
        )
        assert all(s["status"] == "pending" for s in order["steps"])

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G5 — Null customer / manager IDs.
# ─────────────────────────────────────────────────────────────────────


def test_g5_null_customer_and_manager_no_crash():
    """G5: customerId / managerId may legitimately be None on legacy
    invoices.  Helper must still create the order and emit both
    business events with a sane context shape."""
    async def scenario(db, helper, recorder, label):
        inv = _make_invoice(
            invoice_id="inv_g5_nulls",
            customer_id=None,
            manager_id=None,
            manager_email=None,
        )
        order = await helper(inv)

        assert order["invoiceId"] == "inv_g5_nulls"
        assert order["customerId"] is None
        assert order["managerId"] is None

        events = [e["event"] for e in recorder.notification_emissions]
        import notifications as notif
        assert notif.EVENT_PAYMENT_CONFIRMED in events
        assert notif.EVENT_ORDER_STARTED in events

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G6 — notifications.emit raises: order STILL created.
# ─────────────────────────────────────────────────────────────────────


def test_g6_notifications_emit_failure_does_not_abort():
    """G6: ``notifications.emit`` raising must NOT abort the order
    creation.  Helper wraps the dispatch in try/except + logger.exception
    (best-effort fan-out)."""
    async def scenario(db, helper, recorder, label):
        recorder.notification_should_raise = True
        inv = _make_invoice(invoice_id="inv_g6_notif_fail")
        order = await helper(inv)

        assert order, f"[G6 / {label}] order creation aborted by notif failure"
        assert order["invoiceId"] == "inv_g6_notif_fail"
        assert order["status"] == "in_progress"
        # No notifications were recorded because the stub raised
        assert recorder.notification_emissions == []
        # — Order still persisted in DB
        persisted = await db.orders.find_one({"invoiceId": "inv_g6_notif_fail"})
        assert persisted is not None, f"[G6] order not persisted to DB"

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G7 — sio.emit raises: order STILL created.
# ─────────────────────────────────────────────────────────────────────


def test_g7_sio_emit_failure_does_not_abort():
    """G7: ``sio.emit`` raising must NOT abort order creation.  Helper
    wraps the emit in ``try/except pass`` (best-effort broadcast).
    Notifications fire independently, even when sio fails."""
    async def scenario(db, helper, recorder, label):
        recorder.sio_should_raise = True
        inv = _make_invoice(invoice_id="inv_g7_sio_fail")
        order = await helper(inv)

        assert order, f"[G7 / {label}] order creation aborted by sio failure"
        assert order["invoiceId"] == "inv_g7_sio_fail"
        assert recorder.sio_emissions == []  # stub raised → nothing recorded
        events = [e["event"] for e in recorder.notification_emissions]
        import notifications as notif
        assert notif.EVENT_PAYMENT_CONFIRMED in events
        assert notif.EVENT_ORDER_STARTED in events

    _run(scenario)


# ─────────────────────────────────────────────────────────────────────
# G8 — Missing invoice.id: returns {} early, no DB write.
# ─────────────────────────────────────────────────────────────────────


def test_g8_missing_invoice_id_returns_empty_no_write():
    """G8: Invoice without ``id`` (or completely empty / None invoice)
    must return ``{}`` early with no orders insertion and no
    side-effects.  Pins the legacy guard:
        ``if not invoice or not invoice.get("id"): return {}``
    """
    async def scenario(db, helper, recorder, label):
        # Case A — missing id field entirely
        inv = _make_invoice(invoice_id="x")  # placeholder, will pop()
        inv.pop("id", None)
        result_a = await helper(inv)
        assert result_a == {}, f"[G8a / {label}] expected {{}}; got {result_a!r}"

        # Case B — empty invoice dict
        result_b = await helper({})
        assert result_b == {}, f"[G8b / {label}] expected {{}}; got {result_b!r}"

        # Case C — None invoice
        result_c = await helper(None)  # type: ignore[arg-type]
        assert result_c == {}, f"[G8c / {label}] expected {{}}; got {result_c!r}"

        # — No orders persisted
        count = await db.orders.count_documents({})
        assert count == 0, f"[G8 / {label}] expected 0 orders persisted; got {count}"

        # — No side-effects fired
        assert recorder.sio_emissions == [], (
            f"[G8 / {label}] unexpected sio emissions: {recorder.sio_emissions!r}"
        )
        assert recorder.notification_emissions == [], (
            f"[G8 / {label}] unexpected notifications: {recorder.notification_emissions!r}"
        )

    _run(scenario)
