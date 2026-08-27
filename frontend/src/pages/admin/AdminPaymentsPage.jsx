/**
 * Master-Admin Payments Dashboard
 * --------------------------------
 * Full visibility & control over every Stripe charge:
 *  - KPI cards (total, succeeded, failed, refunded, pending)
 *  - By-method breakdown (Card / Apple Pay / Google Pay / Link / Klarna / Crypto / Bank…)
 *  - Daily revenue trend
 *  - Searchable & filterable payments table
 *  - Detail drawer with Stripe info + receipt + refund action
 *  - Sync button to pull latest PaymentIntents from Stripe API
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { useLang } from '../../i18n';
import {
  CreditCard,
  RefreshCw,
  Search,
  Download,
  X,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  ExternalLink,
  TrendingUp,
  DollarSign,
  Activity,
  Filter,
  Wallet,
} from 'lucide-react';
// WhiteSelect — the canonical white dropdown (portal-rendered, auto-flip,
// matches the design system used across catalog/admin filters).
import WhiteSelect from '../../components/ui/WhiteSelect';
import IntegrationsPage from './IntegrationsPage';
import { ChevronDown } from 'lucide-react';
import RefreshButton from '../../components/ui/RefreshButton';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_BADGE = {
  succeeded:                'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200',
  complete:                 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200',
  paid:                     'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200',
  processing:               'bg-blue-100 text-blue-700 ring-1 ring-blue-200',
  requires_payment_method:  'bg-amber-100 text-amber-700 ring-1 ring-amber-200',
  requires_action:          'bg-amber-100 text-amber-700 ring-1 ring-amber-200',
  open:                     'bg-amber-100 text-amber-700 ring-1 ring-amber-200',
  failed:                   'bg-rose-100 text-rose-700 ring-1 ring-rose-200',
  canceled:                 'bg-gray-200 text-gray-600 ring-1 ring-gray-300',
  expired:                  'bg-gray-200 text-gray-600 ring-1 ring-gray-300',
};

const METHOD_META = {
  card:              { label: 'Card',           color: '#635BFF', icon: '💳' },
  apple_pay:         { label: 'adm_apple_pay',      color: '#000000', icon: '' },
  google_pay:        { label: 'adm_google_pay',     color: '#4285F4', icon: '🅖' },
  link:              { label: 'adm_link',           color: '#00D924', icon: '🔗' },
  klarna:            { label: 'adm_klarna',         color: '#FFB3C7', icon: 'K' },
  afterpay_clearpay: { label: 'Afterpay',       color: '#B2FCE4', icon: 'A' },
  cashapp:           { label: 'Cash App',       color: '#00D632', icon: '$' },
  crypto:            { label: 'Crypto',         color: '#F7931A', icon: '₿' },
  us_bank_account:   { label: 'ACH',            color: '#0F62FE', icon: '🏦' },
  sepa_debit:        { label: 'SEPA',           color: '#3B82F6', icon: '€' },
  ideal:             { label: 'iDEAL',          color: '#CC0066', icon: 'I' },
  bancontact:        { label: 'adm_bancontact',     color: '#005498', icon: 'B' },
  p24:               { label: 'adm_przelewy24',     color: '#D40028', icon: 'P' },
  blik:              { label: 'BLIK',           color: '#000',    icon: 'B' },
  alipay:            { label: 'adm_alipay',         color: '#1677FF', icon: 'A' },
  wechat_pay:        { label: 'WeChat',         color: '#07C160', icon: 'W' },
};

const fmtAmount = (n, ccy = 'usd') => {
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: (ccy || 'USD').toUpperCase() }).format(n || 0);
  } catch {
    return `${(n || 0).toFixed(2)} ${(ccy || 'USD').toUpperCase()}`;
  }
};

const fmtDate = (iso) => {
  try { return new Date(iso).toLocaleString(); } catch { return iso || '—'; }
};

const StatCard = ({ label, value, sub, icon: Icon, accent = '#635BFF' }) => (
  <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-sm transition-shadow min-w-0 h-full flex flex-col">
    {/* Top row: label + flat icon (no inner-card background — eliminates the
        "card-in-card" feel the user pointed out). Icon sits inline as a
        15-px accent glyph instead of a 40x40 chip. */}
    <div className="flex items-center justify-between gap-2">
      <p className="text-[10px] sm:text-[11px] font-semibold text-gray-500 uppercase tracking-wider leading-tight break-words">
        {label}
      </p>
      <Icon className="w-4 h-4 flex-shrink-0" style={{ color: accent }} />
    </div>
    <p className="text-xl sm:text-2xl font-bold text-gray-900 mt-2 tabular-nums leading-none">{value}</p>
    {/* Sub-text always rendered (even if empty) so all 5 cards have identical height */}
    <p className="text-[11px] text-gray-500 mt-2 truncate min-h-[14px]">{sub || '\u00a0'}</p>
  </div>
);

