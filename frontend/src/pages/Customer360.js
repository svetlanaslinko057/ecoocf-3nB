/**
 * Customer 360 Page
 * 
 * Повна картка клієнта:
 * - Контактна інформація
 * - Агреговані метрики (leads, quotes, deals)
 * - Timeline всіх подій
 * - LTV tracking
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { useLang } from '../i18n';
import RefreshButton from '../components/ui/RefreshButton';
import ReassignDialog from '../components/ui/ReassignDialog';
import useManagersMap from '../hooks/useManagersMap';
import {
  ArrowLeft,
  User,
  Phone,
  Envelope,
  Buildings,
  MapPin,
  CurrencyCircleDollar,
  TrendUp,
  Receipt,
  Handshake,
  Coins,
  ClockCounterClockwise,
  CaretRight,
  CheckCircle,
  XCircle,
  ArrowSquareOut,
  Wallet,
  ArrowsClockwise,
  FileText,
  FilePdf,
  UploadSimple,
  Trash,
  Eye,
} from '@phosphor-icons/react';
import HealthChip from '../components/health/HealthChip';
import Overview360 from '../components/overview360/Overview360';
import CallsTab from '../components/calls/CallsTab';
import OnlineActivityBadge from '../components/widgets/OnlineActivityBadge';
import { eventLabel, minutesAgoLabel, onSitePrefix } from '../components/shared/activityLabels';
import InvoicesTab from '../components/customer360/InvoicesTab';
import OrdersTab from '../components/customer360/OrdersTab';
import PaymentsTab from '../components/customer360/PaymentsTab';
import FileManagerTab from '../components/customer360/FileManagerTab';
import RoadmapTab from '../components/customer360/RoadmapTab';
import CommentsTab from '../components/customer360/CommentsTab';
import TasksTab from '../components/customer360/TasksTab';
import TimelineTab from '../components/customer360/TimelineTab';
import ActivityTab from '../components/shared/ActivityTab';
import ChangeHistoryTab from '../components/history/ChangeHistoryTab';
// Phase Final / Block 2 & Block 3 — Sales & Meetings tabs
import SalesTab from '../components/customer360/SalesTab';
import DepositsTab from '../components/customer360/DepositsTab';
import Customer360Indicators from '../components/customer360/Customer360Indicators';
import MeetingsTab from '../components/customer360/MeetingsTab';

const Customer360 = () => {
  const { t, lang } = useLang();
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const canReassign = ['admin', 'owner', 'master_admin', 'team_lead'].includes(role);
  const { managers: managersMap, invalidate: invalidateManagers } = useManagersMap();
  const [data, setData] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(() => searchParams.get('tab') || 'overview');
  const [showReassign, setShowReassign] = useState(false);
  const [docsUnread, setDocsUnread] = useState(0);
  const [docsTotals, setDocsTotals] = useState({ total_files: 0, total_size_bytes: 0, folders_count: 0 });

  // React to ?tab=... param changes (e.g. when navigating from /admin/roadmaps)
  useEffect(() => {
    const t = searchParams.get('tab');
    if (t) setActiveTab(t);
  }, [searchParams]);

  useEffect(() => {
    fetchData();
  }, [id]);

  // ── UAT v1 read-tracker — "new files since last visit" badge ───────
  // Stamp "last visit" when the Documents tab is opened, and refresh
  // the unread-count badge whenever the user navigates AWAY from it.
  const refreshDocsUnread = async () => {
    try {
      const [unreadRes, totalsRes] = await Promise.all([
        axios.get(`${API_URL}/api/customers/${id}/files/unread-count`),
        axios.get(`${API_URL}/api/customers/${id}/files/totals`),
      ]);
      setDocsUnread(Number(unreadRes?.data?.unread || 0));
      setDocsTotals({
        total_files:      Number(totalsRes?.data?.total_files || 0),
        total_size_bytes: Number(totalsRes?.data?.total_size_bytes || 0),
        folders_count:    Number(totalsRes?.data?.folders_count || 0),
      });
    } catch {
      // ACL or network — silently zero out so the badge never shows stale data.
      setDocsUnread(0);
    }
  };

  useEffect(() => {
    if (!id) return;
    refreshDocsUnread();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!id) return;
    if (activeTab === 'documents') {
      // Fire-and-forget mark-read on tab open + zero out the badge instantly.
      // We do NOT re-fetch the unread count when leaving the Documents tab
      // to avoid a race with mark-read; the next mount / page-navigation
      // will refresh it cleanly from the server.
      axios.post(`${API_URL}/api/customers/${id}/files/mark-read`).catch(() => {});
      setDocsUnread(0);
    }
  }, [activeTab, id]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async () => {
    try {
      setLoading(true);
      const [fullRes, timelineRes] = await Promise.all([
        axios.get(`${API_URL}/api/customers/${id}/360`),
        axios.get(`${API_URL}/api/customers/${id}/timeline`),
      ]);
      setData(fullRes.data);
      setTimeline(timelineRes.data || []);
    } catch (err) {
      toast.error(t('adm_customer_data_loading_error'));
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshStats = async () => {
    try {
      await axios.patch(`${API_URL}/api/customers/${id}/refresh-stats`);
      toast.success(t('adm_statistics_updated'));
      fetchData();
    } catch (err) {
      toast.error(t('adm_statistics_update_error'));
    }
  };

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="customer-360-loading">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  const { customer, leads, quotes, deals, deposits = [], summary, health, lead_context = {} } = data;

  const statusColors = {
    active: 'bg-[#D1FAE5] text-[#059669]',
    inactive: 'bg-[#F4F4F5] text-[#71717A]',
    vip: 'bg-[#FEF3C7] text-[#D97706]',
    blacklisted: 'bg-[#FEE2E2] text-[#DC2626]',
  };

  const dealStatusColors = {
    new: 'bg-[#E0E7FF] text-[#4F46E5]',
    negotiation: 'bg-[#FEF3C7] text-[#D97706]',
    waiting_deposit: 'bg-[#FEE2E2] text-[#DC2626]',
    deposit_paid: 'bg-[#D1FAE5] text-[#059669]',
    purchased: 'bg-[#DBEAFE] text-[#2563EB]',
    in_delivery: 'bg-[#E0E7FF] text-[#7C3AED]',
    completed: 'bg-[#D1FAE5] text-[#059669]',
    cancelled: 'bg-[#F4F4F5] text-[#71717A]',
  };

  return (
    <motion.div
      data-testid="customer-360-page"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-6"
    >
      {/* Header — mobile-friendly (wraps on small screens) */}
      <div className="flex items-start sm:items-center gap-3 flex-wrap">
        <button
          onClick={() => navigate('/admin/customers')}
          className="p-2 hover:bg-[#F4F4F5] rounded-lg transition-colors shrink-0"
          data-testid="back-btn"
        >
          <ArrowLeft size={20} className="text-[#71717A]" />
        </button>
        <div className="flex-1 min-w-[160px]">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
            {customer.firstName} {customer.lastName}
          </h1>
          <p className="text-[12px] sm:text-sm text-[#71717A] mt-0.5">{t('adm_customer_360_view')}</p>
        </div>
        {/* Wave 7 — Owner badge + Change owner */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#F4F4F5] border border-[#E4E4E7]" data-testid="customer-owner-badge">
          <User size={14} className="text-[#71717A]" />
          <span className="text-xs text-[#71717A]">Owner:</span>
          {customer.managerId && managersMap[customer.managerId] ? (
            <span className="text-sm font-semibold text-[#18181B]">{managersMap[customer.managerId].name || managersMap[customer.managerId].email}</span>
          ) : (
            <span className="text-sm font-medium text-[#A1A1AA] italic">unassigned</span>
          )}
          {canReassign && (
            <button
              onClick={() => setShowReassign(true)}
              className="ml-1 p-1.5 hover:bg-white rounded-lg transition-colors"
              title="Change owner"
              data-testid="customer-change-owner-btn"
            >
              <ArrowsClockwise size={14} className="text-[#4F46E5]" />
            </button>
          )}
        </div>
        <span className={`px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full text-[11px] sm:text-sm font-medium ${statusColors[customer.status] || statusColors.active}`}>
          {customer.status || 'active'}
        </span>
        {health && (
          <HealthChip
            size="md"
            score={health.score}
            segment={health.segment}
            risks={health.risks}
            breakdown={health.breakdown}
          />
        )}
        <RefreshButton
          onClick={handleRefreshStats}
          ariaLabel={t('adm_refresh_statistics')}
          testId="refresh-stats-btn"
        />
      </div>

      {/* Contact Info + KPIs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contact Card */}
        <div className="section-card lg:col-span-1">
          <div className="section-title-clean">
            <User size={22} weight="duotone" className="text-[#4F46E5]" />
            <span>{t('adm_contact_information')}</span>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-16 h-16 bg-gradient-to-br from-[#18181B] to-[#3F3F46] rounded-2xl flex items-center justify-center text-xl font-bold text-white">
                {customer.firstName?.[0]}{customer.lastName?.[0]}
              </div>
              <div>
                <p className="font-semibold text-[#18181B]">{customer.firstName} {customer.lastName}</p>
                <p className="text-sm text-[#71717A]">{customer.company || 'Individual'}</p>
              </div>
            </div>

            {/* UAT #4 — Indicators ribbon (task / meeting / deposit / sale / contract / risks / progress) */}
            <div className="pt-3 border-t border-[#E4E4E7]">
              <Customer360Indicators customerId={id} lang={lang} />
            </div>

            {/* Доопр #19 — Site online-activity status */}
            <CustomerOnlineStrip customerId={id} />
            
            <div className="space-y-3 pt-3 border-t border-[#E4E4E7]">
              <ContactItem icon={Envelope} label={t('adm_email')} value={customer.email} />
              <ContactItem icon={Phone} label={t('adm_phone_2')} value={customer.phone || '—'} />
              <ContactItem icon={Buildings} label={t('adm_company')} value={customer.company || '—'} />
              <ContactItem icon={MapPin} label={t('adm_city')} value={customer.city || '—'} />
              <ContactItem icon={MapPin} label={t('adm_country_direction')} value={customer.country || '—'} />
            </div>

            {/* Lead context — first request + UTM (read-only, surfaced from earliest lead) */}
            {(lead_context.first_request_at || lead_context.utm_source || lead_context.utm_campaign || lead_context.utm_medium || lead_context.utm_content || lead_context.utm_term) && (
              <div className="pt-3 border-t border-[#E4E4E7]" data-testid="customer-lead-context">
                <p className="text-xs text-[#71717A] uppercase tracking-wider mb-2">{t('adm_lead_context')}</p>
                <dl className="grid grid-cols-1 gap-y-1.5 text-[12.5px]">
                  {lead_context.first_request_at && (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">{t('adm_first_request')}</dt>
                      <dd className="font-medium text-[#18181B] text-right">
                        {new Date(lead_context.first_request_at).toLocaleDateString()}
                      </dd>
                    </div>
                  )}
                  {lead_context.utm_source && (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">UTM Source</dt>
                      <dd className="font-medium text-[#18181B] text-right truncate max-w-[60%]">{lead_context.utm_source}</dd>
                    </div>
                  )}
                  {lead_context.utm_medium && (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">UTM Medium</dt>
                      <dd className="font-medium text-[#18181B] text-right truncate max-w-[60%]">{lead_context.utm_medium}</dd>
                    </div>
                  )}
                  {lead_context.utm_campaign && (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">UTM Campaign</dt>
                      <dd className="font-medium text-[#18181B] text-right truncate max-w-[60%]">{lead_context.utm_campaign}</dd>
                    </div>
                  )}
                  {lead_context.utm_content && (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">UTM Content</dt>
                      <dd className="font-medium text-[#18181B] text-right truncate max-w-[60%]">{lead_context.utm_content}</dd>
                    </div>
                  )}
                  {lead_context.utm_term && (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">UTM Term</dt>
                      <dd className="font-medium text-[#18181B] text-right truncate max-w-[60%]">{lead_context.utm_term}</dd>
                    </div>
                  )}
                </dl>
              </div>
            )}

            {/* Wishes — what the customer is looking for (budget / timeline / note) */}
            {customer.wishes && (customer.wishes.budget_min || customer.wishes.budget_max || customer.wishes.timeline_months || customer.wishes.note || customer.vehicleInterest) && (
              <div className="pt-3 border-t border-[#E4E4E7]" data-testid="customer-wishes">
                <p className="text-xs text-[#71717A] uppercase tracking-wider mb-2">{t('adm_customer_wishes')}</p>
                <dl className="grid grid-cols-1 gap-y-1.5 text-[12.5px]">
                  {(customer.wishes?.budget_min || customer.wishes?.budget_max) ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">{t('adm_budget')}</dt>
                      <dd className="font-medium text-[#18181B] text-right">
                        {(customer.wishes.budget_min || 0).toLocaleString()} — {(customer.wishes.budget_max || 0).toLocaleString()} {customer.wishes.currency || 'EUR'}
                      </dd>
                    </div>
                  ) : null}
                  {customer.wishes?.timeline_months ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">{t('adm_timeline')}</dt>
                      <dd className="font-medium text-[#18181B] text-right">{customer.wishes.timeline_months} {t('adm_months_short')}</dd>
                    </div>
                  ) : null}
                  {customer.vehicleInterest ? (
                    <div className="flex justify-between gap-3">
                      <dt className="text-[#71717A]">{t('adm_vehicle_interest')}</dt>
                      <dd className="font-medium text-[#18181B] text-right truncate max-w-[60%]">{customer.vehicleInterest}</dd>
                    </div>
                  ) : null}
                  {customer.wishes?.note ? (
                    <div className="pt-1">
                      <dt className="text-[#71717A] mb-1">{t('adm_wish_note')}</dt>
                      <dd className="text-[#18181B] leading-snug">{customer.wishes.note}</dd>
                    </div>
                  ) : null}
                </dl>
              </div>
            )}

            {customer.source && (
              <div className="pt-3 border-t border-[#E4E4E7]">
                <p className="text-xs text-[#71717A] uppercase tracking-wider">{t('adm_source')}</p>
                <p className="font-medium text-[#18181B] mt-1">{customer.source}</p>
              </div>
            )}
          </div>
        </div>

        {/* KPIs Grid */}
        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-3 gap-4">
          <KpiCard icon={Receipt} label={t('adm_leads')} value={summary.totalLeads} color="#4F46E5" />
          <KpiCard icon={Receipt} label={t('adm_quotes')} value={summary.totalQuotes} color="#7C3AED" />
          <KpiCard icon={Handshake} label={t('adm_deals')} value={summary.totalDeals} color="#D97706" />
          <KpiCard icon={CheckCircle} label={t('adm_completed')} value={summary.completedDeals} color="#059669" />
          <KpiCard icon={Wallet} label={t('adm_deposits')} value={summary.depositsCount || deposits.length} color="#2563EB" />
          <KpiCard icon={CurrencyCircleDollar} label={t('adm_revenue')} value={`$${summary.totalRevenue.toLocaleString()}`} color="#059669" />
          <KpiCard icon={Coins} label={t('adm_profit')} value={`$${summary.totalProfit.toLocaleString()}`} color="#059669" highlight />
          <KpiCard icon={Wallet} label={t('adm_deposits_sum')} value={`$${(summary.totalDepositsAmount || 0).toLocaleString()}`} color="#2563EB" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#E4E4E7] overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0" style={{ scrollbarWidth: 'none' }}>
        {['overview', 'roadmap', 'comments', 'tasks', 'legal', 'leads', 'quotes', 'deals', 'sales', 'meetings', 'invoices', 'orders', 'payments', 'deposits', 'calls', 'contracts', 'documents', 'activity', 'timeline', 'history'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 sm:px-4 py-2.5 sm:py-3 text-[12.5px] sm:text-sm font-medium whitespace-nowrap shrink-0 transition-colors ${
              activeTab === tab
                ? 'text-[#18181B] border-b-2 border-[#18181B]'
                : 'text-[#71717A] hover:text-[#18181B] border-b-2 border-transparent'
            }`}
            data-testid={`tab-${tab}`}
          >
            {tab === 'calls'
              ? (t('w2a_calls_tab_title') || 'Calls & AI')
              : tab === 'activity'
                ? (t('activity_title') || 'Activity')
                : tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === 'deposits' && deposits.length > 0 && (
              <span className="ml-1 text-[10px] sm:text-xs bg-[#E4E4E7] text-[#18181B] px-1.5 py-0.5 rounded-full">{deposits.length}</span>
            )}
            {tab === 'documents' && docsUnread > 0 && (
              <span
                className="ml-1 text-[10px] sm:text-xs font-semibold bg-[#4F46E5] text-white px-1.5 py-0.5 rounded-full"
                title={(t('fm_new_files_tooltip') || '{n} new file(s) since your last visit').replace('{n}', docsUnread)}
                data-testid="documents-tab-unread-badge"
              >
                {docsUnread}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeTab === 'overview' && (
          <>
            {/* ── Documents summary card (UAT spec — Overview block) ── */}
            <button
              onClick={() => setActiveTab('documents')}
              className="w-full flex items-center justify-between gap-3 mb-3 px-4 py-3 bg-white border border-[#E4E4E7] hover:border-[#4F46E5] hover:shadow-sm rounded-xl transition-colors text-left"
              data-testid="overview-documents-summary"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-[#EEF2FF] flex items-center justify-center shrink-0">
                  <FileText size={18} className="text-[#4F46E5]" />
                </div>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-[#18181B]">{t('fm_documents_overview_title') || 'Customer documents'}</p>
                  <p className="text-[11px] text-[#71717A] truncate">
                    {(t('fm_customer_total_files') || '{n} file(s)').replace('{n}', docsTotals.total_files)} · {t('fm_total_size')}: {(function(n){if(!n)return '0 B';const u=['B','KB','MB','GB'];let i=0;let v=Number(n);while(v>=1024&&i<u.length-1){v/=1024;i++;}return `${v.toFixed(v<10?1:0)} ${u[i]}`;})(docsTotals.total_size_bytes)} · {t('fm_folders')}: {docsTotals.folders_count}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {docsUnread > 0 && (
                  <span
                    className="text-[11px] font-semibold bg-[#4F46E5] text-white px-2 py-0.5 rounded-full"
                    title={(t('fm_new_files_tooltip') || '{n} new file(s) since your last visit').replace('{n}', docsUnread)}
                    data-testid="overview-documents-unread-badge"
                  >
                    {docsUnread} {t('fm_new_files_badge') || 'new'}
                  </span>
                )}
                <span className="text-[11px] text-[#4F46E5] font-medium">{t('fm_open_documents') || 'Open'} →</span>
              </div>
            </button>
            <Overview360
            health={health}
            lastContact={
              health?.last_contact
                ? { at: health.last_contact, channel: 'auto', manager: null, outcome: null }
                : null
            }
            nextAction={
              health?.risks?.length
                ? { text: `${health.risks[0]} — ${t('overview_next_action_followup')}`, source: 'rule' }
                : null
            }
            openTasks={[]}
            openDeals={(deals || [])
              .filter((d) => !['won', 'completed', 'cancelled', 'purchased'].includes((d.status || '').toLowerCase()))
              .map((d) => ({
                id: d.id,
                title: d.title || d.vin || 'Deal',
                stage: d.status || d.stage,
                amount: d.clientPrice || d.total_price || d.totalValue,
                currency: d.currency || 'EUR',
              }))}
            recentActivity={[
              ...((deals || []).slice(0, 3).map((d) => ({
                at: d.updated_at || d.created_at,
                type: 'deal',
                title: `${t('adm_deals')}: ${d.title || d.vin || d.id}`,
                meta: d.status,
              }))),
              ...((deposits || []).slice(0, 3).map((dep) => ({
                at: dep.created_at,
                type: 'deposit',
                title: `${t('adm_deposits')}: ${(dep.amount || 0).toLocaleString()} ${dep.currency || 'EUR'}`,
                meta: dep.status,
              }))),
            ].sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, 5)}
          />
          </>
        )}

        {activeTab === 'legal' && (
          <CustomerLegalSection customerId={id} />
        )}

        {activeTab === 'leads' && (
          <EntitySection
            title={`Leads (${leads.length})`}
            items={leads}
            emptyMessage={t('adm_no_leads')}
            renderItem={(item) => (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#18181B]">{item.firstName} {item.lastName}</p>
                  <p className="text-sm text-[#71717A]">VIN: {item.vin || '—'} | {new Date(item.createdAt).toLocaleDateString()}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${dealStatusColors[item.status] || 'bg-[#F4F4F5] text-[#71717A]'}`}>
                    {item.status}
                  </span>
                  <ArrowSquareOut size={16} className="text-[#71717A]" />
                </div>
              </div>
            )}
          />
        )}

        {activeTab === 'quotes' && (
          <EntitySection
            title={`Quotes (${quotes.length})`}
            items={quotes}
            emptyMessage={t('adm_no_miscalculations')}
            renderItem={(item) => (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-[#18181B]">{item.quoteNumber || item.vehicleTitle}</p>
                  <p className="text-sm text-[#71717A]">VIN: {item.vin} | {item.selectedScenario}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-[#18181B]">${(item.visibleTotal || 0).toLocaleString()}</p>
                  <p className="text-xs text-[#059669]">Margin: ${(item.hiddenFee || 0).toLocaleString()}</p>
                </div>
              </div>
            )}
          />
        )}

        {activeTab === 'deals' && (
          <EntitySection
            title={`Deals (${deals.length})`}
            items={deals}
            emptyMessage={t('adm_no_deals')}
            renderItem={(item) => (
              <div
                className="flex items-center justify-between cursor-pointer hover:bg-[#F4F4F5] -mx-2 px-2 py-1 rounded transition-colors"
                onClick={() => item.id && navigate(`/admin/deals/${item.id}/360`)}
                data-testid={`customer360-deal-row-${item.id}`}
              >
                <div>
                  <p className="font-medium text-[#18181B]">{item.title}</p>
                  <p className="text-sm text-[#71717A]">VIN: {item.vin || '—'} | {item.createdAt ? new Date(item.createdAt).toLocaleDateString() : ''}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="font-semibold text-[#18181B]">${(item.clientPrice || 0).toLocaleString()}</p>
                    <p className={`text-xs ${(item.realProfit || item.estimatedMargin || 0) >= 0 ? 'text-[#059669]' : 'text-[#DC2626]'}`}>
                      Profit: ${(item.realProfit || item.estimatedMargin || 0).toLocaleString()}
                    </p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${dealStatusColors[item.status] || 'bg-[#F4F4F5] text-[#71717A]'}`}>
                    {item.status}
                  </span>
                  <CaretRight size={14} className="text-[#A1A1AA]" />
                </div>
              </div>
            )}
          />
        )}

        {activeTab === 'invoices' && (
          <InvoicesTab customerId={id} />
        )}

        {/* Phase Final / Block 2 — Sales tab (sold vehicles for this customer) */}
        {activeTab === 'sales' && (
          <SalesTab customerId={id} />
        )}

        {/* Phase Final / Block 3 — Meetings tab (calendar items for this customer) */}
        {activeTab === 'meetings' && (
          <MeetingsTab customerId={id} />
        )}

        {activeTab === 'orders' && (
          <OrdersTab customerId={id} />
        )}

        {activeTab === 'roadmap' && (
          <RoadmapTab customerId={id} />
        )}

        {activeTab === 'comments' && (
          <CommentsTab customerId={id} />
        )}

        {activeTab === 'tasks' && (
          <TasksTab customerId={id} />
        )}

        {activeTab === 'payments' && (
          <PaymentsTab customerId={id} />
        )}

        {activeTab === 'deposits' && (
          <DepositsTab customerId={id} />
        )}

        {activeTab === 'contracts' && (
          <ContractsSection customerId={id} />
        )}

        {activeTab === 'calls' && (
          <CallsTab customerId={id} customerRole={role} />
        )}

        {activeTab === 'documents' && (
          <FileManagerTab customerId={id} />
        )}

        {activeTab === 'activity' && (
          <ActivityTab entityId={id} entityKind="customer" />
        )}

        {activeTab === 'timeline' && (
          <TimelineTab customerId={id} />
        )}

        {activeTab === 'history' && (
          <ChangeHistoryTab entityType="customer" entityId={id} />
        )}
      </div>
      {/* Wave 7 — Reassign owner dialog */}
      {canReassign && showReassign && (
        <ReassignDialog
          open={showReassign}
          onClose={() => setShowReassign(false)}
          entity="customer"
          ids={[id]}
          currentManagerId={customer.managerId}
          onSuccess={() => {
            invalidateManagers();
            fetchData();
          }}
        />
      )}
    </motion.div>
  );
};

// Helper Components
const ContactItem = ({ icon: Icon, label, value }) => (
  <div className="flex items-center gap-3">
    <Icon size={18} className="text-[#71717A]" />
    <div>
      <p className="text-xs text-[#71717A]">{label}</p>
      <p className="text-sm text-[#18181B]">{value}</p>
    </div>
  </div>
);

const KpiCard = ({ icon: Icon, label, value, color, highlight }) => (
  <div className={`kpi-card ${highlight ? 'border-[#059669] bg-[#F0FDF4]' : ''}`}>
    <div className="mb-3">
      <Icon size={24} weight="duotone" style={{ color }} />
    </div>
    <div className={`kpi-value ${highlight ? 'text-[#059669]' : ''}`}>{value}</div>
    <div className="kpi-label">{label}</div>
  </div>
);

const EntitySection = ({ title, items, emptyMessage, renderItem }) => (
  <div className="section-card">
    <div className="section-title-clean">
      <span>{title}</span>
    </div>
    
    <div className="space-y-3">
      {items.length === 0 ? (
        <p className="text-[#71717A] text-center py-8">{emptyMessage}</p>
      ) : (
        items.map((item, idx) => (
          <div 
            key={item._id || item.id || idx} 
            className="p-4 rounded-xl border border-[#E4E4E7] hover:border-[#4F46E5]/30 transition-colors cursor-pointer"
          >
            {renderItem(item)}
          </div>
        ))
      )}
    </div>
  </div>
);

// ───────────────── Wave-1: Contracts & Documents Sections ──────────

const LIFECYCLE_BADGE = {
  draft:     { cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',     label: 'Draft' },
  sent:      { cls: 'bg-amber-100 text-amber-700 border-amber-200',  label: 'Sent' },
  viewed:    { cls: 'bg-sky-100 text-sky-700 border-sky-200',        label: 'Viewed' },
  signed:    { cls: 'bg-emerald-100 text-emerald-700 border-emerald-200', label: 'Signed' },
  archived:  { cls: 'bg-zinc-100 text-zinc-500 border-zinc-200',     label: 'Archived' },
  cancelled: { cls: 'bg-red-100 text-red-700 border-red-200',        label: 'Cancelled' },
};
const _authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

/**
 * Open a protected PDF (or any file) in a new browser tab.
 *
 * Background: the canonical download endpoint
 *   GET /api/file-manager/files/{id}/download
 * is JWT-protected. A plain `<a href target="_blank">` opens it without
 * the Authorization header (browsers cannot inject custom headers into
 * a new-tab navigation), which yields a blank/401 page. We instead
 * fetch the bytes with the bearer token, create a blob: URL, and open
 * THAT in a new tab so the user sees the document inline.
 */
const openSecurePdf = async (url) => {
  try {
    const full = url?.startsWith('http') ? url : `${API_URL}${url}`;
    const res = await fetch(full, { headers: _authHeaders() });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const obj = window.URL.createObjectURL(blob);
    const w = window.open(obj, '_blank', 'noopener,noreferrer');
    if (!w) {
      // Popup blocked → fall back to download
      const a = document.createElement('a');
      a.href = obj;
      a.download = 'document.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
    // Revoke after a delay so the new tab has time to load the resource.
    setTimeout(() => window.URL.revokeObjectURL(obj), 60000);
  } catch (e) {
    // eslint-disable-next-line no-alert
    alert(`PDF preview failed: ${e?.message || e}`);
  }
};

const ContractsSection = ({ customerId }) => {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(null);
  const [shareUrl, setShareUrl] = useState(null);

  const load = React.useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/customers/${customerId}/contracts`, { headers: _authHeaders() });
      setItems(data.items || []);
    } catch {
      try {
        // Fallback to legacy endpoint for older bundles
        const { data } = await axios.get(`${API_URL}/api/customers/${customerId}/contracts-legacy`);
        setItems(data.items || []);
      } catch {
        // ignore
      }
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${API_URL}/api/customers/${customerId}/contracts`, { headers: _authHeaders() });
        if (!cancelled) setItems(data.items || []);
      } catch {
        try {
          const { data } = await axios.get(`${API_URL}/api/customers/${customerId}/contracts-legacy`);
          if (!cancelled) setItems(data.items || []);
        } catch { /* ignore */ }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const handleSend = async (c) => {
    if (!window.confirm(t('customerConfirmSendContract'))) return;
    setActing(c.id);
    try {
      const { data } = await axios.post(`${API_URL}/api/contract-lifecycle/${c.id}/send`, {}, { headers: _authHeaders() });
      setShareUrl(data.share_url);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || 'Send failed');
    } finally {
      setActing(null);
    }
  };

  const handleArchive = async (c) => {
    if (!window.confirm(t('customerConfirmArchiveContract'))) return;
    setActing(c.id);
    try {
      await axios.post(`${API_URL}/api/contract-lifecycle/${c.id}/archive`, {}, { headers: _authHeaders() });
      load();
    } catch (e) {
      alert(e.response?.data?.detail || 'Archive failed');
    } finally {
      setActing(null);
    }
  };

  const copyShare = (url) => {
    navigator.clipboard?.writeText(url).then(() => alert(t('customerLinkCopied')));
  };

  if (loading) return <p className="text-sm text-[#71717A]">{t('adm_loading_5')}</p>;
  if (!items.length) {
    return (
      <div className="section-card">
        <div className="section-title-clean">
          <FileText size={22} weight="duotone" className="text-[#4F46E5]" />
          <span>{t('contracts_section_title')}</span>
        </div>
        <p className="text-center py-8 text-[#71717A]">{t('contracts_empty')}</p>
      </div>
    );
  }
  return (
    <div className="section-card">
      <div className="section-title-clean">
        <FileText size={22} weight="duotone" className="text-[#4F46E5]" />
        <span>{t('contracts_section_title')} <span className="text-zinc-400 font-normal">({items.length})</span></span>
      </div>

      {shareUrl && (
        <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between gap-3" data-testid="contract-share-banner">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">{t('customerSignLink')}</p>
            <p className="text-sm font-mono text-emerald-900 truncate">{shareUrl}</p>
          </div>
          <button onClick={() => copyShare(shareUrl)} className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs hover:bg-emerald-700 shrink-0">{t('actionCopy')}</button>
          <button onClick={() => setShareUrl(null)} className="p-1 hover:bg-emerald-100 rounded text-emerald-700 shrink-0">×</button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="contracts-table">
          <thead>
            <tr className="border-b border-zinc-200 text-[11px] uppercase tracking-wider text-zinc-500">
              <th className="px-4 py-2 text-left font-medium">{t('contracts_col_number')}</th>
              <th className="px-4 py-2 text-left font-medium">Title</th>
              <th className="px-4 py-2 text-left font-medium">Version</th>
              <th className="px-4 py-2 text-left font-medium">{t('contracts_col_status')}</th>
              <th className="px-4 py-2 text-left font-medium">{t('contracts_col_signed')}</th>
              <th className="px-4 py-2 text-right font-medium">{t('contracts_col_actions')}</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => {
              const lc = (c.lifecycle || c.status || 'draft').toLowerCase();
              const badge = LIFECYCLE_BADGE[lc] || LIFECYCLE_BADGE.draft;
              const canSend = ['draft', 'sent'].includes(lc);
              const canArchive = !['archived'].includes(lc);
              return (
                <tr key={c.id} className="border-b border-zinc-50 hover:bg-zinc-50" data-testid={`contract-row-${c.id}`}>
                  <td className="px-4 py-2 font-mono text-xs text-[#71717A]">{c.id?.slice(-8)}</td>
                  <td className="px-4 py-2 font-medium text-[#18181B]">{c.title || '—'}</td>
                  <td className="px-4 py-2 text-xs text-[#71717A]">v{c.version || 1}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${badge.cls}`} data-testid={`contract-lifecycle-${c.id}`}>
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-[#71717A]">
                    {c.signed_at ? (
                      <span>{new Date(c.signed_at).toLocaleDateString()}<br/><span className="text-[10px] text-zinc-400">{c.signed_full_name}</span></span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center justify-end gap-1">
                      {c.download_url && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); openSecurePdf(c.download_url); }}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-zinc-200 hover:bg-zinc-50 text-xs"
                          title={t('openPdf') || 'Open PDF'}
                          data-testid={`contract-open-pdf-${c.id}`}
                        >
                          <FilePdf size={12} /> PDF
                        </button>
                      )}
                      {canSend && (
                        <button
                          onClick={() => handleSend(c)}
                          disabled={acting === c.id}
                          className="px-2 py-1 rounded-md bg-[#18181B] text-white text-xs hover:bg-[#27272A] disabled:opacity-50"
                          data-testid={`contract-send-${c.id}`}
                        >
                          {lc === 'sent' ? 'Resend' : 'Send'}
                        </button>
                      )}
                      {c.view_token && (
                        <button
                          onClick={() => copyShare(`${window.location.origin}/cabinet/contracts/${c.view_token}`)}
                          className="px-2 py-1 rounded-md border border-zinc-200 hover:bg-zinc-50 text-xs"
                          title="Copy share link"
                        >
                          🔗
                        </button>
                      )}
                      {canArchive && (
                        <button
                          onClick={() => handleArchive(c)}
                          disabled={acting === c.id}
                          className="px-2 py-1 rounded-md border border-zinc-200 hover:bg-zinc-50 text-xs"
                          data-testid={`contract-archive-${c.id}`}
                        >
                          Archive
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const DocumentsSection = ({ customerId }) => {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileRef = React.useRef(null);

  const load = async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/customers/${customerId}/documents`);
      setItems(data.items || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [customerId]);

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 6 * 1024 * 1024) {
      toast.error(t('documents_too_large'));
      return;
    }
    setUploading(true);
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (ev) => resolve(ev.target.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      await axios.post(`${API_URL}/api/customers/${customerId}/documents`, {
        name: file.name,
        type: 'upload',
        mime: file.type,
        data_url: dataUrl,
      });
      toast.success(t('documents_uploaded'));
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('documents_upload_failed'));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const onDelete = async (docId) => {
    try {
      await axios.delete(`${API_URL}/api/customers/${customerId}/documents/${docId}`);
      setItems((prev) => prev.filter((x) => x.id !== docId));
      toast.success(t('documents_deleted'));
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('error'));
    }
  };

  // Group by type
  const groups = items.reduce((acc, d) => {
    const key = d.type || 'other';
    (acc[key] ||= []).push(d);
    return acc;
  }, {});

  return (
    <div className="section-card">
      <div className="section-title-clean flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={22} weight="duotone" className="text-[#4F46E5]" />
          <span>{t('documents_section_title')} <span className="text-zinc-400 font-normal">({items.length})</span></span>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={onUpload}
            data-testid="documents-upload-input"
            accept="image/*,application/pdf,.doc,.docx,.xls,.xlsx"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-[#18181B] hover:bg-[#27272A] text-white rounded-lg text-sm font-medium disabled:opacity-50"
            data-testid="documents-upload-btn"
          >
            <UploadSimple size={14} />
            {uploading ? t('documents_uploading') : t('documents_upload')}
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[#71717A]">{t('adm_loading_5')}</p>
      ) : items.length === 0 ? (
        <p className="text-center py-8 text-[#71717A]">{t('documents_empty')}</p>
      ) : (
        <div className="space-y-4">
          {Object.entries(groups).map(([group, docs]) => (
            <div key={group}>
              <div className="text-[11px] uppercase tracking-wider text-[#71717A] font-semibold mb-2">
                {group} ({docs.length})
              </div>
              <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {docs.map((d) => (
                  <li
                    key={d.id}
                    className="flex items-center justify-between gap-2 p-3 rounded-xl border border-zinc-200 bg-white"
                    data-testid={`document-row-${d.id}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[#18181B] truncate">{d.name}</p>
                      <p className="text-[11px] text-[#71717A]">
                        {d.mime?.split('/')[1] || d.type} · {d.created_at && new Date(d.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {d.file_url && (
                        <a
                          href={d.file_url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1.5 hover:bg-zinc-100 rounded-md"
                          title={t('documents_open')}
                        >
                          <Eye size={14} className="text-[#4F46E5]" />
                        </a>
                      )}
                      <button
                        onClick={() => onDelete(d.id)}
                        className="p-1.5 hover:bg-red-50 rounded-md"
                        title={t('documents_delete')}
                        data-testid={`document-delete-${d.id}`}
                      >
                        <Trash size={14} className="text-[#DC2626]" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ───────────────── P0.1 Customer Legal Section ─────────────────
const CustomerLegalSection = ({ customerId }) => {
  const { t } = useLang();
  const [legal, setLegal] = useState({
    first_name: '', last_name: '', egn: '', national_id_no: '',
    id_card_address: '', id_card_issued_by: '', id_card_issue_date: '',
  });
  const [validation, setValidation] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        axios.get(`${API_URL}/api/customers/${customerId}/legal`),
        axios.get(`${API_URL}/api/customers/${customerId}/legal/validate`),
      ]);
      if (r1.data?.legal) setLegal(prev => ({ ...prev, ...r1.data.legal }));
      setValidation(r2.data);
    } catch (e) {
      // ignore — new customer
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [customerId]);

  const save = async () => {
    if (!/^\d{10}$/.test(legal.egn || '')) return toast.error(t('adm_egn_must_be_exactly_10_digits'));
    if (!/^\d{4}-\d{2}-\d{2}$/.test(legal.id_card_issue_date || ''))
      return toast.error(t('adm_issue_date_in_yyyymmdd_format'));
    setSaving(true);
    try {
      await axios.put(`${API_URL}/api/customers/${customerId}/legal`, legal);
      toast.success(t('adm_legal_fields_saved'));
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t('adm2_4d86bed39c'));
    } finally {
      setSaving(false);
    }
  };

  const F = (key, label, opts = {}) => (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-2">
        {label}<span className="text-[#DC2626]"> *</span>
      </label>
      <input
        type={opts.type || 'text'}
        value={legal[key] || ''}
        onChange={(e) => setLegal({ ...legal, [key]: e.target.value })}
        maxLength={opts.maxLength}
        placeholder={opts.placeholder}
        className="input w-full"
        data-testid={`c360-legal-${key}`}
      />
    </div>
  );

  if (loading) return <p className="text-sm text-[#71717A]">{t('adm_loading_5')}</p>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 section-card">
        <div className="section-title-clean">
          <User size={22} weight="duotone" className="text-[#4F46E5]" />
          <span>{t('adm2_c1725cceb5')}</span>
        </div>
        <div className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {F('first_name', t('adm2_1b2b542aeb'), { placeholder: t('adm_ivan') })}
            {F('last_name',  t('adm2_db93f7d0fb'), { placeholder: t('adm_ivanov') })}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {F('egn', t('adm2_10_106b2ae400'), { maxLength: 10, placeholder: '9901011234' })}
            {F('national_id_no', t('adm2_d9063bb8cb'), { placeholder: t('adm_bg1234567') })}
          </div>
          {F('id_card_address', t('adm2_ecebe5fec5'), { placeholder: t('adm_sofia_str') })}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {F('id_card_issued_by', t('adm2_82a99b398f'), { placeholder: t('adm_ministry_of_interior_sofia') })}
            {F('id_card_issue_date', t('adm2_7803e296c0'), { type: 'date' })}
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={save} disabled={saving} className="btn-primary" data-testid="c360-legal-save">
              {saving ? t('adm2_73dba4fd6c') : t('adm2_74ea58b6a8')}
            </button>
            <button onClick={load} className="btn-secondary">{t('adm_reset_2')}</button>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-title-clean">
          <CheckCircle size={22} weight="duotone" className="text-[#059669]" />
          <span>{t('adm_readiness')}</span>
        </div>
        {validation?.ready_for_deposit_contract ? (
          <div className="bg-[#D1FAE5] border border-[#059669]/30 rounded-xl p-4">
            <div className="flex items-center gap-2 text-[#059669] font-semibold">
              <CheckCircle size={22} weight="fill" /> {t('adm_all_fields_ok')}
            </div>
            <p className="text-sm text-[#047857] mt-2">
              {t('adm3_7126961db5')}
            </p>
          </div>
        ) : (
          <div className="bg-[#FEF3C7] border border-[#D97706]/30 rounded-xl p-4">
            <div className="flex items-center gap-2 text-[#D97706] font-semibold">
              <XCircle size={22} weight="fill" /> {t('adm_missing_fields')}
            </div>
            <ul className="text-sm text-[#92400E] mt-2 list-disc pl-5 space-y-1">
              {(validation?.missing_fields || []).map(f => <li key={f}>{f}</li>)}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

/* Доопр #19 — Site online-activity strip in Customer360 */
function CustomerOnlineStrip({ customerId }) {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!customerId) return;
    let cancelled = false;
    const fetcher = async () => {
      try {
        const r = await axios.get(`${API_URL}/api/v1/site-activity/${customerId}`);
        if (!cancelled) setData(r.data);
      } catch { /* silent */ }
    };
    fetcher();
    const i = setInterval(fetcher, 30000);
    return () => { cancelled = true; clearInterval(i); };
  }, [customerId]);
  if (!data?.data) return null;
  const { badge, data: row } = data;
  if (!badge || badge.status === 'offline') return null;
  return (
    <div className="pt-3 border-t border-[#E4E4E7]">
      <p className="text-xs text-[#71717A] uppercase tracking-wider mb-2">{onSitePrefix(lang)}</p>
      <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-emerald-50 border border-emerald-200">
        <OnlineActivityBadge status={badge.status} minutesAgo={badge.minutes_ago} />
        <span className="text-[12px] text-emerald-900 truncate">
          <b>{eventLabel(row.last_event, lang)}</b>
          {typeof badge.minutes_ago === 'number' ? ` · ${minutesAgoLabel(badge.minutes_ago, lang)}` : ''}
        </span>
      </div>
    </div>
  );
}

export default Customer360;
