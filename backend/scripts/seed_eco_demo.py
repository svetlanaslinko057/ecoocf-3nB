"""
ECO demo data seeder — idempotent.

Populates the generic CRM collections (db.deals / db.contracts / db.payments /
db.leads / db.customers) and a few waste_pickups with REALISTIC Ukrainian
waste-recycling business data (UAH), so the analytics dashboards
(Finance360 / Operations360 / Executive Center / Contract360 / Deal360) show
meaningful numbers instead of zeros.

All seeded docs carry  demo=True  → re-running wipes + re-creates them only,
never touching real business data.

Usage:
    cd /app/backend && python -m scripts.seed_eco_demo
"""
import os
import sys
import random
import uuid
from datetime import datetime, timezone, timedelta

from pymongo import MongoClient

random.seed(42)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

UTC = timezone.utc
NOW = datetime.now(UTC)


def days_ago(n):
    return NOW - timedelta(days=n)


def uid(p):
    return f"{p}_{uuid.uuid4().hex[:12]}"


# ── canonical ECO deal funnel (kept in sync with manager cabinet DEAL_STAGES) ──
DEAL_STAGES = ["new", "negotiation", "contract", "pickup", "utilization", "won", "lost"]
STAGE_PROB = {
    "new": 0.10, "negotiation": 0.30, "contract": 0.55,
    "pickup": 0.75, "utilization": 0.90, "won": 1.0, "lost": 0.0,
}

COMPANIES = [
    ("ТОВ «Київмедскло»", "Медичні відходи"),
    ("ПрАТ «ДніпроХімПром»", "Хімічні реагенти"),
    ("ТОВ «АвтоПласт Захід»", "Відпрацьовані мастила"),
    ("КП «Чисте Місто Львів»", "Люмінесцентні лампи"),
    ("ТОВ «Агросвіт Поділля»", "Агрохімічна тара"),
    ("ПАТ «Запоріжсталь-Еко»", "Металургійні шлаки"),
    ("ТОВ «Фарма Логістик»", "Фармацевтичні відходи"),
    ("ТОВ «ЕнергоСервіс Одеса»", "Нафтошлами"),
    ("ТОВ «ТехноРесайкл»", "Електронний брухт"),
    ("ТОВ «БудЕкоСервіс»", "Будівельні відходи"),
]

CONTACTS = [
    "Олена Коваленко", "Андрій Мельник", "Сергій Бондаренко", "Наталія Шевчук",
    "Ігор Ткаченко", "Марина Кравець", "Олександр Поліщук", "Вікторія Романюк",
    "Дмитро Савченко", "Тетяна Гнатюк",
]


def get_managers(db):
    rows = list(db.staff.find({"role": {"$in": ["admin", "manager"]}}, {"_id": 0, "id": 1, "role": 1, "name": 1}))
    if not rows:
        # Fallback ids matching the env-seeded staff convention.
        rows = [{"id": "staff_admin_seed", "role": "admin", "name": "Admin"},
                {"id": "staff_manager_seed", "role": "manager", "name": "Manager"}]
    return rows


def wipe_demo(db):
    for coll in ("deals", "contracts", "payments", "leads", "customers"):
        db[coll].delete_many({"demo": True})
    db.waste_pickups.delete_many({"demo": True})


