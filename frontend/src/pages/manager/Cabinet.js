import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Users, Trophy, Wallet, Phone, ClipboardList, AlertTriangle, CalendarClock,
  TrendingUp, ArrowRight, Sparkles, PhoneMissed, PhoneIncoming, PhoneOutgoing,
} from "lucide-react";
import { ManagerAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, TableSkeleton, EmptyState } from "@/components/portal/PortalUI";
import { StatusPill, FunnelBar, SectionCard } from "@/components/manager/ManagerUI";
import {
  LEAD_STATUS_ORDER, LEAD_STATUS_LABELS, LEAD_STATUS_TONE,
  CALL_STATUS_TONE, CALL_STATUS_LABELS, CALL_DIR_LABELS,
  fmtMoney, fmtDate, fmtDateTime, dueMeta,
} from "@/lib/managerMeta";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";

export default function Cabinet() {
  useSeo("Кабінет менеджера", "Персональний робочий простір менеджера: ліди, угоди, завдання, дзвінки.");
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [err, setErr] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    ManagerAPI.overview()
      .then((r) => { setData(r); setErr(false); })
      .catch(() => setErr(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const seed = async () => {
    setSeeding(true);
    try {
      const r = await ManagerAPI.seed();
      toast.success(`Демо-дані готові: ${r.seeded.leads} лідів, ${r.seeded.deals} угод, ${r.seeded.tasks} завдань`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не вдалося згенерувати демо-дані");
    } finally { setSeeding(false); }
  };

  const k = data?.kpis || {};
  const funnel = data?.funnel || {};
  const maxFunnel = Math.max(1, ...LEAD_STATUS_ORDER.map((s) => funnel[s] || 0));
  const isEmpty = !loading && data && (k.leads_total || 0) === 0;

  return (
    <div data-testid="manager-cabinet">
      <PageHeader
        title={`Вітаю, ${(user?.name || user?.email || "менеджере").split("@")[0]}!`}
        subtitle="Ваш персональний робочий простір: воронка, угоди, завдання та дзвінки"
        actions={
          <Button variant="outline" onClick={seed} disabled={seeding} data-testid="seed-demo-button">
            <Sparkles className="mr-2 h-4 w-4" /> {seeding ? "Генеруємо…" : "Демо-дані"}
          </Button>
        }
      />

      {loading && <TableSkeleton rows={5} />}
      {err && <div className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-4 text-sm text-[#991B1B]">Не вдалося завантажити дані кабінету.</div>}

      {isEmpty && (
        <EmptyState
          icon={Sparkles}
          title="Кабінет поки порожній"
          hint="Згенеруйте набір реалістичних демо-даних (ліди, угоди, завдання, дзвінки), щоб одразу побачити робочий простір у дії."
          action={<Button onClick={seed} disabled={seeding} data-testid="seed-demo-cta"><Sparkles className="mr-2 h-4 w-4" /> {seeding ? "Генеруємо…" : "Заповнити демо-даними"}</Button>}
          testid="cabinet-empty"
        />
      )}

      {data && !isEmpty && (
        <div className="space-y-8">
          {/* KPI grid */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={Users} label="Мої ліди" value={k.leads_total ?? 0} hint={`відкритих: ${k.open_leads ?? 0}`} testid="kpi-leads" />
            <StatCard icon={TrendingUp} label="Конверсія" value={`${k.conversion ?? 0}%`} hint={`виграно: ${k.won_leads ?? 0}`} testid="kpi-conversion" />
            <StatCard icon={Wallet} label="Виграно (міс.)" value={fmtMoney(k.won_value_month)} hint={`всього: ${fmtMoney(k.won_value)}`} testid="kpi-won-value" />
            <StatCard icon={Trophy} label="Воронка угод" value={fmtMoney(k.pipeline_value)} hint={`відкритих: ${k.deals_open ?? 0}`} testid="kpi-pipeline" />
          </div>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={ClipboardList} label="Завдання сьогодні" value={k.tasks_today ?? 0} hint={`відкритих: ${k.tasks_open ?? 0}`} testid="kpi-tasks-today" />
            <StatCard icon={AlertTriangle} label="Прострочені" value={k.tasks_overdue ?? 0} hint="потребують уваги" testid="kpi-tasks-overdue" />
            <StatCard icon={Phone} label="Дзвінки (тиждень)" value={k.calls_week ?? 0} hint={`сьогодні: ${k.calls_today ?? 0}`} testid="kpi-calls-week" />
            <StatCard icon={PhoneMissed} label="Пропущені" value={k.calls_missed ?? 0} hint="за весь період" testid="kpi-calls-missed" />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Funnel */}
            <SectionCard
              className="lg:col-span-2"
              title="Воронка лідів"
              subtitle="Розподіл моїх лідів за статусами"
              actions={<Button asChild variant="ghost" size="sm"><Link to="/app/cabinet/leads" data-testid="to-leads">Усі ліди <ArrowRight className="ml-1.5 h-4 w-4" /></Link></Button>}
              testid="funnel-card"
            >
              <div className="space-y-3">
                {LEAD_STATUS_ORDER.map((s) => (
                  <FunnelBar
                    key={s}
                    label={LEAD_STATUS_LABELS[s]}
                    value={funnel[s] || 0}
                    max={maxFunnel}
                    tone={s === "won" ? "pos" : s === "lost" ? "danger" : "primary"}
                  />
                ))}
              </div>
            </SectionCard>

            {/* Upcoming tasks */}
            <SectionCard
              title="Найближчі завдання"
              actions={<Button asChild variant="ghost" size="sm"><Link to="/app/cabinet/tasks" data-testid="to-tasks"><CalendarClock className="h-4 w-4" /></Link></Button>}
              testid="upcoming-tasks-card"
            >
              {(data.upcoming_tasks || []).length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-400">Немає відкритих завдань 🎉</p>
              ) : (
                <ul className="space-y-3">
                  {data.upcoming_tasks.map((t) => {
                    const dm = dueMeta(t.due_at);
                    return (
                      <li key={t.id} className="flex items-start gap-3">
                        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dm.overdue ? "bg-[#B91C1C]" : dm.soon ? "bg-[#D97706]" : "bg-[#0E5E3A]"}`} />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-slate-800">{t.title}</div>
                          <div className={`text-xs ${dm.overdue ? "text-[#B91C1C]" : "text-slate-400"}`}>{dm.label}</div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </SectionCard>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Recent leads */}
            <SectionCard
              title="Останні ліди"
              actions={<Button asChild variant="ghost" size="sm"><Link to="/app/cabinet/leads">Перейти <ArrowRight className="ml-1.5 h-4 w-4" /></Link></Button>}
              testid="recent-leads-card"
            >
              {(data.recent_leads || []).length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-400">Лідів ще немає</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {data.recent_leads.map((l) => (
                    <li key={l.id} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-slate-800">{l.company || l.name}</div>
                        <div className="truncate text-xs text-slate-400">{l.name} · {fmtDate(l.created_at)}</div>
                      </div>
                      <StatusPill tone={LEAD_STATUS_TONE[l.status]}>{LEAD_STATUS_LABELS[l.status] || l.status}</StatusPill>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            {/* Recent calls */}
            <SectionCard
              title="Останні дзвінки"
              actions={<Button asChild variant="ghost" size="sm"><Link to="/app/cabinet/calls">Перейти <ArrowRight className="ml-1.5 h-4 w-4" /></Link></Button>}
              testid="recent-calls-card"
            >
              {(data.recent_calls || []).length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-400">Дзвінків ще немає</p>
              ) : (
                <ul className="divide-y divide-slate-100">
                  {data.recent_calls.map((c) => (
                    <li key={c.id} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="flex min-w-0 items-center gap-2.5">
                        {c.direction === "inbound"
                          ? <PhoneIncoming className="h-4 w-4 shrink-0 text-[#0E5E3A]" />
                          : <PhoneOutgoing className="h-4 w-4 shrink-0 text-slate-400" />}
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-slate-800">{c.contactName || c.phone}</div>
                          <div className="truncate text-xs text-slate-400">{CALL_DIR_LABELS[c.direction]} · {fmtDateTime(c.started_at)}</div>
                        </div>
                      </div>
                      <StatusPill tone={CALL_STATUS_TONE[c.status]}>{CALL_STATUS_LABELS[c.status] || c.status}</StatusPill>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>
        </div>
      )}
    </div>
  );
}
