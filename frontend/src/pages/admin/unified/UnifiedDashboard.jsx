// UnifiedDashboard — Phase D1.5 (Unified Admin Platform hub).
// A single cross-domain overview so admins stop bouncing between islands.
// Additive: mounted at /app/hub — the legacy /app operations Dashboard is
// untouched and still reachable.
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Users, Handshake, Building2, Leaf, Truck, FileText, HelpCircle, Image as ImageIcon,
  Globe, ScrollText, Receipt, Banknote, UsersRound, Command, ArrowRight, Loader2,
  Package, Sparkles,
} from "lucide-react";
import { UnifiedAPI } from "@/lib/api";
import ActivityFeed from "@/components/unified/ActivityFeed";

const fmtMoney = (v) =>
  new Intl.NumberFormat("uk-UA", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(v || 0);

const TYPE_ICON = {
  lead: Users, deal: Handshake, pickup: Truck, content_page: FileText,
};

function Stat({ icon: Icon, label, value, to, accent }) {
  const body = (
    <div className={`group flex items-center gap-3 rounded-xl border p-4 transition-all ${accent ? "border-[#0E5E3A]/20 bg-[#F4FBEF]" : "border-slate-100 bg-white hover:border-[#5BC47A]/40 hover:shadow-sm"}`}>
      <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${accent ? "bg-[#0E5E3A] text-white" : "bg-slate-50 text-[#0E5E3A]"}`}>
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-tight text-slate-800">{value}</div>
        <div className="truncate text-xs uppercase tracking-wide text-slate-400">{label}</div>
      </div>
      {to && <ArrowRight className="ml-auto h-4 w-4 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-[#0E5E3A]" />}
    </div>
  );
  return to ? <Link to={to} data-testid={`hub-stat-${label}`}>{body}</Link> : <div data-testid={`hub-stat-${label}`}>{body}</div>;
}

function DomainCard({ title, icon: Icon, to, children }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <Icon className="h-4 w-4 text-[#0E5E3A]" />{title}
        </h3>
        {to && <Link to={to} className="text-xs font-medium text-[#0E5E3A] hover:underline">Відкрити →</Link>}
      </div>
      <div className="grid grid-cols-3 gap-2">{children}</div>
    </div>
  );
}

function MiniStat({ value, label }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-center">
      <div className="text-lg font-bold text-slate-800">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
    </div>
  );
}

function RecentColumn({ title, items, onOpen }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
      <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
      {(!items || items.length === 0) ? (
        <div className="py-6 text-center text-xs text-slate-300">Немає записів</div>
      ) : (
        <ul className="space-y-1">
          {items.map((it) => {
            const Icon = TYPE_ICON[it.type] || Package;
            return (
              <li key={`${it.type}-${it.id}`}>
                <button
                  type="button"
                  onClick={() => onOpen(it.url)}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-slate-50"
                >
                  <Icon className="h-3.5 w-3.5 shrink-0 text-[#0E5E3A]" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] text-slate-700">{it.title}</span>
                    <span className="block truncate text-[10px] text-slate-400">{it.subtitle}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function UnifiedDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const d = await UnifiedAPI.dashboard();
        setData(d);
      } catch (e) {
        setError(e?.response?.data?.detail || e.message || "Помилка завантаження");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <div className="flex h-64 items-center justify-center text-slate-400"><Loader2 className="h-7 w-7 animate-spin" /></div>;
  }
  if (error) {
    return <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600" data-testid="hub-error">{error}</div>;
  }

  const c = data?.cards || {};
  const r = data?.recent || {};

  return (
    <div className="space-y-6" data-testid="unified-dashboard">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-800">
            <Sparkles className="h-6 w-6 text-[#0E5E3A]" /> Єдиний центр адміністрування
          </h1>
          <p className="mt-1 text-sm text-slate-400">Крос-доменний огляд: CRM · Відходи · Контент · SEO · Фінанси · Команда</p>
        </div>
        <button
          type="button"
          onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm hover:border-[#5BC47A]/50 hover:text-slate-700"
          data-testid="hub-open-palette"
        >
          <Command className="h-4 w-4" /> Командна палітра
          <kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 text-[11px]">Ctrl K</kbd>
        </button>
      </div>

      {/* Top KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={Banknote} label="Портфель угод" value={fmtMoney(c.deals_value)} accent />
        <Stat icon={Handshake} label="Угоди" value={c.crm?.deals ?? 0} to="/app/crm" />
        <Stat icon={Users} label="Ліди" value={c.crm?.leads ?? 0} to="/app/leads" />
        <Stat icon={ScrollText} label="Договори" value={c.finance?.contracts ?? 0} to="/app/contracts" />
      </div>

      {/* Domain cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <DomainCard title="Відходи" icon={Leaf} to="/app/directory">
          <MiniStat value={c.waste?.codes ?? 0} label="Коди" />
          <MiniStat value={c.waste?.companies ?? 0} label="Компанії" />
          <MiniStat value={c.waste?.pickups ?? 0} label="Вивози" />
        </DomainCard>

        <DomainCard title="Контент" icon={FileText} to="/app/content/pages">
          <MiniStat value={c.content?.published ?? 0} label="Опубл." />
          <MiniStat value={c.content?.drafts ?? 0} label="Чернетки" />
          <MiniStat value={c.content?.review ?? 0} label="Рев'ю" />
          <MiniStat value={c.content?.pages ?? 0} label="Сторінки" />
          <MiniStat value={c.content?.faq ?? 0} label="FAQ" />
          <MiniStat value={c.content?.media ?? 0} label="Медіа" />
        </DomainCard>

        <DomainCard title="Фінанси та команда" icon={Receipt} to="/app/finance">
          <MiniStat value={c.finance?.invoices ?? 0} label="Рахунки" />
          <MiniStat value={c.finance?.payments ?? 0} label="Платежі" />
          <MiniStat value={c.staff?.members ?? 0} label="Персонал" />
        </DomainCard>
      </div>

      {/* Quick access chips */}
      <div className="flex flex-wrap gap-2">
        {[
          { to: "/app/companies", label: "Компанії", icon: Building2 },
          { to: "/app/requests", label: "Заявки", icon: FileText },
          { to: "/app/operations", label: "Операції", icon: Truck },
          { to: "/app/content/media", label: "Медіа", icon: ImageIcon },
          { to: "/app/content/faq", label: "FAQ", icon: HelpCircle },
          { to: "/app/seo", label: "SEO", icon: Globe },
          { to: "/app/staff", label: "Персонал", icon: UsersRound },
        ].map((x) => (
          <Link key={x.to} to={x.to} className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-sm text-slate-600 hover:border-[#5BC47A]/50 hover:text-[#0E5E3A]">
            <x.icon className="h-3.5 w-3.5" /> {x.label}
          </Link>
        ))}
      </div>

      {/* Recent activity across domains */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Остання активність</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <RecentColumn title="Ліди" items={r.leads} onOpen={navigate} />
          <RecentColumn title="Угоди" items={r.deals} onOpen={navigate} />
          <RecentColumn title="Вивози" items={r.pickups} onOpen={navigate} />
          <RecentColumn title="Контент" items={r.content} onOpen={navigate} />
        </div>
      </div>

      {/* Universal Activity Feed (Slice 2) */}
      <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            <Sparkles className="h-4 w-4 text-[#0E5E3A]" /> Стрічка подій платформи
          </h2>
          <Link to="/app/activity" className="text-xs font-medium text-[#0E5E3A] hover:underline" data-testid="hub-activity-link">Вся стрічка →</Link>
        </div>
        <ActivityFeed limit={12} compact />
      </div>
    </div>
  );
}