def seed(db):
    managers = get_managers(db)
    mgr_ids = [m["id"] for m in managers]
    company_id_map = {}

    # Ensure each demo company also exists as a waste_company (for ops linkage)
    for name, _wt in COMPANIES:
        existing = db.waste_companies.find_one({"name": name})
        if existing:
            company_id_map[name] = existing["id"]
        else:
            cid = uid("co")
            db.waste_companies.insert_one({
                "id": cid, "name": name, "source": "demo",
                "assigned_manager_id": random.choice(mgr_ids),
                "status": "active", "demo": True,
                "created_at": days_ago(random.randint(40, 120)).isoformat(),
                "updated_at": NOW.isoformat(),
            })
            company_id_map[name] = cid

    deals = []
    contracts = []
    payments = []

    # Distribution of deals across stages (a realistic funnel).
    stage_plan = (
        ["new"] * 5 + ["negotiation"] * 5 + ["contract"] * 4 +
        ["pickup"] * 3 + ["utilization"] * 3 + ["won"] * 7 + ["lost"] * 3
    )
    random.shuffle(stage_plan)

    for i, stage in enumerate(stage_plan):
        name, wt = COMPANIES[i % len(COMPANIES)]
        cid = company_id_map[name]
        mgr = random.choice(mgr_ids)
        created = days_ago(random.randint(2, 115))
        amount = round(random.uniform(45_000, 920_000), 2)
        cost = round(amount * random.uniform(0.52, 0.74), 2)
        contact = CONTACTS[i % len(CONTACTS)]
        # expected close: future for open deals, past for closed
        if stage in ("won", "lost"):
            exp_close = created + timedelta(days=random.randint(10, 45))
        else:
            exp_close = NOW + timedelta(days=random.randint(5, 80))
        deal_id = uid("deal")
        deals.append({
            "id": deal_id, "managerId": mgr, "company_id": cid,
            "title": f"Утилізація — {wt}", "customerName": contact, "company": name,
            "amount": amount, "cost": cost, "currency": "UAH",
            "stage": stage, "wasteType": wt,
            "probability": STAGE_PROB[stage],
            "expected_close": exp_close.isoformat(),
            "created_at": created, "updated_at": NOW, "demo": True,
        })

        # Contracts for deals that reached at least the contract stage.
        if stage in ("contract", "pickup", "utilization", "won"):
            if stage == "contract":
                cstatus = random.choice(["draft", "pending_approval", "sent"])
            elif stage in ("pickup", "utilization"):
                cstatus = random.choice(["signed", "active"])
            else:  # won
                cstatus = random.choice(["active", "archived"])
            c_created = created + timedelta(days=random.randint(1, 7))
            due_sign = c_created + timedelta(days=10)
            signed_at = None
            if cstatus in ("signed", "active", "archived"):
                signed_at = (c_created + timedelta(days=random.randint(2, 9)))
            # payment progress
            if cstatus == "archived":
                paid = amount
            elif cstatus == "active":
                paid = round(amount * random.uniform(0.3, 0.9), 2)
            elif cstatus == "signed":
                paid = round(amount * random.uniform(0.0, 0.5), 2)
            else:
                paid = 0.0
            con_id = uid("con")
            contracts.append({
                "id": con_id, "number": f"ECO-{created.year}-{1000 + i}",
                "deal_id": deal_id, "company_id": cid, "company": name,
                "customerId": contact, "customer_name": contact,
                "status": cstatus, "value": amount, "amount": amount, "cost": cost,
                "paid_amount": paid, "currency": "UAH", "wasteType": wt,
                "signed_at": signed_at.isoformat() if signed_at else None,
                "due_signature_at": due_sign.isoformat(),
                "created_at": c_created, "updated_at": NOW, "demo": True,
            })
            # Income payment(s)
            if paid > 0:
                payments.append({
                    "id": uid("pay"), "deal_id": deal_id, "contract_id": con_id,
                    "company": name, "customer_name": contact, "kind": "income",
                    "amount": paid, "status": "paid", "currency": "UAH",
                    "date": (signed_at or c_created).isoformat(),
                    "created_at": (signed_at or c_created), "demo": True,
                })
            # Cost / expense payment
            payments.append({
                "id": uid("pay"), "deal_id": deal_id, "contract_id": con_id,
                "company": name, "customer_name": contact, "kind": "expense",
                "amount": round(cost * random.uniform(0.4, 1.0), 2), "status": "paid",
                "currency": "UAH", "date": c_created.isoformat(),
                "created_at": c_created, "demo": True,
            })

    if deals:
        db.deals.insert_many(deals)
    if contracts:
        db.contracts.insert_many(contracts)
    if payments:
        db.payments.insert_many(payments)

    # ── Cold leads ───────────────────────────────────────────────────────────
    leads = []
    lead_stages = ["lead", "new", "qualifying", "negotiation"]
    for i in range(9):
        name, wt = COMPANIES[(i + 3) % len(COMPANIES)]
        leads.append({
            "id": uid("lead"), "managerId": random.choice(mgr_ids),
            "name": CONTACTS[(i + 2) % len(CONTACTS)], "company": f"{name} (потенційний)",
            "phone": f"+38067{random.randint(1000000, 9999999)}",
            "email": f"lead{i}@example.ua", "wasteType": wt,
            "budgetEur": round(random.uniform(30_000, 400_000), 2),
            "stage": random.choice(lead_stages), "status": "new",
            "source": random.choice(["site", "call", "referral"]),
            "created_at": days_ago(random.randint(1, 30)), "updated_at": NOW, "demo": True,
        })
    if leads:
        db.leads.insert_many(leads)

    # ── Customers (B2B) ──────────────────────────────────────────────────────
    customers = []
    for i in range(6):
        name, _wt = COMPANIES[i]
        customers.append({
            "id": uid("cust"), "companyName": name, "name": CONTACTS[i],
            "email": f"client{i}@{['kyiv','dnipro','lviv','odesa','zp','poltava'][i]}.ua",
            "managerId": random.choice(mgr_ids), "status": "active",
            "created_at": days_ago(random.randint(20, 110)), "updated_at": NOW, "demo": True,
        })
    if customers:
        db.customers.insert_many(customers)

    # ── Waste pickups (for Operations SLA / in-transit / overdue) ────────────
    pickups = []
    pk_statuses = ["planning", "route", "driver_assigned", "picked_up", "delivered"]
    for i in range(10):
        name, _wt = COMPANIES[i % len(COMPANIES)]
        cid = company_id_map[name]
        status = pk_statuses[i % len(pk_statuses)]
        # a couple of overdue (scheduled in the past, not delivered)
        if i in (1, 4):
            scheduled = days_ago(random.randint(2, 8))
            status = random.choice(["route", "driver_assigned"])
        else:
            scheduled = NOW + timedelta(days=random.randint(1, 14))
        pickups.append({
            "id": uid("pu"), "number": f"PU-{NOW.year}-{2000 + i}",
            "company_id": cid, "status": status,
            "weight_kg": round(random.uniform(200, 8000), 1),
            "scheduled_at": scheduled.isoformat(),
            "created_at": days_ago(random.randint(1, 20)).isoformat(),
            "updated_at": NOW.isoformat(), "demo": True,
        })
    if pickups:
        db.waste_pickups.insert_many(pickups)

    return {
        "deals": len(deals), "contracts": len(contracts), "payments": len(payments),
        "leads": len(leads), "customers": len(customers), "pickups": len(pickups),
        "managers": len(mgr_ids),
    }


def main():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    wipe_demo(db)
    stats = seed(db)
    print("[seed_eco_demo] OK:", stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
