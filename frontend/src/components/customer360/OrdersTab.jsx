/**
 * Customer360 - Orders Tab
 * ------------------------
 * Read-only list of all service orders (workflows) for a customer.
 * Each row shows status, items count, progress bar (computed from
 * completed steps / total steps), amount, and a quick expand-on-click
 * to reveal the step list inline.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Package,
  CheckCircle,
  Spinner,
  XCircle,
  CaretDown,
  CaretUp,
  Calendar,
  FilePdf,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_META = {
  new:             { color: 'bg-blue-100 text-blue-700',       label: 'New' },
  in_progress:     { color: 'bg-amber-100 text-amber-700',     label: 'In progress' },
  waiting_client:  { color: 'bg-purple-100 text-purple-700',   label: 'Waiting client' },
  completed:       { color: 'bg-emerald-100 text-emerald-700', label: 'Completed' },
  cancelled:       { color: 'bg-zinc-100 text-zinc-500',       label: 'Cancelled' },
};

const STEP_STATUS = {
  pending:     { color: 'bg-zinc-100 text-zinc-600',       icon: Spinner,     label: 'Pending' },
  in_progress: { color: 'bg-amber-100 text-amber-700',     icon: Spinner,     label: 'In progress' },
  done:        { color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle, label: 'Done' },
  completed:   { color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle, label: 'Done' },
  blocked:     { color: 'bg-red-100 text-red-700',         icon: XCircle,     label: 'Blocked' },
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

const OrdersTab = ({ customerId }) => {
  const { t } = useLang();
  const [orders, setOrders] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});
  const [generating, setGenerating] = useState(null);

  const authHeaders = () => {
    const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
    return tok ? { Authorization: `Bearer ${tok}` } : {};
  };

  const handleGenerateAct = async (orderId, e) => {
    e?.stopPropagation();
    if (!confirm('Generate Acceptance Act PDF for this order?')) return;
    try {
      setGenerating(orderId);
      const res = await axios.post(
        `${API_URL}/api/orders/${orderId}/acceptance-act`,
        {},
        { headers: authHeaders() }
      );
      const f = res.data?.file;
      toast.success(`Acceptance Act v${res.data.document.version} generated (${f?.original_name})`);
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
        const res = await axios.get(`${API_URL}/api/customers/${customerId}/orders`);
        if (!cancelled) {
          setOrders(res.data?.items || []);
          setSummary(res.data?.summary || {});
        }
      } catch (err) {
        if (!cancelled) console.error('Orders fetch failed', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const toggle = (id) => setExpanded((s) => ({ ...s, [id]: !s[id] }));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40" data-testid="orders-tab-loading">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="customer360-orders-tab">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label={t('adm_total_3') || 'Total'}     value={summary.total || 0}      accent="#4F46E5" />
        <KpiCard label="In progress"                     value={summary.inProgress || 0} accent="#D97706" />
        <KpiCard label={t('adm_completed') || 'Completed'} value={summary.completed || 0} accent="#059669" />
        <KpiCard label="Cancelled"                       value={summary.cancelled || 0}  accent="#71717A" />
      </div>

      {/* List */}
      {orders.length === 0 ? (
        <div className="section-card text-center py-12" data-testid="orders-empty">
          <Package size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">No orders yet. Orders are created automatically after an invoice is paid.</p>
        </div>
      ) : (
        <div className="section-card">
          <div className="divide-y divide-[#E4E4E7]">
            {orders.map((o) => {
              const meta = STATUS_META[(o.status || '').toLowerCase()] || STATUS_META.in_progress;
              const isOpen = !!expanded[o.id];
              return (
                <div key={o.id} className="py-3" data-testid={`order-row-${o.id}`}>
                  <div
                    className="flex items-center justify-between cursor-pointer hover:bg-[#F9F9FB] -mx-2 px-2 py-1 rounded-lg transition-colors"
                    onClick={() => toggle(o.id)}
                  >
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <div className="shrink-0 w-9 h-9 rounded-xl bg-[#F4F4F5] flex items-center justify-center">
                        <Package size={18} className="text-[#4F46E5]" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-[#18181B] truncate">
                          Order #{(o.id || '').slice(-8)}
                        </p>
                        <p className="text-xs text-[#71717A]">
                          {(o.items?.length || 0)} {o.items?.length === 1 ? 'service' : 'services'}
                          {o.invoiceId && ` · from invoice #${(o.invoiceId || '').slice(-8)}`}
                          {o.created_at && ` · ${new Date(o.created_at).toLocaleDateString()}`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="hidden sm:flex items-center gap-2 w-32">
                        <div className="flex-1 h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#4F46E5] transition-all"
                            style={{ width: `${o.progress_pct || 0}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-[#71717A] tabular-nums w-9 text-right">
                          {o.progress_pct || 0}%
                        </span>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-[#18181B] tabular-nums">
                          {fmtMoney(o.amount, o.currency)}
                        </p>
                      </div>
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium ${meta.color}`}>
                        {meta.label}
                      </span>
                      <button
                        onClick={(e) => handleGenerateAct(o.id, e)}
                        disabled={generating === o.id}
                        className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium bg-[#18181B] text-white rounded-lg hover:bg-[#3F3F46] disabled:opacity-50"
                        title="Generate Acceptance Act PDF"
                        data-testid={`gen-act-${o.id}`}
                      >
                        <FilePdf size={11} />
                        {generating === o.id ? 'Generating…' : 'Act'}
                      </button>
                      {isOpen ? <CaretUp size={14} className="text-[#A1A1AA]" /> : <CaretDown size={14} className="text-[#A1A1AA]" />}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-3 pl-12 pr-2 space-y-2" data-testid={`order-steps-${o.id}`}>
                      {(o.steps || []).length === 0 ? (
                        <p className="text-sm text-[#A1A1AA] italic">No steps defined for this order.</p>
                      ) : (
                        (o.steps || []).map((st, idx) => {
                          const sm = STEP_STATUS[(st.status || '').toLowerCase()] || STEP_STATUS.pending;
                          const Icon = sm.icon;
                          return (
                            <div key={st.id || idx} className="flex items-center gap-3 py-1.5 border-l-2 pl-3" style={{ borderColor: '#E4E4E7' }}>
                              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${sm.color}`}>
                                <Icon size={12} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-[#18181B] truncate">
                                  {st.label || st.service_name || st.key}
                                </p>
                                {st.service_name && st.label && st.service_name !== st.label && (
                                  <p className="text-[10px] text-[#A1A1AA] truncate">{st.service_name}</p>
                                )}
                              </div>
                              <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${sm.color}`}>
                                {sm.label}
                              </span>
                              {st.completed_at && (
                                <span className="text-[10px] text-[#A1A1AA] flex items-center gap-1">
                                  <Calendar size={10} />
                                  {new Date(st.completed_at).toLocaleDateString()}
                                </span>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
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

export default OrdersTab;
