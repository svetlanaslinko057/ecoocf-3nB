// ECO Deal360 (Wave 6 + 11) — повна картка угоди (воронка, фінанси, договори, оплати)
import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, RefreshCw, Wallet, Banknote, TrendingUp, FileSignature,
  Building2, Activity, CheckCircle2, AlertTriangle,
} from "lucide-react";
import { DealsAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";

const money = (v) => { const n = Number(v || 0); return `${Math.round(n).toLocaleString("uk-UA")} ₴`; };

const STAGE_OPTIONS = [
  ["new", "Нова"], ["negotiation", "Переговори"], ["contract", "Договір"],
  ["pickup", "Вивіз"], ["utilization", "Утилізація"], ["won", "Виграно"], ["lost", "Втрачено"],
];

const HEALTH_TONE = {
  healthy: "bg-[#DCFCE7] text-[#166534]", warning: "bg-[#FEF3C7] text-[#92400E]", critical: "bg-[#FEE2E2] text-[#991B1B]",
};

export default function Deal360() {
  const { dealId } = useParams();
  const navigate = useNavigate();
  useSeo("Угода 360 · CRM", "Повна картка угоди: воронка, фінанси, договори, оплати.");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await DealsAPI.full360(dealId); setData(r?.data || null); }
    catch { toast.error("Не вдалося завантажити угоду"); }
    finally { setLoading(false); }
  }, [dealId]);
  useEffect(() => { load(); }, [load]);

  const transition = async (stage) => {
    setSaving(true);
    try { await DealsAPI.transition(dealId, { stage }); toast.success("Етап оновлено"); await load(); }
    catch { toast.error("Не вдалося оновити етап"); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-4"><TableSkeleton rows={8} /></div>;
  if (!data) return <EmptyState icon={Activity} title="Угоду не знайдено" hint="Можливо, її видалено." testid="deal360-empty" />;

  const d = data.deal || {};
  const fin = data.financials || {};
  const sp = data.stage_progress || {};
  const h = data.health || {};
  const contracts = data.contracts || [];
  const payments = data.payments || [];

  return (
    <div data-testid="portal-deal360">
      <PageHeader
        title={d.title || "Угода"}
        subtitle={`${d.company || d.customerName || "—"}${d.wasteType ? " · " + d.wasteType : ""}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => navigate(-1)} className="gap-2" data-testid="deal360-back"><ArrowLeft className="h-4 w-4" /> Назад</Button>
            <Button variant="secondary" onClick={load} className="gap-2" data-testid="deal360-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>
          </div>
        }
      />

      {/* Health + stage control */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold ${HEALTH_TONE[h.label] || HEALTH_TONE.warning}`} data-testid="deal360-health">
          {h.label === "critical" ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />} Здоров'я {h.score ?? 0}/100
        </span>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">Етап:</span>
          <Select value={d.stage} onValueChange={transition} disabled={saving}>
            <SelectTrigger className="h-9 w-[170px]" data-testid="deal360-stage"><SelectValue /></SelectTrigger>
            <SelectContent>{STAGE_OPTIONS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-6 rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
        <div className="mb-3 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-700">Воронка ECO</span>
          <span className="text-slate-500">{sp.percent ?? 0}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-[#0E5E3A] transition-all" style={{ width: `${sp.percent ?? 0}%` }} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {(sp.stages || []).map((s) => (
            <span key={s.key} className={`rounded-md px-2.5 py-1 text-xs font-medium ${s.done ? "bg-[#0E5E3A] text-white" : "bg-slate-100 text-slate-500"}`}>{s.label}</span>
          ))}
        </div>
      </div>

      {/* Financials */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Wallet} label="Сума угоди" value={money(fin.amount)} testid="deal360-amount" />
        <StatCard icon={Banknote} label="Надходження" value={money(fin.income)} testid="deal360-income" />
        <StatCard icon={TrendingUp} label="Витрати" value={money(fin.expense)} testid="deal360-expense" />
        <StatCard icon={Wallet} label="До сплати" value={money(fin.outstanding)} testid="deal360-outstanding" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Contracts */}
        <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
          <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-700"><FileSignature className="h-4 w-4" /> Договори ({contracts.length})</div>
          {contracts.length === 0 ? <EmptyState icon={FileSignature} title="Немає договорів" hint="Договір з'явиться після переходу на етап «Договір»." testid="deal360-ctr-empty" /> : (
            <ul className="divide-y divide-slate-50">{contracts.map((c) => (
              <li key={c.id} className="flex items-center justify-between px-5 py-3" data-testid="deal360-ctr-row">
                <div><div className="font-medium text-slate-800">{c.number}</div><div className="text-xs text-slate-500">{c.status}</div></div>
                <div className="text-right"><div className="font-semibold text-slate-800">{money(c.value || c.amount)}</div><div className="text-xs text-slate-500">сплачено {money(c.paid_amount)}</div></div>
              </li>
            ))}</ul>
          )}
        </div>

        {/* Payments + company */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
            <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-700"><Banknote className="h-4 w-4" /> Оплати ({payments.length})</div>
            {payments.length === 0 ? <EmptyState icon={Banknote} title="Оплат немає" hint="—" testid="deal360-pay-empty" /> : (
              <ul className="divide-y divide-slate-50">{payments.slice(0, 8).map((p) => (
                <li key={p.id} className="flex items-center justify-between px-5 py-2.5" data-testid="deal360-pay-row">
                  <div className="text-sm text-slate-600">{fmtDateTime(p.date || p.created_at)}</div>
                  <div className={`font-semibold ${p.kind === "income" ? "text-[#0E5E3A]" : "text-[#B45309]"}`}>{p.kind === "income" ? "+" : "−"}{money(p.amount)}</div>
                </li>
              ))}</ul>
            )}
          </div>
          {data.company && (
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700"><Building2 className="h-4 w-4" /> Компанія</div>
              <div className="text-slate-800">{data.company.name}</div>
              <div className="text-xs text-slate-500">{data.company.status}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
