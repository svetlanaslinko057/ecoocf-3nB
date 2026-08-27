/**
 * Customer360 - Payments Tab
 * --------------------------
 * Read-only list of all Stripe payment records for a customer.
 * Each row shows: amount, currency, status, payment_intent (last 8
 * chars), invoice link, refunded amount.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  CreditCard,
  CheckCircle,
  XCircle,
  ArrowsClockwise,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  succeeded: { color: 'bg-emerald-100 text-emerald-700', label: 'Succeeded', icon: CheckCircle },
  paid:      { color: 'bg-emerald-100 text-emerald-700', label: 'Paid',      icon: CheckCircle },
  failed:    { color: 'bg-red-100 text-red-700',         label: 'Failed',    icon: XCircle },
  canceled:  { color: 'bg-zinc-100 text-zinc-500',       label: 'Canceled',  icon: XCircle },
  refunded:  { color: 'bg-purple-100 text-purple-700',   label: 'Refunded',  icon: ArrowsClockwise },
  pending:   { color: 'bg-amber-100 text-amber-700',     label: 'Pending',   icon: ArrowsClockwise },
};

const fmtMoney = (n, ccy = 'USD') => {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: (ccy || 'USD').toUpperCase(),
      maximumFractionDigits: 2,
    }).format(Number(n || 0));
  } catch {
    return `${Number(n || 0).toFixed(2)} ${(ccy || 'USD').toUpperCase()}`;
  }
};

const PaymentsTab = ({ customerId }) => {
  const { t } = useLang();
  const [payments, setPayments] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/api/customers/${customerId}/payments`);
        if (!cancelled) {
          setPayments(res.data?.items || []);
          setSummary(res.data?.summary || {});
        }
      } catch (err) {
        if (!cancelled) console.error('Payments fetch failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40" data-testid="payments-tab-loading">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="customer360-payments-tab">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label={t('adm_total_3') || 'Total'} value={summary.total || 0} accent="#4F46E5" />
        <KpiCard label="Succeeded" value={summary.succeeded || 0} accent="#059669" />
        <KpiCard label="Refunded" value={summary.refunded || 0} accent="#7C3AED" />
        <KpiCard
          label="Collected"
          value={fmtMoney(summary.totalAmount || 0)}
          accent="#059669"
        />
      </div>

      {payments.length === 0 ? (
        <div className="section-card text-center py-12" data-testid="payments-empty">
          <CreditCard size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">No payments recorded for this customer yet.</p>
        </div>
      ) : (
        <div className="section-card">
          <div className="divide-y divide-[#E4E4E7]">
            {payments.map((p) => {
              const meta = STATUS_META[(p.status || '').toLowerCase()] || STATUS_META.pending;
              const Icon = meta.icon;
              const pi = p.stripe_payment_intent || p.payment_intent || p.id || '';
              return (
                <div
                  key={p.id || p.stripe_payment_intent}
                  className="flex items-center justify-between py-3"
                  data-testid={`payment-row-${p.id || pi}`}
                >
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <div className="shrink-0 w-9 h-9 rounded-xl bg-[#F4F4F5] flex items-center justify-center">
                      <CreditCard size={18} className="text-[#4F46E5]" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-[#18181B] font-mono text-xs truncate">
                        {pi ? pi.slice(-12) : '—'}
                      </p>
                      <p className="text-xs text-[#71717A]">
                        {p.invoice_id && `Invoice: ${p.invoice_id.slice(-8)}`}
                        {p.created_at && ` · ${new Date(p.created_at).toLocaleString()}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <p className="font-semibold text-[#18181B] tabular-nums">
                        {fmtMoney(p.amount, p.currency)}
                      </p>
                      {Number(p.refunded_amount) > 0 && (
                        <p className="text-[10px] text-[#7C3AED]">
                          Refunded: {fmtMoney(p.refunded_amount, p.currency)}
                        </p>
                      )}
                    </div>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium ${meta.color}`}>
                      <Icon size={12} />
                      {meta.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

const KpiCard = ({ label, value, accent }) => (
  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-3">
    <p className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">{label}</p>
    <p className="text-xl font-bold mt-1 tabular-nums" style={{ color: accent }}>{value}</p>
  </div>
);

export default PaymentsTab;
