// Wave 5A: CRM Hub — єдиний дашборд Tasks / Calls / Invoices / Documents.
import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { ListTodo, Phone, Receipt, FileStack, Bell, AlertTriangle, CheckCircle2, Clock, TrendingUp, ArrowRight } from "lucide-react";
import { CrmAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDate, fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";

const money = (v, c = "UAH") => `${Number(v || 0).toLocaleString("uk-UA", { maximumFractionDigits: 2 })} ${c}`;

export default function CrmHub() {
  useSeo("CRM-хаб", "Єдиний дашборд Tasks / Calls / Invoices / Documents.");
  const [data, setData] = useState({ taskStats: null, invAna: null, missed: [], queue: [], overdue: [], docsPending: [] });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const safe = async (fn, fb) => { try { return await fn(); } catch { return fb; } };
    const [taskStats, invAna, queue, missed, overdue, docsPending] = await Promise.all([
      safe(CrmAPI.taskStats, { stats: { total: 0, pending: 0, completed: 0, overdue: 0 } }),
      safe(CrmAPI.invoiceAnalytics, { analytics: { total: 0, paid: 0, pending: 0, overdue: 0, totalAmount: 0, paidAmount: 0 } }),
      safe(CrmAPI.taskQueue, { data: [] }),
      safe(CrmAPI.missedCalls, { data: [] }),
      safe(CrmAPI.invoicesOverdue, { data: [] }),
      safe(CrmAPI.documentsPending, { data: [] }),
    ]);
    setData({ taskStats: taskStats.stats, invAna: invAna.analytics, queue: queue.data || [], missed: missed.data || missed.calls || [], overdue: overdue.data || [], docsPending: docsPending.data || [] });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const ts = data.taskStats || {}; const ia = data.invAna || {};
  return (
    <div data-testid="portal-crm-hub">
      <PageHeader title="CRM-хаб" subtitle="Єдиний робочий простір завдань, дзвінків, рахунків і документів" />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <ModuleCard to="/app/crm/tasks" icon={ListTodo} label="Завдання" value={ts.pending ?? 0} hint={`всього ${ts.total ?? 0} · викон. ${ts.completed ?? 0}`} accent={(ts.overdue || 0) > 0 ? "warn" : "primary"} testid="crm-kpi-tasks" />
        <ModuleCard to="/app/crm/calls" icon={Phone} label="Пропущені дзвінки" value={data.missed.length} hint="Ringostat · останні 24г" accent={data.missed.length > 0 ? "danger" : "primary"} testid="crm-kpi-calls" />
        <ModuleCard to="/app/crm/invoices" icon={Receipt} label="Рахунки (всього)" value={ia.total ?? 0} hint={`Оплачено ${money(ia.paidAmount, "грн")} / ${money(ia.totalAmount, "грн")}`} accent="primary" testid="crm-kpi-inv" />
        <ModuleCard to="/app/crm/documents" icon={FileStack} label="Документи на перевірці" value={data.docsPending.length} hint="договори / акти / додатки" accent={data.docsPending.length > 0 ? "warn" : "primary"} testid="crm-kpi-docs" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Прострочені рахунки" icon={AlertTriangle} link="/app/crm/invoices" linkLabel="Усі »" testid="crm-panel-overdue">
          {(data.overdue || []).length === 0 ? <EmptyHint icon={CheckCircle2} text="Боргів немає" />
            : <ul className="divide-y divide-[hsl(var(--border))]">{data.overdue.slice(0, 5).map((inv) => (
                <li key={inv.id} className="flex items-center justify-between py-2 text-sm">
                  <div><div className="font-mono text-xs text-slate-500">{inv.id}</div><div className="text-slate-700">{inv.customerId || "—"}</div></div>
                  <div className="text-right"><div className="font-mono font-semibold text-[#991B1B]">{money(inv.amount, inv.currency || "UAH")}</div><div className="text-xs text-slate-400">до {fmtDate(inv.dueDate)}</div></div>
                </li>
              ))}</ul>}
        </Panel>

        <Panel title="Черга завдань" icon={Clock} link="/app/crm/tasks?filter=pending" linkLabel="Усі »" testid="crm-panel-queue">
          {(data.queue || []).length === 0 ? <EmptyHint icon={CheckCircle2} text="Черга порожня — все під контролем" />
            : <ul className="divide-y divide-[hsl(var(--border))]">{data.queue.slice(0, 5).map((t) => (
                <li key={t.id} className="flex items-center justify-between py-2 text-sm">
                  <div><div className="text-slate-800">{t.title}</div><div className="text-xs text-slate-400">{t.assigneeName || t.assigneeId || "—"} · {t.dueDate ? fmtDate(t.dueDate) : "без дедлайну"}</div></div>
                  <span className="inline-flex items-center rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--secondary))] px-2 py-0.5 text-xs text-slate-500">{t.priority || "medium"}</span>
                </li>
              ))}</ul>}
        </Panel>

        <Panel title="Пропущені дзвінки" icon={Phone} link="/app/crm/calls" linkLabel="Повна історія »" testid="crm-panel-missed">
          {(data.missed || []).length === 0 ? <EmptyHint icon={CheckCircle2} text="Пропущених немає" />
            : <ul className="divide-y divide-[hsl(var(--border))]">{data.missed.slice(0, 5).map((c) => (
                <li key={c.id || c._id} className="flex items-center justify-between py-2 text-sm">
                  <div><div className="text-slate-800">{c.caller_number || c.from || "—"}</div><div className="text-xs text-slate-400">{c.lead?.name || c.deal?.title || "—"}</div></div>
                  <div className="text-xs text-slate-500">{fmtDateTime(c.started_at || c.created_at)}</div>
                </li>
              ))}</ul>}
        </Panel>

        <Panel title="Документи на перевірці" icon={FileStack} link="/app/crm/documents" linkLabel="Усі »" testid="crm-panel-docs">
          {(data.docsPending || []).length === 0 ? <EmptyHint icon={CheckCircle2} text="Черга порожня" />
            : <ul className="divide-y divide-[hsl(var(--border))]">{data.docsPending.slice(0, 5).map((d) => (
                <li key={d.id} className="flex items-center justify-between py-2 text-sm">
                  <div><div className="text-slate-800">{d.name || d.type}</div><div className="text-xs text-slate-400">{d.type} · {fmtDate(d.created_at)}</div></div>
                  <span className="inline-flex items-center rounded-md border border-[#FDE68A] bg-[#FFFBEB] px-2 py-0.5 text-xs text-[#92400E]">на перевірці</span>
                </li>
              ))}</ul>}
        </Panel>
      </div>
    </div>
  );
}

function ModuleCard({ to, icon: Icon, label, value, hint, accent = "primary", testid }) {
  const accents = {
    primary: "border-[hsl(var(--border))] bg-white hover:border-[hsl(var(--primary))]",
    warn: "border-[#FDE68A] bg-[#FFFBEB] hover:border-[#F59E0B]",
    danger: "border-[#FECACA] bg-[#FEF2F2] hover:border-[#EF4444]",
  };
  const iconColor = accent === "danger" ? "text-[#EF4444]" : accent === "warn" ? "text-[#F59E0B]" : "text-[hsl(var(--primary))]";
  return (
    <Link to={to} data-testid={testid} className={`group block rounded-2xl border p-5 transition ${accents[accent]}`}>
      <div className="flex items-start justify-between">
        <Icon className={`h-8 w-8 ${iconColor}`} />
        <ArrowRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-1 group-hover:text-slate-500" />
      </div>
      <div className="mt-3 text-2xl font-semibold text-slate-900">{value}</div>
      <div className="text-sm text-slate-600">{label}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </Link>
  );
}

function Panel({ title, icon: Icon, link, linkLabel, testid, children }) {
  return (
    <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-5" data-testid={testid}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Icon className="h-4 w-4 text-[hsl(var(--primary))]" /> {title}</div>
        {link && <Link to={link} className="text-xs font-medium text-[hsl(var(--primary))] hover:underline">{linkLabel}</Link>}
      </div>
      {children}
    </div>
  );
}

function EmptyHint({ icon: Icon, text }) {
  return <div className="flex items-center gap-2 rounded-lg border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/60 px-3 py-4 text-sm text-slate-500"><Icon className="h-4 w-4 text-[#065F46]" /> {text}</div>;
}
