import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  CurrencyEur, TrendUp, Wallet, ReceiptX, Coins, Plus, CheckCircle, XCircle, ArrowsClockwise,
} from '@phosphor-icons/react';
import { API_URL } from '../../App';

const Tile = ({ icon: Icon, label, value, hint, tone = 'neutral', testId }) => {
  const toneCls = {
    neutral: 'bg-white border-[#E4E4E7]',
    good:    'bg-emerald-50 border-emerald-200',
    warn:    'bg-amber-50 border-amber-200',
    bad:     'bg-red-50 border-red-200',
  }[tone] || 'bg-white border-[#E4E4E7]';
  return (
    <div className={`border rounded-2xl p-4 ${toneCls}`} data-testid={testId}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
        <Icon size={14} weight="bold" /> {label}
      </div>
      <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{value}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5">{hint}</div> : null}
    </div>
  );
};

const fmt = (n, ccy = 'EUR') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};

const pill = (cls, label) => (
  <span className={`text-[10px] uppercase tracking-wider font-bold rounded-full px-2 py-0.5 border ${cls}`}>{label}</span>
);

const statusPill = (status) => {
  const v = (status || '').toLowerCase();
  if (['confirmed','paid','received'].includes(v))         return pill('bg-emerald-50 text-emerald-700 border-emerald-200', v);
  if (['rejected','failed','void','voided'].includes(v))   return pill('bg-red-50 text-red-700 border-red-200', v);
  if (['refunded'].includes(v))                            return pill('bg-zinc-100 text-zinc-700 border-zinc-200', v);
  return pill('bg-amber-50 text-amber-800 border-amber-200', v || 'pending');
};

const Section = ({ title, children, action }) => (
  <div className="bg-white border border-[#E4E4E7] rounded-2xl">
    <div className="px-4 py-3 border-b border-[#E4E4E7] flex items-center justify-between">
      <div className="text-[11px] font-bold uppercase tracking-wider text-[#71717A]">{title}</div>
      {action}
    </div>
    {children}
  </div>
);

