"""
LEAD_STAGES — единый словарь стадий лида.

Закреплено в W1 как защита от расползания сущностей.

Lead → Quote → Request → Converted-to-Deal — это **состояния одной
коллекции `db.leads`**, а не отдельные таблицы. Любая новая «заявка/
расчёт/опportunity» должна укладываться в один из этих стадий
или добавляться сюда централизованно.

⚠️  Не создавать `customer_requests`, `requests_v2`, `customer_quotes` —
ничего такого. Только `db.leads` с полем `stage`.
"""

# Канонический порядок стадий — отражает воронку и используется для
# сегментов в UI `[All] [Lead] [Quote] [Request] [Converted]`.
LEAD_STAGES = (
    "lead",                 # первичный контакт / интерес
    "quote",                # выслан расчёт
    "request",              # клиент подтвердил конкретный запрос
    "converted_to_deal",    # стал сделкой
)

# Алиасы для совместимости со старыми записями.
LEAD_STAGE_ALIASES = {
    None:           "lead",
    "":             "lead",
    "new":          "lead",
    "opportunity":  "request",
    "converted":    "converted_to_deal",
}


def normalize_stage(value: str | None) -> str:
    """Привести любое значение стадии к каноническому виду."""
    v = (value or "").strip().lower()
    if v in LEAD_STAGES:
        return v
    return LEAD_STAGE_ALIASES.get(v, "lead")
