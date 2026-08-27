/**
 * ManagerDrillSheet.jsx — opens a right-side Sheet with deep manager pipeline detail.
 *
 * Data sources:
 *   GET /api/team/managers/{id}     → manager profile + load (best-effort)
 *   GET /api/admin/kpi/leaderboard  → cross-checking score
 *   GET /api/team/leads/stale?owner=... → stale leads belonging to this manager
 *   GET /api/team/payments/overdue?owner=... → overdue invoices
 *   GET /api/risk/manager/{id}     → risk score (if available)
 */
import React, { useEffect, useState } from 'react';
import { UsersThree, Target, Clock, Warning, CurrencyDollar, Trophy } from '@phosphor-icons/react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../ui/sheet';
import { safeGet, fmtCompact, fmtMoney, fmtPct, riskBandClass } from './insightsApi';
import { InsightsLoading, InsightsEmpty, MetricChip } from './InsightsCard';

const SectionTile = ({ icon: Icon, label, value, tone = 'neutral' }) => {
  const toneClass = tone === 'positive' ? 'border-emerald-200 bg-emerald-50' :
                    tone === 'warning' ? 'border-amber-200 bg-amber-50' :
                    tone === 'negative' ? 'border-red-200 bg-red-50' :
                    'border-zinc-200 bg-white';
  return (
    <div className={`rounded-xl border ${toneClass} px-3 py-2.5`}>
      <div className="flex items-center justify-between text-zinc-500">
        <span className="text-[10.5px] font-medium uppercase tracking-wider">{label}</span>
        {Icon && <Icon size={13} weight="duotone" />}
      </div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-zinc-900">{value}</div>
    </div>
  );
};

