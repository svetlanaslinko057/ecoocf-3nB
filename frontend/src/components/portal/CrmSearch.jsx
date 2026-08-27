// CrmSearch — global command/search bar for the operator workspace header.
// Lets staff jump to any CRM block/subsection by typing its name (UA) or a
// keyword. Works on web (inline search box) and mobile (full-width overlay).
import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X, CornerDownLeft, User, Receipt, FileSignature, ClipboardList, Building2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

const GROUP_ICON = { customer: User, invoice: Receipt, contract: FileSignature, request: ClipboardList, company: Building2 };

// Flat index of navigable CRM destinations. `roles` limits visibility.
// `keywords` boost fuzzy matching (synonyms / latin / common terms).
const INDEX = [
  // Огляд / Operations
  { label: "Єдиний центр", section: "Огляд", path: "/app/hub", keywords: "hub єдиний центр unified дашборд огляд командна палітра" },
  { label: "Дашборд", section: "Огляд", path: "/app", keywords: "огляд головна dashboard kpi показники" },
  { label: "Директорський центр", section: "Огляд", path: "/app/executive", roles: ["admin"], keywords: "executive керівник директор аналітика" },
  { label: "Операції", section: "Огляд", path: "/app/operations", keywords: "operations договори вивози акти процеси" },
  { label: "Операції 360", section: "Огляд", path: "/app/operations360", keywords: "operations360 аналітика воронка" },
  // Клієнти та продажі
  { label: "Компанії", section: "Клієнти та продажі", path: "/app/companies", keywords: "клієнти компанії b2b реєстр company" },
  { label: "Ліди", section: "Клієнти та продажі", path: "/app/leads", keywords: "leads потенційні клієнти заявки" },
  { label: "Заявки", section: "Клієнти та продажі", path: "/app/requests", keywords: "requests звернення заявки на вивіз" },
  { label: "Звернення", section: "Клієнти та продажі", path: "/app/inquiries", keywords: "inquiries звернення повідомлення з сайту" },
  // Команда · CRM
  { label: "CRM-хаб", section: "Команда · CRM", path: "/app/crm", keywords: "crm hub хаб" },
  { label: "Центр дій", section: "Команда · CRM", path: "/app/crm/actions", roles: ["admin"], keywords: "actions центр дій інбокс задачі" },
  { label: "Завдання команди", section: "Команда · CRM", path: "/app/crm/tasks", keywords: "tasks завдання задачі нагадування" },
  { label: "Дзвінки команди", section: "Команда · CRM", path: "/app/crm/calls", keywords: "calls дзвінки журнал комунікації" },
  { label: "Ringostat (кол-трекінг)", section: "Команда · CRM", path: "/app/ringostat", roles: ["admin"], keywords: "ringostat call tracking телефонія" },
  { label: "Повідомлення", section: "Команда · CRM", path: "/app/crm/messages", keywords: "messages чат листування" },
  { label: "Сповіщення", section: "Команда · CRM", path: "/app/crm/notifications", keywords: "notifications алерти" },
  // Документи та рахунки
  { label: "Договори 360", section: "Документи та рахунки", path: "/app/contracts", keywords: "contracts договір договори підпис угоди контракт" },
  { label: "Фінанси 360", section: "Документи та рахунки", path: "/app/finance", keywords: "finance фінанси гроші виручка прибуток" },
  { label: "Рахунки", section: "Документи та рахунки", path: "/app/crm/invoices", keywords: "invoices рахунки iban оплата" },
  { label: "Документи", section: "Документи та рахунки", path: "/app/crm/documents", keywords: "documents документи pdf акти" },
  { label: "Файли", section: "Документи та рахунки", path: "/app/crm/files", keywords: "files файли сховище фото" },
  // Каталог · Ліцензії · Тарифи
  { label: "Довідник кодів", section: "Каталог · Ліцензії · Тарифи", path: "/app/directory", keywords: "directory коди відходів довідник" },
  { label: "Каталог відходів", section: "Каталог · Ліцензії · Тарифи", path: "/app/waste-codes", roles: ["admin"], keywords: "waste codes каталог відходи коди" },
  { label: "Ліцензії", section: "Каталог · Ліцензії · Тарифи", path: "/app/licenses", keywords: "licenses ліцензії дозволи" },
  { label: "Тарифи", section: "Каталог · Ліцензії · Тарифи", path: "/app/pricing", keywords: "pricing тарифи ціни прайс" },
  // Контент сайту (admin)
  { label: "Статті блогу", section: "Контент сайту", path: "/app/blog", roles: ["admin"], keywords: "blog блог статті" },
  { label: "Футер сайту", section: "Контент сайту", path: "/app/settings/footer", roles: ["admin"], keywords: "footer футер" },
  { label: "Контакти сайту", section: "Контент сайту", path: "/app/settings/contacts", roles: ["admin"], keywords: "contacts контакти" },
  { label: "Інформація сайту", section: "Контент сайту", path: "/app/info", roles: ["admin"], keywords: "info політика faq відгуки" },
  // Адміністрування (admin)
  { label: "Центр персоналу", section: "Адміністрування", path: "/app/staff", roles: ["admin"], keywords: "staff персонал співробітники команда" },
  { label: "Розподіл лідів", section: "Адміністрування", path: "/app/staff/assignment", roles: ["admin"], keywords: "assignment розподіл лідів призначення" },
  { label: "Налаштування", section: "Адміністрування", path: "/app/settings", roles: ["admin"], keywords: "settings налаштування реквізити iban email cors" },
  { label: "Реквізити для оплати (IBAN)", section: "Адміністрування", path: "/app/settings?section=requisites", roles: ["admin"], keywords: "iban реквізити рахунок оплата банк" },
  { label: "Безпека (2FA)", section: "Адміністрування", path: "/app/cabinet/security", keywords: "security 2fa безпека двофакторна" },
  // Менеджер — особистий кабінет
  { label: "Мій кабінет", section: "Мій кабінет", path: "/app/cabinet", roles: ["manager"], keywords: "cabinet огляд кабінет" },
  { label: "Мої ліди", section: "Мій кабінет", path: "/app/cabinet/leads", roles: ["manager"], keywords: "my leads мої ліди" },
  { label: "Мої угоди", section: "Мій кабінет", path: "/app/cabinet/deals", roles: ["manager"], keywords: "my deals мої угоди" },
  { label: "Мої завдання", section: "Мій кабінет", path: "/app/cabinet/tasks", roles: ["manager"], keywords: "my tasks мої завдання" },
  { label: "Мої дзвінки", section: "Мій кабінет", path: "/app/cabinet/calls", roles: ["manager"], keywords: "my calls мої дзвінки" },
];

