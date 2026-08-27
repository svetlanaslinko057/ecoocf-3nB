// ECO Contract360 (Wave 15) — життєвий цикл договорів на вивіз/утилізацію
import React, { useEffect, useState, useCallback } from "react";
import { FileSignature, RefreshCw, AlertTriangle, CheckCircle2, Clock, Archive } from "lucide-react";
import { ContractsAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const money = (v) => { const n = Number(v || 0); return n ? `${Math.round(n).toLocaleString("uk-UA")} ₴` : "0 ₴"; };

const SEGMENTS = [
  { key: "healthy", label: "Здорові", color: "#0E5E3A", icon: CheckCircle2 },
  { key: "unsigned", label: "Непідписані", color: "#9A3412", icon: Clock },
  { key: "pending_approval", label: "На узгодженні", color: "#075985", icon: Clock },
  { key: "critical", label: "Критичні", color: "#DC2626", icon: AlertTriangle },
  { key: "draft", label: "Чернетки", color: "#64748B", icon: FileSignature },
  { key: "archived", label: "Архів", color: "#94A3B8", icon: Archive },
];

export default function Contract360() {
  useSeo("Договори 360 · CRM", "Життєвий цикл договорів: шаблони, підписи, ризики.");
  const [tab, setTab] = useState("overview");
  const [ov, setOv] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [o, l] = await Promise.all([
        ContractsAPI.overview().catch(() => null),
        ContractsAPI.list({ limit: 200 }).catch(() => null),
      ]);
      setOv(o?.data || null); setItems(l?.items || []);
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const t = ov?.totals || {}; const seg = ov?.by_segment || {};

  return (
    <div data-testid="portal-contract360">
      <PageHeader title="Договори 360" subtitle="Життєвий цикл договорів на вивіз та утилізацію відходів"
        actions={<Button variant="secondary" onClick={load} className="gap-2" data-testid="ctr-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileSignature} label="Усього договорів" value={t.contracts ?? 0} testid="ctr-kpi-total" />
        <StatCard icon={CheckCircle2} label="Активна вартість" value={money(t.active_value)} testid="ctr-kpi-active" />
        <StatCard icon={Clock} label="Непідписана вартість" value={money(t.unsigned_value)} testid="ctr-kpi-unsigned" />
        <StatCard icon={AlertTriangle} label="Простр. підпису" value={t.overdue_signature ?? 0} testid="ctr-kpi-overdue" />
      </div>

      <div className="mb-4"><Tabs value={tab} onValueChange={setTab}><TabsList>
        <TabsTrigger value="overview" data-testid="ctr-tab-overview">Огляд</TabsTrigger>
        <TabsTrigger value="list" data-testid="ctr-tab-list">Договори ({items.length})</TabsTrigger>
      </TabsList></Tabs></div>

      {loading ? <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4"><TableSkeleton rows={6} /></div>
      : tab === "overview" ? (
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Сегменти договорів</h3>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            {SEGMENTS.map((s) => (
              <div key={s.key} className="flex items-center gap-3 rounded-xl border border-slate-100 p-4" data-testid={`ctr-seg-${s.key}`}>
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg" style={{ background: `${s.color}1A` }}><s.icon className="h-5 w-5" style={{ color: s.color }} /></span>
                <div><div className="text-2xl font-bold text-slate-900">{seg[s.key] ?? 0}</div><div className="text-xs text-slate-500">{s.label}</div></div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
          {items.length === 0 ? <EmptyState icon={FileSignature} title="Немає договорів" hint="Договори з'являться після створення з заявок." testid="ctr-list-empty" /> : (
            <div className="overflow-x-auto"><table className="w-full text-sm">
              <thead><tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
                <th className="px-4 py-2">№</th><th className="px-3 py-2">Клієнт</th><th className="px-3 py-2">Статус</th><th className="px-3 py-2">Вартість</th><th className="px-3 py-2">Оновлено</th>
              </tr></thead>
              <tbody>{items.map((c) => (
                <tr key={c.id} className="border-b border-slate-50" data-testid="ctr-row">
                  <td className="px-4 py-2 font-medium text-slate-800">{c.number || c.id}</td>
                  <td className="px-3 py-2 text-slate-600">{c.customer_name || c.customerId || "—"}</td>
                  <td className="px-3 py-2"><span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs">{c.status || "—"}</span></td>
                  <td className="px-3 py-2">{money(c.value || c.amount)}</td>
                  <td className="px-3 py-2 text-slate-500">{fmtDateTime(c.updated_at || c.created_at)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
      )}
    </div>
  );
}
