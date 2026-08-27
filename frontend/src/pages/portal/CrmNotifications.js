// Wave 5A: Unified Notifications feed (агрегує з різних джерел)
import React, { useEffect, useState, useCallback } from "react";
import { Bell, AlertTriangle, PhoneMissed, FileStack, Receipt, ListTodo, RefreshCw, CheckCircle2 } from "lucide-react";
import { CrmAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { fmtDateTime } from "@/lib/portalMeta";
import { PageHeader, StatCard, EmptyState, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Link } from "react-router-dom";

const SOURCE_META = {
  task_overdue: { icon: ListTodo, color: "#991B1B", label: "Завдання прострочено", to: "/app/crm/tasks?filter=overdue" },
  invoice_overdue: { icon: Receipt, color: "#991B1B", label: "Рахунок прострочено", to: "/app/crm/invoices" },
  call_missed: { icon: PhoneMissed, color: "#92400E", label: "Пропущений дзвінок", to: "/app/crm/calls" },
  doc_pending: { icon: FileStack, color: "#92400E", label: "Документ очікує перевірку", to: "/app/crm/documents" },
};

export default function CrmNotifications() {
  useSeo("Сповіщення · CRM", "Єдиний фід подій з всіх модулів.");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    const safe = async (fn, fb = []) => { try { return (await fn()).data || (await fn()).calls || fb; } catch { return fb; } };
    const [overdueT, overdueI, missed, pending] = await Promise.all([
      CrmAPI.tasks({ filter: "overdue", limit: 50 }).then((r) => r.data || r.items || []).catch(() => []),
      CrmAPI.invoicesOverdue().then((r) => r.data || []).catch(() => []),
      CrmAPI.missedCalls().then((r) => r.data || r.calls || []).catch(() => []),
      CrmAPI.documentsPending().then((r) => r.data || []).catch(() => []),
    ]);
    const feed = [];
    overdueT.forEach((t) => feed.push({ id: `t-${t.id}`, source: "task_overdue", title: t.title, hint: `${t.assigneeName || t.assigneeId || "—"} · дедлайн ${t.dueDate || "—"}`, at: t.dueDate || t.created_at }));
    overdueI.forEach((i) => feed.push({ id: `i-${i.id}`, source: "invoice_overdue", title: `${i.id}`, hint: `${i.customerId || "—"} · ${i.amount} ${i.currency || "UAH"}`, at: i.dueDate || i.created_at }));
    missed.forEach((c) => feed.push({ id: `c-${c.id || c._id}`, source: "call_missed", title: c.caller_number || c.from || "—", hint: c.lead?.name || c.deal?.title || "", at: c.started_at || c.created_at }));
    pending.forEach((d) => feed.push({ id: `d-${d.id}`, source: "doc_pending", title: d.name || d.type, hint: `${d.type || "document"} · ${d.customerId || "—"}`, at: d.created_at }));
    feed.sort((a, b) => (new Date(b.at || 0)).getTime() - (new Date(a.at || 0)).getTime());
    setItems(feed); setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = tab === "all" ? items : items.filter((x) => x.source === tab);
  const cnt = (s) => items.filter((x) => x.source === s).length;
  return (
    <div data-testid="portal-crm-notifications">
      <PageHeader title="Сповіщення" subtitle="Дивайджест важливих подій (завдання / рахунки / дзвінки / документи)" actions={<Button variant="secondary" onClick={load} className="gap-2" data-testid="notif-refresh"><RefreshCw className="h-4 w-4" /> Оновити</Button>} />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={ListTodo} label="Простр. завдань" value={cnt("task_overdue")} testid="notif-kpi-tasks" />
        <StatCard icon={Receipt} label="Простр. рахунків" value={cnt("invoice_overdue")} testid="notif-kpi-inv" />
        <StatCard icon={PhoneMissed} label="Пропущених дзвінків" value={cnt("call_missed")} testid="notif-kpi-calls" />
        <StatCard icon={FileStack} label="Док. на перевірці" value={cnt("doc_pending")} testid="notif-kpi-docs" />
      </div>

      <div className="mb-4">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="all" data-testid="notif-tab-all">Усі ({items.length})</TabsTrigger>
            <TabsTrigger value="task_overdue" data-testid="notif-tab-tasks">Завдання</TabsTrigger>
            <TabsTrigger value="invoice_overdue" data-testid="notif-tab-invoices">Рахунки</TabsTrigger>
            <TabsTrigger value="call_missed" data-testid="notif-tab-calls">Дзвінки</TabsTrigger>
            <TabsTrigger value="doc_pending" data-testid="notif-tab-docs">Документи</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="rounded-2xl border border-[hsl(var(--border))] bg-white">
        {loading ? <div className="p-4"><TableSkeleton rows={6} /></div>
          : filtered.length === 0 ? <EmptyState icon={CheckCircle2} title="Усе під контролем" hint="Немає подій, які потребують уваги." testid="notif-empty" />
          : <ul className="divide-y divide-[hsl(var(--border))]">{filtered.map((n) => {
              const m = SOURCE_META[n.source]; const Icon = m?.icon || Bell;
              return (
                <li key={n.id} className="flex items-start gap-3 px-4 py-3" data-testid="notif-row">
                  <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" style={{ background: `${m?.color}1A` }}><Icon className="h-4 w-4" style={{ color: m?.color || "#475569" }} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm"><span className="font-medium text-slate-900">{m?.label || n.source}</span><span className="truncate text-slate-600">{n.title}</span></div>
                    {n.hint && <div className="mt-0.5 text-xs text-slate-500 truncate">{n.hint}</div>}
                  </div>
                  <div className="text-right"><div className="text-xs text-slate-400">{fmtDateTime(n.at)}</div>{m?.to && <Link to={m.to} className="text-xs font-medium text-[hsl(var(--primary))] hover:underline">Відкрити »</Link>}</div>
                </li>
              );
            })}</ul>}
      </div>
    </div>
  );
}