const norm = (s) => (s || "").toLowerCase().trim();

function scoreItem(item, q) {
  const label = norm(item.label);
  const sec = norm(item.section);
  const kw = norm(item.keywords);
  if (!q) return 0;
  if (label === q) return 100;
  if (label.startsWith(q)) return 80;
  if (label.includes(q)) return 60;
  if (kw.includes(q)) return 40;
  if (sec.includes(q)) return 25;
  // Inflection-tolerant stem match (Ukrainian word endings differ, e.g.
  // "договір" vs "договори"): compare on a trimmed prefix of the query.
  if (q.length >= 4) {
    const stem = q.slice(0, Math.max(4, q.length - 2));
    if (label.includes(stem) || kw.includes(stem) || sec.includes(stem)) return 35;
  }
  return 0;
}

export default function CrmSearch() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = String(user?.role || "").toLowerCase();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef(null);
  const inputRef = useRef(null);
  const mobileInputRef = useRef(null);

  const items = useMemo(
    () => INDEX.filter((it) => !it.roles || it.roles.includes(role) || role === "admin" || role === "master_admin"),
    [role]
  );

  const results = useMemo(() => {
    const query = norm(q);
    if (!query) return [];
    return items
      .map((it) => ({ it, s: scoreItem(it, query) }))
      .filter((r) => r.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map((r) => r.it);
  }, [q, items]);

  useEffect(() => { setActive(0); }, [q]);

  // ── Live entity search (customers / invoices / contracts / requests / companies)
  const [entityGroups, setEntityGroups] = useState([]);
  const [entityLoading, setEntityLoading] = useState(false);
  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) { setEntityGroups([]); setEntityLoading(false); return; }
    let active = true;
    setEntityLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await api.get("/crm/search", { params: { q: query } });
        if (active) setEntityGroups(r.data?.groups || []);
      } catch { if (active) setEntityGroups([]); }
      finally { if (active) setEntityLoading(false); }
    }, 250);
    return () => { active = false; clearTimeout(t); };
  }, [q]);

  // Flattened, ordered list of ALL selectable results (entities first, then
  // navigation sections) — the single source of truth for keyboard nav.
  const entityItemsFlat = useMemo(
    () => entityGroups.flatMap((g) => (g.items || []).map((it) => ({ ...it, _url: it.customer_360_url || it.url }))),
    [entityGroups]
  );
  const flat = useMemo(
    () => [
      ...entityItemsFlat.map((it) => ({ type: "entity", url: it._url })),
      ...results.map((it) => ({ type: "nav", url: it.path })),
    ],
    [entityItemsFlat, results]
  );
  useEffect(() => { setActive(0); }, [q]);
  useEffect(() => { if (active > flat.length - 1) setActive(0); }, [flat.length, active]);

  const goUrl = useCallback((url) => {
    if (!url) return;
    setOpen(false); setMobileOpen(false); setQ("");
    navigate(url);
  }, [navigate]);

  const EntityResults = () => {
    if (q.trim().length < 2) return null;
    const totalEntities = entityGroups.reduce((n, g) => n + (g.items?.length || 0), 0);
    if (!totalEntities) {
      return entityLoading ? <div className="px-4 py-3 text-xs text-slate-400" data-testid="crm-search-entities-loading">Пошук записів…</div> : null;
    }
    let gi = -1; // running global index across all entity items
    return (
      <div className="border-b border-slate-100" data-testid="crm-search-entities">
        {entityGroups.map((g) => {
          const Icon = GROUP_ICON[g.type] || Search;
          return (
            <div key={g.type} className="py-1">
              <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{g.label}</div>
              {(g.items || []).map((it) => {
                gi += 1; const idx = gi;
                return (
                <button
                  key={`${g.type}-${it.id}`}
                  type="button"
                  onMouseEnter={() => setActive(idx)}
                  onClick={() => goUrl(it.customer_360_url || it.url)}
                  className={`flex w-full items-center gap-3 px-4 py-2 text-left ${idx === active ? "bg-[#F4FBEF]" : "hover:bg-[#F4FBEF]"}`}
                  data-testid="crm-search-entity"
                >
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600"><Icon className="h-3.5 w-3.5" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800">{it.display_label || it.label || it.number || it.id}</span>
                    {(it.number || it.status || it.email) && (
                      <span className="block truncate text-[11px] text-slate-400">{[it.number, it.status, it.email].filter(Boolean).join(" · ")}</span>
                    )}
                  </span>
                  {idx === active && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-[#0E5E3A]" />}
                </button>
                );
              })}
            </div>
          );
        })}
      </div>
    );
  };

  // close on outside click (desktop)
  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const go = useCallback((item) => {
    setOpen(false); setMobileOpen(false); setQ("");
    navigate(item.path);
  }, [navigate]);

  const onKey = (e) => {
    if (!flat.length) { if (e.key === "Escape") { setOpen(false); setMobileOpen(false); } return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, flat.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); const sel = flat[active] || flat[0]; if (sel) goUrl(sel.url); }
    else if (e.key === "Escape") { setOpen(false); setMobileOpen(false); }
  };

  const ResultList = ({ onPick }) => (
    results.length === 0 ? (
      (q.trim().length >= 2 && entityItemsFlat.length > 0) ? null : (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          {q ? "Нічого не знайдено" : "Почніть вводити назву розділу…"}
        </div>
      )
    ) : (
      <ul className="py-1" data-testid="crm-search-results">
        {results.map((it, i) => {
          const gidx = entityItemsFlat.length + i;
          return (
          <li key={it.path}>
            <button
              type="button"
              onMouseEnter={() => setActive(gidx)}
              onClick={() => onPick(it)}
              className={`flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors ${gidx === active ? "bg-[#F4FBEF]" : "hover:bg-slate-50"}`}
              data-testid="crm-search-result"
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-slate-800">{it.label}</span>
                <span className="block truncate text-[11px] uppercase tracking-wide text-slate-400">{it.section}</span>
              </span>
              <CornerDownLeft className={`h-3.5 w-3.5 shrink-0 ${gidx === active ? "text-[#0E5E3A]" : "text-slate-300"}`} />
            </button>
          </li>
          );
        })}
      </ul>
    )
  );

  return (
    <>
      {/* Desktop inline search */}
      <div className="relative hidden sm:block" ref={boxRef} data-testid="crm-search">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 shadow-sm focus-within:border-[#5BC47A] focus-within:ring-2 focus-within:ring-[#5BC47A]/20">
          <Search className="h-4 w-4 shrink-0 text-slate-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => { setQ(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKey}
            placeholder="Пошук по CRM…"
            className="w-44 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400 lg:w-60"
            data-testid="crm-search-input"
          />
          {q && (
            <button type="button" onClick={() => { setQ(""); inputRef.current?.focus(); }} className="text-slate-400 hover:text-slate-600" aria-label="Очистити">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        {open && q && (
          <div className="absolute left-0 right-0 z-50 mt-2 max-h-[70vh] overflow-y-auto rounded-2xl border border-[#0B1A14]/10 bg-white shadow-xl" data-testid="crm-search-panel">
            <EntityResults />
            <ResultList onPick={go} />
          </div>
        )}
      </div>

      {/* Mobile icon trigger */}
      <button
        type="button"
        onClick={() => { setMobileOpen(true); setTimeout(() => mobileInputRef.current?.focus(), 50); }}
        className="flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 sm:hidden"
        aria-label="Пошук по CRM"
        data-testid="crm-search-mobile-trigger"
      >
        <Search className="h-[18px] w-[18px]" />
      </button>

      {/* Mobile full-width overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-[60] bg-black/40 sm:hidden" data-testid="crm-search-mobile-overlay" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-x-0 top-0 rounded-b-2xl bg-white p-3 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2">
              <Search className="h-4 w-4 shrink-0 text-slate-400" />
              <input
                ref={mobileInputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={onKey}
                placeholder="Пошук по CRM…"
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
                data-testid="crm-search-mobile-input"
              />
              <button type="button" onClick={() => setMobileOpen(false)} className="text-slate-400 hover:text-slate-600" aria-label="Закрити">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-2 max-h-[70vh] overflow-y-auto rounded-xl border border-slate-100">
              <EntityResults />
              <ResultList onPick={go} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
