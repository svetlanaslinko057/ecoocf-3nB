// ECO Operations360 (Wave 14) — операційний дашборд (вузькі місця, SLA, ризики)
import React, { useEffect, useState, useCallback } from "react";
import { Workflow, RefreshCw, AlertTriangle, Clock, Truck, Users, Wallet, Activity } from "lucide-react";
import { OpsAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";

const money = (v) => { const n = Number(v || 0); return n ? `${Math.round(n).toLocaleString("uk-UA")} ₴` : "0 ₴"; };

const TILES = [
  { key: "active_leads", label: "Активні ліди", icon: Users },
  { key: "active_deals", label: "Активні угоди", icon: Activity },
  { key: "revenue_mtd", label: "Виручка (міс.)", icon: Wallet, money: true },
  { key: "profit_mtd", label: "Прибуток (міс.)", icon: Wallet, money: true },
  { key: "outstanding", label: "До сплати", icon: Wallet, money: true },
  { key: "cars_in_transit", label: "Вивози в роботі", icon: Truck },
  { key: "critical_deliveries", label: "Критичні вивози", icon: AlertTriangle },
  { key: "at_risk_deals", label: "Угоди під ризиком", icon: AlertTriangle },
];

export default function Operations360() {
  useSeo("Операції 360 · CRM", "Операційний дашборд: вивози, утилізація, SLA.");
  const [data, setData] = useState(null);
  const [sla, setSla] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([OpsAPI.dashboard().catch(() => null), OpsAPI.sla().catch(() => null)]);
      setData(d?.data || null); setSla(s?.data || null);
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const tiles = data?.tiles || {};
  const rules = sla?.rules || [];

  return (
    <div data-testid="portal-operations360">
      <PageHeader title="Операції 360" subtitle="Вузькі місця, SLA та ризики по вивозах/утилізації"
        actions={<Button variant="secondary" onClick={load} className="gap-2" data-testid="ops-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>} />

      {loading ? <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4"><TableSkeleton rows={6} /></div> : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {TILES.map((t) => (
              <StatCard key={t.key} icon={t.icon} label={t.label} value={t.money ? money(tiles[t.key]) : (tiles[t.key] ?? 0)} testid={`ops-tile-${t.key}`} />
            ))}
          </div>
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
            <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-700"><Clock className="h-4 w-4" /> SLA моніторинг</div>
            {rules.length === 0 ? <EmptyState icon={Workflow} title="SLA під контролем" hint="Немає порушень SLA." testid="ops-sla-empty" /> : (
              <ul className="divide-y divide-slate-100">{rules.map((r) => (
                <li key={r.id} className="flex items-center justify-between px-5 py-3" data-testid="ops-sla-row">
                  <div><div className="font-medium text-slate-800">{r.label}</div><div className="text-xs text-slate-500">{r.limit_label}</div></div>
                  <span className={`rounded-full px-3 py-1 text-sm font-bold ${r.count > 0 ? "bg-[#FEE2E2] text-[#991B1B]" : "bg-[#DCFCE7] text-[#166534]"}`}>{r.count}</span>
                </li>
              ))}</ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
