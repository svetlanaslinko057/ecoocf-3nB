/**
 * PaymentMethodPicker
 * --------------------
 * Premium modal that lets the customer choose how to pay BEFORE
 * being redirected to Stripe Checkout.
 *
 * Reads `/api/stripe/public-config` to know which methods the admin enabled
 * (Card, Apple Pay, Google Pay, Link, Klarna, Crypto, etc.) and renders a
 * tactile, branded picker. The actual payment flow always goes through
 * Stripe Checkout (most secure & compliant) — the picker just communicates
 * choice and gives customers the visual confidence of seeing all the
 * options up-front.
 *
 * Usage:
 *   <PaymentMethodPicker
 *      open={open}
 *      onClose={...}
 *      amount={123.45}
 *      currency="usd"
 *      onProceed={async (selectedMethod) => { ...createCheckoutSession }}
 *   />
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { X, Lock, Loader2, ChevronRight } from 'lucide-react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const METHOD_VISUAL = {
  card:              { label: 'Pay with card',      hint: 'Visa, Mastercard, Amex, Discover',     accent: '#635BFF', logo: 'CARDS' },
  apple_pay:         { label: 'Apple Pay',          hint: 'One-tap on Safari / iOS',              accent: '#000000', logo: '' },
  google_pay:        { label: 'Google Pay',         hint: 'One-tap on Chrome / Android',          accent: '#4285F4', logo: 'G·Pay' },
  link:              { label: 'Link',               hint: 'Stripe one-click checkout',            accent: '#00D924', logo: 'Link' },
  klarna:            { label: 'Klarna',             hint: 'Pay in 4 instalments',                 accent: '#FFB3C7', logo: 'Klarna' },
  afterpay_clearpay: { label: 'Afterpay / Clearpay', hint: 'Pay in 4 instalments',               accent: '#B2FCE4', logo: 'after' },
  cashapp:           { label: 'Cash App Pay',       hint: 'USD only',                             accent: '#00D632', logo: '$' },
  crypto:            { label: 'Pay with Crypto',    hint: 'USDC stablecoin (Stripe Crypto)',      accent: '#F7931A', logo: '₿' },
  us_bank_account:   { label: 'Bank account (ACH)', hint: 'USA',                                  accent: '#0F62FE', logo: 'ACH' },
  sepa_debit:        { label: 'SEPA Direct Debit',  hint: 'EU bank account',                      accent: '#3B82F6', logo: 'SEPA' },
  ideal:             { label: 'iDEAL',              hint: 'Netherlands',                          accent: '#CC0066', logo: 'iDEAL' },
  bancontact:        { label: 'Bancontact',         hint: 'Belgium',                              accent: '#005498', logo: 'BC' },
  p24:               { label: 'Przelewy24',         hint: 'Poland',                               accent: '#D40028', logo: 'P24' },
  blik:              { label: 'BLIK',               hint: 'Poland',                               accent: '#000000', logo: 'BLIK' },
  alipay:            { label: 'Alipay',             hint: 'China',                                accent: '#1677FF', logo: 'Ali' },
  wechat_pay:        { label: 'WeChat Pay',         hint: 'China',                                accent: '#07C160', logo: 'WeChat' },
};

const fmtAmount = (n, ccy = 'usd') => {
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: (ccy || 'USD').toUpperCase() }).format(n || 0);
  } catch {
    return `${(n || 0).toFixed(2)} ${(ccy || 'USD').toUpperCase()}`;
  }
};

export default function PaymentMethodPicker({
  open,
  onClose,
  amount,
  currency,
  description = 'Order payment',
  onProceed,
}) {
  const { t } = useLang();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState('card');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    axios.get(`${API_URL}/api/stripe/public-config`)
      .then(res => { if (!cancelled) { setConfig(res.data); if (res.data?.displayMethods?.[0]) setSelected(res.data.displayMethods[0].key); } })
      .catch(() => { if (!cancelled) setConfig({ enabled: false, displayMethods: [] }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open]);

  if (!open) return null;

  const handleProceed = async () => {
    setSubmitting(true);
    try {
      await onProceed?.(selected);
    } finally {
      setSubmitting(false);
    }
  };

  const ccy = currency || config?.currency || 'usd';
  const methods = config?.displayMethods || [];

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-br from-[#635BFF] via-[#7C6FFF] to-[#9D8EFF] px-6 py-6 text-white relative">
          <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-white/20">
            <X className="w-4 h-4" />
          </button>
          <p className="text-xs uppercase tracking-wider opacity-80">{t('cmp_total_to_pay')}</p>
          <p className="text-3xl font-bold mt-1">{fmtAmount(amount, ccy)}</p>
          <p className="text-sm opacity-90 mt-1 truncate">{description}</p>
        </div>

        {/* Body */}
        <div className="p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">{t('cmp_choose_payment_method')}</h3>
            <span className="inline-flex items-center gap-1 text-[11px] text-gray-500">
              <Lock className="w-3 h-3" /> {t('cmp_secured_by_stripe')}
            </span>
          </div>

          {loading ? (
            <div className="py-12 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : !config?.enabled ? (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-4 text-sm">
              {t('cmp_payments_are_not_yet_configured_please_contact_sup')}
            </div>
          ) : methods.length === 0 ? (
            <div className="bg-gray-50 border border-gray-200 text-gray-700 rounded-xl p-4 text-sm">
              {t('cmp_no_payment_methods_enabled_admin_must_enable_at_le')}
            </div>
          ) : (
            <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
              {methods.map((m) => {
                const v = METHOD_VISUAL[m.key] || { label: m.label, hint: m.hint, accent: '#635BFF', logo: m.label[0] };
                const active = selected === m.key;
                return (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => setSelected(m.key)}
                    className={`w-full flex items-center gap-3 p-3.5 rounded-2xl border-2 text-left transition-all ${active ? 'border-[#635BFF] bg-[#635BFF]/5 shadow-sm' : 'border-gray-200 hover:border-gray-300 bg-white'}`}
                  >
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xs shrink-0"
                      style={{ backgroundColor: `${v.accent}15`, color: v.accent }}
                    >
                      {v.logo}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-gray-900 text-sm">{v.label}</div>
                      <div className="text-xs text-gray-500">{v.hint}</div>
                    </div>
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors ${active ? 'border-[#635BFF] bg-[#635BFF]' : 'border-gray-300 bg-white'}`}>
                      {active && <div className="w-2 h-2 rounded-full bg-white" />}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <button
            disabled={submitting || !config?.enabled || methods.length === 0}
            onClick={handleProceed}
            className="mt-5 w-full flex items-center justify-center gap-2 px-4 py-3.5 bg-[#635BFF] hover:bg-[#5147d4] text-white rounded-2xl font-semibold transition-colors disabled:opacity-50"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <>{t('cmp_continue_to_payment')} <ChevronRight className="w-4 h-4" /></>}
          </button>

          <p className="text-[11px] text-gray-400 text-center mt-3">
            {t('cmp_youll_be_redirected_to_stripes_secure_checkout_to')}
          </p>
        </div>
      </div>
    </div>
  );
}
