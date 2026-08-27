/**
 * Customer 360 → Deposits Tab (UAT Enhancement #2)
 * ------------------------------------------------
 * Spec fields:
 *   Date · Payment Date · Amount · Currency · Status ·
 *   Manager · Contract · Files · Comment · Created · Updated
 *
 * Architecture:
 *   - Reads/writes via the unified `/api/customers/{cid}/deposits`
 *     and `/api/deposits/{id}` endpoints (single backend layer on
 *     db.legal_deposits).
 *   - Manager dropdown → `/api/team/managers`
 *   - Contract dropdown → `/api/customers/{cid}/contracts`
 *   - Files attachment → `/api/customers/{cid}/files` (File Manager)
 *   - i18n via useLang() — all strings under `dep_*`.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Wallet, Plus, Pencil, X, Paperclip, ExternalLink,
  CheckCircle2, Clock, XCircle, RefreshCcw, Trash2, FileText,
} from 'lucide-react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  pending:   { icon: Clock,        bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   key: 'dep_status_pending' },
  paid:      { icon: CheckCircle2, bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', key: 'dep_status_paid' },
  cancelled: { icon: XCircle,      bg: 'bg-zinc-100',   border: 'border-zinc-200',    text: 'text-zinc-500',    key: 'dep_status_cancelled' },
  refunded:  { icon: RefreshCcw,   bg: 'bg-violet-50',  border: 'border-violet-200',  text: 'text-violet-700',  key: 'dep_status_refunded' },
};

const CURRENCIES = ['EUR', 'USD', 'BGN', 'UAH', 'GBP'];

const fmtMoney = (n, ccy = 'EUR') => {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: (ccy || 'EUR').toUpperCase(),
      maximumFractionDigits: 2,
    }).format(Number(n || 0));
  } catch {
    return `${Number(n || 0).toFixed(2)} ${(ccy || 'EUR').toUpperCase()}`;
  }
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return '—'; }
};
const fmtDateTime = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return '—'; }
};

const toDateInput = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toISOString().slice(0, 10);
  } catch { return ''; }
};

const StatusPill = ({ status, t }) => {
  const meta = STATUS_META[(status || 'pending').toLowerCase()] || STATUS_META.pending;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold border ${meta.bg} ${meta.border} ${meta.text}`}
      data-testid={`dep-status-${(status || 'pending')}`}
    >
      <Icon className="w-3 h-3" />
      {t(meta.key) || status}
    </span>
  );
};

const KpiCard = ({ label, value, accent = '#2563EB', testId }) => (
  <div
    className="bg-white border border-zinc-200 rounded-2xl p-3"
    data-testid={testId}
  >
    <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500">{label}</p>
    <p className="text-xl font-bold mt-1 tabular-nums" style={{ color: accent }}>{value}</p>
  </div>
);

// ─────────────────────────────────────────────────────────────────
// Files picker modal — selects existing files from File Manager
// ─────────────────────────────────────────────────────────────────
const FilesPickerModal = ({ open, onClose, customerId, selectedIds, onSave, t }) => {
  const [files, setFiles] = useState([]);
  const [picked, setPicked] = useState(new Set(selectedIds || []));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPicked(new Set(selectedIds || []));
    (async () => {
      try {
        setLoading(true);
        const r = await axios.get(`${API_URL}/api/customers/${customerId}/files`);
        setFiles(r.data?.items || []);
      } catch {
        toast.error(t('dep_loading') || 'Loading failed');
      } finally {
        setLoading(false);
      }
    })();
  }, [open, customerId, selectedIds, t]);

  if (!open) return null;
  const toggle = (id) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPicked(next);
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 px-3" data-testid="dep-files-picker">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <div className="px-5 py-3.5 border-b flex items-center justify-between">
          <h3 className="text-base font-semibold text-zinc-900">{t('dep_attach_files') || 'Attach files'}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100"><X className="w-4 h-4" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="text-sm text-zinc-400 text-center py-6">{t('dep_loading') || 'Loading…'}</div>
          ) : files.length === 0 ? (
            <div className="text-sm text-zinc-400 text-center py-6">{t('dep_no_files') || 'No files'}</div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {files.map((f) => (
                <li key={f.id} className="py-2 flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={picked.has(f.id)}
                    onChange={() => toggle(f.id)}
                    className="w-4 h-4 accent-[#4F46E5]"
                    data-testid={`dep-picker-file-${f.id}`}
                  />
                  <FileText className="w-4 h-4 text-zinc-500 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-zinc-900 truncate">{f.original_name || f.name || 'file'}</p>
                    <p className="text-[11px] text-zinc-400">{((f.size_bytes || 0) / 1024).toFixed(1)} KB</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="px-5 py-3 border-t flex justify-end gap-2 bg-zinc-50">
          <button
            onClick={onClose}
            className="h-9 px-4 rounded-xl border border-zinc-200 text-zinc-700 text-[12.5px] font-semibold hover:bg-white"
            data-testid="dep-picker-cancel"
          >{t('dep_cancel') || 'Cancel'}</button>
          <button
            onClick={() => { onSave(Array.from(picked)); onClose(); }}
            className="h-9 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold"
            data-testid="dep-picker-save"
          >{t('dep_save') || 'Save'}</button>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
// Add / Edit dialog
// ─────────────────────────────────────────────────────────────────
const DepositDialog = ({ open, onClose, customerId, deposit, onSaved, t }) => {
  const isEdit = !!deposit;
  const [form, setForm] = useState({});
  const [managers, setManagers] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [filesPickerOpen, setFilesPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const base = deposit ? {
      date: toDateInput(deposit.date || deposit.created_at),
      paymentDate: toDateInput(deposit.paymentDate),
      amount: deposit.amount ?? '',
      currency: deposit.currency || 'EUR',
      status: deposit.status || 'pending',
      managerId: deposit.managerId || '',
      contractId: deposit.contractId || '',
      fileIds: deposit.fileIds || (deposit.files || []).map((f) => f.id),
      comment: deposit.comment || deposit.note || '',
    } : {
      date: toDateInput(new Date().toISOString()),
      paymentDate: '',
      amount: '',
      currency: 'EUR',
      status: 'pending',
      managerId: '',
      contractId: '',
      fileIds: [],
      comment: '',
    };
    setForm(base);
    (async () => {
      try {
        const [m, c] = await Promise.all([
          axios.get(`${API_URL}/api/team/managers`).catch(() => ({ data: { data: [] } })),
          axios.get(`${API_URL}/api/customers/${customerId}/contracts`).catch(() => ({ data: { items: [] } })),
        ]);
        setManagers(m.data?.data || m.data?.items || []);
        setContracts(c.data?.items || []);
      } catch { /* ignore */ }
    })();
  }, [open, deposit, customerId]);

  if (!open) return null;

  const submit = async () => {
    if (!form.amount || Number(form.amount) <= 0) {
      toast.error(t('dep_required') || 'Required field');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        amount: Number(form.amount),
        currency: form.currency,
        status: form.status,
        date: form.date ? new Date(form.date).toISOString() : null,
        paymentDate: form.paymentDate ? new Date(form.paymentDate).toISOString() : null,
        managerId: form.managerId || null,
        contractId: form.contractId || null,
        fileIds: form.fileIds || [],
        comment: form.comment || null,
      };
      if (isEdit) {
        await axios.patch(`${API_URL}/api/deposits/${deposit.id}`, payload);
        toast.success(t('dep_save') || 'Saved');
      } else {
        await axios.post(`${API_URL}/api/customers/${customerId}/deposits`, payload);
        toast.success(t('dep_save') || 'Saved');
      }
      onSaved();
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/50 px-3 py-6 overflow-y-auto" data-testid="dep-dialog">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl">
        <div className="px-5 py-3.5 border-b flex items-center justify-between">
          <h3 className="text-base font-semibold text-zinc-900">
            {isEdit ? (t('dep_edit') || 'Edit Deposit') : (t('dep_add') || 'Add Deposit')}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100"><X className="w-4 h-4" /></button>
        </div>
        <div className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t('dep_date') || 'Date'}>
            <input type="date" value={form.date || ''} onChange={(e) => setForm({ ...form, date: e.target.value })}
              className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-date" />
          </Field>
          <Field label={t('dep_payment_date') || 'Payment Date'}>
            <input type="date" value={form.paymentDate || ''} onChange={(e) => setForm({ ...form, paymentDate: e.target.value })}
              className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-payment-date" />
          </Field>
          <Field label={`${t('dep_amount') || 'Amount'} *`}>
            <input type="number" min="0" step="0.01" value={form.amount ?? ''}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              placeholder={t('dep_amount_placeholder') || '0.00'} className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-amount" />
          </Field>
          <Field label={t('dep_currency') || 'Currency'}>
            <select value={form.currency || 'EUR'} onChange={(e) => setForm({ ...form, currency: e.target.value })}
              className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-currency">
              {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label={t('dep_status') || 'Status'}>
            <select value={form.status || 'pending'} onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-status">
              <option value="pending">{t('dep_status_pending') || 'Pending'}</option>
              <option value="paid">{t('dep_status_paid') || 'Paid'}</option>
              <option value="cancelled">{t('dep_status_cancelled') || 'Cancelled'}</option>
              <option value="refunded">{t('dep_status_refunded') || 'Refunded'}</option>
            </select>
          </Field>
          <Field label={t('dep_manager') || 'Manager'}>
            <select value={form.managerId || ''} onChange={(e) => setForm({ ...form, managerId: e.target.value })}
              className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-manager">
              <option value="">{t('dep_select_manager') || '— Select manager —'}</option>
              {managers.map((m) => (
                <option key={m.id} value={m.id}>
                  {(m.firstName || m.name || m.email) + (m.lastName ? ` ${m.lastName}` : '')}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('dep_contract') || 'Contract'}>
            <select value={form.contractId || ''} onChange={(e) => setForm({ ...form, contractId: e.target.value })}
              className="w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors" data-testid="dep-field-contract">
              <option value="">{t('dep_select_contract') || '— No contract —'}</option>
              {contracts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.contract_number || c.title || c.id?.slice(-8)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('dep_files') || 'Files'}>
            <button type="button" onClick={() => setFilesPickerOpen(true)}
              className="form-input flex items-center justify-between text-left"
              data-testid="dep-field-files">
              <span className="inline-flex items-center gap-1.5"><Paperclip className="w-3.5 h-3.5" />
                {(form.fileIds || []).length > 0
                  ? (t('dep_files_count') || '{n} file(s)').replace('{n}', (form.fileIds || []).length)
                  : (t('dep_attach_files') || 'Attach files')}
              </span>
            </button>
          </Field>
          <div className="sm:col-span-2">
            <Field label={t('dep_comment') || 'Comment'}>
              <textarea value={form.comment || ''} onChange={(e) => setForm({ ...form, comment: e.target.value })}
                placeholder={t('dep_comment_placeholder') || ''} rows={3} className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors"
                data-testid="dep-field-comment" />
            </Field>
          </div>
        </div>
        <div className="px-5 py-3 border-t flex justify-end gap-2 bg-zinc-50 rounded-b-2xl">
          <button onClick={onClose}
            className="h-9 px-4 rounded-xl border border-zinc-200 text-zinc-700 text-[12.5px] font-semibold hover:bg-white"
            data-testid="dep-dialog-cancel">
            {t('dep_cancel') || 'Cancel'}
          </button>
          <button onClick={submit} disabled={saving}
            className="h-9 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold disabled:opacity-60"
            data-testid="dep-dialog-save">
            {saving ? '…' : (t('dep_save') || 'Save')}
          </button>
        </div>
      </div>
      <FilesPickerModal
        open={filesPickerOpen}
        onClose={() => setFilesPickerOpen(false)}
        customerId={customerId}
        selectedIds={form.fileIds || []}
        onSave={(ids) => setForm({ ...form, fileIds: ids })}
        t={t}
      />
    </div>
  );
};

const Field = ({ label, children }) => (
  <label className="block">
    <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-1 block">{label}</span>
    {children}
  </label>
);

// ─────────────────────────────────────────────────────────────────
// Main tab
// ─────────────────────────────────────────────────────────────────
export default function DepositsTab({ customerId }) {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/customers/${customerId}/deposits`);
      setItems(r.data?.items || []);
      setSummary(r.data?.summary || {});
    } catch (e) {
      toast.error(t('dep_loading') || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [customerId, t]);

  useEffect(() => { load(); }, [load]);

  const openAdd = () => { setEditing(null); setDialogOpen(true); };
  const openEdit = (dep) => { setEditing(dep); setDialogOpen(true); };

  const cancelDeposit = async (dep) => {
    if (!window.confirm(t('dep_confirm_delete') || 'Cancel this deposit?')) return;
    try {
      await axios.delete(`${API_URL}/api/deposits/${dep.id}`);
      toast.success(t('dep_delete') || 'Cancelled');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    }
  };

  const fmCurrency = useMemo(() => (items[0]?.currency || 'EUR'), [items]);

  return (
    <div className="space-y-4" data-testid="customer360-deposits-tab">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-zinc-500" />
          <h3 className="text-base font-semibold text-zinc-900">
            {t('dep_title') || 'Deposits'} ({items.length})
          </h3>
        </div>
        <button
          onClick={openAdd}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold"
          data-testid="dep-add-btn"
        >
          <Plus className="w-4 h-4" /> {t('dep_add') || 'Add Deposit'}
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label={t('dep_kpi_total') || 'Total'} value={summary.total ?? 0} accent="#2563EB" testId="dep-kpi-total" />
        <KpiCard label={t('dep_kpi_paid') || 'Paid'} value={summary.paid ?? 0} accent="#059669" testId="dep-kpi-paid" />
        <KpiCard label={t('dep_kpi_pending') || 'Pending'} value={summary.pending ?? 0} accent="#D97706" testId="dep-kpi-pending" />
        <KpiCard label={t('dep_kpi_amount') || 'Amount'} value={fmtMoney(summary.totalAmount || 0, fmCurrency)} accent="#18181B" testId="dep-kpi-amount" />
      </div>

      {/* Body */}
      {loading ? (
        <div className="text-center py-10 text-zinc-400 text-sm" data-testid="dep-loading">
          <div className="animate-spin inline-block w-6 h-6 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-10 text-zinc-400 text-sm bg-zinc-50 rounded-2xl" data-testid="dep-empty">
          {t('dep_no_items') || 'No deposits yet'}
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1100px]">
              <thead className="bg-zinc-50 text-zinc-600 text-[11.5px] uppercase">
                <tr>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_date') || 'Date'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_payment_date') || 'Payment Date'}</th>
                  <th className="text-right px-3 py-2.5 font-semibold">{t('dep_amount') || 'Amount'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_status') || 'Status'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_phone') || 'Phone'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_manager') || 'Manager'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_contract') || 'Contract'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_files') || 'Files'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep_comment') || 'Comment'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep7_col_utm')}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep7_col_lead_source')}</th>
                  <th className="text-right px-3 py-2.5 font-semibold">{''}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {items.map((d) => (
                  <tr key={d.id} data-testid={`dep-row-${d.id}`}>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">{fmtDate(d.date)}</td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">{fmtDate(d.paymentDate)}</td>
                    <td className="px-3 py-3 text-right font-semibold text-zinc-900 tabular-nums whitespace-nowrap">
                      {fmtMoney(d.amount, d.currency)}
                    </td>
                    <td className="px-3 py-3"><StatusPill status={d.status} t={t} /></td>
                    <td className="px-3 py-3 whitespace-nowrap font-mono text-[12px]">
                      {d.customerPhone ? (
                        <a href={`tel:${String(d.customerPhone).replace(/\s+/g,'')}`}
                           className="text-zinc-700 hover:text-[#4F46E5]"
                           data-testid={`dep-phone-${d.id}`}>
                          {d.customerPhone}
                        </a>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">
                      {d.managerName || (d.managerId ? d.managerId.slice(-6) : t('dep_no_manager') || '—')}
                    </td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">
                      {d.contractId ? (
                        <a href={`/admin/contracts`} className="inline-flex items-center gap-1 text-[#4F46E5] hover:underline">
                          <FileText className="w-3.5 h-3.5" />
                          {d.contractNumber || d.contractId.slice(-6)}
                        </a>
                      ) : <span className="text-zinc-400">{t('dep_no_contract') || '—'}</span>}
                    </td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">
                      {(d.files || []).length > 0 ? (
                        <span className="inline-flex items-center gap-1 text-zinc-700">
                          <Paperclip className="w-3.5 h-3.5" />
                          {(t('dep_files_count') || '{n}').replace('{n}', d.files.length)}
                        </span>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 text-zinc-600 max-w-[220px] truncate" title={d.comment || ''}>
                      {d.comment || '—'}
                    </td>
                    <td className="px-3 py-3">
                      {d.utm && (d.utm.utm_source || d.utm.utm_medium || d.utm.utm_campaign) ? (
                        <span
                          title={`source: ${d.utm.utm_source || '—'}\nmedium: ${d.utm.utm_medium || '—'}\ncampaign: ${d.utm.utm_campaign || '—'}\ncontent: ${d.utm.utm_content || '—'}\nterm: ${d.utm.utm_term || '—'}`}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10.5px] font-mono bg-violet-50 text-violet-700 border border-violet-200 max-w-[180px] truncate"
                          data-testid={`dep-utm-${d.id}`}
                        >
                          {[d.utm.utm_source, d.utm.utm_medium ? `/ ${d.utm.utm_medium}` : '', d.utm.utm_campaign ? `· ${d.utm.utm_campaign}` : ''].filter(Boolean).join(' ')}
                        </span>
                      ) : <span className="text-zinc-400 text-[11px]">—</span>}
                    </td>
                    <td className="px-3 py-3">
                      {d.leadSource ? (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200"
                          data-testid={`dep-lead-source-${d.id}`}
                        >
                          {d.leadSource}
                        </span>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1">
                        <button
                          onClick={() => openEdit(d)}
                          title={t('dep_edit') || 'Edit'}
                          className="h-8 w-8 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 inline-flex items-center justify-center text-zinc-600"
                          data-testid={`dep-edit-${d.id}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        {d.status !== 'cancelled' && (
                          <button
                            onClick={() => cancelDeposit(d)}
                            title={t('dep_delete') || 'Cancel'}
                            className="h-8 w-8 rounded-lg border border-rose-100 bg-rose-50 hover:bg-rose-100 text-rose-700 inline-flex items-center justify-center"
                            data-testid={`dep-delete-${d.id}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Footer audit info (created/updated) */}
          <div className="border-t bg-zinc-50 px-3 py-2 text-[11px] text-zinc-500 flex flex-wrap gap-x-4 gap-y-1">
            <span>{t('dep_created_at') || 'Created'}: {fmtDateTime(items[0]?.created_at)}</span>
            <span>{t('dep_updated_at') || 'Updated'}: {fmtDateTime(items[0]?.updated_at)}</span>
          </div>
        </div>
      )}

      <DepositDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        customerId={customerId}
        deposit={editing}
        onSaved={load}
        t={t}
      />
    </div>
  );
}
