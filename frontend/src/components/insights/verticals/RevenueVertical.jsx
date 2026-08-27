/**
 * RevenueVertical.jsx — Payment Analytics + Contracts Accounting + Documents merged.
 *
 * Sections:
 *   1. Revenue Trend
 *   2. AR Ageing (buckets + table)
 *   3. Contracts Ledger
 *   4. Documents Registry & Verification Queue
 */
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, BarChart, Bar } from 'recharts';
import { CurrencyDollar, FileText, Receipt, Download } from '@phosphor-icons/react';
import { InsightsCard, InsightsSection, InsightsLoading, InsightsEmpty, MetricChip } from '../shared/InsightsCard';
import { safeGet, fmtMoney, fmtCompact } from '../shared/insightsApi';
import { API_URL } from '../../../App';
import ContractDrillSheet from '../shared/ContractDrillSheet';
import { useLang } from '../../../i18n';

const RevenueVertical = ({ scope, period = 30 }) => {
  const { t } = useLang();
  const [loading, setLoading] = useState(true);
  const [owner, setOwner] = useState(null);
  const [contracts, setContracts] = useState([]);
  const [docs, setDocs] = useState([]);
  const [pending, setPending] = useState([]);
  const [bucketFilter, setBucketFilter] = useState('all');
  const [drillContract, setDrillContract] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [o, c, d, p] = await Promise.all([
        safeGet('/api/owner-dashboard', { days: period }),
        safeGet('/api/admin/contracts/accounting'),
        safeGet('/api/documents'),
        safeGet('/api/documents/queue/pending-verification'),
      ]);
      if (!alive) return;
      setOwner(o.data || {});
      setContracts(c.data?.contracts || c.data?.items || []);
      setDocs(Array.isArray(d.data?.data) ? d.data.data : Array.isArray(d.data) ? d.data : []);
      setPending(Array.isArray(p.data) ? p.data : p.data?.items || []);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [scope, period]);

  if (loading) return <InsightsLoading rows={8} />;

  // Build AR ageing buckets from contracts/invoices
  const buckets = { '0-30': [], '30-60': [], '60-90': [], '90+': [] };
  contracts.forEach(c => {
    const age = Number(c.ageDays ?? c.daysOutstanding ?? c.overdueDays ?? 0);
    const status = (c.status || '').toLowerCase();
    if (status === 'paid' || status === 'closed' || status === 'cancelled') return;
    if (age <= 30) buckets['0-30'].push(c);
    else if (age <= 60) buckets['30-60'].push(c);
    else if (age <= 90) buckets['60-90'].push(c);
    else buckets['90+'].push(c);
  });

  const visibleContracts = bucketFilter === 'all' ? contracts : buckets[bucketFilter];

  // Revenue trend series
  const trend = owner?.revenueTrend || owner?.revenueSeries || owner?.series || [];
  const breakdown = owner?.revenueByManager || owner?.byManager || [];

  const exportContracts = () => {
    window.open(`${API_URL}/api/admin/contracts/export`, '_blank');
  };

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="space-y-6">
      <InsightsSection id="revenue-trend" title={t('ins_sec_revenue_trend')} subtitle={`${t('ins_period_' + (period === 7 ? '7d' : period === 90 ? '90d' : '30d'))} · ${fmtMoney(owner?.totalRevenue || owner?.revenue || 0)}`} tip={t('ins_tip_revenue_trend')}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <InsightsCard className="lg:col-span-8" title={t('ins_sec_revenue_trend')} testId="insights-revenue-trend-card">
            {trend.length === 0 ? <InsightsEmpty title="No revenue data" /> : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trend} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#71717a' }} />
                    <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={48} tickFormatter={v => fmtMoney(v).replace(/\D*$/,'')} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} formatter={v => fmtMoney(v)} />
                    <Line type="monotone" dataKey="revenue" stroke="#18181b" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </InsightsCard>
          <InsightsCard className="lg:col-span-4" title={t('ins_card_by_manager')}>
            {breakdown.length === 0 ? <InsightsEmpty title="—" /> : (
              <ul className="space-y-2">
                {breakdown.slice(0, 8).map((b, i) => (
                  <li key={i} className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2">
                    <span className="truncate text-sm text-zinc-700">{b.name || b.manager || b.email}</span>
                    <MetricChip value={fmtMoney(b.revenue || b.amount || 0)} tone="positive" />
                  </li>
                ))}
              </ul>
            )}
          </InsightsCard>
        </div>
      </InsightsSection>

      <InsightsSection id="ar-ageing" title={t('ins_sec_ar_ageing')} subtitle={t('ins_sec_ar_ageing_sub')} tip={t('ins_tip_ar_ageing')}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {['0-30','30-60','60-90','90+'].map((k) => {
            const arr = buckets[k];
            const sum = arr.reduce((a, b) => a + Number(b.amount || b.totalAmount || 0), 0);
            const tone = k === '90+' ? 'negative' : k === '60-90' ? 'warning' : 'neutral';
            const isActive = bucketFilter === k;
            return (
              <button key={k} onClick={() => setBucketFilter(isActive ? 'all' : k)}
                data-testid={`insights-ar-bucket-${k.replace('+','plus')}`}
                className={`flex flex-col rounded-2xl border bg-white p-4 text-left shadow-sm transition-[box-shadow,border-color] duration-150 hover:border-zinc-300 hover:shadow-md ${isActive ? 'border-zinc-900' : 'border-zinc-200'}`}>
                <span className="text-[11px] uppercase tracking-wider text-zinc-500">{k} days</span>
                <span className="mt-1 text-xl font-semibold tabular-nums text-zinc-900">{fmtMoney(sum)}</span>
                <MetricChip className="mt-2 self-start" value={`${arr.length} invoices`} tone={tone} />
              </button>
            );
          })}
        </div>
      </InsightsSection>

      <InsightsSection id="contracts-ledger" title={t('ins_sec_contracts_ledger')} subtitle={`${visibleContracts.length} · ${bucketFilter==='all' ? '' : bucketFilter + ' days'}`} tip={t('ins_tip_contracts_ledger')}
        actions={<button onClick={exportContracts} data-testid="insights-contracts-export-button" className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"><Download size={12} weight="bold" /> {t('ins_btn_export_csv')}</button>}>
        <InsightsCard padded={false} testId="insights-contracts-ledger-table">
          {visibleContracts.length === 0 ? <div className="p-5"><InsightsEmpty title="No contracts match filter" /></div> : (
            <div className="max-h-[480px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-2 text-left font-medium">Contract</th>
                  <th className="px-4 py-2 text-left font-medium">Customer</th>
                  <th className="px-4 py-2 text-left font-medium">Manager</th>
                  <th className="px-4 py-2 text-right font-medium">Amount</th>
                  <th className="px-4 py-2 text-right font-medium">Age</th>
                  <th className="px-4 py-2 text-left font-medium">Status</th>
                </tr></thead>
                <tbody>
                  {visibleContracts.slice(0, 100).map((c, i) => (
                    <tr key={c._id || c.id || i} className="cursor-pointer border-b border-zinc-50 hover:bg-zinc-50" onClick={() => setDrillContract(c)} data-testid={`insights-contract-row-${i}`}>
                      <td className="px-4 py-2 font-medium text-zinc-900">{c.title || c.contractNumber || c.dealTitle || c._id}</td>
                      <td className="px-4 py-2 text-zinc-700">{c.customerName || c.customer || '—'}</td>
                      <td className="px-4 py-2 text-zinc-700">{c.managerEmail || c.owner || '—'}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-zinc-900">{fmtMoney(c.amount || c.totalAmount || 0)}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{c.ageDays ? `${c.ageDays}d` : '—'}</td>
                      <td className="px-4 py-2"><MetricChip value={c.status || '—'} tone={String(c.status).toLowerCase()==='paid'?'positive':String(c.status).toLowerCase().includes('overdue')?'negative':'neutral'} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      <InsightsSection id="documents-registry" title="Documents Registry & Verification Queue" subtitle="Registry of signed/unsigned docs and items awaiting verification">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><FileText size={14} weight="duotone" /> Registry</span>} testId="insights-documents-registry-table" padded={false}>
            {docs.length === 0 ? <div className="p-5"><InsightsEmpty title="No documents" /></div> : (
              <div className="max-h-[320px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                    <th className="px-4 py-2 text-left font-medium">Document</th>
                    <th className="px-4 py-2 text-left font-medium">Type</th>
                    <th className="px-4 py-2 text-left font-medium">Status</th>
                  </tr></thead>
                  <tbody>
                    {docs.slice(0, 50).map((d, i) => (
                      <tr key={d._id || d.id || i} className="border-b border-zinc-50 hover:bg-zinc-50">
                        <td className="px-4 py-2 font-medium text-zinc-900 truncate">{d.title || d.fileName || d.name || d._id}</td>
                        <td className="px-4 py-2 text-zinc-700">{d.type || d.documentType || '—'}</td>
                        <td className="px-4 py-2"><MetricChip value={d.status || 'unknown'} tone={d.status==='verified'?'positive':d.status==='pending'?'warning':'neutral'} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </InsightsCard>
          <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Receipt size={14} weight="duotone" /> {t('ins_card_documents_verification')} ({pending.length})</span>} tip={t('ins_tip_documents_verification')} testId="insights-documents-verification-queue" padded={false}>
            {pending.length === 0 ? <div className="p-5"><InsightsEmpty title="Verification queue clear" /></div> : (
              <ul className="divide-y divide-zinc-100 max-h-[320px] overflow-auto">
                {pending.slice(0, 50).map((p, i) => (
                  <li key={p._id || p.id || i} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-zinc-50">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-zinc-900">{p.title || p.fileName || p._id}</p>
                      <p className="text-[11px] text-zinc-500">{p.type || '—'} · {p.uploadedBy || '—'}</p>
                    </div>
                    <MetricChip value="Pending" tone="warning" />
                  </li>
                ))}
              </ul>
            )}
          </InsightsCard>
        </div>
      </InsightsSection>

      {/* Contract drill-down sheet — opens on contract row click */}
      <ContractDrillSheet open={!!drillContract} onOpenChange={(o) => !o && setDrillContract(null)} contract={drillContract} />
    </motion.div>
  );
};

export default RevenueVertical;
