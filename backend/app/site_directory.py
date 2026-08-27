"""
Site directory data: company-suggest registry + editable public contacts.

`company_registry` — a lightweight, locally-seeded directory of well-known
Ukrainian companies/establishments (public names) used to power the
autocomplete on public forms. It is intentionally a *starter* set: the live
endpoint also merges the operator's own `waste_companies`, and the schema is
ready to be enriched from an external registry (Opendatabot / YouControl /
data.gov.ua EDR) once an API key/dataset is configured.

`public_contacts` — the single source of truth for the phone numbers / emails
shown in the header, footer and Contacts page. Editable from the admin portal.
"""
from __future__ import annotations

from typing import Any, Dict, List

# ── Curated starter registry (public company names) ─────────────────────────
# (name, region, kind)  — edrpou intentionally left blank; operators/managers
# attach the official code later. Names are public knowledge.
_RAW_COMPANIES: List[tuple] = [
    # Retail / FMCG
    ("ТОВ «АТБ-Маркет»", "Дніпро", "retail"),
    ("ТОВ «Сільпо-Фуд»", "Київ", "retail"),
    ("ПрАТ «Фоззі Груп»", "Київ", "retail"),
    ("ТОВ «Епіцентр К»", "Київ", "retail"),
    ("ТОВ «Нова Лінія»", "Київ", "retail"),
    ("ТОВ «Ашан Україна Гіпермаркет»", "Київ", "retail"),
    ("ТОВ «МЕТРО Кеш енд Кері Україна»", "Київ", "retail"),
    ("ТОВ «Розетка.УА»", "Київ", "retail"),
    ("ТОВ «Алло»", "Дніпро", "retail"),
    ("ТОВ «Фокстрот»", "Київ", "retail"),
    ("ТОВ «Єва (РУШ)»", "Дніпро", "retail"),
    ("ТОВ «Цитрус Дискаунт»", "Одеса", "retail"),
    # Logistics / post
    ("ТОВ «Нова Пошта»", "Київ", "logistics"),
    ("АТ «Укрпошта»", "Київ", "logistics"),
    ("ТОВ «Міст Експрес»", "Київ", "logistics"),
    ("ТОВ «Делівері»", "Дніпро", "logistics"),
    # Telecom / IT
    ("ПрАТ «Київстар»", "Київ", "telecom"),
    ("ТОВ «Лайфселл»", "Київ", "telecom"),
    ("ПрАТ «ВФ Україна» (Vodafone)", "Київ", "telecom"),
    ("ТОВ «Датагруп»", "Київ", "telecom"),
    ("ТОВ «EPAM Systems»", "Київ", "it"),
    ("ТОВ «SoftServe»", "Львів", "it"),
    ("ТОВ «GlobalLogic Україна»", "Київ", "it"),
    # Banks / finance
    ("АТ КБ «ПриватБанк»", "Дніпро", "finance"),
    ("АТ «Ощадбанк»", "Київ", "finance"),
    ("АТ «Райффайзен Банк»", "Київ", "finance"),
    ("АТ «УкрСиббанк»", "Київ", "finance"),
    ("АТ «ПУМБ»", "Київ", "finance"),
    ("АТ «Монобанк» (Universal Bank)", "Київ", "finance"),
    # Energy / industry
    ("ПрАТ «ДТЕК»", "Київ", "energy"),
    ("НАК «Нафтогаз України»", "Київ", "energy"),
    ("ПАТ «Укрнафта»", "Київ", "energy"),
    ("ТОВ «ОККО»", "Львів", "fuel"),
    ("ТОВ «WOG» (Західна Нафтова Група)", "Луцьк", "fuel"),
    ("ПАТ «Укрзалізниця»", "Київ", "transport"),
    ("ТОВ «Метінвест Холдинг»", "Маріуполь", "metallurgy"),
    ("ПрАТ «АрселорМіттал Кривий Ріг»", "Кривий Ріг", "metallurgy"),
    ("ПрАТ «Інтерпайп НТЗ»", "Дніпро", "metallurgy"),
    ("ПАТ «Запоріжсталь»", "Запоріжжя", "metallurgy"),
    ("ТОВ «Кернел-Трейд»", "Київ", "agro"),
    ("ТОВ «МХП» (Миронівський хлібопродукт)", "Київ", "agro"),
    ("ПрАТ «Астарта-Київ»", "Київ", "agro"),
    ("ТОВ «Нібулон»", "Миколаїв", "agro"),
    # Food / beverage
    ("ПрАТ «Оболонь»", "Київ", "food"),
    ("ТОВ «Карлсберг Україна»", "Запоріжжя", "food"),
    ("ПрАТ «Кока-Кола Беверіджиз Україна»", "Київ", "food"),
    ("ПрАТ «Нестле Україна»", "Київ", "food"),
    ("ТОВ «Рошен»", "Київ", "food"),
    ("ПрАТ «Конті»", "Костянтинівка", "food"),
    ("ТОВ «Лакталіс-Україна»", "Павлоград", "food"),
    ("ПрАТ «Галичина»", "Радехів", "food"),
    # Pharma / medical
    ("ТОВ «Фармак»", "Київ", "pharma"),
    ("Корпорація «Артеріум»", "Київ", "pharma"),
    ("ТОВ «Дарниця»", "Київ", "pharma"),
    ("ТОВ «Аптека Доброго Дня»", "Київ", "pharma"),
    ("ТОВ «Аптека 9-1-1»", "Харків", "pharma"),
    ("ТОВ «Медична мережа Добробут»", "Київ", "medical"),
    ("ТОВ «Сінево Україна»", "Київ", "medical"),
    ("ТОВ «Медлабекспрес»", "Київ", "medical"),
    ("КНП «Київська міська клінічна лікарня №1»", "Київ", "medical"),
    ("ДУ «Інститут серця МОЗ України»", "Київ", "medical"),
    ("ТОВ «Дентал Клінік»", "Київ", "medical"),
    # Auto / service
    ("ТОВ «Богдан-Авто»", "Київ", "auto"),
    ("ТОВ «Атлант-М»", "Київ", "auto"),
    ("ТОВ «Віннер Імпортс Україна»", "Київ", "auto"),
    ("ПрАТ «Єврокар»", "Соломоново", "auto"),
    ("ТОВ «АВТ Баварія»", "Київ", "auto"),
    # Construction / materials
    ("ПрАТ «Київміськбуд»", "Київ", "construction"),
    ("ТОВ «Кнауф Гіпс Київ»", "Київ", "construction"),
    ("ПрАТ «Івано-Франківськцемент»", "Івано-Франківськ", "construction"),
    ("ТОВ «ХенкельБаутехнік (Україна)»", "Вишгород", "construction"),
    # Chemicals
    ("ПрАТ «Азот» (Черкаси)", "Черкаси", "chemicals"),
    ("ПрАТ «Дніпроазот»", "Кам'янське", "chemicals"),
    ("ТОВ «Барва»", "Івано-Франківськ", "chemicals"),
    # HoReCa / generic establishments
    ("Мережа ресторанів «Пузата Хата»", "Київ", "horeca"),
    ("Готель «Прем'єр Палац»", "Київ", "horeca"),
    ("Бізнес-центр «Гуллівер»", "Київ", "office"),
    ("ТРЦ «Lavina Mall»", "Київ", "retail"),
    ("Стоматологічна клініка «Люмі-Дент»", "Київ", "medical"),
    ("Ветеринарна клініка «Лісовий Ветцентр»", "Київ", "veterinary"),
    ("Автосервіс «АТЛ»", "Київ", "auto"),
    ("Друкарня «Юнісофт»", "Харків", "printing"),
    ("Лабораторія «ДІЛА»", "Київ", "medical"),
    ("Завод «Кredens cosmetics»", "Бровари", "chemicals"),
]


def company_seed_docs(gen_id, now_iso) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for name, region, kind in _RAW_COMPANIES:
        docs.append({
            "id": gen_id("creg"),
            "name": name,
            "name_lower": name.lower(),
            "edrpou": "",
            "region": region,
            "kind": kind,
            "source": "seed",
            "created_at": now_iso(),
        })
    return docs


# ── Default editable public contacts (REAL company data; admin-editable) ─────
DEFAULT_CONTACTS: Dict[str, Any] = {
    "id": "public_contacts",
    "phones": [
        {"label": "Гаряча лінія", "value": "+380 66 788 04 45"},
    ],
    "emails": [
        {"label": "Загальний", "value": "Econova2013@ukr.net"},
    ],
    "address": "Україна, Житомирська обл., Звягельський р-н, м. Баранівка, вул. Івана Франка, 104А",
    "working_hours": "Пн–Пт: 9:00–18:00",
    "telegram": "",
    "viber": "",
    "messenger": "",
}
