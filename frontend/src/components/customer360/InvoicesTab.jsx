/**
 * Customer360 - Invoices Tab
 * --------------------------
 * Read-only list of all invoices for a customer.
 * Each row shows: status badge, items count, amount, currency, dates,
 * and (if available) a quick link to the linked order.
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
  Receipt,
  CheckCircle,
  Clock,
  XCircle,
  ArrowsClockwise,
  CaretRight,
  CurrencyCircleDollar,
  FilePdf,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  draft:     { color: 'bg-zinc-100 text-zinc-700',       label: 'Draft',    icon: Receipt },
  sent:      { color: 'bg-blue-100 text-blue-700',       label: 'Sent',     icon: ArrowsClockwise },
  pending:   { color: 'bg-amber-100 text-amber-700',     label: 'Pending',  icon: Clock },
  paid:      { color: 'bg-emerald-100 text-emerald-700', label: 'Paid',     icon: CheckCircle },
  cancelled: { color: 'bg-zinc-100 text-zinc-500',       label: 'Cancelled', icon: XCircle },
  refunded:  { color: 'bg-purple-100 text-purple-700',   label: 'Refunded', icon: ArrowsClockwise },
};

const fmtMoney = (n, ccy = 'USD') => {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: (ccy || 'USD').toUpperCase(),
      maximumFractionDigits: 0,
    }).format(Number(n || 0));
  } catch {
    return `${Number(n || 0).toFixed(2)} ${(ccy || 'USD').toUpperCase()}`;
  }
};

const InvoicesTab = ({ customerId }) => {
  const { t } = useLang();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [generating, setGenerating] = useState(null);

  const authHeaders = () => {
    const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
    return tok ? { Authorization: `Bearer ${tok}` } : {};
  };

  const handleGenerate = async (invId, kind, e) => {
    e?.stopPropagation();
    if (!confirm(`Generate ${kind === 'contract' ? 'Contract' : 'Invoice'} PDF?`)) return;
    try {
      setGenerating(`${invId}:${kind}`);
      const url = kind === 'contract'
        ? `${API_URL}/api/invoices/${invId}/contract`
        : `${API_URL}/api/invoices/${invId}/invoice-pdf`;
      const res = await axios.post(url, {}, { headers: authHeaders() });
      const f = res.data?.file;
      toast.success(`${kind === 'contract' ? 'Contract' : 'Invoice PDF'} v${res.data.document.version} generated`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Generation failed');
    } finally {
      setGenerating(null);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/api/customers/${customerId}/invoices`);
        if (!cancelled) {
          setInvoices(res.data?.items || []);
          setSummary(res.data?.summary || {});
        }
      } catch (err) {
        if (!cancelled) console.error('Invoices fetch failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const filtered = useMemo(() => {
    if (statusFilter === 'all') return invoices;
    return invoices.filter((i) => (i.status || '').toLowerCase() === statusFilter);
  }, [invoices, statusFilter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40" data-testid="invoices-tab-loading">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="customer360-invoices-tab">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label={t('adm_total_3') || 'Total'} value={summary.total || 0} accent="#4F46E5" />
        <KpiCard label={t('adm_paid') || 'Paid'} value={summary.paid || 0} accent="#059669" />
        <KpiCard label={t('adm_awaiting') || 'Pending'} value={summary.pending || 0} accent="#D97706" />
        <KpiCard
          label={t('adm_collected') || 'Paid Amount'}
          value={fmtMoney(summary.paidAmount || 0)}
          accent="#059669"
        />
      </div>

      {/* Filter */}
      <div className="flex flex-wrap gap-1 border-b border-[#E4E4E7] pb-2">
        {['all', 'paid', 'pending', 'sent', 'draft', 'cancelled', 'refunded'].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              statusFilter === s
                ? 'bg-[#18181B] text-white'
                : 'text-[#71717A] hover:bg-[#F4F4F5]'
            }`}
            data-testid={`invoices-filter-${s}`}
          >
            {s === 'all' ? 'All' : (STATUS_META[s]?.label || s)}
          </button>
        ))}
      </div>

      {/* List */}
      {filtered.length === 0 ? (
        <div className="section-card text-center py-12" data-testid="invoices-empty">
          <Receipt size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">{t('adm_no_invoices') || 'No invoices yet'}</p>
        </div>
      ) : (
        <div className="section-card">
          <div className="divide-y divide-[#E4E4E7]">
            {filtered.map((inv) => {
              const meta = STATUS_META[(inv.status || '').toLowerCase()] || STATUS_META.draft;
              const Icon = meta.icon;
              return (
                <div
                  key={inv.id}
                  className="flex items-center justify-between py-3 hover:bg-[#F9F9FB] -mx-2 px-2 rounded-lg transition-colors cursor-pointer"
                  onClick={() => navigate(`/admin/invoices/${inv.id}`)}
                  data-testid={`invoice-row-${inv.id}`}
                >
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <div className="shrink-0 w-9 h-9 rounded-xl bg-[#F4F4F5] flex items-center justify-center">
                      <Receipt size={18} className="text-[#4F46E5]" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-[#18181B] truncate">
                        {inv.description || `Invoice #${(inv.id || '').slice(-8)}`}
                      </p>
                      <p className="text-xs text-[#71717A]">
                        {(inv.items?.length || 0)} {inv.items?.length === 1 ? 'service' : 'services'}
                        {inv.created_at && ` · ${new Date(inv.created_at).toLocaleDateString()}`}
                        {inv.utm_source && ` · UTM: ${inv.utm_source}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <p className="font-semibold text-[#18181B] tabular-nums">
                        {fmtMoney(inv.total || inv.amount, inv.currency)}
                      </p>
                      {inv.dueDate && (
                        <p className="text-[10px] text-[#A1A1AA]">Due: {new Date(inv.dueDate).toLocaleDateString()}</p>
                      )}
                    </div>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium ${meta.color}`}>
                      <Icon size={12} />
                      {meta.label}
                    </span>
                    <div className="flex flex-col gap-1">
                      <button
                        onClick={(e) => handleGenerate(inv.id, 'contract', e)}
                        disabled={generating === `${inv.id}:contract`}
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium bg-[#18181B] text-white rounded-md hover:bg-[#3F3F46] disabled:opacity-50"
                        title="Generate Contract PDF"
                        data-testid={`gen-contract-${inv.id}`}
                      >
                        <FilePdf size={10} />
                        {generating === `${inv.id}:contract` ? '…' : 'Contract'}
                      </button>
                      <button
                        onClick={(e) => handleGenerate(inv.id, 'invoice', e)}
                        disabled={generating === `${inv.id}:invoice`}
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium bg-white border border-[#E4E4E7] text-[#3F3F46] rounded-md hover:bg-[#F4F4F5] disabled:opacity-50"
                        title="Export Invoice PDF"
                        data-testid={`gen-invoice-${inv.id}`}
                      >
                        <FilePdf size={10} />
                        {generating === `${inv.id}:invoice` ? '…' : 'PDF'}
                      </button>
                    </div>
                    <CaretRight size={14} className="text-[#A1A1AA]" />
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

export default InvoicesTab;
