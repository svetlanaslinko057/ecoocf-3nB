/**
 * ContractDrillSheet.jsx — opens a right-side Sheet with deep contract detail.
 *
 * Triggered from RevenueVertical → Contracts Ledger row click.
 *
 * Data sources (parallel, best-effort):
 *   GET /api/admin/contracts/{id}            → contract profile + line items
 *   GET /api/admin/contracts/{id}/payments   → payments timeline
 *   GET /api/admin/contracts/{id}/documents  → linked documents
 *
 * Modular — receives `contract` prop and self-fetches enrichment data.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { CurrencyDollar, Receipt, FileText, Clock, ArrowDown, CheckCircle, Hourglass, Warning } from '@phosphor-icons/react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../ui/sheet';
import { ResponsiveContainer, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';
import { safeGet, fmtMoney, fmtCompact } from './insightsApi';
import { InsightsLoading, InsightsEmpty, MetricChip } from './InsightsCard';

const KpiTile = ({ icon: Icon, label, value, tone = 'neutral' }) => {
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

const PaymentRow = ({ p }) => {
  const status = (p.status || (p.paidAt ? 'paid' : p.dueAt && new Date(p.dueAt) < new Date() ? 'overdue' : 'pending')).toLowerCase();
  const tone = status === 'paid' ? 'positive' : status === 'overdue' ? 'negative' : 'warning';
  const Icon = status === 'paid' ? CheckCircle : status === 'overdue' ? Warning : Hourglass;
  return (
    <li className="flex items-center justify-between gap-3 py-2.5 text-sm">
      <div className="flex min-w-0 items-start gap-2">
        <Icon size={14} weight="duotone" className={
          status === 'paid' ? 'text-emerald-600 shrink-0 mt-0.5' :
          status === 'overdue' ? 'text-red-600 shrink-0 mt-0.5' :
          'text-amber-600 shrink-0 mt-0.5'
        } />
        <div className="min-w-0">
          <p className="truncate font-medium text-zinc-900">{p.label || p.title || p.method || 'Payment'}</p>
          <p className="text-[11px] text-zinc-500">
            {p.paidAt ? `Paid ${p.paidAt.slice(0,10)}` : p.dueAt ? `Due ${p.dueAt.slice(0,10)}` : ''}
            {p.method ? ` · ${p.method}` : ''}
          </p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="text-sm font-semibold tabular-nums text-zinc-900">{fmtMoney(p.amount || 0)}</span>
        <MetricChip value={status} tone={tone} />
      </div>
    </li>
  );
};

const ContractDrillSheet = ({ open, onOpenChange, contract }) => {
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState(null);
  const [payments, setPayments] = useState([]);
  const [docs, setDocs] = useState([]);

  const id = contract?._id || contract?.id || contract?.contractId;

  useEffect(() => {
    if (!open || !id) return;
    let alive = true;
    (async () => {
      setLoading(true);
      const [prof, pay, dcs] = await Promise.all([
        safeGet(`/api/admin/contracts/${encodeURIComponent(id)}`),
        safeGet(`/api/admin/contracts/${encodeURIComponent(id)}/payments`),
        safeGet(`/api/admin/contracts/${encodeURIComponent(id)}/documents`),
      ]);
      if (!alive) return;
      setProfile(prof.data || contract);
      const pays = pay.data?.payments || pay.data?.items || (Array.isArray(pay.data) ? pay.data : []);
      // Sort: most recent first (paid > due)
      const sorted = [...pays].sort((a, b) => {
        const ad = a.paidAt || a.dueAt || a.createdAt || '';
        const bd = b.paidAt || b.dueAt || b.createdAt || '';
        return bd.localeCompare(ad);
      });
      setPayments(sorted);
      const docList = dcs.data?.documents || dcs.data?.items || (Array.isArray(dcs.data) ? dcs.data : []);
      setDocs(docList);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [open, id, contract]);

  // Aggregate payment stats
  const stats = useMemo(() => {
    const total = profile?.amount ?? profile?.totalAmount ?? contract?.amount ?? 0;
    const paid = payments.filter(p => (p.status || '').toLowerCase() === 'paid' || p.paidAt).reduce((s, p) => s + Number(p.amount || 0), 0);
    const overdue = payments.filter(p => {
      const st = (p.status || '').toLowerCase();
      return st === 'overdue' || (!p.paidAt && p.dueAt && new Date(p.dueAt) < new Date());
    }).reduce((s, p) => s + Number(p.amount || 0), 0);
    const pending = Math.max(0, Number(total) - paid - overdue);
    return { total: Number(total), paid, overdue, pending };
  }, [payments, profile, contract]);

  // Build mini-chart for payment cadence (cumulative paid by month)
  const cadence = useMemo(() => {
    if (!payments.length) return [];
    const byMonth = {};
    payments.forEach(p => {
      if (!p.paidAt) return;
      const m = p.paidAt.slice(0, 7);
      byMonth[m] = (byMonth[m] || 0) + Number(p.amount || 0);
    });
    return Object.entries(byMonth).sort().map(([month, value]) => ({ month, value }));
  }, [payments]);

  const status = (profile?.status || contract?.status || 'unknown').toLowerCase();
  const statusTone = status === 'paid' ? 'positive' : status.includes('overdue') ? 'negative' : status === 'draft' ? 'neutral' : 'info';

  const title = profile?.title || profile?.contractNumber || contract?.title || contract?.contractNumber || `Contract ${id || ''}`;
  const subtitle = profile?.customerName || contract?.customerName || profile?.customer || '';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle data-testid="contract-drill-title">{title}</SheetTitle>
          <SheetDescription>{subtitle}</SheetDescription>
        </SheetHeader>

        {loading ? <div className="mt-6"><InsightsLoading rows={4} /></div> : (
          <div className="mt-5 space-y-5">
            {/* Status + amount + progress */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="contract-drill-header">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Status</div>
                  <div className="mt-1"><MetricChip value={status} tone={statusTone} /></div>
                </div>
                <div className="text-right">
                  <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Total</div>
                  <div className="text-2xl font-semibold tabular-nums text-zinc-900">{fmtMoney(stats.total)}</div>
                </div>
              </div>
              {/* Progress bar: paid / overdue / pending */}
              {stats.total > 0 && (
                <div className="mt-3">
                  <div className="mb-1 flex items-center justify-between text-[11px] text-zinc-600">
                    <span>Collected {fmtMoney(stats.paid)}</span>
                    <span className="tabular-nums">{Math.round((stats.paid / stats.total) * 100)}%</span>
                  </div>
                  <div className="flex h-2 w-full overflow-hidden rounded-full bg-zinc-100">
                    <div className="bg-emerald-500" style={{ width: `${(stats.paid / stats.total) * 100}%` }} />
                    <div className="bg-red-500" style={{ width: `${(stats.overdue / stats.total) * 100}%` }} />
                    <div className="bg-amber-300" style={{ width: `${(stats.pending / stats.total) * 100}%` }} />
                  </div>
                </div>
              )}
            </div>

            {/* KPI tiles */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="contract-drill-kpis">
              <KpiTile icon={CheckCircle} label="Paid"     value={fmtMoney(stats.paid)}    tone="positive" />
              <KpiTile icon={Hourglass}   label="Pending"  value={fmtMoney(stats.pending)} tone="warning" />
              <KpiTile icon={Warning}     label="Overdue"  value={fmtMoney(stats.overdue)} tone={stats.overdue > 0 ? 'negative' : 'neutral'} />
              <KpiTile icon={Clock}       label="Age"      value={profile?.ageDays ? `${profile.ageDays}d` : '—'} />
            </div>

            {/* Cadence chart */}
            {cadence.length > 1 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="contract-drill-cadence-chart">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Payment cadence · by month</div>
                <div className="h-28">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={cadence} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                      <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#71717a' }} />
                      <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={42} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={(v) => fmtMoney(v)} />
                      <Bar dataKey="value" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Payment timeline */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="contract-drill-payments-list">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Payments timeline ({payments.length})</span>
                {stats.overdue > 0 && <MetricChip value={`${fmtMoney(stats.overdue)} overdue`} tone="negative" />}
              </div>
              {payments.length === 0 ? <InsightsEmpty title="No payment records" hint="Payments will appear here when recorded against this contract." /> : (
                <ul className="divide-y divide-zinc-100">
                  {payments.map((p, i) => <PaymentRow key={p._id || p.id || i} p={p} />)}
                </ul>
              )}
            </div>

            {/* Linked documents */}
            {docs.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="contract-drill-documents-list">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Linked documents ({docs.length})</div>
                <ul className="divide-y divide-zinc-100">
                  {docs.slice(0, 12).map((d, i) => (
                    <li key={d._id || d.id || i} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText size={13} weight="duotone" className="shrink-0 text-zinc-500" />
                        <p className="truncate font-medium text-zinc-900">{d.title || d.fileName || d._id}</p>
                      </div>
                      <MetricChip value={d.status || d.type || 'doc'} tone={d.status === 'verified' ? 'positive' : 'neutral'} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Owner / customer info */}
            {(profile?.managerEmail || profile?.customerName || contract?.managerEmail) && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Owner & customer</div>
                <div className="grid grid-cols-1 gap-2 text-xs text-zinc-700 sm:grid-cols-2">
                  {(profile?.managerEmail || contract?.managerEmail) && (
                    <div className="rounded-md border border-zinc-200 bg-white px-2 py-1.5">
                      <div className="text-[10px] text-zinc-500">Manager</div>
                      <div className="font-medium">{profile?.managerEmail || contract?.managerEmail}</div>
                    </div>
                  )}
                  {(profile?.customerName || contract?.customerName) && (
                    <div className="rounded-md border border-zinc-200 bg-white px-2 py-1.5">
                      <div className="text-[10px] text-zinc-500">Customer</div>
                      <div className="font-medium">{profile?.customerName || contract?.customerName}</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default ContractDrillSheet;
