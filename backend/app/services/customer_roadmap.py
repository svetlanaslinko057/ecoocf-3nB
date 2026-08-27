"""
Customer Roadmap Service — Sprint 3.5
=====================================

Client-facing journey tracker for the "From auction to keys" lifecycle.

While ``app/services/orders.py`` tracks **operational** workflow steps
tied to individual invoice line items, this service tracks the
**client-visible** journey of the *vehicle itself*: where is my car
right now and what's next?

The canonical seven-stage roadmap is:

  1. vehicle_found      — Automobile selected at auction / listing
  2. vehicle_purchased  — Bid won / purchase confirmed
  3. delivery_europe    — Loaded on vessel / in transit to EU
  4. arrived_bulgaria   — Vehicle reached Bulgarian port / warehouse
  5. adaptation         — Technical adaptation works in progress
  6. registration       — Documents / KAT registration ongoing
  7. handover           — Vehicle handed over to client (DONE)

Key design choices
------------------
* **One roadmap per (customer, vehicle/deal/order) tuple.** A customer
  with three vehicles has three roadmaps. Each can advance independently.
* **Three labels per stage** (en / ru / bg) baked into the document so
  the frontend can render in any language without a separate i18n call.
* **SLA tracking** baked into each stage: ``sla_days`` is the *target*,
  ``deadline_at`` is computed from the stage's ``started_at + sla_days``.
  Once a stage is overdue we mark it via ``sla_breached: true`` which
  drives Team Lead / Admin dashboards.
* **Read-only for customer.** Mutations are restricted to manager /
  team_lead / admin at the router layer.
* **Soft-delete only**: cancelled roadmaps remain in the collection with
  ``status = 'cancelled'`` so analytics keep working historically.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.db_runtime import get_db

logger = logging.getLogger("bibi.customer_roadmap")

COLLECTION = "customer_roadmaps"


# ---------------------------------------------------------------------
# Canonical roadmap template
# ---------------------------------------------------------------------
#
# Each stage carries:
#   key       — stable machine identifier (do NOT rename, used by FE/api)
#   label_en  — English label (default UI)
#   label_ru  — Russian label
#   label_bg  — Bulgarian label
#   sla_days  — default SLA window (manager can override per instance)
#   icon      — phosphor-icon name for the FE stepper
#
DEFAULT_STAGES: List[Dict[str, Any]] = [
    {
        "key": "vehicle_found",
        "label_en": "Vehicle found",
        "label_ru": "Автомобиль найден",
        "label_bg": "Намерен автомобил",
        "description_en": "We located a matching vehicle at auction or partner listing.",
        "description_ru": "Мы нашли подходящий автомобиль на аукционе или у партнёра.",
        "description_bg": "Открихме подходящ автомобил на търг или при партньор.",
        "sla_days": 7,
        "icon": "MagnifyingGlass",
    },
    {
        "key": "vehicle_purchased",
        "label_en": "Vehicle purchased",
        "label_ru": "Автомобиль куплен",
        "label_bg": "Закупен автомобил",
        "description_en": "Auction won / dealer payment processed.",
        "description_ru": "Аукцион выигран / оплата дилеру проведена.",
        "description_bg": "Печелим търга / плащането към дилъра е извършено.",
        "sla_days": 5,
        "icon": "Coins",
    },
    {
        "key": "delivery_europe",
        "label_en": "Delivery to Europe",
        "label_ru": "Доставка в Европу",
        "label_bg": "Доставка в Европа",
        "description_en": "Vehicle loaded on a vessel / RoRo and shipped to EU.",
        "description_ru": "Автомобиль загружен на судно / RoRo и отправлен в ЕС.",
        "description_bg": "Автомобилът е товарен на кораб / RoRo и изпратен към ЕС.",
        "sla_days": 30,
        "icon": "Boat",
    },
    {
        "key": "arrived_bulgaria",
        "label_en": "Arrived in Bulgaria",
        "label_ru": "Прибыл в Болгарию",
        "label_bg": "Пристигна в България",
        "description_en": "Vehicle cleared customs and reached the warehouse.",
        "description_ru": "Таможня пройдена, авто прибыло на склад.",
        "description_bg": "Митницата е премината, автомобилът е в склада.",
        "sla_days": 5,
        "icon": "MapPin",
    },
    {
        "key": "adaptation",
        "label_en": "Adaptation",
        "label_ru": "Адаптация",
        "label_bg": "Адаптация",
        "description_en": "Technical adaptation, conversion and quality checks.",
        "description_ru": "Техническая адаптация, переоборудование и проверки.",
        "description_bg": "Техническа адаптация, преоборудване и проверки.",
        "sla_days": 14,
        "icon": "Wrench",
    },
    {
        "key": "registration",
        "label_en": "Registration",
        "label_ru": "Регистрация",
        "label_bg": "Регистрация",
        "description_en": "Paperwork & KAT registration in progress.",
        "description_ru": "Оформление документов и регистрация в КАТ.",
        "description_bg": "Документация и регистрация в КАТ.",
        "sla_days": 7,
        "icon": "Stamp",
    },
    {
        "key": "handover",
        "label_en": "Handover to client",
        "label_ru": "Передача клиенту",
        "label_bg": "Предаване на клиента",
        "description_en": "Vehicle handed over to the client. Welcome aboard!",
        "description_ru": "Автомобиль передан клиенту. Добро пожаловать!",
        "description_bg": "Автомобилът е предаден на клиента. Добре дошъл!",
        "sla_days": 3,
        "icon": "Key",
    },
]


# ---------------------------------------------------------------------
# UAT Enhancement #4 — Sales Pipeline Roadmap (10 canonical stages)
# ---------------------------------------------------------------------
#
# This is the PRE-purchase customer journey from first contact through
# closing the deal — complements the post-purchase vehicle_journey
# template above. Both templates live in the same `customer_roadmaps`
# collection, distinguished by `pipeline_type`.
#
SALES_PIPELINE_STAGES: List[Dict[str, Any]] = [
    {
        "key": "new_lead",
        "label_en": "New lead",
        "label_uk": "Новий лід",
        "label_ru": "Новый лид",
        "label_bg": "Нов лийд",
        "description_en": "First touch — lead just landed in the funnel.",
        "description_uk": "Перший контакт — лід щойно потрапив у воронку.",
        "description_ru": "Первое касание — лид только попал в воронку.",
        "description_bg": "Първи контакт — лийдът току-що влезе във фунията.",
        "sla_days": 1,
        "icon": "Sparkle",
        "key_actions": ["welcome_message", "log_source", "qualify_intent"],
        "recommended_next_en": "Reach out within 1 hour and log first impression.",
        "recommended_next_uk": "Звʼязатися протягом 1 години та зафіксувати перше враження.",
        "recommended_next_ru": "Связаться в течение 1 часа и зафиксировать первое впечатление.",
        "recommended_next_bg": "Свържете се до 1 час и запишете първото впечатление.",
    },
    {
        "key": "contact_established",
        "label_en": "Contact established",
        "label_uk": "Контакт встановлено",
        "label_ru": "Контакт установлен",
        "label_bg": "Установен контакт",
        "description_en": "Customer responded and confirmed interest.",
        "description_uk": "Клієнт відповів та підтвердив зацікавленість.",
        "description_ru": "Клиент ответил и подтвердил интерес.",
        "description_bg": "Клиентът отговори и потвърди интерес.",
        "sla_days": 2,
        "icon": "ChatCircleText",
        "key_actions": ["intro_call_done", "save_preferences", "schedule_followup"],
        "recommended_next_en": "Send a short product brief and book a discovery call.",
        "recommended_next_uk": "Надішліть короткий бриф та забронюйте дзвінок-діагностику.",
        "recommended_next_ru": "Отправьте короткий бриф и запланируйте дискавери-звонок.",
        "recommended_next_bg": "Изпратете кратко представяне и насрочете discovery разговор.",
    },
    {
        "key": "need_diagnostic",
        "label_en": "Need diagnostic",
        "label_uk": "Діагностика потреби",
        "label_ru": "Диагностика потребности",
        "label_bg": "Диагностика на нуждата",
        "description_en": "Understand budget, timeline, vehicle preferences.",
        "description_uk": "Зʼясувати бюджет, терміни, переваги по авто.",
        "description_ru": "Выяснить бюджет, сроки, предпочтения по авто.",
        "description_bg": "Изясняване на бюджет, срокове, предпочитания за автомобил.",
        "sla_days": 3,
        "icon": "Target",
        "key_actions": ["budget_known", "timeline_known", "vehicle_type_known", "country_known"],
        "recommended_next_en": "Summarise needs in writing and send proposed shortlist.",
        "recommended_next_uk": "Резюмуйте потреби письмово та надішліть пропозиції.",
        "recommended_next_ru": "Резюмируйте потребности письменно и отправьте подборку.",
        "recommended_next_bg": "Обобщете нуждите писмено и предложете шортлист.",
    },
    {
        "key": "offer_prep",
        "label_en": "Offer preparation",
        "label_uk": "Підготовка оферти",
        "label_ru": "Подготовка оферты",
        "label_bg": "Подготовка на оферта",
        "description_en": "Build commercial proposal: vehicle, price, terms.",
        "description_uk": "Підготувати комерційну пропозицію: авто, ціна, умови.",
        "description_ru": "Подготовить коммерческое предложение: авто, цена, условия.",
        "description_bg": "Подгответе оферта: автомобил, цена, условия.",
        "sla_days": 2,
        "icon": "FileText",
        "key_actions": ["price_calculated", "calc_pdf_ready", "delivery_terms"],
        "recommended_next_en": "Send the quote and schedule a review call.",
        "recommended_next_uk": "Надішліть оферту і призначте дзвінок для обговорення.",
        "recommended_next_ru": "Отправьте оферту и назначьте звонок-обсуждение.",
        "recommended_next_bg": "Изпратете офертата и насрочете обзорен разговор.",
    },
    {
        "key": "follow_up",
        "label_en": "Follow-up",
        "label_uk": "Follow-up",
        "label_ru": "Follow-up",
        "label_bg": "Последващи действия",
        "description_en": "Address questions, refine the offer if needed.",
        "description_uk": "Відповісти на питання, уточнити пропозицію.",
        "description_ru": "Ответить на вопросы, скорректировать предложение.",
        "description_bg": "Отговорете на въпроси, прецизирайте офертата.",
        "sla_days": 3,
        "icon": "ArrowsClockwise",
        "key_actions": ["objections_handled", "alternatives_offered", "decision_blockers"],
        "recommended_next_en": "Propose an in-person or video meeting.",
        "recommended_next_uk": "Запропонуйте особисту або відео-зустріч.",
        "recommended_next_ru": "Предложите личную или видео-встречу.",
        "recommended_next_bg": "Предложете лична или видео среща.",
    },
    {
        "key": "meeting",
        "label_en": "Meeting",
        "label_uk": "Зустріч",
        "label_ru": "Встреча",
        "label_bg": "Среща",
        "description_en": "Face-to-face or call: confirm intent, agree on details.",
        "description_uk": "Особиста або онлайн зустріч: підтвердити намір, узгодити деталі.",
        "description_ru": "Личная или онлайн встреча: подтвердить намерение, согласовать детали.",
        "description_bg": "Лична или онлайн среща: потвърдете намерението, договорете детайли.",
        "sla_days": 5,
        "icon": "UsersThree",
        "key_actions": ["meeting_scheduled", "meeting_held", "minutes_logged"],
        "recommended_next_en": "Send recap + draft contract terms.",
        "recommended_next_uk": "Надіслати підсумок зустрічі + проект умов договору.",
        "recommended_next_ru": "Отправить резюме + проект условий договора.",
        "recommended_next_bg": "Изпратете резюме + проектодоговор.",
    },
    {
        "key": "closing",
        "label_en": "Closing",
        "label_uk": "Закриття угоди",
        "label_ru": "Закрытие сделки",
        "label_bg": "Затваряне на сделката",
        "description_en": "Final negotiation, contract signature.",
        "description_uk": "Фінальні переговори, підписання договору.",
        "description_ru": "Финальные переговоры, подписание договора.",
        "description_bg": "Финални преговори, подписване на договор.",
        "sla_days": 5,
        "icon": "PenNib",
        "key_actions": ["contract_sent", "contract_signed", "deposit_invoice_issued"],
        "recommended_next_en": "Send the deposit invoice and confirm payment instructions.",
        "recommended_next_uk": "Надіслати рахунок на депозит та узгодити умови оплати.",
        "recommended_next_ru": "Отправить счёт на депозит и согласовать оплату.",
        "recommended_next_bg": "Изпратете фактура за депозит и потвърдете плащането.",
    },
    {
        "key": "deposit",
        "label_en": "Deposit",
        "label_uk": "Депозит",
        "label_ru": "Депозит",
        "label_bg": "Депозит",
        "description_en": "Client paid the deposit, vehicle search/purchase begins.",
        "description_uk": "Клієнт сплатив депозит, починається пошук/купівля авто.",
        "description_ru": "Клиент оплатил депозит, начинается поиск/покупка авто.",
        "description_bg": "Клиентът плати депозита, започва търсене/закупуване.",
        "sla_days": 3,
        "icon": "Wallet",
        "key_actions": ["deposit_received", "deposit_receipt_sent", "search_started"],
        "recommended_next_en": "Move to vehicle search / purchase workflow.",
        "recommended_next_uk": "Перейти до пошуку та покупки авто.",
        "recommended_next_ru": "Перейти к поиску и покупке авто.",
        "recommended_next_bg": "Преминете към търсене и закупуване на автомобила.",
    },
    {
        "key": "sale",
        "label_en": "Sale",
        "label_uk": "Продаж",
        "label_ru": "Продажа",
        "label_bg": "Продажба",
        "description_en": "Vehicle purchased and assigned to the client.",
        "description_uk": "Авто куплено та закріплено за клієнтом.",
        "description_ru": "Автомобиль куплен и закреплён за клиентом.",
        "description_bg": "Автомобилът е закупен и присвоен на клиента.",
        "sla_days": 14,
        "icon": "ShoppingBag",
        "key_actions": ["vehicle_purchased", "sale_record_created", "payment_plan_confirmed"],
        "recommended_next_en": "Start the post-purchase vehicle journey roadmap.",
        "recommended_next_uk": "Запустити roadmap «Vehicle journey» (післяпродажний).",
        "recommended_next_ru": "Запустить roadmap «Vehicle journey» (постпродажный).",
        "recommended_next_bg": "Стартирайте roadmap-а след покупка (vehicle journey).",
    },
    {
        "key": "deal_completed",
        "label_en": "Deal completed",
        "label_uk": "Завершена угода",
        "label_ru": "Завершённая сделка",
        "label_bg": "Завършена сделка",
        "description_en": "All payments settled, car delivered, deal closed.",
        "description_uk": "Всі платежі виконані, авто передане, угода закрита.",
        "description_ru": "Все платежи выполнены, авто передано, сделка закрыта.",
        "description_bg": "Всички плащания приключени, автомобилът е предаден, сделката е затворена.",
        "sla_days": 7,
        "icon": "Trophy",
        "key_actions": ["payment_balanced", "handover_done", "review_collected"],
        "recommended_next_en": "Ask for a review and add to retention loop.",
        "recommended_next_uk": "Запросити відгук і додати до програми лояльності.",
        "recommended_next_ru": "Запросить отзыв и добавить в программу лояльности.",
        "recommended_next_bg": "Поискайте отзив и добавете в програмата за лоялност.",
    },
]


# Pipeline type registry — easy to extend in the future.
PIPELINE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "vehicle_journey": DEFAULT_STAGES,
    "sales_pipeline":  SALES_PIPELINE_STAGES,
}
DEFAULT_PIPELINE_TYPE = "vehicle_journey"


def template_for(pipeline_type: Optional[str]) -> List[Dict[str, Any]]:
    return PIPELINE_TEMPLATES.get((pipeline_type or DEFAULT_PIPELINE_TYPE).lower(), DEFAULT_STAGES)

# Allowed status values for a stage
STAGE_STATUSES = {"pending", "in_progress", "done", "blocked", "skipped"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def build_default_stages(pipeline_type: str = DEFAULT_PIPELINE_TYPE) -> List[Dict[str, Any]]:
    """Return a fresh copy of the canonical stage list for the given pipeline type.

    UAT Enhancement #4 — each stage instance also carries:
      * ``checklist`` — list of {key, label, done, done_at, done_by}
        derived from the template ``key_actions``.
      * ``comment``  — free-text manager note for this stage.
      * ``risks``    — list of {id, label, severity, noted_at, noted_by}.
      * ``transitions`` — chronological history of status changes.
    """
    tpl = template_for(pipeline_type)
    out: List[Dict[str, Any]] = []
    for stg in tpl:
        # Build checklist from key_actions (sales_pipeline template only;
        # vehicle_journey keeps an empty list — also fine).
        actions = stg.get("key_actions") or []
        checklist = [{
            "key": a,
            "label": a.replace("_", " ").capitalize(),
            "done": False,
            "done_at": None,
            "done_by": None,
        } for a in actions]
        out.append({
            **stg,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "deadline_at": None,
            "eta": None,
            "sla_breached": False,
            "notes": [],
            "checklist": checklist,
            "comment": None,
            "risks": [],
            "transitions": [],
            "updated_by": None,
            "updated_by_email": None,
        })
    return out


def _recalc_progress(stages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute roadmap-level summary fields from the stage list."""
    if not stages:
        return {"progress_pct": 0, "current_stage": None, "current_stage_index": -1, "overall_status": "pending"}

    total = len(stages)
    done = sum(1 for s in stages if (s.get("status") or "").lower() in {"done", "completed", "skipped"})
    pct = round((done / total) * 100)

    # find first non-done stage
    current_idx = -1
    for i, s in enumerate(stages):
        if (s.get("status") or "").lower() not in {"done", "completed", "skipped"}:
            current_idx = i
            break

    if current_idx == -1:
        overall = "completed"
        current_stage = None
    else:
        st = (stages[current_idx].get("status") or "pending").lower()
        if st == "blocked":
            overall = "blocked"
        elif done == 0:
            overall = "pending"
        else:
            overall = "in_progress"
        current_stage = stages[current_idx]["key"]

    return {
        "progress_pct": pct,
        "current_stage": current_stage,
        "current_stage_index": current_idx,
        "overall_status": overall,
    }