const ManagerDrillSheet = ({ open, onOpenChange, manager }) => {
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState(null);
  const [risk, setRisk] = useState(null);
  const [staleLeads, setStaleLeads] = useState([]);
  const [overdueInvoices, setOverdueInvoices] = useState([]);

  const id = manager?.id || manager?._id;
  const email = manager?.email || manager?.ownerEmail;

  useEffect(() => {
    if (!open || (!id && !email)) return;
    let alive = true;
    (async () => {
      setLoading(true);
      const [prof, riskRes, stale, overdue] = await Promise.all([
        id ? safeGet(`/api/team/managers/${encodeURIComponent(id)}`) : Promise.resolve({ data: null }),
        id ? safeGet(`/api/risk/manager/${encodeURIComponent(id)}`) : Promise.resolve({ data: null }),
        safeGet(`/api/team/leads/stale`, email ? { owner: email } : undefined),
        safeGet(`/api/team/payments/overdue`, email ? { owner: email } : undefined),
      ]);
      if (!alive) return;
      setProfile(prof.data || manager);
      setRisk(riskRes.data || null);
      const sa = Array.isArray(stale.data) ? stale.data : stale.data?.items || [];
      const oa = Array.isArray(overdue.data) ? overdue.data : overdue.data?.items || [];
      // filter to this manager if backend returned everyone
      setStaleLeads(email ? sa.filter(l => (l.ownerEmail || l.owner || l.managerEmail) === email) : sa);
      setOverdueInvoices(email ? oa.filter(l => (l.ownerEmail || l.owner || l.managerEmail) === email) : oa);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [open, id, email, manager]);

  const riskScore = risk?.score ?? manager?.score;
  const band = riskBandClass(riskScore);
  const total = (profile?.leadsCount ?? profile?.leads ?? 0) + (profile?.customersCount ?? profile?.customers ?? 0) + (profile?.dealsCount ?? profile?.deals ?? 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle data-testid="manager-drill-title">{profile?.name || manager?.name || email || 'Manager'}</SheetTitle>
          <SheetDescription>{email || '—'} · {profile?.role || manager?.role || 'manager'}</SheetDescription>
        </SheetHeader>

        {loading ? <div className="mt-6"><InsightsLoading rows={4} /></div> : (
          <div className="mt-5 space-y-5">
            {/* Risk + KPI strip */}
            <div className={`rounded-2xl border ${band.border} ${band.bg} p-4`} data-testid="manager-drill-risk">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Risk score</div>
                  <div className={`text-3xl font-semibold tabular-nums ${band.text}`}>{riskScore != null ? Math.round(riskScore) : '—'}</div>
                  <div className="text-[11px] text-zinc-600">{riskScore >= 70 ? 'Critical — needs immediate review' : riskScore >= 40 ? 'Watch — monitor weekly' : 'Healthy'}</div>
                </div>
                <Trophy size={36} weight="duotone" className={band.text} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="manager-drill-kpi-tiles">
              <SectionTile icon={UsersThree} label="Leads"     value={fmtCompact(profile?.leadsCount ?? profile?.leads ?? 0)} />
              <SectionTile icon={UsersThree} label="Customers" value={fmtCompact(profile?.customersCount ?? profile?.customers ?? 0)} />
              <SectionTile icon={Target}     label="Deals"     value={fmtCompact(profile?.dealsCount ?? profile?.deals ?? 0)} />
              <SectionTile icon={Clock}      label="Total load" value={fmtCompact(total)} tone={total > 50 ? 'negative' : total > 25 ? 'warning' : 'positive'} />
            </div>

            {/* Performance row */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <SectionTile label="Win rate"          value={fmtPct(profile?.conversionRate ?? profile?.winRate ?? manager?.score ?? 0)} />
              <SectionTile label="Avg response"      value={profile?.avgResponseMinutes ? `${profile.avgResponseMinutes}m` : '—'} />
              <SectionTile label="Revenue (MTD)"     value={fmtMoney(profile?.revenueMtd ?? profile?.revenue ?? 0)} />
            </div>

            {/* Stale leads */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="manager-drill-stale-leads">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Stale leads ({staleLeads.length})</span>
                {staleLeads.length > 0 && <MetricChip value="action needed" tone="warning" />}
              </div>
              {staleLeads.length === 0 ? <InsightsEmpty title="No stale leads" /> : (
                <ul className="divide-y divide-zinc-100">
                  {staleLeads.slice(0, 8).map((l, i) => (
                    <li key={l._id || l.id || i} className="flex items-center justify-between py-2 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-zinc-900">{l.name || l.email || l.phone || `Lead ${l._id || l.id}`}</p>
                        <p className="text-[11px] text-zinc-500">{l.source || '—'} · last touch {l.lastTouchAt || l.updatedAt || '—'}</p>
                      </div>
                      <MetricChip value={l.ageDays ? `${l.ageDays}d` : '—'} tone="warning" />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Overdue invoices */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="manager-drill-overdue-invoices">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Overdue invoices ({overdueInvoices.length})</span>
                {overdueInvoices.length > 0 && <MetricChip value="$" tone="negative" />}
              </div>
              {overdueInvoices.length === 0 ? <InsightsEmpty title="No overdue invoices" /> : (
                <ul className="divide-y divide-zinc-100">
                  {overdueInvoices.slice(0, 8).map((p, i) => (
                    <li key={p._id || p.id || i} className="flex items-center justify-between py-2 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-zinc-900">{p.title || p.invoiceNumber || p.dealTitle || `Invoice ${p._id || p.id}`}</p>
                        <p className="text-[11px] text-zinc-500">{p.daysOverdue ? `${p.daysOverdue}d overdue` : '—'} · {p.customerName || ''}</p>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-red-700">{fmtMoney(p.amount || 0)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Risk drivers (if backend provides) */}
            {risk?.drivers && Array.isArray(risk.drivers) && risk.drivers.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Risk drivers</div>
                <ul className="space-y-1.5">
                  {risk.drivers.slice(0, 5).map((d, i) => (
                    <li key={i} className="flex items-center justify-between rounded-md bg-zinc-50 px-2 py-1.5">
                      <span className="text-sm text-zinc-700">{d.label || d.name}</span>
                      <MetricChip value={fmtCompact(d.count || d.value || 0)} tone={d.severity === 'critical' ? 'negative' : 'warning'} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default ManagerDrillSheet;