const DealFinancialsTab = ({ dealId, financials, deposits = [], payments = [], onChange }) => {
  const fin = financials || {};
  const ccy = fin.currency || 'EUR';
  const profit = Number(fin.profit || 0);
  const profitTone = profit > 0 ? 'good' : profit < 0 ? 'bad' : 'neutral';

  const [depOpen, setDepOpen] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [depForm, setDepForm] = useState({ amount: '', method: 'bank_transfer', note: '' });
  const [payForm, setPayForm] = useState({ amount: '', type: 'milestone', status: 'pending', note: '' });
  const [busy, setBusy] = useState(false);

  const registerDeposit = async (e) => {
    e?.preventDefault?.();
    const amount = Number(depForm.amount);
    if (!(amount > 0)) { toast.error('Amount must be > 0'); return; }
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/deals/${dealId}/deposits`, {
        amount, method: depForm.method, note: depForm.note || undefined,
      });
      toast.success('Deposit registered');
      setDepForm({ amount: '', method: 'bank_transfer', note: '' });
      setDepOpen(false);
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setBusy(false); }
  };

  const depositAction = async (depId, action) => {
    const note = (action === 'confirm') ? undefined : (window.prompt(`Reason for ${action} (optional):`) || undefined);
    try {
      await axios.post(`${API_URL}/api/deals/${dealId}/deposits/${depId}/${action}`, { note });
      toast.success(`Deposit ${action}ed`);
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    }
  };

  const registerPayment = async (e) => {
    e?.preventDefault?.();
    const amount = Number(payForm.amount);
    if (!(amount > 0)) { toast.error('Amount must be > 0'); return; }
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/deals/${dealId}/payments`, {
        amount, type: payForm.type, status: payForm.status, note: payForm.note || undefined,
      });
      toast.success('Payment registered');
      setPayForm({ amount: '', type: 'milestone', status: 'pending', note: '' });
      setPayOpen(false);
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setBusy(false); }
  };

  const paymentAction = async (payId, action) => {
    const note = (action === 'confirm') ? undefined : (window.prompt(`Reason for ${action} (optional):`) || undefined);
    try {
      await axios.post(`${API_URL}/api/deals/${dealId}/payments/${payId}/${action}`, { note });
      toast.success(`Payment ${action}ed`);
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    }
  };

  const ActionBtn = ({ onClick, icon: Icon, label, tone = 'neutral', testId }) => {
    const toneCls = {
      good:    'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border-emerald-200',
      warn:    'bg-amber-50 hover:bg-amber-100 text-amber-800 border-amber-200',
      bad:     'bg-red-50 hover:bg-red-100 text-red-700 border-red-200',
      neutral: 'bg-white hover:bg-[#F4F4F5] text-[#52525B] border-[#E4E4E7]',
    }[tone];
    return (
      <button onClick={onClick} className={`inline-flex items-center gap-1 border rounded-lg px-2 py-0.5 text-[10px] uppercase tracking-wider font-bold ${toneCls}`} data-testid={testId}>
        <Icon size={11} weight="bold" /> {label}
      </button>
    );
  };

  return (
    <div className="space-y-6" data-testid="deal-financials-tab">
      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile icon={CurrencyEur} label="Revenue"     value={fmt(fin.revenue, ccy)}     testId="fin-tile-revenue" />
        <Tile icon={Wallet}      label="Cost"        value={fmt(fin.cost, ccy)}        testId="fin-tile-cost" />
        <Tile icon={TrendUp}     label="Profit"      value={fmt(profit, ccy)}          hint={`${fin.margin_pct || 0}% margin`} tone={profitTone} testId="fin-tile-profit" />
        <Tile icon={ReceiptX}    label="Balance due" value={fmt(fin.balance_due, ccy)} tone={Number(fin.balance_due || 0) > 0 ? 'warn' : 'good'} testId="fin-tile-balance" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile icon={Coins} label="Deposit received"  value={fmt(fin.deposit_received, ccy)} testId="fin-tile-deposit-received" />
        <Tile icon={Coins} label="Deposit pending"   value={fmt(fin.deposit_pending, ccy)}  tone={Number(fin.deposit_pending || 0) > 0 ? 'warn' : 'neutral'} testId="fin-tile-deposit-pending" />
        <Tile icon={Coins} label="Payments received" value={fmt(fin.payments_received, ccy)} testId="fin-tile-payments-received" />
        <Tile icon={Coins} label="Payments pending"  value={fmt(fin.payments_pending, ccy)} testId="fin-tile-payments-pending" />
      </div>

      {/* Deposits */}
      <Section
        title={`Deposits (${deposits.length})`}
        action={(
          <button onClick={() => setDepOpen((v) => !v)} className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#4F46E5] hover:underline" data-testid="deal-register-deposit-toggle">
            <Plus size={12} weight="bold" /> Register deposit
          </button>
        )}
      >
        {depOpen ? (
          <form onSubmit={registerDeposit} className="px-4 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA] grid grid-cols-1 md:grid-cols-4 gap-2 items-end" data-testid="deal-register-deposit-form">
            <div>
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Amount ({ccy})</label>
              <input type="number" min="0" step="0.01" value={depForm.amount}
                onChange={(e) => setDepForm((f) => ({ ...f, amount: e.target.value }))}
                className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm" required />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Method</label>
              <select value={depForm.method} onChange={(e) => setDepForm((f) => ({ ...f, method: e.target.value }))} className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm bg-white">
                <option value="bank_transfer">Bank transfer</option>
                <option value="card">Card</option>
                <option value="cash">Cash</option>
                <option value="crypto">Crypto</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="md:col-span-1">
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Note</label>
              <input value={depForm.note} onChange={(e) => setDepForm((f) => ({ ...f, note: e.target.value }))} placeholder="e.g. 10% deposit" className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm" />
            </div>
            <div className="flex items-center gap-2">
              <button type="submit" disabled={busy} className="bg-[#18181B] text-white text-sm font-semibold rounded-lg px-3 py-1.5 disabled:opacity-50" data-testid="deal-register-deposit-confirm">Save</button>
              <button type="button" onClick={() => setDepOpen(false)} className="text-sm text-[#71717A]">Cancel</button>
            </div>
          </form>
        ) : null}

        {deposits.length === 0 ? (
          <div className="px-4 py-6 text-center text-[#71717A] text-sm">No deposits yet</div>
        ) : (
          <div className="divide-y divide-[#F4F4F5]">
            {deposits.map((d, i) => {
              const isPending  = ['pending','draft','requested'].includes((d.status || '').toLowerCase());
              const isConfirmed = ['confirmed','paid','received'].includes((d.status || '').toLowerCase());
              return (
                <div key={d.id || i} className="flex items-center justify-between px-4 py-3 gap-3" data-testid={`deposit-row-${d.id || i}`}>
                  <div className="min-w-0">
                    <div className="font-semibold text-[#18181B]">{fmt(d.amount, d.currency || ccy)}</div>
                    <div className="text-[12px] text-[#71717A] truncate">{d.method ? d.method.replace('_', ' ') + ' · ' : ''}{d.created_at ? new Date(d.created_at).toLocaleString() : ''}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {statusPill(d.status)}
                    {d.id && isPending ? (
                      <>
                        <ActionBtn onClick={() => depositAction(d.id, 'confirm')} icon={CheckCircle} label="Confirm" tone="good" testId={`deposit-confirm-${d.id}`} />
                        <ActionBtn onClick={() => depositAction(d.id, 'reject')}  icon={XCircle}     label="Reject"  tone="bad" testId={`deposit-reject-${d.id}`} />
                      </>
                    ) : null}
                    {d.id && isConfirmed ? (
                      <ActionBtn onClick={() => depositAction(d.id, 'refund')} icon={ArrowsClockwise} label="Refund" tone="warn" testId={`deposit-refund-${d.id}`} />
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      {/* Payments */}
      <Section
        title={`Payments (${payments.length})`}
        action={(
          <button onClick={() => setPayOpen((v) => !v)} className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#4F46E5] hover:underline" data-testid="deal-register-payment-toggle">
            <Plus size={12} weight="bold" /> Add payment
          </button>
        )}
      >
        {payOpen ? (
          <form onSubmit={registerPayment} className="px-4 py-3 border-b border-[#F4F4F5] bg-[#FAFAFA] grid grid-cols-1 md:grid-cols-5 gap-2 items-end" data-testid="deal-register-payment-form">
            <div>
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Amount ({ccy})</label>
              <input type="number" min="0" step="0.01" value={payForm.amount}
                onChange={(e) => setPayForm((f) => ({ ...f, amount: e.target.value }))}
                className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm" required />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Type</label>
              <select value={payForm.type} onChange={(e) => setPayForm((f) => ({ ...f, type: e.target.value }))} className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm bg-white">
                <option value="milestone">Milestone</option>
                <option value="final">Final</option>
                <option value="after_win">After win</option>
                <option value="shipping">Shipping</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Status</label>
              <select value={payForm.status} onChange={(e) => setPayForm((f) => ({ ...f, status: e.target.value }))} className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm bg-white">
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Note</label>
              <input value={payForm.note} onChange={(e) => setPayForm((f) => ({ ...f, note: e.target.value }))} className="mt-1 w-full px-2 py-1.5 border border-[#E4E4E7] rounded-lg text-sm" />
            </div>
            <div className="flex items-center gap-2">
              <button type="submit" disabled={busy} className="bg-[#18181B] text-white text-sm font-semibold rounded-lg px-3 py-1.5 disabled:opacity-50" data-testid="deal-register-payment-confirm">Save</button>
              <button type="button" onClick={() => setPayOpen(false)} className="text-sm text-[#71717A]">Cancel</button>
            </div>
          </form>
        ) : null}

        {payments.length === 0 ? (
          <div className="px-4 py-6 text-center text-[#71717A] text-sm">No payments recorded</div>
        ) : (
          <div className="divide-y divide-[#F4F4F5]">
            {payments.map((p, i) => {
              const isPending  = ['pending','scheduled'].includes((p.status || '').toLowerCase());
              const isConfirmed = ['confirmed','paid','received'].includes((p.status || '').toLowerCase());
              return (
                <div key={p.id || i} className="flex items-center justify-between px-4 py-3 gap-3" data-testid={`payment-row-${p.id || i}`}>
                  <div className="min-w-0">
                    <div className="font-semibold text-[#18181B]">{fmt(p.amount, p.currency || ccy)}</div>
                    <div className="text-[12px] text-[#71717A] truncate">{p.type || p.label || 'payment'} · {p.created_at ? new Date(p.created_at).toLocaleString() : ''}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {statusPill(p.status)}
                    {p.id && isPending ? (
                      <>
                        <ActionBtn onClick={() => paymentAction(p.id, 'confirm')} icon={CheckCircle} label="Confirm" tone="good" testId={`payment-confirm-${p.id}`} />
                        <ActionBtn onClick={() => paymentAction(p.id, 'fail')}    icon={XCircle}     label="Fail"    tone="bad" testId={`payment-fail-${p.id}`} />
                      </>
                    ) : null}
                    {p.id && isConfirmed ? (
                      <ActionBtn onClick={() => paymentAction(p.id, 'refund')} icon={ArrowsClockwise} label="Refund" tone="warn" testId={`payment-refund-${p.id}`} />
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>
    </div>
  );
};

export default DealFinancialsTab;
