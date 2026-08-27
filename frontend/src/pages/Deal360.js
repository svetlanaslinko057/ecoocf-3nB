/**
 * BIBI Cars — Wave 11 — Deal360
 *
 * Single pane of glass for one deal:
 *   Header   : title · VIN · customer chip · manager chip · health badge · refresh
 *   Hero     : pipeline progress bar (Wave 11 stage_progress) + KPI strip
 *   Tabs     :
 *      - Overview (light financial summary + customer/lead snippets + next action)
 *      - Finance  (DealFinancialsTab — deposits + payments + KPIs)
 *      - Delivery (DealDeliveryTab — shipments)
 *      - Contracts (DealContractsTab)
 *      - Documents (DealDocumentsTab — add/remove links)
 *      - Timeline (DealTimelineTab — Wave 6 deal_timeline events)
 *      - Notes    (DealNotesTab — read + write notes to timeline)
 *
 * Backend bundle: GET /api/deals/{id}/360
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  ArrowLeft, ArrowsClockwise, ChartLine, ClipboardText, CurrencyEur, Truck,
  FileText, File as FileIcon, Clock, NotePencil, UserCircle, Phone, EnvelopeSimple,
  Car as CarIcon,
} from '@phosphor-icons/react';

import { API_URL, useAuth } from '../App';

import DealHealthBadge from '../components/deal360/DealHealthBadge';
import FinancialHealthBadge from '../components/deal360/FinancialHealthBadge';
import DeliveryHealthBadge from '../components/delivery360/DeliveryHealthBadge';
import DealStagePipeline from '../components/deal360/DealStagePipeline';
import DealPipelineActions from '../components/deal360/DealPipelineActions';
import DealBlockersList from '../components/deal360/DealBlockersList';
import DealFinancialsTab from '../components/deal360/DealFinancialsTab';
import DealDeliveryTab from '../components/deal360/DealDeliveryTab';
import DealContractsTab from '../components/deal360/DealContractsTab';
import DealDocumentsTab from '../components/deal360/DealDocumentsTab';
import DealTimelineTab from '../components/deal360/DealTimelineTab';
import DealNotesTab from '../components/deal360/DealNotesTab';

const TABS = [
  { key: 'overview',  label: 'Overview',  icon: ChartLine },
  { key: 'finance',   label: 'Finance',   icon: CurrencyEur },
  { key: 'delivery',  label: 'Delivery',  icon: Truck },
  { key: 'contracts', label: 'Contracts', icon: FileText },
  { key: 'documents', label: 'Documents', icon: FileIcon },
  { key: 'timeline',  label: 'Timeline',  icon: Clock },
  { key: 'notes',     label: 'Notes',     icon: NotePencil },
];

const fmt = (n, ccy = 'EUR') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};

const formatWhen = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return String(iso); }
};

const Chip = ({ icon: Icon, label, value, onClick, testId }) => {
  const body = (
    <span className="inline-flex items-center gap-1.5 text-[12px] text-[#18181B]">
      {Icon ? <Icon size={14} className="text-[#71717A]" /> : null}
      {label ? <span className="text-[#71717A]">{label}:</span> : null}
      <span className="font-semibold truncate max-w-[200px]">{value || '—'}</span>
    </span>
  );
  return onClick ? (
    <button onClick={onClick} className="hover:underline" data-testid={testId}>{body}</button>
  ) : (
    <span data-testid={testId}>{body}</span>
  );
};

const Deal360 = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/deals/${id}/360`);
      setData(r.data);
    } catch (err) {
      const code = err.response?.status;
      if (code === 404) toast.error('Deal not found');
      else if (code === 403) toast.error('You cannot view this deal');
      else toast.error(err.response?.data?.detail || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-32" data-testid="deal360-loading">
        <div className="w-8 h-8 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!data?.deal) {
    return (
      <div className="text-center py-32 text-[#71717A]" data-testid="deal360-empty">
        <div className="text-lg font-semibold">Deal not found</div>
        <Link to="/admin/legal?tab=deal_pipeline" className="inline-block mt-3 text-[#4F46E5] underline">
          Back to Deal Pipeline
        </Link>
      </div>
    );
  }

  const {
    deal, customer, lead, manager, health, financial_health, delivery_health, stage_progress, financials,
    deposits = [], contracts = [], payments = [], shipments = [],
    documents = [], timeline = [], counts = {},
    available_transitions = [], blockers = [],
  } = data;

  const dealTitle = deal.title || deal.name || `Deal ${deal.id?.slice(-8) || ''}`;
  const ccy = financials?.currency || deal.currency || 'EUR';

  return (
    <motion.div
      data-testid="deal360-page"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      {/* Back + actions row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#52525B] hover:text-[#18181B]"
          data-testid="deal360-back"
        >
          <ArrowLeft size={14} weight="bold" /> Back
        </button>
        <button
          onClick={fetchData}
          className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#52525B] hover:text-[#18181B]"
          data-testid="deal360-refresh"
        >
          <ArrowsClockwise size={14} weight="bold" /> Refresh
        </button>
      </div>

      {/* Header card */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3 min-w-0">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#18181B] to-[#3F3F46] text-white flex items-center justify-center shrink-0">
              <CarIcon size={24} weight="bold" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-bold text-[#18181B] truncate" data-testid="deal360-title">{dealTitle}</h1>
                {health ? <DealHealthBadge health={health} size="md" /> : null}
                {financial_health ? <FinancialHealthBadge health={financial_health} size="md" /> : null}
                {delivery_health ? <DeliveryHealthBadge health={delivery_health} size="md" /> : null}
              </div>
              <div className="mt-1 flex items-center gap-3 flex-wrap text-[12px]">
                <span className="text-[#71717A]">ID: <span className="font-mono">{deal.id?.slice(-12) || '—'}</span></span>
                {deal.vin ? <Chip label="VIN" value={deal.vin} testId="deal360-vin" /> : null}
                {customer ? (
                  <Chip
                    icon={UserCircle}
                    value={customer.name || `${customer.first_name || ''} ${customer.last_name || ''}`.trim() || customer.email}
                    onClick={() => navigate(`/admin/customers/${customer.id}/360`)}
                    testId="deal360-customer-chip"
                  />
                ) : null}
                {lead ? (
                  <Chip
                    icon={ClipboardText}
                    label="Lead"
                    value={lead.name || lead.email || lead.id}
                    onClick={() => navigate(`/admin/leads/${lead.id}`)}
                    testId="deal360-lead-chip"
                  />
                ) : null}
                {manager ? (
                  <Chip
                    icon={UserCircle}
                    label="Manager"
                    value={manager.name || manager.email}
                    testId="deal360-manager-chip"
                  />
                ) : null}
              </div>
            </div>
          </div>
        </div>

        {/* Pipeline progress + actions */}
        <div className="mt-4 space-y-3">
          {stage_progress ? <DealStagePipeline progress={stage_progress} /> : null}
          <DealPipelineActions
            deal={deal}
            availableTransitions={available_transitions}
            onChange={fetchData}
          />
        </div>
      </div>

      {/* Blockers (Wave 11.1) */}
      <DealBlockersList dealId={deal.id} blockers={blockers} onChange={fetchData} />

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal360-kpi-revenue">
          <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Revenue</div>
          <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{fmt(financials?.revenue, ccy)}</div>
          <div className="text-[11px] text-[#71717A] mt-0.5">{financials?.margin_pct || 0}% margin</div>
        </div>
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal360-kpi-profit">
          <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Profit</div>
          <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{fmt(financials?.profit, ccy)}</div>
          <div className="text-[11px] text-[#71717A] mt-0.5">Cost {fmt(financials?.cost, ccy)}</div>
        </div>
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal360-kpi-deposit">
          <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Deposits</div>
          <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{fmt(financials?.deposit_received, ccy)}</div>
          <div className="text-[11px] text-[#71717A] mt-0.5">{counts.deposits || 0} record(s)</div>
        </div>
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal360-kpi-balance">
          <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Balance due</div>
          <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{fmt(financials?.balance_due, ccy)}</div>
          <div className="text-[11px] text-[#71717A] mt-0.5">{counts.payments || 0} payment(s)</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl">
        <div className="flex items-center gap-1 px-2 overflow-x-auto border-b border-[#E4E4E7]">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`inline-flex items-center gap-1.5 px-3 py-2 text-[12px] font-semibold border-b-2 transition-colors ${active ? 'border-[#18181B] text-[#18181B]' : 'border-transparent text-[#71717A] hover:text-[#18181B]'}`}
                data-testid={`deal360-tab-${t.key}`}
              >
                <Icon size={14} weight="bold" /> {t.label}
              </button>
            );
          })}
        </div>

        <div className="p-4">
          {tab === 'overview' ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2 space-y-3">
                <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Deal description</div>
                  <div className="text-sm text-[#18181B] whitespace-pre-wrap">
                    {deal.description || deal.notes || 'No description provided.'}
                  </div>
                </div>
                <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Vehicle</div>
                  <div className="grid grid-cols-2 gap-2 text-sm text-[#18181B]">
                    <div><span className="text-[#71717A]">VIN:</span> <span className="font-mono">{deal.vin || '—'}</span></div>
                    <div><span className="text-[#71717A]">Lot:</span> {deal.lot || '—'}</div>
                    <div><span className="text-[#71717A]">Year:</span> {deal.year || '—'}</div>
                    <div><span className="text-[#71717A]">Make/Model:</span> {[deal.make, deal.model].filter(Boolean).join(' ') || deal.vehiclePlaceholder || '—'}</div>
                  </div>
                </div>
              </div>

              <aside className="space-y-3">
                <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Customer</div>
                  {customer ? (
                    <div className="space-y-1 text-sm">
                      <div className="font-semibold text-[#18181B]">{customer.name || [customer.first_name, customer.last_name].filter(Boolean).join(' ')}</div>
                      {customer.email ? <div className="text-[#71717A] flex items-center gap-1"><EnvelopeSimple size={12} />{customer.email}</div> : null}
                      {customer.phone ? <div className="text-[#71717A] flex items-center gap-1"><Phone size={12} />{customer.phone}</div> : null}
                      <button
                        onClick={() => navigate(`/admin/customers/${customer.id}/360`)}
                        className="mt-1 inline-flex items-center text-[12px] text-[#4F46E5] font-semibold hover:underline"
                      >
                        Open Customer 360 →
                      </button>
                    </div>
                  ) : (
                    <div className="text-sm text-[#71717A]">No customer linked</div>
                  )}
                </div>

                <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Activity</div>
                  <div className="text-sm text-[#18181B]">
                    <div className="flex justify-between py-0.5"><span className="text-[#71717A]">Created</span><span>{formatWhen(deal.created_at)}</span></div>
                    <div className="flex justify-between py-0.5"><span className="text-[#71717A]">Updated</span><span>{formatWhen(deal.updated_at)}</span></div>
                    <div className="flex justify-between py-0.5"><span className="text-[#71717A]">Events</span><span>{counts.timeline || 0}</span></div>
                    <div className="flex justify-between py-0.5"><span className="text-[#71717A]">Documents</span><span>{counts.documents || 0}</span></div>
                    <div className="flex justify-between py-0.5"><span className="text-[#71717A]">Shipments</span><span>{counts.shipments || 0}</span></div>
                  </div>
                </div>
              </aside>
            </div>
          ) : null}

          {tab === 'finance'   ? <DealFinancialsTab dealId={deal.id} financials={financials} deposits={deposits} payments={payments} onChange={fetchData} /> : null}
          {tab === 'delivery'  ? <DealDeliveryTab dealId={deal.id} shipments={shipments} onChanged={fetchData} /> : null}
          {tab === 'contracts' ? <DealContractsTab contracts={contracts} /> : null}
          {tab === 'documents' ? <DealDocumentsTab dealId={deal.id} documents={documents} onChange={fetchData} /> : null}
          {tab === 'timeline'  ? <DealTimelineTab timeline={timeline} /> : null}
          {tab === 'notes'     ? <DealNotesTab dealId={deal.id} timeline={timeline} onChange={fetchData} /> : null}
        </div>
      </div>
    </motion.div>
  );
};

export default Deal360;
