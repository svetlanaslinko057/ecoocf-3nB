// ECO Finance360 (Wave 12) — фінанси по waste-контрактах/інвойсах
import React, { useEffect, useState, useCallback } from "react";
import { Banknote, TrendingUp, AlertTriangle, Wallet, RefreshCw, PiggyBank, Activity } from "lucide-react";
import { FinanceAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const money = (v) => { const n = Number(v || 0); return n ? `${Math.round(n).toLocaleString("uk-UA")} ₴` : "0 ₴"; };

const SEGMENTS = [
  { key: "healthy", label: "Здорові", color: "#0E5E3A" },
  { key: "warning", label: "Увага", color: "#9A3412" },
  { key: "at_risk", label: "Під ризиком", color: "#B45309" },
  { key: "critical", label: "Критичні", color: "#DC2626" },
];

export default function Finance360() {
  useSeo("Фінанси 360 · CRM", "Фінансовий центр: виручка, прибуток, борги, прогноз.");
  const [tab, setTab] = useState("overview");
  const [fin, setFin] = useState(null);
  const [fc, setFc] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [o, f] = await Promise.all([
        FinanceAPI.overview().catch(() => null),
        FinanceAPI.forecast().catch(() => null),
      ]);
      setFin(o?.data || null); setFc(f?.data || null);
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const t = fin?.totals || {}; const c = fin?.counts || {}; const seg = fin?.risk?.by_segment || {};
  const horizons = fc?.how_much?.horizons || {};
  const weeks = fc?.when?.weeks || [];

  return (
    <div data-testid="portal-finance360">
      <PageHeader title="Фінанси 360" subtitle="Гроші по контрактах на вивіз/утилізацію відходів"
        actions={<Button variant="secondary" onClick={load} className="gap-2" data-testid="fin-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Banknote} label="Виручка" value={money(t.revenue)} testid="fin-kpi-revenue" />
        <StatCard icon={TrendingUp} label="Прибуток" value={money(t.profit)} testid="fin-kpi-profit" />
        <StatCard icon={Wallet} label="До сплати" value={money(t.outstanding)} testid="fin-kpi-outstanding" />
        <StatCard icon={AlertTriangle} label="Під ризиком" value={money(t.at_risk)} testid="fin-kpi-atrisk" />
      </div>

      <div className="mb-4"><Tabs value={tab} onValueChange={setTab}><TabsList>
        <TabsTrigger value="overview" data-testid="fin-tab-overview">Огляд</TabsTrigger>
        <TabsTrigger value="forecast" data-testid="fin-tab-forecast">Прогноз</TabsTrigger>
      </TabsList></Tabs></div>

      {loading ? <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4"><TableSkeleton rows={6} /></div>
      : tab === "overview" ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <StatCard icon={Activity} label="Усього угод" value={c.deals_total ?? 0} />
            <StatCard icon={Activity} label="Відкриті" value={c.deals_open ?? 0} />
            <StatCard icon={PiggyBank} label="Завершені" value={c.deals_delivered ?? 0} />
          </div>
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
            <h3 className="mb-4 text-sm font-semibold text-slate-700">Сегменти ризику</h3>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {SEGMENTS.map((s) => { const d = seg[s.key] || {}; return (
                <div key={s.key} className="rounded-xl border border-slate-100 p-4" data-testid={`fin-seg-${s.key}`}>
                  <div className="text-xs font-bold uppercase tracking-wide" style={{ color: s.color }}>{s.label}</div>
                  <div className="mt-1 text-2xl font-bold text-slate-900">{d.count ?? 0}</div>
                  <div className="mt-1 text-xs text-slate-500">Борг: {money(d.outstanding)}</div>
                </div>); })}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            {[30, 60, 90].map((h) => { const d = horizons[h] || {}; return (
              <div key={h} className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5" data-testid={`fin-horizon-${h}`}>
                <div className="text-xs font-bold uppercase tracking-wide text-[#0E5E3A]">{h} днів</div>
                <div className="mt-2 text-2xl font-bold text-slate-900">{money(d.weighted)}</div>
                <div className="mt-1 text-xs text-slate-500">{d.deals ?? 0} угод · прибуток {money(d.profit)}</div>
              </div>); })}
          </div>
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
            <div className="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-700">Грошовий потік (13 тижнів)</div>
            {weeks.length === 0 ? <EmptyState icon={Banknote} title="Немає даних" hint="Прогноз з'явиться з появою угод." testid="fin-cash-empty" /> : (
              <div className="overflow-x-auto"><table className="w-full text-sm">
                <thead><tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                  <th className="px-4 py-2">Тиждень</th><th className="px-3 py-2">Надходження</th><th className="px-3 py-2">Витрати</th><th className="px-3 py-2">Нетто</th><th className="px-3 py-2">Баланс</th>
                </tr></thead>
                <tbody>{weeks.slice(0, 13).map((w, i) => (
                  <tr key={i} className="border-b border-slate-50"><td className="px-4 py-2 text-slate-700">{(w.start || "").slice(5)}</td>
                    <td className="px-3 py-2 text-[#0E5E3A]">{money(w.cash_in)}</td><td className="px-3 py-2 text-[#DC2626]">{money(w.cash_out)}</td>
                    <td className="px-3 py-2">{money(w.net)}</td><td className="px-3 py-2 font-medium">{money(w.running_balance)}</td></tr>
                ))}</tbody>
              </table></div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
