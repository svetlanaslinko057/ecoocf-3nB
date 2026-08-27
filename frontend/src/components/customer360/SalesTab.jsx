/**
 * Customer 360 → Sales Tab (UAT Enhancement #2)
 * ---------------------------------------------
 * Spec columns:
 *   Date · Client · Phone · Manager · Country · Auto (Make/Model/Year)
 *   · VIN · Auction · Lot · Amount · Contract · Docs · Status · Comment
 *
 * Architecture:
 *   - Reuses single backend layer: `/api/customers/{cid}/sales` (list,
 *     enriched), `/api/sales` (create), `/api/sales/{id}` (patch/cancel).
 *   - Manager dropdown → `/api/team/managers`
 *   - Contract dropdown → `/api/customers/{cid}/contracts`
 *   - Docs (files) → `/api/customers/{cid}/files` (File Manager).
 *   - i18n via useLang() — keys under `sales_*`.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Banknote, Plus, ExternalLink, CheckCircle2, XCircle,
  Pencil, X, Paperclip, FileText, Trash2,
} from 'lucide-react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  draft:     { icon: Pencil,       bg: 'bg-zinc-100',   border: 'border-zinc-200',    text: 'text-zinc-700',    key: 'sales_status_draft' },
  active:    { icon: CheckCircle2, bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700',   key: 'sales_status_active' },
  sold:      { icon: CheckCircle2, bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', key: 'sales_status_sold' },
  cancelled: { icon: XCircle,      bg: 'bg-rose-50',    border: 'border-rose-200',    text: 'text-rose-700',    key: 'sales_status_cancelled' },
};

const CURRENCIES = ['UAH', 'USD', 'EUR', 'BGN', 'GBP'];
const HAZARD_CLASSES = ['I', 'II', 'III', 'IV'];
const UNITS = ['kg', 't', 'l', 'pcs', 'm3'];
const UNIT_LABEL = { kg: 'кг', t: 'т', l: 'л', pcs: 'шт', m3: 'м³' };

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
const fmtDate = (iso) => { if (!iso) return '—'; try { return new Date(iso).toLocaleDateString(); } catch { return '—'; } };
const toDateInput = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toISOString().slice(0, 10); } catch { return ''; }
};

const StatusPill = ({ status, t }) => {
  const meta = STATUS_META[(status || 'draft').toLowerCase()] || STATUS_META.draft;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold border ${meta.bg} ${meta.border} ${meta.text}`}
      data-testid={`sales-status-${(status || 'draft')}`}
    >
      <Icon className="w-3 h-3" />
      {t(meta.key) || status}
    </span>
  );
};

const KpiCard = ({ label, value, accent = '#2563EB', testId }) => (
  <div className="bg-white border border-zinc-200 rounded-2xl p-3" data-testid={testId}>
    <p className="text-[10px] uppercase tracking-wider font-bold text-zinc-500">{label}</p>
    <p className="text-xl font-bold mt-1 tabular-nums" style={{ color: accent }}>{value}</p>
  </div>
);

const Field = ({ label, children }) => (
  <label className="block">
    <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-1 block">{label}</span>
    {children}
  </label>
);

const inputCls = "w-full h-9 px-3 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors";

// ─────────────────────────────────────────────────────────────────
// Files picker
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
      } catch { toast.error('Failed to load files'); }
      finally { setLoading(false); }
    })();
  }, [open, customerId, selectedIds]);

  if (!open) return null;
  const toggle = (id) => {
    const next = new Set(picked);
    if (next.has(id)) next.delete(id); else next.add(id);
    setPicked(next);
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 px-3" data-testid="sales-files-picker">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <div className="px-5 py-3.5 border-b flex items-center justify-between">
          <h3 className="text-base font-semibold text-zinc-900">{t('sales_docs') || 'Documents'}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100"><X className="w-4 h-4" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <div className="text-sm text-zinc-400 text-center py-6">{t('sales_loading') || 'Loading…'}</div>
          ) : files.length === 0 ? (
            <div className="text-sm text-zinc-400 text-center py-6">{t('sales_no_docs') || 'No documents'}</div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {files.map((f) => (
                <li key={f.id} className="py-2 flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={picked.has(f.id)}
                    onChange={() => toggle(f.id)}
                    className="w-4 h-4 accent-[#4F46E5]"
                    data-testid={`sales-picker-file-${f.id}`}
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
            data-testid="sales-picker-cancel"
          >{t('sales_cancel') || 'Cancel'}</button>
          <button
            onClick={() => { onSave(Array.from(picked)); onClose(); }}
            className="h-9 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold"
            data-testid="sales-picker-save"
          >{t('sales_save') || 'Save'}</button>
        </div>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
// Sale Add/Edit Dialog
// ─────────────────────────────────────────────────────────────────
const SaleDialog = ({ open, onClose, customerId, sale, onSaved, t }) => {
  const isEdit = !!sale;
  const [form, setForm] = useState({});
  const [managers, setManagers] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [picker, setPicker] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(sale ? {
      saleDate: toDateInput(sale.saleDate || sale.created_at),
      wasteType: sale.wasteType || '',
      wasteCode: sale.wasteCode || '',
      batchNo: sale.batchNo || '',
      hazardClass: sale.hazardClass || '',
      quantity: sale.quantity ?? '',
      unit: sale.unit || 'kg',
      saleAmount: sale.saleAmount ?? '',
      saleCurrency: sale.saleCurrency || 'UAH',
      managerId: sale.managerId || '',
      contractId: sale.contractId || '',
      fileIds: sale.fileIds || (sale.files || []).map((f) => f.id),
      status: sale.status || 'draft',
      comment: sale.comment || sale.notes || '',
      phone: sale.phone || sale.customerPhone || '',
    } : {
      saleDate: toDateInput(new Date().toISOString()),
      wasteType: '', wasteCode: '', batchNo: '', hazardClass: '',
      quantity: '', unit: 'kg',
      saleAmount: '', saleCurrency: 'UAH',
      managerId: '', contractId: '', fileIds: [],
      status: 'draft', comment: '', phone: '',
    });
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
  }, [open, sale, customerId]);

  if (!open) return null;

  const submit = async () => {
    if (!isEdit && !form.wasteType && !form.wasteCode) {
      toast.error(t('sales_waste_required') || 'Waste type or code required');
      return;
    }
    if (!form.saleAmount || Number(form.saleAmount) <= 0) {
      toast.error(t('sales_required') || 'Amount required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        customerId,
        wasteType: form.wasteType || null,
        wasteCode: form.wasteCode || null,
        batchNo: form.batchNo || null,
        hazardClass: form.hazardClass || null,
        quantity: form.quantity !== '' ? Number(form.quantity) : null,
        unit: form.unit || null,
        saleAmount: Number(form.saleAmount),
        saleCurrency: form.saleCurrency || 'UAH',
        saleDate: form.saleDate ? new Date(form.saleDate).toISOString() : null,
        managerId: form.managerId || null,
        contractId: form.contractId || null,
        fileIds: form.fileIds || [],
        status: form.status || 'draft',
        comment: form.comment || null,
        phone: form.phone || null,
      };
      if (isEdit) {
        await axios.patch(`${API_URL}/api/sales/${sale.id}`, payload);
      } else {
        await axios.post(`${API_URL}/api/sales`, payload);
      }
      toast.success(t('sales_save') || 'Saved');
      onSaved();
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/50 px-3 py-6 overflow-y-auto" data-testid="sales-dialog">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl">
        <div className="px-5 py-3.5 border-b flex items-center justify-between">
          <h3 className="text-base font-semibold text-zinc-900">
            {isEdit ? (t('sales_edit') || 'Edit Sale') : (t('sales_add') || 'Add Sale')}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-100"><X className="w-4 h-4" /></button>
        </div>

        <div className="px-5 py-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t('sales_date') || 'Date'}>
            <input type="date" value={form.saleDate || ''} onChange={(e) => setForm({ ...form, saleDate: e.target.value })}
              className={inputCls} data-testid="sales-field-date" />
          </Field>
          <Field label={t('sales_phone') || 'Phone'}>
            <input type="tel" value={form.phone || ''} onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+380…" className={inputCls} data-testid="sales-field-phone" />
          </Field>
          <Field label={t('sales_make') || 'Make'}>
            <input value={form.brand || ''} onChange={(e) => setForm({ ...form, brand: e.target.value })}
              className={inputCls} data-testid="sales-field-make" />
          </Field>
          <Field label={t('sales_model') || 'Model'}>
            <input value={form.model || ''} onChange={(e) => setForm({ ...form, model: e.target.value })}
              className={inputCls} data-testid="sales-field-model" />
          </Field>
          <Field label={t('sales_year') || 'Year'}>
            <input type="number" min="1900" max="2099" value={form.year || ''}
              onChange={(e) => setForm({ ...form, year: e.target.value })}
              className={inputCls} data-testid="sales-field-year" />
          </Field>
          <Field label={t('sales_country') || 'Country'}>
            <select value={form.country || 'OTHER'} onChange={(e) => setForm({ ...form, country: e.target.value })}
              className={inputCls} data-testid="sales-field-country">
              {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label={t('sales_vin') || 'VIN'}>
            <input value={form.vin || ''} onChange={(e) => setForm({ ...form, vin: e.target.value.toUpperCase() })}
              className={inputCls + ' font-mono uppercase'} data-testid="sales-field-vin" />
          </Field>
          <Field label={t('sales_lot') || 'Lot'}>
            <input value={form.lot || ''} onChange={(e) => setForm({ ...form, lot: e.target.value })}
              className={inputCls} data-testid="sales-field-lot" />
          </Field>
          <Field label={t('sales_auction') || 'Auction'}>
            <select value={form.auction || ''} onChange={(e) => setForm({ ...form, auction: e.target.value })}
              className={inputCls} data-testid="sales-field-auction">
              <option value="">—</option>
              {AUCTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>
          <Field label={`${t('sales_amount') || 'Amount'} *`}>
            <div className="flex gap-2">
              <input type="number" min="0" step="0.01" value={form.saleAmount ?? ''}
                onChange={(e) => setForm({ ...form, saleAmount: e.target.value })}
                className={inputCls} data-testid="sales-field-amount" />
              <select value={form.saleCurrency || 'USD'} onChange={(e) => setForm({ ...form, saleCurrency: e.target.value })}
                className={inputCls + ' w-24'} data-testid="sales-field-currency">
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </Field>
          <Field label={t('sales_manager') || 'Manager'}>
            <select value={form.managerId || ''} onChange={(e) => setForm({ ...form, managerId: e.target.value })}
              className={inputCls} data-testid="sales-field-manager">
              <option value="">{t('dep_select_manager') || '— Select manager —'}</option>
              {managers.map((m) => (
                <option key={m.id} value={m.id}>
                  {(m.firstName || m.name || m.email) + (m.lastName ? ` ${m.lastName}` : '')}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('sales_contract') || 'Contract'}>
            <select value={form.contractId || ''} onChange={(e) => setForm({ ...form, contractId: e.target.value })}
              className={inputCls} data-testid="sales-field-contract">
              <option value="">{t('dep_select_contract') || '— No contract —'}</option>
              {contracts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.contract_number || c.title || c.id?.slice(-8)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('sales_docs') || 'Docs'}>
            <button type="button" onClick={() => setPicker(true)}
              className={inputCls + ' flex items-center justify-between text-left hover:border-[#4F46E5]'}
              data-testid="sales-field-docs">
              <span className="inline-flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5" />
                {(form.fileIds || []).length > 0
                  ? (t('dep_files_count') || '{n}').replace('{n}', (form.fileIds || []).length)
                  : (t('dep_attach_files') || 'Attach')}
              </span>
            </button>
          </Field>
          <Field label={t('sales_status') || 'Status'}>
            <select value={form.status || 'draft'} onChange={(e) => setForm({ ...form, status: e.target.value })}
              className={inputCls} data-testid="sales-field-status">
              <option value="draft">{t('sales_status_draft') || 'Draft'}</option>
              <option value="active">{t('sales_status_active') || 'Active'}</option>
              <option value="sold">{t('sales_status_sold') || 'Sold'}</option>
              <option value="cancelled">{t('sales_status_cancelled') || 'Cancelled'}</option>
            </select>
          </Field>
          <div className="sm:col-span-2">
            <Field label={t('sales_comment') || 'Comment'}>
              <textarea value={form.comment || ''} onChange={(e) => setForm({ ...form, comment: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm text-zinc-900 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/20 focus:outline-none transition-colors"
                data-testid="sales-field-comment" />
            </Field>
          </div>
        </div>

        <div className="px-5 py-3 border-t flex justify-end gap-2 bg-zinc-50 rounded-b-2xl">
          <button onClick={onClose}
            className="h-9 px-4 rounded-xl border border-zinc-200 text-zinc-700 text-[12.5px] font-semibold hover:bg-white"
            data-testid="sales-dialog-cancel">
            {t('sales_cancel') || 'Cancel'}
          </button>
          <button onClick={submit} disabled={saving}
            className="h-9 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold disabled:opacity-60"
            data-testid="sales-dialog-save">
            {saving ? '…' : (t('sales_save') || 'Save')}
          </button>
        </div>
      </div>
      <FilesPickerModal
        open={picker}
        onClose={() => setPicker(false)}
        customerId={customerId}
        selectedIds={form.fileIds || []}
        onSave={(ids) => setForm({ ...form, fileIds: ids })}
        t={t}
      />
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
// Main tab
// ─────────────────────────────────────────────────────────────────
export default function SalesTab({ customerId }) {
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
      const r = await axios.get(`${API_URL}/api/customers/${customerId}/sales`);
      setItems(r.data?.items || []);
      setSummary(r.data?.summary || {});
    } catch {
      toast.error('Failed to load sales');
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => { load(); }, [load]);

  const openAdd = () => { setEditing(null); setDialogOpen(true); };
  const openEdit = (s) => { setEditing(s); setDialogOpen(true); };

  const markSold = async (s) => {
    try {
      await axios.patch(`${API_URL}/api/sales/${s.id}`, { status: 'sold' });
      toast.success(t('sales_mark_sold') || 'Marked as sold');
      load();
    } catch { toast.error('Failed to update'); }
  };

  const cancelSale = async (s) => {
    if (!window.confirm(t('sales_confirm_delete') || 'Cancel this sale?')) return;
    try {
      await axios.delete(`${API_URL}/api/sales/${s.id}`);
      toast.success(t('sales_delete') || 'Cancelled');
      load();
    } catch { toast.error('Failed'); }
  };

  const fmCurrency = useMemo(() => (items[0]?.saleCurrency || 'USD'), [items]);

  return (
    <div className="space-y-4" data-testid="customer360-sales-tab">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Banknote className="w-5 h-5 text-zinc-500" />
          <h3 className="text-base font-semibold text-zinc-900">
            {t('sales_title') || 'Sales'} ({items.length})
          </h3>
        </div>
        <button
          onClick={openAdd}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold"
          data-testid="sales-add-btn"
        >
          <Plus className="w-4 h-4" /> {t('sales_add') || 'Add Sale'}
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label={t('sales_kpi_total') || 'Total'} value={summary.total ?? 0} accent="#2563EB" testId="sales-kpi-total" />
        <KpiCard label={t('sales_kpi_sold') || 'Sold'} value={summary.sold ?? 0} accent="#059669" testId="sales-kpi-sold" />
        <KpiCard label={t('sales_kpi_active') || 'Active'} value={summary.active ?? 0} accent="#D97706" testId="sales-kpi-active" />
        <KpiCard label={t('sales_kpi_amount') || 'Amount'} value={fmtMoney(summary.totalAmount || 0, fmCurrency)} accent="#18181B" testId="sales-kpi-amount" />
      </div>

      {/* Body */}
      {loading ? (
        <div className="text-center py-10 text-zinc-400 text-sm" data-testid="sales-loading">
          <div className="animate-spin inline-block w-6 h-6 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-10 text-zinc-400 text-sm bg-zinc-50 rounded-2xl" data-testid="sales-empty">
          {t('sales_no_items') || 'No sales yet'}
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[1200px]">
              <thead className="bg-zinc-50 text-zinc-600 text-[11.5px] uppercase">
                <tr>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_date') || 'Date'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_client') || 'Client'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_phone') || 'Phone'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_manager') || 'Manager'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_country') || 'Country'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_car') || 'Vehicle'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_vin') || 'VIN'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_auction') || 'Auction'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_lot') || 'Lot'}</th>
                  <th className="text-right px-3 py-2.5 font-semibold">{t('sales_amount') || 'Amount'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_contract') || 'Contract'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_docs') || 'Docs'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_status') || 'Status'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('sales_comment') || 'Comment'}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep7_col_utm')}</th>
                  <th className="text-left px-3 py-2.5 font-semibold">{t('dep7_col_lead_source')}</th>
                  <th className="text-right px-3 py-2.5 font-semibold">{''}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {items.map((s) => (
                  <tr key={s.id} data-testid={`sales-row-${s.id}`}>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">{fmtDate(s.saleDate || s.created_at)}</td>
                    <td className="px-3 py-3 text-zinc-900 font-medium whitespace-nowrap">{s.customerName || '—'}</td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap font-mono text-[12px]">{s.customerPhone || s.phone || '—'}</td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">{s.managerName || (s.managerId ? s.managerId.slice(-6) : '—')}</td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">{s.country || '—'}</td>
                    <td className="px-3 py-3 text-zinc-900 whitespace-nowrap">
                      {[s.brand, s.model].filter(Boolean).join(' ') || '—'}
                      {s.year ? <span className="text-zinc-500"> · {s.year}</span> : null}
                    </td>
                    <td className="px-3 py-3 font-mono text-[12px] whitespace-nowrap">{s.vin || '—'}</td>
                    <td className="px-3 py-3 text-zinc-700 whitespace-nowrap">{s.auction || '—'}</td>
                    <td className="px-3 py-3 font-mono text-[12px] whitespace-nowrap">{s.lot || '—'}</td>
                    <td className="px-3 py-3 text-right font-semibold text-zinc-900 tabular-nums whitespace-nowrap">
                      {fmtMoney(s.saleAmount, s.saleCurrency)}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {s.contractId ? (
                        <a href={`/admin/contracts`} className="inline-flex items-center gap-1 text-[#4F46E5] hover:underline">
                          <FileText className="w-3.5 h-3.5" />
                          {s.contractNumber || s.contractId.slice(-6)}
                        </a>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {(s.files || []).length > 0 ? (
                        <span className="inline-flex items-center gap-1 text-zinc-700">
                          <Paperclip className="w-3.5 h-3.5" />
                          {(t('dep_files_count') || '{n}').replace('{n}', s.files.length)}
                        </span>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3"><StatusPill status={s.status} t={t} /></td>
                    <td className="px-3 py-3 text-zinc-600 max-w-[200px] truncate" title={s.comment || ''}>
                      {s.comment || '—'}
                    </td>
                    <td className="px-3 py-3">
                      {s.utm && (s.utm.utm_source || s.utm.utm_medium || s.utm.utm_campaign) ? (
                        <span
                          title={`source: ${s.utm.utm_source || '—'}\nmedium: ${s.utm.utm_medium || '—'}\ncampaign: ${s.utm.utm_campaign || '—'}\ncontent: ${s.utm.utm_content || '—'}\nterm: ${s.utm.utm_term || '—'}`}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10.5px] font-mono bg-violet-50 text-violet-700 border border-violet-200 max-w-[160px] truncate"
                          data-testid={`sales-utm-${s.id}`}
                        >
                          {[s.utm.utm_source, s.utm.utm_medium ? `/ ${s.utm.utm_medium}` : '', s.utm.utm_campaign ? `· ${s.utm.utm_campaign}` : ''].filter(Boolean).join(' ')}
                        </span>
                      ) : <span className="text-zinc-400 text-[11px]">—</span>}
                    </td>
                    <td className="px-3 py-3">
                      {s.leadSource ? (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200"
                          data-testid={`sales-lead-source-${s.id}`}
                        >
                          {s.leadSource}
                        </span>
                      ) : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center gap-1">
                        <button
                          onClick={() => openEdit(s)}
                          title={t('sales_edit') || 'Edit'}
                          className="h-8 w-8 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 inline-flex items-center justify-center text-zinc-600"
                          data-testid={`sales-edit-${s.id}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        {s.status !== 'sold' && s.status !== 'cancelled' && (
                          <button
                            onClick={() => markSold(s)}
                            title={t('sales_mark_sold') || 'Mark as sold'}
                            className="h-8 w-8 rounded-lg border border-emerald-100 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 inline-flex items-center justify-center"
                            data-testid={`sales-mark-sold-${s.id}`}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <a
                          href="/admin/sales"
                          title={t('sales_open_page') || 'Open Sales page'}
                          className="h-8 w-8 rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-600 inline-flex items-center justify-center"
                          data-testid={`sales-open-${s.id}`}
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                        {s.status !== 'cancelled' && (
                          <button
                            onClick={() => cancelSale(s)}
                            title={t('sales_delete') || 'Cancel'}
                            className="h-8 w-8 rounded-lg border border-rose-100 bg-rose-50 hover:bg-rose-100 text-rose-700 inline-flex items-center justify-center"
                            data-testid={`sales-delete-${s.id}`}
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
        </div>
      )}

      <SaleDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        customerId={customerId}
        sale={editing}
        onSaved={load}
        t={t}
      />
    </div>
  );
}
