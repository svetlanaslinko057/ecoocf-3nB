/**
 * Cabinet · Financials Page (P1.2-cabinet)
 *
 * /cabinet/financials              → list of customer's deals
 * /cabinet/deals/:dealId/financials → full money picture for one deal
 *
 * Customer-facing view of:
 *   • Total / Paid / Remaining (with progress bar)
 *   • Breakdown items (cash items shown in red, locked badge)
 *   • Payments timeline
 *   • "Pay via Stripe" button (stub until P1.2-stripe phase)
 *
 * Auth: uses customer-session bearer token via the same `customer_session`
 * localStorage entry that Favorites/Watchlist use.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useLang } from '../../i18n/LanguageContext';
import {
  Wallet, Receipt, CreditCard, Lock, Info, ArrowLeft,
  CheckCircle, Clock, X as IconX, ArrowRight,
} from '@phosphor-icons/react';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// ────────────────────────── helpers ───────────────────────────

function getCustomerToken() {
  // Same priority as the rest of the cabinet
  try {
    const sess = JSON.parse(localStorage.getItem('customer_session') || '{}');
    if (sess?.sessionToken) return sess.sessionToken;
    if (sess?.accessToken) return sess.accessToken;
    if (sess?.token) return sess.token;
  } catch {}
  return (
    localStorage.getItem('customer_token') ||
    localStorage.getItem('customerToken') ||
    localStorage.getItem('token') ||
    ''
  );
}

function authedAxios() {
  const token = getCustomerToken();
  return axios.create({
    baseURL: API_URL,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

function fmt(n) {
  if (n === null || n === undefined) return '—';
  const v = Number(n);
  return `€${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const METHOD_META = {
  bank: { label: 'Bank', tint: 'bg-blue-100 text-blue-700' },
  stripe: { label: 'Card', tint: 'bg-indigo-100 text-indigo-700' },
  cash_off_books: { label: 'Cash', tint: 'bg-red-100 text-red-700' },
  internal: { label: 'Internal', tint: 'bg-zinc-100 text-zinc-700' },
  other: { label: 'Other', tint: 'bg-amber-100 text-amber-700' },
};

const STATUS_META = {
  unpaid: { label: 'Unpaid', tint: 'bg-red-100 text-red-700', bar: 'bg-red-500' },
  partial: { label: 'Partially', tint: 'bg-amber-100 text-amber-700', bar: 'bg-amber-500' },
  paid: { label: 'Paid', tint: 'bg-emerald-100 text-emerald-700', bar: 'bg-emerald-500' },
  overpaid: { label: 'Overpayment', tint: 'bg-blue-100 text-blue-700', bar: 'bg-blue-500' },
};

const PAYMENT_STATUS_META = {
  pending: { label: 'Awaiting', tint: 'bg-amber-100 text-amber-700', icon: Clock },
  confirmed: { label: 'Confirmed', tint: 'bg-emerald-100 text-emerald-700', icon: CheckCircle },
  voided: { label: 'Cancelled', tint: 'bg-zinc-100 text-zinc-500', icon: IconX },
};

// ════════════════════════════════════════════════════════════════════
// Page 1 — list of customer's deals
// ════════════════════════════════════════════════════════════════════

export function CabinetFinancialsListPage() {
  const { t } = useLang();
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      try {
        const r = await authedAxios().get('/api/cabinet/deals');
        setDeals(r.data?.data || []);
      } catch (e) {
        toast.error(e?.response?.data?.detail || t('adm3_993b0691af'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto" data-testid="cabinet-financials-list">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900 mb-2 flex items-center gap-2">
          <Wallet size={28} weight="duotone" className="text-emerald-600" />
          {t('adm3_06e9309373')}
        </h1>
        <p className="text-zinc-600">
          {t('adm3_93527eff64')}
        </p>
      </div>

      {deals.length === 0 ? (
        <div className="bg-white border border-zinc-200 rounded-xl p-8 text-center text-zinc-500">
          {t('adm3_d39d80b171')}
        </div>
      ) : (
        <div className="space-y-3">
          {deals.map(d => {
            const ps = d.payment_status || 'unpaid';
            const meta = STATUS_META[ps] || STATUS_META.unpaid;
            const summary = d.payment_summary || {};
            return (
              <button
                key={d.id}
                onClick={() => navigate(`/cabinet/deals/${d.id}/financials`)}
                data-testid={`cabinet-deal-${d.id}`}
                className="w-full text-left bg-white border border-zinc-200 rounded-xl p-4
                           hover:shadow-md hover:border-emerald-300 transition-all"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="font-semibold text-zinc-900">
                      {d.title || d.vin || `${t('r9_deal_hash')}${(d.id || '').slice(-8)}`}
                    </div>
                    <div className="text-xs text-zinc-500 mt-0.5">
                      {d.stage || d.status || '—'}
                      {d.created_at && ` · ${new Date(d.created_at).toLocaleDateString()}`}
                    </div>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${meta.tint}`}>
                    {meta.label}
                  </span>
                </div>
                {summary.total_all > 0 && (
                  <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <div className="text-[10px] uppercase text-zinc-500 font-medium">{t('adm3_28807c941f')}</div>
                      <div className="font-mono font-bold text-zinc-900">{fmt(summary.total_all)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase text-emerald-600 font-medium">{t('adm3_079864b89e')}</div>
                      <div className="font-mono font-bold text-emerald-600">{fmt(summary.paid_total)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase text-zinc-500 font-medium">{t('adm3_6a0b2e7739')}</div>
                      <div className={`font-mono font-bold ${
                        summary.remaining > 0 ? 'text-red-600'
                        : summary.remaining < 0 ? 'text-blue-600'
                        : 'text-emerald-600'
                      }`}>{fmt(summary.remaining)}</div>
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════
// Page 2 — single deal financial detail
// ════════════════════════════════════════════════════════════════════

export function CabinetDealFinancialsPage() {
  const { t } = useLang();
  const { dealId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authedAxios().get(`/api/cabinet/deals/${dealId}/financials`);
      setData(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('adm3_1965b20789'));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [dealId]);

  useEffect(() => { reload(); }, [reload]);

  const handlePay = async () => {
    setPaying(true);
    try {
      const r = await authedAxios().post(`/api/cabinet/deals/${dealId}/pay-intent`, {});
      if (r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
      } else if (r.data?.stub) {
        toast.info(r.data.message || t('adm3_5104bc3a45'));
      } else if (r.data?.reason === 'no_official_due') {
        toast.success(t('adm3_a87edb64f5'));
      } else {
        toast.error(t('adm3_c9ea42552f'));
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('adm3_fd77287f02'));
    } finally {
      setPaying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <button onClick={() => navigate('/cabinet/financials')}
                className="text-zinc-600 hover:text-zinc-900 mb-4 flex items-center gap-1 text-sm">
          <ArrowLeft size={16} /> {t('adm3_70aaad9473')}
        </button>
        <div className="bg-white border border-zinc-200 rounded-xl p-8 text-center text-zinc-500">
          {t('adm3_ab3b6f38f3')}
        </div>
      </div>
    );
  }

  const { deal, breakdowns = [], payments = [], summary = {}, payment_status = 'unpaid' } = data;
  const meta = STATUS_META[payment_status] || STATUS_META.unpaid;
  const total = summary.total_all || 0;
  const paid = summary.paid_total || 0;
  const remaining = summary.remaining || 0;
  const progress = total > 0 ? Math.min(100, (paid / total) * 100) : 0;
  const officialDue = Math.max(0, (summary.total_official || 0) - (summary.paid_official || 0));

  return (
    <div className="p-6 max-w-4xl mx-auto" data-testid="cabinet-deal-financials">
      <button onClick={() => navigate('/cabinet/financials')}
              className="text-zinc-600 hover:text-zinc-900 mb-4 flex items-center gap-1 text-sm">
        <ArrowLeft size={16} /> {t('adm3_70aaad9473')}
      </button>

      {/* Hero summary */}
      <div className="bg-gradient-to-br from-emerald-50 to-blue-50 border border-emerald-200 rounded-2xl p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 mb-1">
              {deal?.title || deal?.vin || `${t('r9_deal_hash')}${(dealId || '').slice(-8)}`}
            </h1>
            <p className="text-sm text-zinc-600">{deal?.stage || deal?.status || '—'}</p>
          </div>
          <span className={`px-3 py-1.5 rounded-full text-sm font-semibold ${meta.tint}`}
                data-testid="cabinet-payment-status">
            {meta.label}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <div className="text-xs uppercase text-zinc-500 font-medium tracking-wider">{t('adm3_28807c941f')}</div>
            <div className="text-2xl font-mono font-bold text-zinc-900" data-testid="cabinet-total">
              {fmt(total)}
            </div>
          </div>
          <div>
            <div className="text-xs uppercase text-emerald-600 font-medium tracking-wider">{t('adm3_079864b89e')}</div>
            <div className="text-2xl font-mono font-bold text-emerald-600" data-testid="cabinet-paid">
              {fmt(paid)}
            </div>
          </div>
          <div>
            <div className="text-xs uppercase text-zinc-500 font-medium tracking-wider">{t('adm3_6a0b2e7739')}</div>
            <div className={`text-2xl font-mono font-bold ${
              remaining > 0 ? 'text-red-600' : remaining < 0 ? 'text-blue-600' : 'text-emerald-600'
            }`} data-testid="cabinet-remaining">
              {fmt(remaining)}
            </div>
          </div>
        </div>

        <div className="h-3 bg-white rounded-full overflow-hidden mb-4 border border-zinc-200">
          <div className={`h-full transition-all ${meta.bar}`} style={{ width: `${progress}%` }} />
        </div>

        {officialDue > 0 ? (
          <button
            onClick={handlePay}
            disabled={paying}
            data-testid="cabinet-pay-btn"
            className="w-full px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60
                       text-white font-semibold rounded-xl flex items-center justify-center gap-2
                       transition-colors"
          >
            <CreditCard size={20} weight="bold" />
            {paying ? t('adm3_f2e2c8113e') : `${t('r9_pay_amount_prefix')}${fmt(officialDue)}${t('r9_by_card_suffix')}`}
            <ArrowRight size={18} />
          </button>
        ) : remaining <= 0 && total > 0 ? (
          <div className="text-center text-emerald-700 font-semibold py-2 flex items-center justify-center gap-2">
            <CheckCircle size={20} weight="bold" /> {t('adm3_3277bf6d77')}
          </div>
        ) : null}

        {(summary.total_cash || 0) > 0 && (
          <div className="mt-3 bg-white/60 rounded-lg p-3 flex gap-2 text-xs text-zinc-600">
            <Info size={14} className="flex-shrink-0 mt-0.5 text-amber-600" />
            <div>
              <b>{fmt(summary.total_cash)}</b> {t('adm3_e9487d58b1')}
            </div>
          </div>
        )}
      </div>

      {/* Breakdowns */}
      {breakdowns.length > 0 && (
        <div className="bg-white border border-zinc-200 rounded-xl p-5 mb-6">
          <h2 className="text-lg font-bold text-zinc-900 mb-4 flex items-center gap-2">
            <Receipt size={20} weight="duotone" className="text-indigo-600" />
            {t('adm3_de39493b1e')}
          </h2>
          <div className="space-y-4">
            {breakdowns.map(b => (
              <CustomerBreakdownCard key={b.id} bd={b} />
            ))}
          </div>
        </div>
      )}

      {/* Payments */}
      <div className="bg-white border border-zinc-200 rounded-xl p-5">
        <h2 className="text-lg font-bold text-zinc-900 mb-4 flex items-center gap-2">
          <Wallet size={20} weight="duotone" className="text-emerald-600" />
          {t('adm3_31332b4a4b')}
        </h2>
        {payments.length === 0 ? (
          <p className="text-sm text-zinc-500">{t('adm3_f9ae4d1caa')}</p>
        ) : (
          <div className="space-y-2">
            {payments.map(p => {
              const meth = METHOD_META[p.method] || METHOD_META.other;
              const stMeta = PAYMENT_STATUS_META[p.status] || PAYMENT_STATUS_META.pending;
              const StIcon = stMeta.icon;
              const isCash = p.method === 'cash_off_books';
              const isVoided = p.status === 'voided';
              return (
                <div key={p.id}
                     data-testid={`cabinet-payment-${p.id}`}
                     className={`border border-zinc-100 rounded-lg p-3 flex items-center justify-between ${
                       isVoided ? 'opacity-50' : ''
                     } ${isCash ? 'bg-red-50/40' : ''}`}>
                  <div className="flex items-center gap-3">
                    <div className={`px-2.5 py-1 rounded-md text-xs font-medium ${meth.tint}`}>
                      {meth.label}
                    </div>
                    <div>
                      <div className={`font-mono font-semibold ${isCash ? 'text-red-700' : 'text-zinc-900'}`}>
                        {fmt(p.amount)}
                      </div>
                      <div className="text-[10px] text-zinc-500">
                        {p.created_at && new Date(p.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {p.proof_url && !isVoided && (
                      <a href={p.proof_url} target="_blank" rel="noreferrer"
                         className="text-xs text-indigo-600 underline">proof</a>
                    )}
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${stMeta.tint}`}>
                      <StIcon size={10} weight="bold" />
                      {stMeta.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────── Breakdown card ───────────────────────────
function CustomerBreakdownCard({ bd }) {
  const { t } = useLang();
  const totals = bd.totals || {};
  const items = bd.items || [];
  return (
    <div className="border border-zinc-200 rounded-lg overflow-hidden"
         data-testid={`cabinet-breakdown-${bd.id}`}>
      <div className="bg-zinc-50 px-3 py-2 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold uppercase tracking-wide text-zinc-700">
            {bd.kind === 'final' ? t('adm3_0c15116ea3') : t('adm3_0047c0a8d1')}
          </span>
          {bd.locked && (
            <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-zinc-200 text-zinc-700 flex items-center gap-1">
              <Lock size={9} weight="bold" /> {t('adm3_b92d2d56b6')}
            </span>
          )}
        </div>
        <div className="text-zinc-500">
          {bd.created_at && new Date(bd.created_at).toLocaleDateString()}
        </div>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {items.map((it, idx) => {
            const isCash = it.payment_type === 'cash_off_books';
            const isNeg = Number(it.amount) < 0;
            return (
              <tr key={idx} className={`border-b border-zinc-100 ${isCash ? 'bg-red-50/40' : ''}`}>
                <td className="py-2 px-3 text-zinc-700">
                  {it.label || it.name || it.key}
                  {isCash && <span className="ml-2 text-[10px] text-red-600 font-semibold">{t('adm3_534d33a7a0')}</span>}
                </td>
                <td className={`py-2 px-3 text-right font-mono font-semibold ${
                  isNeg ? 'text-emerald-600' : isCash ? 'text-red-600' : 'text-zinc-900'
                }`}>
                  {fmt(it.amount)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="px-3 py-2 bg-zinc-50 grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-zinc-500">{t('adm3_b2d00a1144')}</div>
          <div className="font-mono font-bold text-zinc-900">{fmt(totals.total_all ?? bd.amount)}</div>
        </div>
        <div>
          <div className="text-emerald-600">{t('adm3_cdf4215996')}</div>
          <div className="font-mono font-bold text-emerald-600">{fmt(totals.total_official)}</div>
        </div>
        <div>
          <div className="text-red-600">{t('adm3_9edc3636cf')}</div>
          <div className="font-mono font-bold text-red-600">{fmt(totals.total_cash)}</div>
        </div>
      </div>
    </div>
  );
}

export default CabinetDealFinancialsPage;
