// CommandPalette — Phase D1.5 (Universal Command Palette, Ctrl/Cmd+K).
// A Notion/Linear-style launcher that unifies: (1) navigation to any admin
// section, (2) quick "create" intents, and (3) LIVE cross-domain data search
// via UnifiedAPI.search. Mounted once globally inside PortalLayout.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search, CornerDownLeft, LayoutDashboard, Building2, Users, ClipboardList,
  Workflow, FileText, Banknote, Leaf, FileStack, HelpCircle, Image as ImageIcon,
  Globe, UsersRound, Settings as SettingsIcon, Plus, ArrowRight, Package,
  Handshake, Truck, ScrollText, BookText,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { UnifiedAPI } from "@/lib/api";

// Icon per unified result type (keeps the palette scannable).
const TYPE_ICON = {
  waste_code: Package, company: Building2, lead: Users, deal: Handshake,
  contract: ScrollText, pickup: Truck, customer: UsersRound,
  content_page: FileText, faq: HelpCircle, media: ImageIcon,
  seo_page: Globe, blog: BookText,
};

// Static command index: navigation + quick-create. `roles` limits visibility.
const COMMANDS = [
  { id: "nav-hub", label: "Єдиний дашборд", hint: "Огляд", icon: LayoutDashboard, path: "/app/hub", kw: "hub dashboard дашборд огляд єдиний" },
  { id: "nav-dash", label: "Операційний дашборд", hint: "Огляд", icon: LayoutDashboard, path: "/app", kw: "dashboard операції kpi" },
  { id: "nav-companies", label: "Компанії", hint: "CRM", icon: Building2, path: "/app/companies", kw: "companies клієнти" },
  { id: "nav-leads", label: "Ліди", hint: "CRM", icon: Users, path: "/app/leads", kw: "leads потенційні" },
  { id: "nav-requests", label: "Заявки", hint: "CRM", icon: ClipboardList, path: "/app/requests", kw: "requests звернення" },
  { id: "nav-crm", label: "CRM-хаб", hint: "CRM", icon: LayoutDashboard, path: "/app/crm", kw: "crm hub" },
  { id: "nav-operations", label: "Операції", hint: "Операції", icon: Workflow, path: "/app/operations", kw: "operations вивози" },
  { id: "nav-contracts", label: "Договори 360", hint: "Документи", icon: ScrollText, path: "/app/contracts", kw: "contracts договори" },
  { id: "nav-finance", label: "Фінанси 360", hint: "Фінанси", icon: Banknote, path: "/app/finance", kw: "finance гроші" },
  { id: "nav-waste", label: "Каталог відходів", hint: "Каталог", icon: Leaf, path: "/app/waste-codes", roles: ["admin"], kw: "waste codes коди" },
  { id: "nav-directory", label: "Довідник кодів", hint: "Каталог", icon: BookText, path: "/app/directory", kw: "directory довідник" },
  { id: "nav-content", label: "Контент-центр", hint: "Контент", icon: FileText, path: "/app/content/pages", roles: ["admin"], kw: "content сторінки cms" },
  { id: "nav-media", label: "Медіа-бібліотека", hint: "Контент", icon: ImageIcon, path: "/app/content/media", roles: ["admin"], kw: "media медіа зображення" },
  { id: "nav-faq", label: "FAQ", hint: "Контент", icon: HelpCircle, path: "/app/content/faq", roles: ["admin"], kw: "faq питання" },
  { id: "nav-seo", label: "SEO Центр", hint: "SEO", icon: Globe, path: "/app/seo", roles: ["admin"], kw: "seo метадані" },
  { id: "nav-staff", label: "Центр персоналу", hint: "Адмін", icon: UsersRound, path: "/app/staff", roles: ["admin"], kw: "staff персонал" },
  { id: "nav-settings", label: "Налаштування", hint: "Адмін", icon: SettingsIcon, path: "/app/settings", roles: ["admin"], kw: "settings налаштування" },
  // Quick-create intents
  { id: "new-request", label: "Нова заявка", hint: "Створити", icon: Plus, path: "/app/requests?new=1", create: true, kw: "нова заявка створити new request" },
  { id: "new-company", label: "Нова компанія", hint: "Створити", icon: Plus, path: "/app/companies?new=1", create: true, kw: "нова компанія new company" },
  { id: "new-page", label: "Нова сторінка", hint: "Створити", icon: Plus, path: "/app/content/pages?new=1", create: true, roles: ["admin"], kw: "нова сторінка new page" },
];

const norm = (s) => (s || "").toLowerCase().trim();