def _recalc_sla_breaches(stages: List[Dict[str, Any]]) -> None:
    """Mark `sla_breached` on every stage that is in progress past its deadline."""
    now = _now()
    for s in stages:
        st = (s.get("status") or "").lower()
        deadline = _parse_iso(s.get("deadline_at"))
        if st in {"in_progress", "pending"} and deadline and now > deadline:
            s["sla_breached"] = True
        else:
            # Once done/skipped/blocked, do NOT recompute breach. Done == done.
            if st in {"done", "completed", "skipped"}:
                s["sla_breached"] = False


# ---------------------------------------------------------------------
# Repository-style I/O helpers
# ---------------------------------------------------------------------


def _new_id() -> str:
    return f"rm_{uuid.uuid4().hex[:14]}"


async def create_roadmap(
    *,
    customer_id: str,
    title: Optional[str] = None,
    vehicle: Optional[Dict[str, Any]] = None,
    deal_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    order_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    manager_email: Optional[str] = None,
    initial_stage: Optional[str] = None,
    pipeline_type: str = DEFAULT_PIPELINE_TYPE,
    created_by: Optional[str] = None,
    created_by_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a brand-new roadmap.

    ``pipeline_type`` selects the stage template (``vehicle_journey`` or
    ``sales_pipeline``). ``initial_stage`` lets the caller bootstrap the
    roadmap at a more advanced point. When omitted, the first stage of
    the chosen template is used.
    """
    db = get_db()
    now = _now()
    pipeline_type = (pipeline_type or DEFAULT_PIPELINE_TYPE).lower()
    if pipeline_type not in PIPELINE_TEMPLATES:
        pipeline_type = DEFAULT_PIPELINE_TYPE
    stages = build_default_stages(pipeline_type)

    tpl = template_for(pipeline_type)
    first_key = (tpl[0] or {}).get("key") if tpl else None
    initial_stage = (initial_stage or first_key or "").lower()

    # Pre-mark stages up to `initial_stage` as done
    if initial_stage and initial_stage != first_key:
        for s in stages:
            if s["key"] == initial_stage:
                s["status"] = "in_progress"
                s["started_at"] = _iso(now)
                s["deadline_at"] = _iso(now + timedelta(days=int(s.get("sla_days") or 0)))
                s.setdefault("transitions", []).append({
                    "at": _iso(now), "by": created_by_email or created_by,
                    "from": None, "to": "in_progress", "reason": "initial",
                })
                break
            s["status"] = "done"
            s["started_at"] = _iso(now)
            s["completed_at"] = _iso(now)
            s.setdefault("transitions", []).append({
                "at": _iso(now), "by": created_by_email or created_by,
                "from": None, "to": "done", "reason": "pre_marked",
            })
    else:
        # First stage starts immediately
        first = stages[0]
        first["status"] = "in_progress"
        first["started_at"] = _iso(now)
        first["deadline_at"] = _iso(now + timedelta(days=int(first.get("sla_days") or 0)))
        first.setdefault("transitions", []).append({
            "at": _iso(now), "by": created_by_email or created_by,
            "from": None, "to": "in_progress", "reason": "initial",
        })

    summary = _recalc_progress(stages)

    doc = {
        "id": _new_id(),
        "pipeline_type": pipeline_type,
        "customerId": customer_id,
        "customer_id": customer_id,  # snake_case alias for query flexibility
        "dealId": deal_id,
        "invoiceId": invoice_id,
        "orderId": order_id,
        "managerId": manager_id,
        "managerEmail": manager_email,
        "title": title or (vehicle or {}).get("name") or (
            "Sales pipeline" if pipeline_type == "sales_pipeline" else "Vehicle roadmap"
        ),
        "vehicle": vehicle or {},
        "stages": stages,
        "status": summary["overall_status"],
        "progress_pct": summary["progress_pct"],
        "current_stage": summary["current_stage"],
        "current_stage_index": summary["current_stage_index"],
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "created_by": created_by,
        "created_by_email": created_by_email,
    }
    await db[COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_customer_roadmaps(customer_id: str) -> List[Dict[str, Any]]:
    db = get_db()
    flt = {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]}
    cursor = db[COLLECTION].find(flt, {"_id": 0}).sort("created_at", -1)
    items = await cursor.to_list(length=200)
    for it in items:
        _recalc_sla_breaches(it.get("stages") or [])
    return items


async def get_roadmap(roadmap_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await db[COLLECTION].find_one({"id": roadmap_id}, {"_id": 0})
    if doc:
        _recalc_sla_breaches(doc.get("stages") or [])
    return doc


async def update_stage(
    roadmap_id: str,
    stage_key: str,
    *,
    status: Optional[str] = None,
    eta: Optional[str] = None,
    sla_days: Optional[int] = None,
    note_body: Optional[str] = None,
    comment: Optional[str] = None,
    updated_by: Optional[str] = None,
    updated_by_email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update a single stage's status / eta / sla / note / comment. Recalculates rolling summary."""
    db = get_db()
    doc = await db[COLLECTION].find_one({"id": roadmap_id})
    if not doc:
        return None
    stages = doc.get("stages") or []
    target = next((s for s in stages if s.get("key") == stage_key), None)
    if not target:
        return None

    now = _now()
    if status is not None:
        status = status.lower()
        if status not in STAGE_STATUSES:
            raise ValueError(f"Invalid status '{status}', expected one of {STAGE_STATUSES}")
        prev_status = (target.get("status") or "pending").lower()
        target["status"] = status
        if status == "in_progress":
            if not target.get("started_at"):
                target["started_at"] = _iso(now)
            target["completed_at"] = None
            target["deadline_at"] = _iso(now + timedelta(days=int(target.get("sla_days") or 0)))
        elif status in {"done", "completed"}:
            target["status"] = "done"
            if not target.get("started_at"):
                target["started_at"] = _iso(now)
            target["completed_at"] = _iso(now)
            target["sla_breached"] = False
        elif status == "skipped":
            target["completed_at"] = _iso(now)
            target["sla_breached"] = False
        elif status == "pending":
            target["started_at"] = None
            target["completed_at"] = None
            target["deadline_at"] = None
            target["sla_breached"] = False
        # blocked: keep existing started_at/deadline_at so SLA still ticks

        # Record stage-level transition history (UAT Enhancement #4)
        target.setdefault("transitions", []).append({
            "at": _iso(now),
            "by": updated_by_email or updated_by,
            "from": prev_status,
            "to": target["status"],
        })

        # Auto-advance the next stage to in_progress when the current goes done
        if target["status"] == "done":
            idx = next((i for i, s in enumerate(stages) if s.get("key") == stage_key), -1)
            if idx >= 0 and idx + 1 < len(stages):
                nxt = stages[idx + 1]
                if (nxt.get("status") or "").lower() == "pending":
                    nxt["status"] = "in_progress"
                    nxt["started_at"] = _iso(now)
                    nxt["deadline_at"] = _iso(now + timedelta(days=int(nxt.get("sla_days") or 0)))
                    nxt.setdefault("transitions", []).append({
                        "at": _iso(now),
                        "by": updated_by_email or updated_by,
                        "from": "pending",
                        "to": "in_progress",
                        "reason": "auto_advance",
                    })

    if sla_days is not None:
        target["sla_days"] = int(sla_days)
        # If currently in progress, recompute deadline from started_at
        started = _parse_iso(target.get("started_at"))
        if started:
            target["deadline_at"] = _iso(started + timedelta(days=int(sla_days)))

    if eta is not None:
        target["eta"] = eta or None

    if comment is not None:
        target["comment"] = comment.strip() or None

    if note_body:
        note = {
            "id": str(uuid.uuid4()),
            "body": note_body,
            "author": updated_by_email or updated_by,
            "created_at": _iso(now),
        }
        target.setdefault("notes", []).append(note)

    target["updated_by"] = updated_by
    target["updated_by_email"] = updated_by_email

    _recalc_sla_breaches(stages)
    summary = _recalc_progress(stages)

    await db[COLLECTION].update_one(
        {"id": roadmap_id},
        {"$set": {
            "stages": stages,
            "status": summary["overall_status"],
            "progress_pct": summary["progress_pct"],
            "current_stage": summary["current_stage"],
            "current_stage_index": summary["current_stage_index"],
            "updated_at": _iso(now),
        }},
    )

    fresh = await db[COLLECTION].find_one({"id": roadmap_id}, {"_id": 0})

    # Sprint 4 — drop a timeline event so Customer360 picks it up
    try:
        from app.services import customer_timeline
        cust_id = (fresh or {}).get("customerId") or (fresh or {}).get("customer_id")
        if cust_id:
            if (fresh or {}).get("status") == "completed":
                kind = "roadmap_completed"
                title = f"Roadmap completed: {fresh.get('title') or ''}"
            else:
                kind = "roadmap_updated"
                title = f"Roadmap stage '{stage_key}' → {(fresh or {}).get('current_stage') or stage_key}"
            await customer_timeline.record_event(
                customer_id=cust_id,
                kind=kind,
                title=title,
                ref={"collection": "customer_roadmaps", "id": roadmap_id},
                actor={"id": updated_by, "email": updated_by_email},
                meta={
                    "stage_key": stage_key,
                    "stage_status": next((s.get("status") for s in (fresh or {}).get("stages") or [] if s.get("key") == stage_key), None),
                    "progress_pct": (fresh or {}).get("progress_pct"),
                },
            )
    except Exception:
        logger.exception("[customer_roadmap] timeline event failed")

    return fresh


async def delete_roadmap(roadmap_id: str) -> bool:
    """Soft delete: mark status=cancelled, keep document."""
    db = get_db()
    r = await db[COLLECTION].update_one(
        {"id": roadmap_id},
        {"$set": {"status": "cancelled", "updated_at": _iso(_now())}},
    )
    return r.matched_count > 0


async def find_existing_for_order(customer_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return await db[COLLECTION].find_one(
        {"$and": [
            {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
            {"orderId": order_id},
        ]},
        {"_id": 0},
    )


async def auto_create_from_order(
    *,
    customer_id: str,
    order: Dict[str, Any],
    invoice: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Best-effort: spawn a roadmap right after a paid order is created.

    Idempotent: a second call with the same order id returns the existing
    roadmap rather than duplicating.
    """
    if not customer_id or not order or not order.get("id"):
        return None
    existing = await find_existing_for_order(customer_id, order["id"])
    if existing:
        return existing

    inv = invoice or {}
    # Try to extract a reasonable vehicle descriptor from the order's items
    vehicle: Dict[str, Any] = {}
    items = order.get("items") or inv.get("items") or []
    if items:
        first = items[0]
        vehicle["name"] = first.get("name") or first.get("service_name")
    vehicle.setdefault("vin", inv.get("vin") or order.get("vin"))

    return await create_roadmap(
        customer_id=customer_id,
        vehicle=vehicle,
        deal_id=inv.get("dealId") or order.get("dealId"),
        invoice_id=inv.get("id") or order.get("invoiceId"),
        order_id=order["id"],
        manager_id=order.get("managerId"),
        manager_email=order.get("managerEmail"),
        # Once the invoice is paid we can already mark stages 1+2 as done
        # (we found the car + payment processed). Customer journey starts
        # at "delivery_europe".
        initial_stage="delivery_europe",
        created_by="system",
        created_by_email="system@bibi.cars",
    )


# ---------------------------------------------------------------------
# Analytics helpers (Team Lead + Master Admin)
# ---------------------------------------------------------------------


async def analytics_summary(
    *,
    manager_id: Optional[str] = None,
    team_manager_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    db = get_db()
    flt: Dict[str, Any] = {}
    if manager_id:
        flt["managerId"] = manager_id
    elif team_manager_ids:
        flt["managerId"] = {"$in": team_manager_ids}

    items = await db[COLLECTION].find(flt, {"_id": 0}).to_list(length=2000)
    # Recompute breaches for accurate live reading
    for it in items:
        _recalc_sla_breaches(it.get("stages") or [])

    by_stage: Dict[str, int] = {s["key"]: 0 for s in DEFAULT_STAGES}
    sla_breaches = 0
    completed = 0
    in_progress = 0
    blocked = 0
    pending = 0
    avg_pct = 0

    for r in items:
        st = (r.get("status") or "").lower()
        if st == "completed":
            completed += 1
        elif st == "in_progress":
            in_progress += 1
        elif st == "blocked":
            blocked += 1
        else:
            pending += 1
        cur = r.get("current_stage")
        if cur and cur in by_stage:
            by_stage[cur] += 1
        for s in (r.get("stages") or []):
            if s.get("sla_breached"):
                sla_breaches += 1
        avg_pct += int(r.get("progress_pct") or 0)

    if items:
        avg_pct = round(avg_pct / len(items))

    return {
        "total": len(items),
        "completed": completed,
        "in_progress": in_progress,
        "blocked": blocked,
        "pending": pending,
        "avg_progress_pct": avg_pct,
        "sla_breaches": sla_breaches,
        "by_stage": by_stage,
        "items": items,
    }


__all__ = [
    "DEFAULT_STAGES",
    "SALES_PIPELINE_STAGES",
    "PIPELINE_TEMPLATES",
    "DEFAULT_PIPELINE_TYPE",
    "template_for",
    "STAGE_STATUSES",
    "build_default_stages",
    "create_roadmap",
    "list_customer_roadmaps",
    "get_roadmap",
    "update_stage",
    "toggle_checklist_item",
    "add_stage_risk",
    "remove_stage_risk",
    "delete_roadmap",
    "find_existing_for_order",
    "auto_create_from_order",
    "analytics_summary",
    "compute_customer_indicators",
]


# ---------------------------------------------------------------------
# UAT Enhancement #4 — Stage-level checklist / risks + customer indicators
# ---------------------------------------------------------------------


async def toggle_checklist_item(
    roadmap_id: str,
    stage_key: str,
    item_key: str,
    *,
    done: bool,
    by_id: Optional[str] = None,
    by_email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Flip a single checklist item on a stage and persist."""
    db = get_db()
    doc = await db[COLLECTION].find_one({"id": roadmap_id})
    if not doc:
        return None
    stages = doc.get("stages") or []
    target = next((s for s in stages if s.get("key") == stage_key), None)
    if not target:
        return None
    checklist = target.get("checklist") or []
    item = next((c for c in checklist if c.get("key") == item_key), None)
    if not item:
        return None
    now = _now()
    item["done"] = bool(done)
    item["done_at"] = _iso(now) if done else None
    item["done_by"] = (by_email or by_id) if done else None
    target["checklist"] = checklist
    target["updated_by"] = by_id
    target["updated_by_email"] = by_email
    await db[COLLECTION].update_one(
        {"id": roadmap_id},
        {"$set": {"stages": stages, "updated_at": _iso(now)}},
    )
    return await db[COLLECTION].find_one({"id": roadmap_id}, {"_id": 0})


async def add_stage_risk(
    roadmap_id: str,
    stage_key: str,
    *,
    label: str,
    severity: str = "medium",
    by_id: Optional[str] = None,
    by_email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Append a risk note to a stage."""
    db = get_db()
    severity = (severity or "medium").lower()
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    doc = await db[COLLECTION].find_one({"id": roadmap_id})
    if not doc:
        return None
    stages = doc.get("stages") or []
    target = next((s for s in stages if s.get("key") == stage_key), None)
    if not target:
        return None
    now = _now()
    risk = {
        "id": str(uuid.uuid4()),
        "label": (label or "").strip(),
        "severity": severity,
        "noted_at": _iso(now),
        "noted_by": by_email or by_id,
    }
    if not risk["label"]:
        raise ValueError("Risk label is required")
    target.setdefault("risks", []).append(risk)
    await db[COLLECTION].update_one(
        {"id": roadmap_id},
        {"$set": {"stages": stages, "updated_at": _iso(now)}},
    )
    return await db[COLLECTION].find_one({"id": roadmap_id}, {"_id": 0})


async def remove_stage_risk(
    roadmap_id: str,
    stage_key: str,
    risk_id: str,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    doc = await db[COLLECTION].find_one({"id": roadmap_id})
    if not doc:
        return None
    stages = doc.get("stages") or []
    target = next((s for s in stages if s.get("key") == stage_key), None)
    if not target:
        return None
    target["risks"] = [r for r in (target.get("risks") or []) if r.get("id") != risk_id]
    await db[COLLECTION].update_one(
        {"id": roadmap_id},
        {"$set": {"stages": stages, "updated_at": _iso(_now())}},
    )
    return await db[COLLECTION].find_one({"id": roadmap_id}, {"_id": 0})


async def compute_customer_indicators(customer_id: str) -> Dict[str, Any]:
    """Compute the small status badges shown on the Customer card.

    Returns booleans + counts for:
      * has_open_task / has_overdue_task
      * had_meeting
      * has_deposit / has_sale / has_contract
      * risk_count (sum of risks across all sales_pipeline roadmaps)
      * roadmap_progress_pct (highest active roadmap)
    """
    db = get_db()
    now = _now()

    # Tasks
    open_task = await db.tasks.find_one(
        {"$or": [{"customer_id": customer_id}, {"customerId": customer_id}],
         "status": {"$nin": ["done", "completed", "cancelled"]}},
        {"_id": 0, "id": 1, "due_at": 1, "dueAt": 1, "status": 1},
    )
    overdue_task = False
    if open_task:
        due = _parse_iso(open_task.get("due_at") or open_task.get("dueAt"))
        if due and now > due:
            overdue_task = True

    # Meetings
    had_meeting = bool(await db.meetings.find_one(
        {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
        {"_id": 0, "id": 1},
    ))

    # Financial entities
    has_deposit = bool(await db.legal_deposits.find_one(
        {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}],
         "status": {"$nin": ["cancelled"]}},
        {"_id": 0, "id": 1},
    ))
    has_sale = bool(await db.sales.find_one(
        {"customerId": customer_id, "status": {"$nin": ["cancelled"]}},
        {"_id": 0, "id": 1},
    ))
    has_contract = bool(await db.contracts_lifecycle.find_one(
        {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}]},
        {"_id": 0, "id": 1},
    )) or bool(await db.contracts.find_one(
        {"customerId": customer_id},
        {"_id": 0, "id": 1},
    ))

    # Roadmap risks + best progress
    risk_count = 0
    best_progress = 0
    cursor = db[COLLECTION].find(
        {"$or": [{"customerId": customer_id}, {"customer_id": customer_id}],
         "status": {"$ne": "cancelled"}},
        {"_id": 0, "stages": 1, "progress_pct": 1, "pipeline_type": 1, "status": 1},
    )
    async for rm in cursor:
        for s in (rm.get("stages") or []):
            risk_count += len(s.get("risks") or [])
        if (rm.get("progress_pct") or 0) > best_progress:
            best_progress = int(rm.get("progress_pct") or 0)

    return {
        "customerId": customer_id,
        "has_open_task": bool(open_task),
        "has_overdue_task": overdue_task,
        "had_meeting": had_meeting,
        "has_deposit": has_deposit,
        "has_sale": has_sale,
        "has_contract": has_contract,
        "risk_count": risk_count,
        "roadmap_progress_pct": best_progress,
        "computed_at": _iso(now),
    }
