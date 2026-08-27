// ECO Executive Center (Wave 16) — директорський зведений лінз (тільки admin)
import React, { useEffect, useState, useCallback } from "react";
import { Crown, RefreshCw, Users, Activity, Wallet, Truck, FileSignature, AlertTriangle } from "lucide-react";
import { ExecAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { PageHeader, StatCard, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";

const money = (v) => { const n = Number(v || 0); return n ? `${Math.round(n).toLocaleString("uk-UA")} ₴` : "0 ₴"; };

const TILES = [
  { key: "active_leads", label: "Активні ліди", icon: Users },
  { key: "active_customers", label: "Клієнти", icon: Users },
  { key: "active_deals", label: "Активні угоди", icon: Activity },
  { key: "revenue_mtd", label: "Виручка (міс.)", icon: Wallet, money: true },
  { key: "profit_mtd", label: "Прибуток (міс.)", icon: Wallet, money: true },
  { key: "outstanding", label: "До сплати", icon: Wallet, money: true },
  { key: "cars_in_transit", label: "Вивози в дорозі", icon: Truck },
  { key: "unsigned_contracts", label: "Непідписані договори", icon: FileSignature },
  { key: "pending_approvals", label: "На узгодженні", icon: FileSignature },
  { key: "expiring_contracts", label: "Спливають", icon: AlertTriangle },
  { key: "active_contracts", label: "Активні договори", icon: FileSignature },
  { key: "critical_deliveries", label: "Критичні вивози", icon: AlertTriangle },
];

export default function ExecutiveCenter() {
  useSeo("Директорський центр · CRM", "Зведений лінз по операціях, фінансах та договорах.");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await ExecAPI.dashboard().catch(() => null); setData(d?.data || null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const tiles = data?.tiles || {};
  const horizons = data?.horizons || {};

  return (
    <div data-testid="portal-executive">
      <PageHeader title="Директорський центр" subtitle="Зведення по операціях, фінансах та договорах ECO"
        actions={<Button variant="secondary" onClick={load} className="gap-2" data-testid="exec-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>} />

      {loading ? <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4"><TableSkeleton rows={6} /></div> : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {TILES.map((t) => (
              <StatCard key={t.key} icon={t.icon} label={t.label} value={t.money ? money(tiles[t.key]) : (tiles[t.key] ?? 0)} testid={`exec-tile-${t.key}`} />
            ))}
          </div>
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-700"><Crown className="h-4 w-4 text-[#0E5E3A]" /> Прогноз виручки</div>
            <div className="grid gap-4 md:grid-cols-3">
              {[30, 60, 90].map((h) => { const d = horizons[h] || {}; return (
                <div key={h} className="rounded-xl border border-slate-100 p-4" data-testid={`exec-horizon-${h}`}>
                  <div className="text-xs font-bold uppercase tracking-wide text-[#0E5E3A]">{h} днів</div>
                  <div className="mt-1 text-2xl font-bold text-slate-900">{money(d.weighted)}</div>
                  <div className="mt-1 text-xs text-slate-500">{d.deals ?? 0} угод · {money(d.profit)} прибуток</div>
                </div>); })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