export default function CommandPalette() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = norm(user?.role);
  const isAdmin = role === "admin" || role === "master_admin" || role === "owner";

  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  // Global Ctrl/Cmd+K toggle.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Focus + reset on open.
  useEffect(() => {
    if (open) {
      setQ(""); setResults([]); setActive(0);
      setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [open]);

  // Filtered static commands (role-aware, client-side match).
  const commands = useMemo(() => {
    const visible = COMMANDS.filter((c) => !c.roles || isAdmin || c.roles.includes(role));
    const query = norm(q);
    if (!query) return visible.slice(0, 8);
    return visible
      .filter((c) => norm(c.label).includes(query) || norm(c.kw).includes(query) || norm(c.hint).includes(query))
      .slice(0, 8);
  }, [q, role, isAdmin]);

  // Live server-side data search (debounced).
  useEffect(() => {
    if (!open) return;
    const query = norm(q);
    if (query.length < 2) { setResults([]); setLoading(false); return; }
    setLoading(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await UnifiedAPI.search(query, { perType: 4 });
        const flat = [];
        (data.groups || []).forEach((g) => (g.items || []).forEach((it) => flat.push(it)));
        setResults(flat.slice(0, 24));
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
  }, [q, open]);

  // Combined flat list for keyboard navigation: commands first, then data.
  const flat = useMemo(() => {
    const cmds = commands.map((c) => ({ kind: "cmd", ...c }));
    const data = results.map((r) => ({ kind: "data", ...r }));
    return [...cmds, ...data];
  }, [commands, results]);

  useEffect(() => { setActive(0); }, [q]);

  const activate = useCallback((item) => {
    if (!item) return;
    setOpen(false);
    navigate(item.path || item.url);
  }, [navigate]);

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, flat.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); activate(flat[active] || flat[0]); }
    else if (e.key === "Escape") { setOpen(false); }
  };

  if (!open) return null;

  let idx = -1; // running index across both groups for active highlighting

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/50 px-4 pt-[12vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
      data-testid="command-palette-overlay"
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-white/10 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        data-testid="command-palette"
      >
        {/* Input */}
        <div className="flex items-center gap-3 border-b border-slate-100 px-4">
          <Search className="h-5 w-5 shrink-0 text-slate-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Пошук по всій системі або команда…"
            className="h-14 w-full bg-transparent text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
            data-testid="command-palette-input"
          />
          <kbd className="hidden shrink-0 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[11px] font-medium text-slate-400 sm:block">ESC</kbd>
        </div>

        {/* Results */}
        <div className="max-h-[60vh] overflow-y-auto py-2" data-testid="command-palette-list">
          {/* Commands group */}
          {commands.length > 0 && (
            <div className="px-2 pb-1">
              <div className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                {norm(q) ? "Дії" : "Швидкі дії"}
              </div>
              {commands.map((c) => {
                idx += 1; const i = idx; const Icon = c.icon || ArrowRight;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onMouseEnter={() => setActive(i)}
                    onClick={() => activate(c)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${i === active ? "bg-[#F4FBEF]" : "hover:bg-slate-50"}`}
                    data-testid="command-palette-item"
                  >
                    <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${c.create ? "bg-[#0E5E3A] text-white" : "bg-slate-100 text-slate-600"}`}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-slate-800">{c.label}</span>
                      <span className="block truncate text-[11px] uppercase tracking-wide text-slate-400">{c.hint}</span>
                    </span>
                    <CornerDownLeft className={`h-3.5 w-3.5 shrink-0 ${i === active ? "text-[#0E5E3A]" : "text-slate-300"}`} />
                  </button>
                );
              })}
            </div>
          )}

          {/* Live data results */}
          {norm(q).length >= 2 && (
            <div className="px-2 pt-1">
              <div className="flex items-center justify-between px-2 py-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Результати пошуку</span>
                {loading && <span className="text-[11px] text-slate-400">завантаження…</span>}
              </div>
              {!loading && results.length === 0 && (
                <div className="px-3 py-6 text-center text-sm text-slate-400">Нічого не знайдено в даних</div>
              )}
              {results.map((r) => {
                idx += 1; const i = idx; const Icon = TYPE_ICON[r.type] || FileStack;
                return (
                  <button
                    key={`${r.type}-${r.id}`}
                    type="button"
                    onMouseEnter={() => setActive(i)}
                    onClick={() => activate(r)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${i === active ? "bg-[#F4FBEF]" : "hover:bg-slate-50"}`}
                    data-testid="command-palette-data-item"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#EAF6EE] text-[#0E5E3A]">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-slate-800">{r.title}</span>
                      <span className="block truncate text-[11px] text-slate-400">{r.subtitle}</span>
                    </span>
                    <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">{r.label}</span>
                  </button>
                );
              })}
            </div>
          )}

          {norm(q).length < 2 && (
            <div className="px-5 pb-3 pt-2 text-[12px] text-slate-400">
              Введіть щонайменше 2 символи, щоб шукати по компаніях, кодах, угодах, договорах, контенту…
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/60 px-4 py-2 text-[11px] text-slate-400">
          <span className="flex items-center gap-2">
            <kbd className="rounded border border-slate-200 bg-white px-1">↑</kbd>
            <kbd className="rounded border border-slate-200 bg-white px-1">↓</kbd> навігація
            <kbd className="ml-2 rounded border border-slate-200 bg-white px-1">↵</kbd> відкрити
          </span>
          <span className="font-medium text-slate-400">Unified Admin · ⌘K</span>
        </div>
      </div>
    </div>
  );
}
