/**
 * BIBI Cars — Wave 19 — Customer Portal View
 *
 * Cross-cutting screen for the three admin cabinets (manager / team_lead /
 * master_admin). Answers ONE question for any selected customer:
 *
 *     "What is happening with this customer's order right now?"
 *
 * Lives inside the existing admin layout (sidebar, header, search) and uses
 * the same design tokens as Executive Center / Notification Center /
 * Customer360 — light theme, Tailwind, Phosphor icons, KpiTile cards.
 *
 * Backend BFF: GET /api/customer-portal/{customer_id}/home — single round-trip
 * returns all 5 blocks (My Car · Delivery Timeline · Documents · Payments ·
 * Notifications) trimmed and tenant-checked server-side.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  Storefront, ArrowsClockwise, MagnifyingGlass, UserCircle, Car, Truck, FileText,
  CurrencyEur, Bell, Download, CheckCircle, Circle, MapPin, ArrowSquareOut,
  Clock, CheckSquare, BellRinging, Image as ImageIcon, CaretRight, Receipt,
} from '@phosphor-icons/react';

import { API_URL } from '../App';
import { useLang } from '../i18n';
import { HelpTooltip } from '../components/ui/HelpTooltip';

// ── helpers ────────────────────────────────────────────────────────────────
const fmtMoney = (n, ccy = 'USD') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};
const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); }
  catch { return iso; }
};
const relTime = (iso) => {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (isNaN(t)) return '';
  const diff = Math.floor((Date.now() - t) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff/86400)}d ago`;
  return new Date(iso).toLocaleDateString();
};

const STATUS_TONE = {
  delivered:  'bg-emerald-50 border-emerald-200 text-emerald-700',
  completed:  'bg-emerald-50 border-emerald-200 text-emerald-700',
  in_transit: 'bg-indigo-50 border-indigo-200 text-indigo-700',
  at_sea:     'bg-indigo-50 border-indigo-200 text-indigo-700',
  customs:    'bg-amber-50 border-amber-200 text-amber-700',
  port_arrived:'bg-amber-50 border-amber-200 text-amber-700',
  loaded:     'bg-blue-50 border-blue-200 text-blue-700',
  picked_up:  'bg-blue-50 border-blue-200 text-blue-700',
  payment_confirmed:'bg-violet-50 border-violet-200 text-violet-700',
  auction_won:'bg-violet-50 border-violet-200 text-violet-700',
  cancelled:  'bg-red-50 border-red-200 text-red-700',
  new:        'bg-slate-50 border-slate-200 text-slate-700',
};

const INV_TONE = {
  paid:    'bg-emerald-100 text-emerald-700',
  open:    'bg-amber-100 text-amber-700',
  overdue: 'bg-red-100 text-red-700',
};

// ── small UI building blocks (mirror Executive Center) ─────────────────────
function Section({ title, hint, children, action }) {
  return (
    <section className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="text-[15px] font-bold text-[#18181B]">{title}</h3>
          {hint ? <p className="text-[12px] text-[#71717A] mt-0.5">{hint}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function KpiTile({ icon: Icon, label, value, hint, tone = 'neutral', tooltip }) {
  const cls = {
    neutral: 'bg-white border-[#E4E4E7]',
    good:    'bg-emerald-50 border-emerald-200',
    warn:    'bg-amber-50 border-amber-200',
    bad:     'bg-red-50 border-red-200',
    accent:  'bg-indigo-50 border-indigo-200',
  }[tone] || 'bg-white border-[#E4E4E7]';
  const tile = (
    <div className={`border rounded-2xl p-4 ${cls}`}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
        <Icon size={14} weight="bold" /> {label}
      </div>
      <div className="text-[22px] font-bold text-[#18181B] mt-1 tabular-nums leading-tight">{value}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5">{hint}</div> : null}
    </div>
  );
  return tooltip ? <HelpTooltip text={tooltip}>{tile}</HelpTooltip> : tile;
}

function EmptyState({ icon: Icon, children }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-[12px] text-[#71717A]">
      {Icon ? <Icon size={28} weight="duotone" className="text-[#A1A1AA] mb-2" /> : null}
      <span>{children}</span>
    </div>
  );
}

// ── customer picker ───────────────────────────────────────────────────────
function CustomerPicker({ onPick }) {
  const { t } = useLang();
  const [query, setQuery] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const load = useCallback(async (q = '') => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API_URL}/api/customer-portal/customers`, { headers, params: q ? { q, limit: 50 } : { limit: 30 } });
      setItems(data?.items || []);
    } catch (e) {
      toast.error(t('cp_load_failed') || 'Failed to load customers');
    } finally { setLoading(false); }
  }, [headers, t]);

  useEffect(() => { load(''); }, [load]);

  const onSubmit = (e) => { e.preventDefault(); load(query.trim()); };

  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5" data-testid="customer-picker">
      {/* Mobile-first header: stacks on mobile, inline on desktop */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div className="min-w-0">
          <h3 className="text-[15px] font-bold text-[#18181B]">{t('cp_pick_customer') || 'Pick a customer'}</h3>
          <p className="text-[12px] text-[#71717A] mt-0.5">{t('cp_pick_customer_hint') || 'Read-only view of what the customer is seeing about their order.'}</p>
        </div>
        <form onSubmit={onSubmit} className="flex items-center gap-2 w-full sm:w-auto shrink-0">
          <div className="relative flex-1 sm:flex-initial">
            <MagnifyingGlass size={14} weight="bold" className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('cp_search_placeholder') || 'Search by name / email / phone'}
              data-testid="cp-search"
              className="pl-8 pr-3 py-2 border border-[#E4E4E7] rounded-xl text-[12px] w-full sm:w-64 lg:w-72 focus:outline-none focus:ring-2 focus:ring-[#18181B]/10"
            />
          </div>
          <button type="submit" className="inline-flex items-center gap-2 px-3 py-2 bg-[#18181B] text-white rounded-xl text-[12px] font-semibold hover:bg-[#27272A] shrink-0">{t('cp_search_btn') || 'Search'}</button>
        </form>
      </div>

      {loading ? (
        <div className="py-10 text-center text-[12px] text-[#71717A]">{t('cp_loading') || 'Loading…'}</div>
      ) : items.length === 0 ? (
        <EmptyState icon={UserCircle}>{t('cp_no_customers') || 'No customers found'}</EmptyState>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="cp-customers-grid">
          {items.map((c) => (
            <button
              key={c.customerId}
              onClick={() => onPick(c.customerId)}
              data-testid={`cp-customer-${c.customerId}`}
              className="text-left bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl p-3 hover:border-[#18181B] hover:bg-white transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#18181B] to-[#52525B] text-white flex items-center justify-center font-bold text-[13px] flex-shrink-0">
                  {(c.name || c.email || 'C').trim().slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold text-[#18181B] truncate">{c.name || c.email || c.customerId}</div>
                  <div className="text-[11px] text-[#71717A] truncate">{c.email}</div>
                  <div className="flex items-center gap-3 mt-1.5 text-[10px] text-[#71717A]">
                    <span className="inline-flex items-center gap-1"><Car size={10} weight="bold" /> {c.dealsCount} {c.dealsCount === 1 ? (t('cp_deal_one') || 'deal') : (t('cp_deal_many') || 'deals')}</span>
                    {c.phone ? <span className="truncate">{c.phone}</span> : null}
                  </div>
                </div>
                <CaretRight size={14} className="text-[#A1A1AA] mt-2 flex-shrink-0" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────
export default function CustomerPortalView() {
  const { t } = useLang();
  const { customerId } = useParams();
  const navigate = useNavigate();
  const [home, setHome] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedDealId, setSelectedDealId] = useState(null);

  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const load = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    setError('');
    try {
      const params = selectedDealId ? { deal_id: selectedDealId } : {};
      const { data } = await axios.get(`${API_URL}/api/customer-portal/${customerId}/home`, { headers, params });
      setHome(data);
      if (!selectedDealId && data?.activeDeal?.id) setSelectedDealId(data.activeDeal.id);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || (t('cp_load_customer_failed') || 'Failed to load customer view');
      setError(msg);
      toast.error(msg);
    } finally { setLoading(false); }
  }, [customerId, selectedDealId, headers, t]);

  useEffect(() => { load(); }, [load]);

  const onMarkRead = async (id) => {
    try {
      await axios.post(`${API_URL}/api/customer-portal/${customerId}/notifications/${id}/read`, null, { headers });
      load();
    } catch (e) { /* silent */ }
  };

  // ── no customer selected → picker ──
  if (!customerId) {
    return (
      <div className="min-h-full" data-testid="customer-portal-view-picker">
        {/* HEADER */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-6">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center flex-shrink-0"><Storefront size={20} weight="bold" /></div>
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-bold text-[#18181B] leading-tight">{t('cp_portal_title') || 'Customer Portal'}</h1>
              <p className="text-[12px] text-[#71717A] mt-0.5">{t('cp_portal_subtitle') || 'Cross-cutting customer order view — manager · team_lead · admin'}</p>
            </div>
          </div>
        </div>
        <CustomerPicker onPick={(cid) => navigate(`/admin/customer-portal/${cid}`)} />
      </div>
    );
  }

  // ── customer selected ──
  const customer = home?.customer;
  const deal = home?.activeDeal;
  const delivery = home?.delivery;
  const documents = home?.documents;
  const payments = home?.payments;
  const notifications = home?.notifications || { items: [], total: 0, unread: 0 };
  const allDeals = home?.allDeals || [];
  const initials = (customer?.name || customer?.email || 'C').trim().slice(0, 2).toUpperCase();
  const statusTone = STATUS_TONE[deal?.status || 'new'] || STATUS_TONE.new;

  return (
    <div className="min-h-full" data-testid="customer-portal-view">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-6">
        <div className="flex items-start gap-3 min-w-0">
          <button onClick={() => navigate('/admin/customer-portal')} className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center hover:bg-black flex-shrink-0" title={t('cp_back_to_picker') || 'Back to customer picker'}>
            <Storefront size={20} weight="bold" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold text-[#18181B] leading-tight">{t('cp_portal_title') || 'Customer Portal'}</h1>
            <p className="text-[12px] text-[#71717A] mt-0.5 truncate">
              {customer ? `${t('cp_viewing') || 'Viewing'}: ${customer.name || customer.email || customer.customerId}` : (t('cp_loading_customer') || 'Loading customer…')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => navigate(`/admin/customers/${customerId}/360`)} className="inline-flex items-center gap-2 px-3 py-2 border border-[#E4E4E7] bg-white rounded-xl text-[12px] font-semibold hover:bg-[#FAFAFA]" data-testid="cp-open-customer360">
            <ArrowSquareOut size={14} weight="bold" /> {t('cp_open_customer360') || 'Open Customer 360'}
          </button>
          <button onClick={load} className="inline-flex items-center gap-2 px-3 py-2 border border-[#E4E4E7] bg-white rounded-xl text-[12px] font-semibold hover:bg-[#FAFAFA]" data-testid="cp-refresh">
            <ArrowsClockwise size={14} weight="bold" /> {t('cp_refresh') || 'Refresh'}
          </button>
        </div>
      </div>

      {/* CUSTOMER BAR */}
      {customer ? (
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 mb-5 flex flex-wrap items-center gap-3 sm:gap-4">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#18181B] to-[#52525B] text-white flex items-center justify-center font-bold text-[14px] flex-shrink-0">
            {initials}
          </div>
          <div className="flex-1 min-w-[150px]">
            <div className="text-[15px] font-bold text-[#18181B] truncate">{customer.name || customer.email}</div>
            <div className="text-[11px] text-[#71717A] truncate">{customer.email}{customer.phone ? ` · ${customer.phone}` : ''}</div>
          </div>
          {allDeals.length > 1 && (
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] text-[#71717A]">{t('cp_deal_label') || 'Deal'}</span>
              <select
                value={selectedDealId || ''}
                onChange={(e) => setSelectedDealId(e.target.value)}
                data-testid="cp-deal-switch"
                className="border border-[#E4E4E7] rounded-xl px-3 py-1.5 text-[12px] bg-white focus:outline-none focus:ring-2 focus:ring-[#18181B]/10 max-w-[200px] sm:max-w-none"
              >
                {allDeals.map((d) => (
                  <option key={d.id} value={d.id}>{d.vehicle} · {d.statusLabel}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      ) : null}

      {loading && !home ? (
        <div className="py-20 text-center text-[12px] text-[#71717A]">{t('cp_loading_view') || 'Loading customer portal view…'}</div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-4 text-[13px]">{error}</div>
      ) : !deal ? (
        <Section title={t('cp_no_active_deal') || 'No active deal'} hint={t('cp_no_deals_hint') || "This customer doesn't have any deals yet."}>
          <EmptyState icon={Car}>{t('cp_nothing_to_display') || 'Nothing to display'}</EmptyState>
        </Section>
      ) : (
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* ── LEFT (2/3): My Car / Delivery / Documents / Payments ── */}
          <div className="lg:col-span-2 space-y-5">
            {/* BLOCK 1 — MY CAR */}
            <Section title={t('cp_my_car') || 'My Car'} hint={`${t('cp_deal_short') || 'Deal'} #${(deal.id || '').slice(-8)} · ${deal.auction || ''}`} action={
              <button onClick={() => navigate(`/admin/deals/${deal.id}/360`)} className="text-[11px] font-semibold text-[#18181B] hover:underline inline-flex items-center gap-1">
                {t('cp_deal_360') || 'Deal 360'} <ArrowSquareOut size={11} weight="bold" />
              </button>
            }>
              <div className="flex flex-col md:flex-row gap-4" data-testid="cp-block-car">
                <div className="w-full md:w-[260px] h-[170px] bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl overflow-hidden flex-shrink-0 flex items-center justify-center text-[#A1A1AA]">
                  {deal.photo ? <img src={deal.photo} alt={deal.vehicle} className="w-full h-full object-cover" /> : <ImageIcon size={32} weight="duotone" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[20px] sm:text-[22px] font-bold text-[#18181B] leading-tight break-words">{deal.vehicle}</div>
                  {deal.vin ? <div className="text-[11px] text-[#71717A] mt-1 font-mono break-all">VIN: {deal.vin}</div> : null}
                  {deal.lot ? <div className="text-[11px] text-[#71717A] mt-0.5">{t('cp_lot') || 'Lot'}: {deal.lot}</div> : null}
                  <span className={`inline-flex items-center mt-3 px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border ${statusTone}`}>
                    {deal.statusLabel || deal.status}
                  </span>
                  {deal.eta ? <div className="text-[12px] text-[#71717A] mt-3">{t('cp_eta') || 'ETA'} · <span className="font-semibold text-[#18181B]">{fmtDate(deal.eta)}</span></div> : null}
                </div>
              </div>
            </Section>

            {/* BLOCK 2 — DELIVERY TIMELINE */}
            <Section title={t('cp_delivery_timeline') || 'Delivery Timeline'} hint={delivery ? `${delivery.progressPercent}% ${t('cp_complete') || 'complete'} · ${t('cp_current_milestone') || 'current milestone'}: ${delivery.currentMilestone || '—'}` : (t('cp_delivery_readonly') || 'Wave 13 timeline (read-only)')} action={
              <button onClick={() => navigate('/admin/delivery')} className="text-[11px] font-semibold text-[#18181B] hover:underline inline-flex items-center gap-1">
                {t('cp_delivery_360') || 'Delivery 360'} <ArrowSquareOut size={11} weight="bold" />
              </button>
            }>
              {delivery ? (
                <div data-testid="cp-block-delivery">
                  <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
                    {delivery.milestones.map((m, idx) => {
                      const isDone = m.state === 'done';
                      const isCurrent = m.state === 'current';
                      const dot = isDone
                        ? 'bg-emerald-500 border-emerald-500 text-white'
                        : isCurrent
                        ? 'bg-indigo-500 border-indigo-500 text-white ring-4 ring-indigo-100'
                        : 'bg-white border-[#E4E4E7] text-[#A1A1AA]';
                      const label = isDone ? 'text-[#18181B]' : isCurrent ? 'text-indigo-700 font-semibold' : 'text-[#A1A1AA]';
                      return (
                        <div key={m.key} className="flex flex-col items-center text-center gap-1.5">
                          <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center text-[11px] font-bold ${dot}`}>
                            {isDone ? <CheckCircle size={16} weight="fill" /> : idx + 1}
                          </div>
                          <span className={`text-[10px] leading-tight ${label}`} style={{ minHeight: 24 }}>{m.label}</span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-4 h-1.5 bg-[#F4F4F5] rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-emerald-500 to-indigo-500" style={{ width: `${delivery.progressPercent}%` }} />
                  </div>
                </div>
              ) : (
                <EmptyState icon={Truck}>{t('cp_timeline_pending') || 'Timeline will appear once the deal moves.'}</EmptyState>
              )}
            </Section>

            {/* BLOCK 3 — DOCUMENTS */}
            <Section title={t('cp_documents') || 'Documents'} hint={documents ? `${documents.items.length} ${documents.items.length === 1 ? (t('cp_file_one') || 'file') : (t('cp_file_many') || 'files')}` : (t('cp_docs_hint') || 'Customer-visible files')}>
              {documents && documents.items.length > 0 ? (
                <div className="space-y-2" data-testid="cp-block-documents">
                  {documents.items.map((d) => (
                    <div key={d.id} className="flex items-center justify-between gap-3 bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl px-3 sm:px-4 py-3 hover:bg-white hover:border-[#D4D4D8] transition-colors">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-9 h-9 rounded-lg bg-white border border-[#E4E4E7] flex items-center justify-center text-[#18181B] flex-shrink-0">
                          <FileText size={16} weight="bold" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-[13px] font-semibold text-[#18181B] truncate">{d.label}</div>
                          <div className="text-[11px] text-[#71717A] truncate">
                            <span className="uppercase tracking-wider">{d.kind}</span>
                            {d.filename ? <> · {d.filename}</> : null}
                            {d.uploadedAt ? <> · {relTime(d.uploadedAt)}</> : null}
                          </div>
                        </div>
                      </div>
                      <a
                        href={`${API_URL}${d.downloadUrl}`}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`cp-doc-${d.id}`}
                        className="inline-flex items-center gap-1 px-2.5 sm:px-3 py-1.5 border border-[#E4E4E7] bg-white rounded-lg text-[11px] font-semibold text-[#18181B] hover:bg-[#FAFAFA] flex-shrink-0"
                      >
                        <Download size={12} weight="bold" /> <span className="hidden sm:inline">{t('cp_download') || 'Download'}</span>
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState icon={FileText}>{t('cp_no_documents') || 'No documents available yet.'}</EmptyState>
              )}
            </Section>

            {/* BLOCK 4 — PAYMENTS */}
            <Section title={t('cp_payments') || 'Payments'} hint={payments ? `${payments.currency} · ${payments.history.length} ${payments.history.length === 1 ? (t('cp_invoice_one') || 'invoice') : (t('cp_invoice_many') || 'invoices')}` : (t('cp_payments_hint') || 'Customer-visible invoices')} action={
              <button onClick={() => navigate('/admin/finance')} className="text-[11px] font-semibold text-[#18181B] hover:underline inline-flex items-center gap-1">
                {t('cp_finance_360') || 'Finance 360'} <ArrowSquareOut size={11} weight="bold" />
              </button>
            }>
              {payments ? (
                <div data-testid="cp-block-payments">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                    <KpiTile icon={CurrencyEur} label={t('cp_kpi_paid') || 'Paid'}        value={fmtMoney(payments.paidAmount, payments.currency)}        tone="good" tooltip={t('tip_cp_kpi_paid')} />
                    <KpiTile icon={CurrencyEur} label={t('cp_kpi_outstanding') || 'Outstanding'} value={fmtMoney(payments.outstandingAmount, payments.currency)} tone={payments.outstandingAmount > 0 ? 'warn' : 'good'} tooltip={t('tip_cp_kpi_outstanding')} />
                    <KpiTile icon={Clock}       label={t('cp_kpi_next_due') || 'Next due'}    value={fmtDate(payments.nextDueDate)} hint={`${t('cp_kpi_total') || 'Total'} ${fmtMoney(payments.totalAmount, payments.currency)}`} tone="neutral" tooltip={t('tip_cp_kpi_next_due')} />
                  </div>
                  {payments.history.length > 0 ? (
                    <div className="overflow-x-auto -mx-3 sm:mx-0">
                      <table className="w-full text-[12px] min-w-[520px]">
                        <thead>
                          <tr className="text-[10px] uppercase tracking-wider text-[#71717A] border-b border-[#E4E4E7]">
                            <th className="text-left font-bold py-2 px-2">{t('cp_th_invoice') || 'Invoice'}</th>
                            <th className="text-right font-bold py-2 px-2">{t('cp_th_amount') || 'Amount'}</th>
                            <th className="text-left font-bold py-2 px-2">{t('cp_th_status') || 'Status'}</th>
                            <th className="text-left font-bold py-2 px-2">{t('cp_th_issued') || 'Issued'}</th>
                            <th className="text-left font-bold py-2 px-2">{t('cp_th_due') || 'Due'}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {payments.history.map((inv) => (
                            <tr key={inv.id} className="border-b border-[#F4F4F5]">
                              <td className="py-2 px-2 font-mono text-[#18181B]">{inv.number || inv.id.slice(-8)}</td>
                              <td className="py-2 px-2 text-right tabular-nums font-semibold text-[#18181B]">{fmtMoney(inv.amount, inv.currency || payments.currency)}</td>
                              <td className="py-2 px-2">
                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${INV_TONE[inv.status] || INV_TONE.open}`}>
                                  {inv.status}
                                </span>
                              </td>
                              <td className="py-2 px-2 text-[#71717A]">{fmtDate(inv.issuedAt)}</td>
                              <td className="py-2 px-2 text-[#71717A]">{fmtDate(inv.dueDate || inv.paidAt)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState icon={Receipt}>{t('cp_no_invoices') || 'No invoices yet.'}</EmptyState>
                  )}
                </div>
              ) : (
                <EmptyState icon={CurrencyEur}>{t('cp_payments_unavailable') || 'Payment summary unavailable.'}</EmptyState>
              )}
            </Section>
          </div>

          {/* ── RIGHT (1/3): Notifications + Other Deals ── */}
          <div className="space-y-5">
            {/* BLOCK 5 — NOTIFICATIONS */}
            <Section title={t('cp_notifications') || 'Notifications'} hint={`${notifications.unread} ${t('cp_unread_of') || 'unread of'} ${notifications.total}`} action={
              <button onClick={() => navigate('/admin/notifications-center')} className="text-[11px] font-semibold text-[#18181B] hover:underline inline-flex items-center gap-1">
                {t('cp_open_center') || 'Open Center'} <ArrowSquareOut size={11} weight="bold" />
              </button>
            }>
              {notifications.items.length > 0 ? (
                <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1" data-testid="cp-block-notifications">
                  {notifications.items.map((n) => {
                    const unread = !n.readAt;
                    return (
                      <div
                        key={n.id}
                        className={`flex items-start gap-3 p-3 rounded-xl border ${unread ? 'border-indigo-200 bg-indigo-50/50' : 'border-[#E4E4E7] bg-[#FAFAFA]'}`}
                      >
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${unread ? 'bg-indigo-100 text-indigo-700' : 'bg-white border border-[#E4E4E7] text-[#71717A]'}`}>
                          {unread ? <BellRinging size={14} weight="bold" /> : <Bell size={14} weight="bold" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[12px] font-semibold text-[#18181B] break-words">{n.title}</div>
                          {n.body ? <div className="text-[11px] text-[#71717A] mt-0.5 leading-snug break-words">{n.body}</div> : null}
                          <div className="flex items-center gap-2 mt-1.5">
                            <span className="text-[10px] text-[#A1A1AA]">{relTime(n.createdAt)}</span>
                            {unread && (
                              <button onClick={() => onMarkRead(n.id)} className="text-[10px] font-semibold text-indigo-700 hover:underline inline-flex items-center gap-1">
                                <CheckSquare size={10} weight="bold" /> {t('cp_mark_read') || 'Mark read'}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <EmptyState icon={Bell}>{t('cp_no_notifications') || 'No notifications.'}</EmptyState>
              )}
            </Section>

            {/* OTHER DEALS quick list */}
            {allDeals.length > 1 && (
              <Section title={t('cp_other_orders') || 'Other orders'} hint={`${allDeals.length - 1} ${t('cp_more') || 'more'}`}>
                <div className="space-y-2">
                  {allDeals.filter((d) => d.id !== deal.id).slice(0, 8).map((d) => (
                    <button
                      key={d.id}
                      onClick={() => setSelectedDealId(d.id)}
                      className="w-full text-left flex items-center gap-3 p-2.5 rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] hover:bg-white hover:border-[#D4D4D8] transition-colors"
                    >
                      <div className="w-12 h-9 rounded-md bg-white border border-[#E4E4E7] overflow-hidden flex-shrink-0 flex items-center justify-center text-[#A1A1AA]">
                        {d.photo ? <img src={d.photo} alt={d.vehicle} className="w-full h-full object-cover" /> : <Car size={14} weight="bold" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] font-semibold text-[#18181B] truncate">{d.vehicle}</div>
                        <div className="text-[10px] text-[#71717A] truncate">{d.statusLabel}</div>
                      </div>
                      <CaretRight size={14} className="text-[#A1A1AA] flex-shrink-0" />
                    </button>
                  ))}
                </div>
              </Section>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}