const MethodPill = ({ method, wallet }) => {
  const m = METHOD_META[method] || { label: method || '—', color: '#6B7280', icon: '?' };
  // If card with wallet (apple_pay/google_pay), show the wallet variant
  let displayMethod = m;
  if (method === 'card' && wallet) {
    displayMethod = METHOD_META[wallet] || m;
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium" style={{ backgroundColor: `${displayMethod.color}15`, color: displayMethod.color }}>
      <span className="text-[10px]">{displayMethod.icon}</span>
      {displayMethod.label}
    </span>
  );
};

const StatusBadge = ({ status }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${STATUS_BADGE[status] || 'bg-gray-100 text-gray-600'}`}>
    {status === 'succeeded' || status === 'complete' || status === 'paid' ? <CheckCircle2 className="w-3 h-3" /> :
     status === 'failed' || status === 'canceled' || status === 'expired' ? <XCircle className="w-3 h-3" /> :
     <Clock className="w-3 h-3" />}
    {status || 'unknown'}
  </span>
);

export default function AdminPaymentsPage() {
  const { t } = useLang();
  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  // `appliedFilters` = the snapshot that drives the actual API request.
  // `draftFilters`   = the user's in-progress edits in the filter row. The
  // Apply button commits draft → applied; additionally, the free-text search
  // field auto-applies after 500ms of inactivity so typing feels live without
  // firing a request on every keystroke.
  const [appliedFilters, setAppliedFilters] = useState({ status: '', method: '', q: '', days: 30 });
  const [draftFilters, setDraftFilters] = useState({ status: '', method: '', q: '', days: 30 });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [refunding, setRefunding] = useState(false);

  // Debounced live-apply for the search field only. Status/Method still wait
  // for explicit Apply so the user is in control of dropdowns.
  useEffect(() => {
    if (draftFilters.q === appliedFilters.q) return;
    const id = setTimeout(() => {
      setAppliedFilters((prev) => ({ ...prev, q: draftFilters.q }));
    }, 500);
    return () => clearTimeout(id);
  }, [draftFilters.q, appliedFilters.q]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (appliedFilters.status) params.set('status', appliedFilters.status);
      if (appliedFilters.method) params.set('method', appliedFilters.method);
      if (appliedFilters.q)      params.set('q', appliedFilters.q);
      params.set('days', String(appliedFilters.days || 30));
      params.set('limit', '200');
      const [statsRes, listRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/payments/stats?days=${appliedFilters.days || 30}`),
        axios.get(`${API_URL}/api/admin/payments?${params.toString()}`),
      ]);
      setStats(statsRes.data);
      setItems(listRes.data.items || []);
      setTotal(listRes.data.total || 0);
    } catch (e) {
      toast.error(t('adm_failed_to_load_payments'));
    } finally {
      setLoading(false);
    }
  }, [appliedFilters, t]);

  useEffect(() => { load(); }, [load]);

  const applyFilters = () => {
    setAppliedFilters({ ...draftFilters });
  };
  const resetFilters = () => {
    const fresh = { status: '', method: '', q: '', days: draftFilters.days };
    setDraftFilters(fresh);
    setAppliedFilters(fresh);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const r = await axios.post(`${API_URL}/api/admin/payments/sync?limit=100`);
      toast.success(`Synced ${r.data.synced || 0} payments from Stripe`);
      await load();
    } catch (e) {
      toast.error(`Sync failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const openDetail = async (payment) => {
    setSelected(payment);
    setDetail(null);
    try {
      const id = payment.paymentIntentId || payment.sessionId || payment.id;
      const r = await axios.get(`${API_URL}/api/admin/payments/${id}`);
      setDetail(r.data);
    } catch (e) {
      toast.error(t('adm_failed_to_load_payment_detail'));
    }
  };

  const handleRefund = async (full = true) => {
    if (!selected) return;
    if (!window.confirm(`Refund ${full ? 'FULL' : 'partial'} amount ${fmtAmount(selected.amount, selected.currency)}? This action cannot be undone.`)) return;
    setRefunding(true);
    try {
      const id = selected.paymentIntentId || selected.id;
      const body = full ? { reason: 'requested_by_customer' } : { reason: 'requested_by_customer', amount: selected.amount / 2 };
      const r = await axios.post(`${API_URL}/api/admin/payments/${id}/refund`, body);
      toast.success(`Refund ${r.data.status}: ${fmtAmount(r.data.amount, selected.currency)}`);
      await load();
      await openDetail(selected);
    } catch (e) {
      toast.error(`Refund failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setRefunding(false);
    }
  };

  const exportCsv = () => {
    const rows = [
      ['Date', 'PaymentIntent', 'Status', 'Amount', 'Currency', 'Method', 'Card', 'Customer', 'Email', 'Invoice'],
      ...items.map(p => [
        p.created_at, p.paymentIntentId || p.sessionId || p.id, p.status, p.amount, p.currency,
        p.wallet || p.method || '', p.cardBrand && p.cardLast4 ? `${p.cardBrand} ****${p.cardLast4}` : '',
        p.customerId || '', p.customerEmail || '', p.invoiceId || '',
      ]),
    ];
    const csv = rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `bibi-payments-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const dailyMax = useMemo(() => Math.max(1, ...(stats?.daily || []).map(d => d.amount || 0)), [stats]);

  return (
    <div className="space-y-4 sm:space-y-5">
      {/*
        ── Payments page header — bullet-proof mobile layout ──────────────
        June 2026 — finalised after multiple regressions. DO NOT replace
        with <AdminPageHeader/>: this page has too many controls (filter
        select + refresh + CSV) for the generic header. Custom layout
        here so the icon stays pinned top-LEFT, refresh stays pinned
        top-RIGHT, and the title sits in the natural reading flow
        between/below them. The 30-day filter and CSV button live on
        their OWN toolbar row so they can never squeeze the title.

        Mobile (< sm):
          ┌──────────────────────────────────────────────────┐
          │ [icon] ............................ [refresh] │  ← Row 1
          │ Payments                                         │  ← Row 2
          │ Master-admin view — pull existing…               │
          ├──────────────────────────────────────────────────┤
          │ [ Last 30 days ▼     ]   [ ⬇ CSV ]               │  ← Row 3
          └──────────────────────────────────────────────────┘

        Desktop (≥ sm):
          ┌──────────────────────────────────────────────────┐
          │ [icon] Payments              [30d][refresh][CSV] │
          │        Master-admin view…                        │
          └──────────────────────────────────────────────────┘
      */}
      <header
        className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5"
        data-testid="payments-header"
      >
        {/* Row 1 (mobile): icon-left + refresh-right.  
            On desktop this row also holds the title and the right-side toolbar. */}
        <div className="flex items-start gap-3 sm:gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <CreditCard size={18} />
          </div>

          {/* Title block — only visible inline on desktop (sm+). On mobile the
              title moves to its own row BELOW (see further down) so the icon
              and refresh sit in their dedicated corners. */}
          <div className="hidden sm:block flex-1 min-w-0">
            <h1 className="text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight break-words">
              {t('paymentsTitle')}
            </h1>
            <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed break-words">
              {t('masterAdminView')}
            </p>
          </div>

          {/* Desktop-only toolbar (30-day select + refresh + CSV) docked right. */}
          <div className="hidden sm:flex items-center gap-2 sm:gap-3 shrink-0">
            <div className="w-[160px] shrink-0">
              <WhiteSelect
                value={String(appliedFilters.days)}
                onChange={(e) => {
                  const days = Number(e.target.value);
                  setDraftFilters((f) => ({ ...f, days }));
                  setAppliedFilters((f) => ({ ...f, days }));
                }}
                data-testid="payments-days-select"
              >
                <option value="7">{t('last7Days')}</option>
                <option value="30">{t('last30Days')}</option>
                <option value="90">{t('last90Days')}</option>
                <option value="365">{t('lastYear')}</option>
                <option value="3650">{t('allTime')}</option>
              </WhiteSelect>
            </div>
            <RefreshButton
              onClick={handleSync}
              loading={syncing}
              ariaLabel={t('syncFromStripe') || 'Refresh'}
              testId="payments-refresh-btn"
              title={t('syncFromStripe')}
            />
            <button
              onClick={exportCsv}
              className="inline-flex items-center justify-center gap-1.5 h-9 px-3.5 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[12.5px] font-medium text-[#18181B] whitespace-nowrap focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
              data-testid="payments-csv-btn"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
          </div>

          {/* Mobile-only refresh in the top-RIGHT corner. ml-auto pins it
              to the far right so the row always reads: icon ←→ refresh. */}
          <div className="ml-auto sm:hidden shrink-0">
            <RefreshButton
              onClick={handleSync}
              loading={syncing}
              ariaLabel={t('syncFromStripe') || 'Refresh'}
              testId="payments-refresh-btn-mobile"
              title={t('syncFromStripe')}
            />
          </div>
        </div>

        {/* Row 2 (mobile only): title + subtitle, full-width, normal flow.
            Never gets letter-wrapped because nothing competes for width. */}
        <div className="mt-3 sm:hidden">
          <h1 className="text-[18px] font-semibold tracking-tight text-[#18181B] leading-tight break-words">
            {t('paymentsTitle')}
          </h1>
          <p className="mt-1 text-[12.5px] text-[#71717A] leading-relaxed break-words">
            {t('masterAdminView')}
          </p>
        </div>

        {/* Row 3 (mobile only): 30-day filter + CSV button on their own row.
            grid-cols-[1fr_auto] = filter stretches, CSV button stays compact. */}
        <div className="mt-4 grid grid-cols-[1fr_auto] gap-2 sm:hidden">
          <WhiteSelect
            value={String(appliedFilters.days)}
            onChange={(e) => {
              const days = Number(e.target.value);
              setDraftFilters((f) => ({ ...f, days }));
              setAppliedFilters((f) => ({ ...f, days }));
            }}
            data-testid="payments-days-select-mobile"
          >
            <option value="7">{t('last7Days')}</option>
            <option value="30">{t('last30Days')}</option>
            <option value="90">{t('last90Days')}</option>
            <option value="365">{t('lastYear')}</option>
            <option value="3650">{t('allTime')}</option>
          </WhiteSelect>
          <button
            onClick={exportCsv}
            className="inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[13px] font-medium text-[#18181B] whitespace-nowrap focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
            data-testid="payments-csv-btn-mobile"
          >
            <Download className="w-3.5 h-3.5" />
            CSV
          </button>
        </div>
      </header>

      {/* KPI Cards — identical templates, equal height via h-full on each card */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <StatCard label={t('totalVolume')}      value={fmtAmount(stats.totalAmount, items[0]?.currency || 'USD')} sub={`${stats.totalCount} successful`} icon={DollarSign}  accent="#635BFF" />
          <StatCard label={t('succeededStatus')}  value={stats.succeeded} sub=""                                    icon={CheckCircle2}                     accent="#10B981" />
          <StatCard label={t('statusPending')}    value={stats.pending}   sub=""                                    icon={Clock}                            accent="#F59E0B" />
          <StatCard label={t('depositFailed')}    value={stats.failed}    sub=""                                    icon={XCircle}                          accent="#EF4444" />
          <StatCard label={t('depositRefunded')}  value={stats.refunded}  sub=""                                    icon={RotateCcw}                        accent="#6B7280" />
        </div>
      )}

      {/* By-method + daily chart row */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="lg:col-span-1 bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <Wallet className="w-4 h-4 text-gray-500" />
              <h3 className="text-sm font-semibold text-gray-900">{t('byPaymentMethod')}</h3>
            </div>
            {stats.byMethod.length === 0 && <p className="text-xs text-gray-400">{t('noDataYet')}</p>}
            <div className="space-y-2">
              {stats.byMethod.map((m) => {
                const meta = METHOD_META[m.method] || { label: m.method || 'unknown', color: '#6B7280', icon: '?' };
                const pct = stats.totalAmount ? Math.round((m.amount / stats.totalAmount) * 100) : 0;
                return (
                  <div key={m.method}>
                    <div className="flex items-center justify-between text-sm mb-1 gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold flex-shrink-0" style={{ backgroundColor: `${meta.color}15`, color: meta.color }}>{meta.icon}</span>
                        <span className="font-medium truncate">{meta.label}</span>
                        <span className="text-xs text-gray-400 flex-shrink-0">×{m.count}</span>
                      </div>
                      <span className="font-semibold tabular-nums flex-shrink-0">{fmtAmount(m.amount)}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: meta.color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-gray-500" />
              <h3 className="text-sm font-semibold text-gray-900">{t('dailyRevenue')}</h3>
            </div>
            {stats.daily.length === 0 ? (
              <div className="h-32 flex items-center justify-center text-xs text-gray-400 text-center px-4">
                {t('noPaymentsYetHint')}
              </div>
            ) : (
              <div className="flex items-end gap-1 h-32">
                {stats.daily.map((d) => (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                    <div className="w-full flex items-end" style={{ height: '100%' }}>
                      <div
                        className="w-full bg-gradient-to-t from-[#635BFF] to-[#9D8EFF] rounded-t hover:opacity-80 transition-opacity"
                        style={{ height: `${(d.amount / dailyMax) * 100}%` }}
                        title={`${d.date}: ${fmtAmount(d.amount)} (${d.count})`}
                      />
                    </div>
                    <span className="text-[9px] text-gray-400 truncate w-full text-center">{d.date.slice(5)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Filters — single flat row, no card-in-card. On mobile each control takes full width. */}
      <div className="bg-white border border-gray-200 rounded-lg p-3 sm:p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[1fr_180px_180px_auto_auto] gap-2.5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            <input
              type="text"
              placeholder={t('adm_search_by_email_invoice_paymentintent')}
              value={draftFilters.q}
              onChange={(e) => setDraftFilters({ ...draftFilters, q: e.target.value })}
              onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
              className="w-full pl-10 pr-3 h-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF]"
            />
          </div>
          <div>
            <WhiteSelect
              value={draftFilters.status}
              onChange={(e) => setDraftFilters({ ...draftFilters, status: e.target.value })}
              data-testid="payments-status-select"
            >
              <option value="">{t('allStatuses')}</option>
              <option value="succeeded">{t('succeededStatus')}</option>
              <option value="paid">{t('stagePaymentDone')}</option>
              <option value="processing">{t('depositProcessing')}</option>
              <option value="requires_action">{t('requiresAction')}</option>
              <option value="failed">{t('depositFailed')}</option>
              <option value="canceled">{t('canceledStatus')}</option>
            </WhiteSelect>
          </div>
          <div>
            <WhiteSelect
              value={draftFilters.method}
              onChange={(e) => setDraftFilters({ ...draftFilters, method: e.target.value })}
              data-testid="payments-method-select"
            >
              <option value="">{t('allMethods')}</option>
              {Object.entries(METHOD_META).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </WhiteSelect>
          </div>
          <button
            onClick={applyFilters}
            className="inline-flex items-center justify-center gap-1.5 h-10 px-4 bg-[#18181B] text-white rounded-lg hover:bg-[#27272A] text-sm font-medium whitespace-nowrap"
          >
            <Filter className="w-3.5 h-3.5" />
            {t('applyFilter')}
          </button>
          <button
            onClick={resetFilters}
            className="inline-flex items-center justify-center gap-1.5 h-10 px-4 border border-gray-200 rounded-lg hover:bg-gray-50 text-sm text-gray-600 whitespace-nowrap"
            title="Reset filters"
            type="button"
          >
            <X className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>
      </div>

      {/* Payments table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 sm:px-5 py-3 border-b border-gray-100 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-gray-900">
            {t('recentPayments')} <span className="font-normal text-gray-400">({total})</span>
          </h3>
          {loading && <RefreshCw className="w-3.5 h-3.5 animate-spin text-gray-400" />}
        </div>
        {items.length === 0 && !loading ? (
          <div className="p-12 text-center">
            <Activity className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">{t('noPaymentsYet')}</p>
            <p className="text-xs text-gray-400 mt-1">{t('waitForFirstPaymentHint')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">{t('date')}</th>
                  <th className="text-left px-5 py-3 font-medium">{t('customer')}</th>
                  <th className="text-left px-5 py-3 font-medium">{t('methodLabel')}</th>
                  <th className="text-left px-5 py-3 font-medium">{t('statusGeneric')}</th>
                  <th className="text-right px-5 py-3 font-medium">{t('amount')}</th>
                  <th className="text-left px-5 py-3 font-medium">{t('docInvoice')}</th>
                  <th className="text-left px-5 py-3 font-medium">{t('paymentIntent')}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((p) => (
                  <tr
                    key={p.id || p.paymentIntentId || p.sessionId}
                    onClick={() => openDetail(p)}
                    className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-5 py-3 text-gray-600 whitespace-nowrap">{fmtDate(p.created_at)}</td>
                    <td className="px-5 py-3">
                      <div className="font-medium text-gray-900 truncate max-w-[200px]">{p.customerEmail || '—'}</div>
                      {p.customerId && (
                        <Link
                          to={`/admin/customers/${p.customerId}/360`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-[#4F46E5] hover:underline truncate max-w-[200px] block"
                          data-testid={`payments-customer-link-${p.id || p.paymentIntentId}`}
                        >
                          {p.customerId}
                        </Link>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <MethodPill method={p.method} wallet={p.wallet} />
                      {p.cardBrand && p.cardLast4 && (
                        <div className="text-xs text-gray-500 mt-0.5">{p.cardBrand} ••{p.cardLast4}</div>
                      )}
                    </td>
                    <td className="px-5 py-3"><StatusBadge status={p.status} /></td>
                    <td className="px-5 py-3 text-right font-semibold tabular-nums">{fmtAmount(p.amount, p.currency)}</td>
                    <td className="px-5 py-3 text-xs text-gray-500 font-mono">{p.invoiceId || '—'}</td>
                    <td className="px-5 py-3 text-xs text-gray-400 font-mono truncate max-w-[160px]">{p.paymentIntentId || p.sessionId || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {selected && (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1 bg-black/40" onClick={() => { setSelected(null); setDetail(null); }} />
          <div className="w-full max-w-xl bg-white shadow-2xl overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">{t('paymentDetail')}</h3>
                <p className="text-xs text-gray-500 font-mono mt-0.5">{selected.paymentIntentId || selected.sessionId}</p>
              </div>
              <button onClick={() => { setSelected(null); setDetail(null); }} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-5">
              <div className="bg-gradient-to-br from-[#635BFF] to-[#7C6FFF] rounded-2xl p-5 text-white">
                <p className="text-xs uppercase tracking-wider opacity-80">{t('amount')}</p>
                <p className="text-4xl font-bold mt-1">{fmtAmount(selected.amount, selected.currency)}</p>
                <div className="flex items-center justify-between mt-4">
                  <StatusBadge status={selected.status} />
                  <MethodPill method={selected.method} wallet={selected.wallet} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <Field label={t('customerEmailLabel')} value={selected.customerEmail} />
                <Field label={t('customerId')} value={selected.customerId} mono />
                <Field label={t('docInvoice')} value={selected.invoiceId} mono />
                <Field label={t('currency')} value={(selected.currency || '').toUpperCase()} />
                <Field label={t('cardMethod')} value={selected.cardBrand && selected.cardLast4 ? `${selected.cardBrand} ••${selected.cardLast4}` : '—'} />
                <Field label={t('walletLabel')} value={selected.wallet || '—'} />
                <Field label={t('createdOn')} value={fmtDate(selected.created_at)} />
                <Field label={t('updated')} value={fmtDate(selected.updated_at)} />
              </div>

              {selected.metadata && Object.keys(selected.metadata || {}).length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase text-gray-500 mb-2">{t('metadataLabel')}</p>
                  <div className="bg-gray-50 rounded-lg p-3 text-xs font-mono space-y-1">
                    {Object.entries(selected.metadata).map(([k, v]) => (
                      <div key={k}><span className="text-gray-500">{k}:</span> <span className="text-gray-900">{String(v)}</span></div>
                    ))}
                  </div>
                </div>
              )}

              {selected.receiptUrl && (
                <a
                  href={selected.receiptUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium"
                >
                  <ExternalLink className="w-4 h-4" />
                  {t('viewStripeReceipt')}
                </a>
              )}

              {(selected.status === 'succeeded' || selected.status === 'complete' || selected.status === 'paid') && selected.paymentIntentId && (
                <div className="border-t pt-4">
                  <p className="text-xs font-semibold uppercase text-gray-500 mb-2">{t('refundAction')}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      disabled={refunding}
                      onClick={() => handleRefund(true)}
                      className="px-4 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      <RotateCcw className="w-4 h-4" />
                      {t('fullRefund')}
                    </button>
                    <button
                      disabled={refunding}
                      onClick={() => handleRefund(false)}
                      className="px-4 py-2.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg text-sm font-medium disabled:opacity-50"
                    >
                      {t('halfRefund')}
                    </button>
                  </div>
                </div>
              )}

              {detail?.stripe && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-700">{t('rawStripePayload')}</summary>
                  <pre className="mt-2 bg-gray-50 p-3 rounded-lg overflow-auto max-h-80 font-mono text-[10px]">{JSON.stringify(detail.stripe, null, 2)}</pre>
                </details>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── Stripe configuration (key, mode, webhook secret) ─── */}
      <div className="mt-10">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <CreditCard className="w-[18px] h-[18px]" />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg sm:text-xl font-bold text-gray-900 leading-tight">
              Stripe Integration
            </h2>
            <p className="text-xs sm:text-sm text-gray-500 mt-1">
              API-ключи, режим (sandbox/live), webhook secret для приёма событий.
            </p>
          </div>
        </div>
        <IntegrationsPage embedded filterProviders={['stripe']} />
      </div>
    </div>
  );
}

const Field = ({ label, value, mono }) => (
  <div>
    <p className="text-xs text-gray-500">{label}</p>
    <p className={`text-sm text-gray-900 ${mono ? 'font-mono' : ''} truncate`}>{value || '—'}</p>
  </div>
);
