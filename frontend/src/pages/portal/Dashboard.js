import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardList, FileCheck2, Truck, BadgeCheck, Building2, Boxes, ArrowRight, Database, ShieldCheck } from "lucide-react";
import { PortalAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { STAGE_ORDER, STAGE_LABELS } from "@/lib/portalMeta";
import { PageHeader, StatCard, TableSkeleton } from "@/components/portal/PortalUI";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  useSeo("Дашборд", "Огляд операцій утилізації небезпечних відходів.");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    PortalAPI.stats()
      .then((r) => alive && setStats(r))
      .catch(() => alive && setErr(true))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  const byStage = stats?.requests_by_stage || {};
  const maxStage = Math.max(1, ...STAGE_ORDER.map((s) => byStage[s] || 0));

  return (
    <div data-testid="portal-dashboard">
      <PageHeader
        title="Огляд"
        subtitle="Ключові показники операційного циклу"
        actions={<Button asChild><Link to="/app/requests" data-testid="dashboard-to-requests">Воронка заявок <ArrowRight className="ml-2 h-4 w-4" /></Link></Button>}
      />

      {loading && <TableSkeleton rows={4} />}
      {err && <div className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] p-4 text-sm text-[#991B1B]">Не вдалося завантажити статистику.</div>}

      {stats && (
        <div className="space-y-8">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={ClipboardList} label="Відкриті заявки" value={stats.open_requests ?? 0} testid="kpi-open-requests" />
            <StatCard icon={FileCheck2} label="Активні договори" value={stats.active_contracts ?? 0} testid="kpi-active-contracts" />
            <StatCard icon={Truck} label="Вивози в роботі" value={stats.pending_pickups ?? 0} testid="kpi-pending-pickups" />
            <StatCard icon={BadgeCheck} label="Підписані акти" value={stats.signed_acts ?? 0} testid="kpi-signed-acts" />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="rounded-2xl border border-[hsl(var(--border))] bg-white p-6 lg:col-span-2" data-testid="dashboard-pipeline">
              <h2 className="text-lg font-semibold text-slate-900">Заявки за етапами</h2>
              <p className="mt-1 text-sm text-slate-500">Розподіл по воронці життєвого циклу.</p>
              <div className="mt-6 space-y-3">
                {STAGE_ORDER.map((s) => {
                  const v = byStage[s] || 0;
                  return (
                    <div key={s} className="flex items-center gap-3">
                      <div className="w-28 shrink-0 text-sm text-slate-600">{STAGE_LABELS[s]}</div>
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[hsl(var(--secondary))]">
                        <div className="h-full rounded-full bg-[hsl(var(--primary))] transition-[width] duration-300" style={{ width: `${(v / maxStage) * 100}%` }} />
                      </div>
                      <div className="w-8 shrink-0 text-right text-sm font-semibold text-slate-800">{v}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-4">
              <StatCard icon={Building2} label="Компанії" value={stats.companies ?? 0} testid="kpi-companies" />
              <StatCard icon={Boxes} label="Об’єкти" value={stats.objects ?? 0} testid="kpi-objects" />
              <StatCard icon={ShieldCheck} label="Ліцензовано (приймаємо)" value={stats.accepted_codes ?? 0} hint={`з ${stats.codes ?? 0} кодів нацпереліку`} testid="kpi-accepted-codes" />
              <StatCard icon={Database} label="Коди відходів (нацперелік)" value={stats.codes ?? 0} hint={`з них небезпечних: ${stats.hazardous_codes ?? 0}`} testid="kpi-codes" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
