/**
 * BIBI Cars — Wave 12 — Finance360
 *
 * Operational money control center, scope-aware:
 *   - admin/owner  → all deals
 *   - team_lead    → own + team
 *   - manager      → own only
 *
 * Tabs:
 *   1. Overview     — KPI grid + Revenue At Risk (12B) + Deals by stage
 *   2. Transactions — unified journal (deposits + payments + refunds)
 *                     with type / status / manager / date / search filters
 *   3. Outstanding  — deals still owing money, sorted by days_overdue
 *   4. Manager P&L  — (12B) per-manager revenue / profit / outstanding /
 *                     at_risk / avg collection days / financial health
 *   5. Collections  — (12B) deals needing active follow-up, worst first
 *
 * "Refunds" is a one-click chip filter inside Transactions (type=refund).
 *
 * Wave 12C will add: Forecasting / Cash Flow projection.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  ChartLine, CurrencyEur, TrendUp, Wallet, ReceiptX, Coins, Clock,
  ArrowsClockwise, Warning, MagnifyingGlass, FunnelSimple, ChartPieSlice,
  ArrowSquareOut, ArrowsCounterClockwise, UsersThree, Lifebuoy, Heartbeat,
} from '@phosphor-icons/react';

import { API_URL, useAuth } from '../App';
import { PageHeader, PageTabs, HeaderActionButton } from '../components/ui/PageHeader';
import RefreshButton from '../components/ui/RefreshButton';
import { HelpTooltip } from '../components/ui/HelpTooltip';
import RoleZoneBadge from '../components/ui/RoleZoneBadge';
import { Select } from '../components/ui/Select';
import { useLang } from '../i18n';

// ─── Helpers ─────────────────────────────────────────────────────────────
const fmt = (n, ccy = 'EUR') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return String(iso); }
};

const typeBadge = (type) => {
  const cfg = {
    deposit: { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', label: 'Deposit' },
    payment: { cls: 'bg-sky-50 text-sky-700 border-sky-200',             label: 'Payment' },
    refund:  { cls: 'bg-red-50 text-red-700 border-red-200',             label: 'Refund'  },
    adjustment: { cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',      label: 'Adjustment' },
  }[type] || { cls: 'bg-zinc-100 text-zinc-700 border-zinc-200', label: type };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 border text-[10px] uppercase tracking-wider font-bold ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
};

const statusBadge = (status) => {
  const v = (status || '').toLowerCase();
  let cls = 'bg-amber-50 text-amber-800 border-amber-200';
  if (['confirmed', 'paid', 'received'].includes(v)) cls = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (['rejected', 'failed'].includes(v))            cls = 'bg-red-50 text-red-700 border-red-200';
  if (['refunded', 'voided'].includes(v))            cls = 'bg-zinc-100 text-zinc-700 border-zinc-200';
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 border text-[10px] uppercase tracking-wider font-bold ${cls}`}>
      {v || 'pending'}
    </span>
  );
};

// ─── Wave 12B — Financial Health segment ─────────────────────────────────
const SEGMENT_CFG = {
  healthy:   { label: 'Healthy',   cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: '#10B981' },
  warning:   { label: 'Warning',   cls: 'bg-amber-50 text-amber-800 border-amber-200',       dot: '#F59E0B' },
  at_risk:   { label: 'At Risk',   cls: 'bg-orange-50 text-orange-800 border-orange-200',    dot: '#EA580C' },
  critical:  { label: 'Critical',  cls: 'bg-red-50 text-red-700 border-red-200',             dot: '#DC2626' },
  cancelled: { label: 'Cancelled', cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',         dot: '#71717A' },
};

const SegmentBadge = ({ segment, testId }) => {
  const cfg = SEGMENT_CFG[segment] || SEGMENT_CFG.healthy;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${cfg.cls}`}
      data-testid={testId || `segment-${segment}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {cfg.label}
    </span>
  );
};

const KpiTile = ({ icon: Icon, label, value, hint, tone = 'neutral', testId, onClick, tooltip }) => {
  const toneCls = {
    neutral: 'bg-white border-[#E4E4E7]',
    good:    'bg-emerald-50 border-emerald-200',
    warn:    'bg-amber-50 border-amber-200',
    bad:     'bg-red-50 border-red-200',
  }[tone] || 'bg-white border-[#E4E4E7]';
  const interactive = onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : '';
  const tile = (
    <div
      className={`border rounded-2xl p-4 ${toneCls} ${interactive}`}
      data-testid={testId}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
    >
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
        <Icon size={14} weight="bold" /> {label}
      </div>
      <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{value}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5">{hint}</div> : null}
    </div>
  );
  return tooltip ? <HelpTooltip text={tooltip}>{tile}</HelpTooltip> : tile;
};

const TABS_FACTORY = (t) => ([
  { key: 'overview',     label: t('w12a_tab_overview'),     icon: ChartLine,    tooltip: t('tip_w12a_tab_overview') },
  { key: 'transactions', label: t('w12a_tab_transactions'), icon: CurrencyEur,  tooltip: t('tip_w12a_tab_transactions') },
  { key: 'outstanding',  label: t('w12a_tab_outstanding'),  icon: ReceiptX,     tooltip: t('tip_w12a_tab_outstanding') },
  { key: 'managers',     label: t('w12a_tab_managers'),     icon: UsersThree,   tooltip: t('tip_w12a_tab_managers') },
  { key: 'collections',  label: t('w12a_tab_collections'),  icon: Lifebuoy,     tooltip: t('tip_w12a_tab_collections') },
]);

// ─── Page ────────────────────────────────────────────────────────────────
const Finance360 = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLang();
  const TABS = useMemo(() => TABS_FACTORY(t), [t]);

  const [tab, setTab] = useState('overview');

  // Overview
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(true);

  // Managers (for filter dropdowns)
  const [managers, setManagers] = useState([]);

  // Transactions
  const [txns, setTxns] = useState({ items: [], total: 0 });
  const [loadingTxns, setLoadingTxns] = useState(false);
  const [filters, setFilters] = useState({ type: '', status: '', manager_id: '', q: '' });

  // Outstanding
  const [outstanding, setOutstanding] = useState({ items: [], summary: { outstanding: 0, deals: 0 } });
  const [loadingOutstanding, setLoadingOutstanding] = useState(false);

  // Wave 12B — Manager P&L
  const [managerPnl, setManagerPnl] = useState({ items: [], total: 0 });
  const [loadingPnl, setLoadingPnl] = useState(false);
  const [pnlSort, setPnlSort] = useState({ key: 'at_risk', dir: 'desc' });

  // Wave 12B — Collections queue
  const [collections, setCollections] = useState({ items: [], total: 0, summary: { outstanding: 0, deals: 0, by_segment: { critical: 0, at_risk: 0, warning: 0 } } });
  const [loadingColl, setLoadingColl] = useState(false);
  const [collDays, setCollDays] = useState(7);

  const ccy = overview?.currency || 'EUR';
  const risk = overview?.risk;

  // ── data loaders ───────────────────────────────────────────────────────
  const loadOverview = useCallback(async () => {
    setLoadingOverview(true);
    try {
      const r = await axios.get(`${API_URL}/api/finance/overview`);
      setOverview(r.data?.data || null);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load overview');
    } finally { setLoadingOverview(false); }
  }, []);

  const loadManagers = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/finance/managers`);
      setManagers(r.data?.items || []);
    } catch { /* non-fatal */ }
  }, []);

  const loadTxns = useCallback(async (params) => {
    const eff = params || filters;
    setLoadingTxns(true);
    try {
      const q = new URLSearchParams();
      Object.entries(eff).forEach(([k, v]) => { if (v) q.set(k, v); });
      q.set('limit', '200');
      const r = await axios.get(`${API_URL}/api/finance/transactions?${q}`);
      setTxns({ items: r.data?.items || [], total: r.data?.total || 0 });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load transactions');
    } finally { setLoadingTxns(false); }
  }, [filters]);

  const loadOutstanding = useCallback(async () => {
    setLoadingOutstanding(true);
    try {
      const r = await axios.get(`${API_URL}/api/finance/outstanding`);
      setOutstanding({
        items:   r.data?.items   || [],
        summary: r.data?.summary || { outstanding: 0, deals: 0 },
      });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load outstanding');
    } finally { setLoadingOutstanding(false); }
  }, []);

  const loadManagerPnl = useCallback(async () => {
    setLoadingPnl(true);
    try {
      const r = await axios.get(`${API_URL}/api/finance/managers/pnl`);
      setManagerPnl({ items: r.data?.items || [], total: r.data?.total || 0 });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load Manager P&L');
    } finally { setLoadingPnl(false); }
  }, []);

  const loadCollections = useCallback(async (days) => {
    const d = typeof days === 'number' ? days : collDays;
    setLoadingColl(true);
    try {
      const q = new URLSearchParams();
      q.set('min_days_overdue', String(d));
      q.set('limit', '200');
      const r = await axios.get(`${API_URL}/api/finance/collections?${q}`);
      setCollections({
        items:   r.data?.items   || [],
        total:   r.data?.total   || 0,
        summary: r.data?.summary || { outstanding: 0, deals: 0, by_segment: { critical: 0, at_risk: 0, warning: 0 } },
      });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load Collections');
    } finally { setLoadingColl(false); }
  }, [collDays]);

  useEffect(() => { loadOverview(); loadManagers(); }, [loadOverview, loadManagers]);
  useEffect(() => { if (tab === 'transactions') loadTxns(filters); }, [tab, loadTxns, filters]);
  useEffect(() => { if (tab === 'outstanding')  loadOutstanding(); }, [tab, loadOutstanding]);
  useEffect(() => { if (tab === 'managers')     loadManagerPnl();  }, [tab, loadManagerPnl]);
  useEffect(() => { if (tab === 'collections')  loadCollections(collDays); }, [tab, loadCollections, collDays]);

  const refreshAll = () => {
    loadOverview();
    if (tab === 'transactions') loadTxns(filters);
    if (tab === 'outstanding')  loadOutstanding();
    if (tab === 'managers')     loadManagerPnl();
    if (tab === 'collections')  loadCollections(collDays);
  };

  // ── overview derived ───────────────────────────────────────────────────
  const tot = overview?.totals || {};
  const c = overview?.counts || {};
  const byStage = useMemo(() => Object.entries(overview?.by_stage || {}).sort((a, b) => b[1] - a[1]), [overview]);

  const profitTone   = (tot.profit || 0)  > 0 ? 'good'  : (tot.profit || 0)  < 0 ? 'bad' : 'neutral';
  const outstandTone = (tot.outstanding || 0) > 0 ? 'warn' : 'good';
  const riskTotal    = risk?.at_risk_total || 0;
  const riskTone     = riskTotal > 0 ? 'bad' : 'good';
  const riskSegments = risk?.by_segment || { warning: { count: 0 }, at_risk: { count: 0 }, critical: { count: 0 } };

  // ── manager pnl sort ───────────────────────────────────────────────────
  const sortedPnl = useMemo(() => {
    const arr = [...(managerPnl.items || [])];
    const { key, dir } = pnlSort;
    arr.sort((a, b) => {
      const av = a?.[key] ?? 0;
      const bv = b?.[key] ?? 0;
      if (typeof av === 'string' || typeof bv === 'string') {
        return dir === 'asc'
          ? String(av).localeCompare(String(bv))
          : String(bv).localeCompare(String(av));
      }
      return dir === 'asc' ? av - bv : bv - av;
    });
    return arr;
  }, [managerPnl, pnlSort]);

  const togglePnlSort = (key) => {
    setPnlSort((s) => s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' });
  };

  const sortIcon = (key) => pnlSort.key === key ? (pnlSort.dir === 'asc' ? '↑' : '↓') : '';

  // ── render ─────────────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      data-testid="finance360-page"
      className="min-h-full space-y-4"
    >
      <PageHeader
        icon={Wallet}
        title={t('w12a_title')}
        subtitle={overview?.scope?.all
          ? t('w360_scope_all')
          : t('w360_scope_managers').replace('{n}', overview?.scope?.managers || 0)}
        actions={<RefreshButton onClick={refreshAll} testId="finance360-refresh" />}
        testId="finance360-header"
      />

      <RoleZoneBadge variant="wave360" />

      <PageTabs tabs={TABS} active={tab} onChange={setTab} testId="finance360-tabs" />

      <div className="space-y-4">
        <div className="p-0 space-y-4">
          {/* ───────────── OVERVIEW ───────────── */}
          {tab === 'overview' ? (
            loadingOverview && !overview ? (
              <div className="flex justify-center py-16">
                <div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <>
                {/* Primary KPI row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KpiTile icon={CurrencyEur} label={t('w12a_kpi_revenue')}  value={fmt(tot.revenue, ccy)} hint={`${c.deals_total || 0} ${t('w14_team_deals').toLowerCase()}`} tooltip={t('tip_w12a_kpi_revenue')} testId="kpi-revenue" />
                  <KpiTile icon={TrendUp}     label="Profit"         value={fmt(tot.profit, ccy)}  hint={`${c.deals_delivered || 0} delivered`} tone={profitTone} tooltip={t('tip_w14_kpi_profit_mtd')} testId="kpi-profit" />
                  <KpiTile icon={Wallet}      label="Cash in door"   value={fmt(tot.cash_in_door, ccy)} hint={`30d: ${fmt(tot.cash_flow_30d, ccy)}`} tone="good" tooltip={t('tip_w12c_tab_cashflow')} testId="kpi-cash" />
                  <KpiTile icon={ReceiptX}    label={t('w12a_kpi_outstanding')}    value={fmt(tot.outstanding, ccy)} hint={`${c.deals_open || 0} open`} tone={outstandTone} tooltip={t('tip_w12a_kpi_outstanding')} testId="kpi-outstanding" />
                </div>

                {/* Secondary KPI row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KpiTile icon={Coins}    label="Deposits received" value={fmt(tot.deposit_received, ccy)} testId="kpi-dep-received" />
                  <KpiTile icon={Coins}    label="Deposits pending"  value={fmt(tot.deposit_pending, ccy)}  tone={(tot.deposit_pending || 0) > 0 ? 'warn' : 'neutral'} testId="kpi-dep-pending" />
                  <KpiTile icon={ArrowsCounterClockwise} label="Refunds paid"   value={fmt(tot.refund_paid, ccy)} hint={`${c.refunds_paid || 0} refunds`} testId="kpi-refund-paid" />
                  {/* Wave 12B — Revenue At Risk */}
                  <KpiTile
                    icon={Heartbeat}
                    label="Revenue at risk"
                    value={fmt(riskTotal, ccy)}
                    hint={risk
                      ? `${risk.deals_at_risk || 0} deals · ${riskSegments.warning?.count || 0}/${riskSegments.at_risk?.count || 0}/${riskSegments.critical?.count || 0} W·AR·C`
                      : 'Outstanding in deals with degraded financial health'}
                    tone={riskTone}
                    testId="kpi-revenue-at-risk"
                    onClick={() => setTab('collections')}
                  />
                </div>

                {/* Wave 12B — Financial Health breakdown */}
                {risk ? (
                  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="finance-health-breakdown">
                    <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">
                      <Heartbeat size={14} weight="bold" /> Financial Health distribution
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {['healthy', 'warning', 'at_risk', 'critical'].map((seg) => {
                        const v = risk.by_segment?.[seg] || { count: 0, outstanding: 0, revenue: 0 };
                        return (
                          <div key={seg} className="border border-[#E4E4E7] rounded-xl p-3" data-testid={`fin-seg-${seg}`}>
                            <div className="flex items-center justify-between mb-1.5">
                              <SegmentBadge segment={seg} />
                              <span className="text-[11px] font-bold tabular-nums text-[#18181B]">{v.count}</span>
                            </div>
                            <div className="text-[10px] uppercase tracking-wider text-[#71717A]">Outstanding</div>
                            <div className="text-[14px] font-semibold tabular-nums text-[#18181B]">{fmt(v.outstanding, ccy)}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {/* By-stage breakdown */}
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                  <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">
                    <ChartPieSlice size={14} weight="bold" /> Deals by stage
                  </div>
                  {byStage.length === 0 ? (
                    <div className="text-sm text-[#71717A]">No deals in your scope yet.</div>
                  ) : (
                    <div className="space-y-2">
                      {byStage.map(([stage, n]) => {
                        const pct = c.deals_total ? Math.round((n / c.deals_total) * 100) : 0;
                        return (
                          <div key={stage} className="flex items-center gap-3">
                            <div className="w-40 text-[12px] text-[#52525B] uppercase tracking-wider">{stage.replace(/_/g, ' ')}</div>
                            <div className="flex-1 h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                              <div className="h-full bg-[#18181B]" style={{ width: `${pct}%` }} />
                            </div>
                            <div className="w-14 text-right tabular-nums text-[12px] font-semibold text-[#18181B]">{n}</div>
                            <div className="w-10 text-right text-[11px] text-[#71717A]">{pct}%</div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )
          ) : null}

          {/* ───────────── TRANSACTIONS ───────────── */}
          {tab === 'transactions' ? (
            <>
              {/* Quick chips */}
              <div className="flex items-center gap-2 flex-wrap">
                {[
                  { id: '', label: 'All' },
                  { id: 'deposit', label: 'Deposits' },
                  { id: 'payment', label: 'Payments' },
                  { id: 'refund',  label: 'Refunds' },
                ].map((opt) => {
                  const active = filters.type === opt.id;
                  return (
                    <button
                      key={opt.id || 'all'}
                      onClick={() => setFilters((f) => ({ ...f, type: opt.id }))}
                      className={`inline-flex items-center rounded-full px-3 py-1 text-[12px] font-semibold border ${active ? 'bg-[#18181B] text-white border-[#18181B]' : 'bg-white text-[#52525B] border-[#E4E4E7] hover:bg-[#F4F4F5]'}`}
                      data-testid={`finance-chip-${opt.id || 'all'}`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>

              {/* Filters bar */}
              <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-3 flex items-center gap-2 flex-wrap" data-testid="finance-filters">
                <div className="flex items-center gap-1.5 bg-white border border-[#E4E4E7] rounded-lg px-2 py-1 flex-1 min-w-[200px]">
                  <MagnifyingGlass size={14} className="text-[#A1A1AA]" />
                  <input
                    type="text" placeholder="Search deal / note / id…"
                    value={filters.q}
                    onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
                    className="flex-1 text-sm outline-none bg-transparent"
                    data-testid="finance-search-input"
                  />
                </div>
                <Select
                  value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
                  size="sm"
                  testId="finance-status-select"
                >
                  <option value="">{t('all_statuses')}</option>
                  <option value="pending">{t('pay_status_pending')}</option>
                  <option value="confirmed">{t('pay_status_confirmed')}</option>
                  <option value="rejected">{t('pay_status_rejected')}</option>
                  <option value="failed">{t('pay_status_failed')}</option>
                  <option value="refunded">{t('pay_status_refunded')}</option>
                  <option value="paid">{t('pay_status_paid')}</option>
                </Select>
                <Select
                  value={filters.manager_id} onChange={(e) => setFilters((f) => ({ ...f, manager_id: e.target.value }))}
                  size="sm"
                  className="max-w-[200px]"
                  testId="finance-manager-select"
                >
                  <option value="">{t('all_managers')}</option>
                  {managers.map((m) => (
                    <option key={m.id} value={m.id}>{m.name || m.email}</option>
                  ))}
                </Select>
                <button
                  onClick={() => setFilters({ type: '', status: '', manager_id: '', q: '' })}
                  className="text-[12px] text-[#71717A] hover:text-[#18181B]"
                >
                  <FunnelSimple size={12} className="inline" /> {t('clear')}
                </button>
              </div>

              {/* Journal */}
              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="finance-journal">
                <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                  <div className="col-span-2">When</div>
                  <div className="col-span-1">Type</div>
                  <div className="col-span-2">Status</div>
                  <div className="col-span-2 text-right">Amount</div>
                  <div className="col-span-3">Deal · Customer</div>
                  <div className="col-span-2">Note</div>
                </div>
                {loadingTxns ? (
                  <div className="py-10 flex justify-center">
                    <div className="w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : txns.items.length === 0 ? (
                  <div className="py-12 text-center text-[#71717A] text-sm">No transactions in this scope</div>
                ) : (
                  <div className="divide-y divide-[#F4F4F5]">
                    {txns.items.map((it) => (
                      <div key={it.id} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`txn-row-${it.id}`}>
                        <div className="col-span-2 text-[#71717A] text-[12px]">{fmtDate(it.at)}</div>
                        <div className="col-span-1">{typeBadge(it.type)}</div>
                        <div className="col-span-2">{statusBadge(it.status)}</div>
                        <div className={`col-span-2 text-right font-semibold tabular-nums ${it.type === 'refund' ? 'text-red-700' : 'text-[#18181B]'}`}>
                          {it.type === 'refund' ? '−' : ''}{fmt(it.amount, it.currency)}
                        </div>
                        <div className="col-span-3 min-w-0">
                          <button
                            className="block w-full text-left truncate font-medium text-[#18181B] hover:underline"
                            onClick={() => it.deal_id && navigate(`/admin/deals/${it.deal_id}/360`)}
                            title={it.deal_title}
                          >
                            {it.deal_title || it.deal_id?.slice(-12) || '—'}
                            <ArrowSquareOut size={10} className="inline ml-1 text-[#A1A1AA]" />
                          </button>
                          <div className="text-[11px] text-[#71717A] truncate">{it.customer_name || '—'}</div>
                        </div>
                        <div className="col-span-2 text-[12px] text-[#52525B] truncate" title={it.note}>{it.note || (it.method ? it.method.replace('_', ' ') : '—')}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="text-[12px] text-[#71717A]">{txns.total} transaction(s)</div>
            </>
          ) : null}

          {/* ───────────── OUTSTANDING ───────────── */}
          {tab === 'outstanding' ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <KpiTile icon={ReceiptX} label="Total outstanding" value={fmt(outstanding.summary.outstanding, ccy)} tone="warn" testId="outstanding-total" />
                <KpiTile icon={ReceiptX} label="Deals owing"       value={outstanding.summary.deals} hint="non-terminal" testId="outstanding-deals" />
                <KpiTile icon={Clock}    label="Oldest"            value={outstanding.items[0]?.days_overdue != null ? `${outstanding.items[0].days_overdue}d` : '—'} hint="since last move" testId="outstanding-oldest" />
              </div>

              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="outstanding-table">
                <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                  <div className="col-span-3">Deal · Customer</div>
                  <div className="col-span-2">Stage</div>
                  <div className="col-span-2 text-right">Expected</div>
                  <div className="col-span-2 text-right">Received</div>
                  <div className="col-span-2 text-right">Outstanding</div>
                  <div className="col-span-1 text-right">Days</div>
                </div>
                {loadingOutstanding ? (
                  <div className="py-10 flex justify-center">
                    <div className="w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : outstanding.items.length === 0 ? (
                  <div className="py-12 text-center text-[#71717A] text-sm">Nothing outstanding — well done!</div>
                ) : (
                  <div className="divide-y divide-[#F4F4F5]">
                    {outstanding.items.map((it) => {
                      const overdueTone =
                        it.days_overdue == null ? 'text-[#71717A]' :
                        it.days_overdue >= 14    ? 'text-red-700' :
                        it.days_overdue >= 7     ? 'text-amber-700' :
                        'text-[#52525B]';
                      return (
                        <div key={it.deal_id} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`outstanding-row-${it.deal_id}`}>
                          <div className="col-span-3 min-w-0">
                            <button
                              className="block w-full text-left truncate font-medium text-[#18181B] hover:underline"
                              onClick={() => navigate(`/admin/deals/${it.deal_id}/360`)}
                              title={it.deal_title}
                            >
                              {it.deal_title || it.deal_id?.slice(-12)} <ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" />
                            </button>
                            <div className="text-[11px] text-[#71717A] truncate">{it.customer_name || '—'}</div>
                          </div>
                          <div className="col-span-2 text-[12px] text-[#52525B] uppercase tracking-wider">{(it.stage || '').replace(/_/g, ' ')}</div>
                          <div className="col-span-2 text-right tabular-nums">{fmt(it.expected, it.currency || ccy)}</div>
                          <div className="col-span-2 text-right tabular-nums text-emerald-700">{fmt(it.received, it.currency || ccy)}</div>
                          <div className="col-span-2 text-right tabular-nums font-semibold text-[#18181B]">{fmt(it.outstanding, it.currency || ccy)}</div>
                          <div className={`col-span-1 text-right tabular-nums font-semibold ${overdueTone}`}>{it.days_overdue ?? '—'}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          ) : null}

          {/* ───────────── Wave 12B — MANAGER P&L ───────────── */}
          {tab === 'managers' ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiTile icon={UsersThree} label="Managers"  value={managerPnl.total} hint="in your scope" testId="pnl-count" />
                <KpiTile icon={CurrencyEur} label="Revenue"  value={fmt(sortedPnl.reduce((s, r) => s + (r.revenue || 0), 0), ccy)} testId="pnl-revenue" />
                <KpiTile icon={TrendUp}     label="Profit"   value={fmt(sortedPnl.reduce((s, r) => s + (r.profit  || 0), 0), ccy)} testId="pnl-profit" />
                <KpiTile icon={Heartbeat}   label="At risk"  value={fmt(sortedPnl.reduce((s, r) => s + (r.at_risk || 0), 0), ccy)} tone={sortedPnl.some(r => (r.at_risk||0)>0) ? 'bad' : 'good'} testId="pnl-at-risk" />
              </div>

              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="manager-pnl-table">
                <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                  <button className="col-span-3 text-left hover:text-[#18181B]"  onClick={() => togglePnlSort('manager_name')}>Manager {sortIcon('manager_name')}</button>
                  <button className="col-span-1 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('deals')}>Deals {sortIcon('deals')}</button>
                  <button className="col-span-2 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('revenue')}>Revenue {sortIcon('revenue')}</button>
                  <button className="col-span-1 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('profit')}>Profit {sortIcon('profit')}</button>
                  <button className="col-span-2 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('outstanding')}>Outstanding {sortIcon('outstanding')}</button>
                  <button className="col-span-1 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('at_risk')}>At Risk {sortIcon('at_risk')}</button>
                  <button className="col-span-1 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('avg_collection_days')}>Avg Days {sortIcon('avg_collection_days')}</button>
                  <button className="col-span-1 text-right hover:text-[#18181B]" onClick={() => togglePnlSort('financial_health')}>Health {sortIcon('financial_health')}</button>
                </div>
                {loadingPnl ? (
                  <div className="py-10 flex justify-center">
                    <div className="w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : sortedPnl.length === 0 ? (
                  <div className="py-12 text-center text-[#71717A] text-sm">No managers with deals in scope</div>
                ) : (
                  <div className="divide-y divide-[#F4F4F5]">
                    {sortedPnl.map((r) => {
                      const riskCls = (r.at_risk || 0) > 0 ? 'text-red-700' : 'text-[#52525B]';
                      return (
                        <div key={r.manager_id || r.manager_name || Math.random()} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`pnl-row-${r.manager_id || 'unassigned'}`}>
                          <div className="col-span-3 min-w-0">
                            <div className="font-medium text-[#18181B] truncate">{r.manager_name}</div>
                            <div className="text-[11px] text-[#71717A] truncate">{r.email || (r.role ? r.role.replace('_', ' ') : '')}</div>
                          </div>
                          <div className="col-span-1 text-right tabular-nums">{r.deals}</div>
                          <div className="col-span-2 text-right tabular-nums">{fmt(r.revenue, ccy)}</div>
                          <div className={`col-span-1 text-right tabular-nums ${(r.profit||0) >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>{fmt(r.profit, ccy)}</div>
                          <div className="col-span-2 text-right tabular-nums">{fmt(r.outstanding, ccy)}</div>
                          <div className={`col-span-1 text-right tabular-nums font-semibold ${riskCls}`}>{fmt(r.at_risk, ccy)}</div>
                          <div className="col-span-1 text-right tabular-nums text-[#52525B]">{r.avg_collection_days != null ? `${r.avg_collection_days}d` : '—'}</div>
                          <div className="col-span-1 text-right"><SegmentBadge segment={r.financial_health} /></div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          ) : null}

          {/* ───────────── Wave 12B — COLLECTIONS ───────────── */}
          {tab === 'collections' ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiTile icon={Lifebuoy}  label="In queue"   value={collections.total} hint={`>${collDays}d or not healthy`} testId="coll-count" />
                <KpiTile icon={ReceiptX}  label="Outstanding" value={fmt(collections.summary.outstanding, ccy)} tone={collections.summary.outstanding > 0 ? 'warn' : 'good'} testId="coll-outstanding" />
                <KpiTile icon={Warning}   label="Critical"   value={collections.summary.by_segment?.critical || 0} tone={collections.summary.by_segment?.critical ? 'bad' : 'neutral'} testId="coll-critical" />
                <KpiTile icon={Heartbeat} label="At risk + warn" value={(collections.summary.by_segment?.at_risk || 0) + (collections.summary.by_segment?.warning || 0)} tone="warn" testId="coll-warn-atrisk" />
              </div>

              <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-3 flex items-center gap-3 flex-wrap text-[12px]">
                <span className="text-[#52525B] font-semibold">Min days overdue:</span>
                {[0, 3, 7, 14, 30].map((d) => (
                  <button
                    key={d}
                    onClick={() => setCollDays(d)}
                    className={`px-2.5 py-1 rounded-full border ${collDays === d ? 'bg-[#18181B] text-white border-[#18181B]' : 'bg-white text-[#52525B] border-[#E4E4E7] hover:bg-[#F4F4F5]'}`}
                    data-testid={`coll-days-${d}`}
                  >
                    {d === 0 ? 'Any' : `≥ ${d}d`}
                  </button>
                ))}
              </div>

              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="collections-table">
                <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                  <div className="col-span-3">Deal · Customer</div>
                  <div className="col-span-2">Stage</div>
                  <div className="col-span-2 text-right">Outstanding</div>
                  <div className="col-span-1 text-right">Days</div>
                  <div className="col-span-2">Health · Score</div>
                  <div className="col-span-2">Reason</div>
                </div>
                {loadingColl ? (
                  <div className="py-10 flex justify-center">
                    <div className="w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : collections.items.length === 0 ? (
                  <div className="py-12 text-center text-[#71717A] text-sm">Nothing to collect — well done!</div>
                ) : (
                  <div className="divide-y divide-[#F4F4F5]">
                    {collections.items.map((it) => {
                      const overdueTone =
                        it.days_overdue == null ? 'text-[#71717A]' :
                        it.days_overdue >= 14    ? 'text-red-700' :
                        it.days_overdue >= 7     ? 'text-amber-700' :
                        'text-[#52525B]';
                      const topReason = (it.reasons && it.reasons[0]) || '—';
                      return (
                        <div key={it.deal_id} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`coll-row-${it.deal_id}`}>
                          <div className="col-span-3 min-w-0">
                            <button
                              className="block w-full text-left truncate font-medium text-[#18181B] hover:underline"
                              onClick={() => navigate(`/admin/deals/${it.deal_id}/360`)}
                              title={it.deal_title}
                            >
                              {it.deal_title || it.deal_id?.slice(-12)} <ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" />
                            </button>
                            <div className="text-[11px] text-[#71717A] truncate">{it.customer_name || (it.vin ? `VIN ${it.vin}` : '—')}</div>
                          </div>
                          <div className="col-span-2 text-[12px] text-[#52525B] uppercase tracking-wider truncate">{(it.stage || '').replace(/_/g, ' ')}</div>
                          <div className="col-span-2 text-right tabular-nums font-semibold text-[#18181B]">{fmt(it.outstanding, it.currency || ccy)}</div>
                          <div className={`col-span-1 text-right tabular-nums font-semibold ${overdueTone}`}>{it.days_overdue ?? '—'}</div>
                          <div className="col-span-2 flex items-center gap-2">
                            <SegmentBadge segment={it.financial_health} />
                            <span className="text-[11px] text-[#71717A] tabular-nums">{it.health_score}</span>
                          </div>
                          <div className="col-span-2 text-[12px] text-[#52525B] truncate" title={(it.reasons || []).join(' · ')}>{topReason}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
};

export default Finance360;
