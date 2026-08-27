/**
 * BIBI Cars — Wave 9 — Lead360
 *
 * Полный рабочий экран для одного лида. Не модалка.
 *
 * Header: Имя · Телефон · Источник · Менеджер · Health · Last contact
 * Tabs:   Overview / Calls / Timeline / Notes / Cars
 * Side:   Next Action card (always visible)
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  ArrowLeft, Phone, EnvelopeSimple, Tag, UserCircle,
  ArrowsClockwise, Pencil, UserPlus, Trash, ChartLine, ListChecks,
  Clock, NotePencil, Car, Receipt, ClockCounterClockwise, Pulse,
} from '@phosphor-icons/react';

import { API_URL, useAuth } from '../App';
import { useLang } from '../i18n';
import RefreshButton from '../components/ui/RefreshButton';
import ReassignDialog from '../components/ui/ReassignDialog';
import CallsTab from '../components/calls/CallsTab';

import LeadHealthBadge from '../components/lead360/LeadHealthBadge';
import LeadNextActionCard from '../components/lead360/LeadNextActionCard';
import LeadTimelinePanel from '../components/lead360/LeadTimelinePanel';
import OnlineActivityBadge from '../components/widgets/OnlineActivityBadge';
import LeadNotesPanel from '../components/lead360/LeadNotesPanel';
import LeadRelatedCars from '../components/lead360/LeadRelatedCars';
import ActivityTab from '../components/shared/ActivityTab';
import LeadPriorityBadge from '../components/leads/LeadPriorityBadge';
import LeadSiteTemperatureBadge from '../components/leads/LeadSiteTemperatureBadge';
import { eventLabel, minutesAgoLabel } from '../components/shared/activityLabels';

import LeadCreateModal from '../components/leads/LeadCreateModal';
import LeadSlaBadge from '../components/leads/LeadSlaBadge';
import ChangeHistoryTab from '../components/history/ChangeHistoryTab';
import { STATUS_THEME, statusLabel, sourceLabel, LEAD_PIPELINE } from '../components/leads/leadConstants';
import { Select, SelectContent, SelectItem, SelectTrigger } from '../components/ui/select';
import { detectCountry, isValidForCountry } from '../components/ui/PhoneInput';

const formatWhen = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return String(iso); }
};

const TABS = [
  { key: 'overview', label: 'Overview', icon: ChartLine },
  { key: 'calls',    label: 'Calls',    icon: Phone },
  { key: 'activity', label: 'Activity', icon: Pulse },
  { key: 'timeline', label: 'Timeline', icon: Clock },
  { key: 'notes',    label: 'Notes',    icon: NotePencil },
  { key: 'cars',     label: 'Cars',     icon: Car },
  { key: 'history',  label: 'History',  icon: ClockCounterClockwise },
];

const KpiTile = ({ label, value, hint, testId }) => (
  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-3" data-testid={testId}>
    <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">{label}</div>
    <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{value}</div>
    {hint ? <div className="text-[11px] text-[#A1A1AA] mt-0.5">{hint}</div> : null}
  </div>
);

const Lead360 = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { lang, t } = useLang();
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const canReassign = ['admin', 'owner', 'master_admin', 'team_lead'].includes(role);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Initial tab is taken from ?tab= so deep-links such as
  // /admin/leads/{id}?tab=activity open the right pane immediately.
  const [tab, setTabState] = useState(() => searchParams.get('tab') || 'overview');

  // Keep URL ↔ state in sync (back/forward button friendly).
  useEffect(() => {
    const next = searchParams.get('tab') || 'overview';
    if (next !== tab) setTabState(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const setTab = (nextTab) => {
    setTabState(nextTab);
    const sp = new URLSearchParams(searchParams);
    if (nextTab === 'overview') {
      sp.delete('tab');
    } else {
      sp.set('tab', nextTab);
    }
    setSearchParams(sp, { replace: false });
  };

  const [showReassign, setShowReassign] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [formData, setFormData] = useState({});
  const [formErrors, setFormErrors] = useState({});

  // Site-activity temperature for the header badge (presentation-only; reuses
  // the existing status endpoint — no new API). Hidden when there is no data.
  const [siteLastSeen, setSiteLastSeen] = useState(null);
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    axios.get(`${API_URL}/api/v1/site-activity/${id}`)
      .then((r) => { if (!cancelled) setSiteLastSeen(r.data?.data?.last_seen_at || null); })
      .catch(() => { /* silent — no activity yet */ });
    return () => { cancelled = true; };
  }, [id]);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/leads/${id}/360`);
      setData(r.data);
    } catch (err) {
      const code = err.response?.status;
      if (code === 404) toast.error('Lead not found');
      else if (code === 403) toast.error('You cannot view this lead');
      else toast.error(err.response?.data?.detail || 'Failed');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Mutations ──
  const handleChangeStatus = async (newStatus) => {
    try {
      await axios.patch(`${API_URL}/api/leads/${id}/status`, { status: newStatus, reason: 'lead360_change' });
      toast.success(`→ ${statusLabel(lang, newStatus)}`);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const handleConvert = async () => {
    if (data?.lead?.customerId) return;
    if (!window.confirm('Convert this lead to a customer?')) return;
    try {
      const r = await axios.post(`${API_URL}/api/leads/${id}/convert`);
      toast.success('Converted');
      const cid = r?.data?.customer?.id;
      if (cid) setTimeout(() => navigate(`/admin/customers/${cid}/360`), 600);
      else fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const handleDelete = async () => {
    if (!window.confirm('Delete this lead permanently?')) return;
    try {
      await axios.delete(`${API_URL}/api/leads/${id}`);
      toast.success('Deleted');
      navigate('/admin/leads');
    } catch (e) { toast.error('Failed'); }
  };

  const openEdit = () => {
    const lead = data?.lead || {};
    const detected = detectCountry(lead.phone);
    setFormData({
      firstName: lead.firstName || '',
      lastName:  lead.lastName  || '',
      email:     lead.email     || '',
      phone:     lead.phone     || '',
      phoneCountry: lead.phoneCountry || (detected && detected.code) || 'BG',
      vehicleInterest: lead.vehicleInterest || '',
      source:    lead.source || 'website',
      description: lead.description || lead.notes || '',
      budgetEur: lead.budgetEur || lead.budgetUsd || '',
    });
    setFormErrors({});
    setShowEdit(true);
  };

  const submitEdit = async (e) => {
    e.preventDefault();
    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const errs = {};
    if (!(formData.firstName || '').trim()) errs.firstName = 'Required';
    if (!(formData.lastName  || '').trim()) errs.lastName  = 'Required';
    if (!(formData.email     || '').trim()) errs.email     = 'Required';
    else if (!EMAIL_RE.test(formData.email.trim())) errs.email = 'Invalid email';
    if (formData.phone && !isValidForCountry(formData.phone, formData.phoneCountry)) errs.phone = 'Invalid phone';
    setFormErrors(errs);
    if (Object.keys(errs).length) { toast.error(t('leadValidateError')); return; }
    try {
      await axios.put(`${API_URL}/api/leads/${id}`, {
        firstName: formData.firstName.trim(),
        lastName:  formData.lastName.trim(),
        email:     formData.email.trim(),
        phone:     formData.phone || null,
        phoneCountry: formData.phoneCountry || null,
        vehicleInterest: formData.vehicleInterest || null,
        source:    formData.source,
        description: formData.description || null,
        budgetEur: Number(formData.budgetEur) || 0,
      });
      toast.success('Saved');
      setShowEdit(false);
      fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
  };

  // ── Render ──
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-32" data-testid="lead360-loading">
        <div className="w-8 h-8 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }
  if (!data?.lead) {
    return (
      <div className="text-center py-32 text-[#71717A]" data-testid="lead360-empty">
        <div className="text-lg font-semibold">Lead not found</div>
        <Link to="/admin/leads" className="inline-block mt-3 text-[#4F46E5] underline">Back to Workspace</Link>
      </div>
    );
  }

  const { lead, health, priority, manager, open_tasks, recent_calls, timeline, related_cars, counts } = data;
  const theme = STATUS_THEME[lead.status] || STATUS_THEME.new;

  return (
    <motion.div
      data-testid="lead360-page"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* Доопр #19 — site online-activity badge */}
      <LeadOnlineBadgeStrip leadId={id} />
      {/* Back + actions row — mobile-friendly (wraps on small screens) */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <button
          onClick={() => navigate('/admin/leads')}
          className="inline-flex items-center gap-1.5 text-[13px] text-[#52525B] hover:text-[#18181B]"
          data-testid="lead360-back"
        >
          <ArrowLeft size={14} weight="bold" /> Workspace
        </button>
        <div className="flex flex-wrap items-center gap-2">
          <RefreshButton onClick={fetchData} loading={loading} ariaLabel="Refresh" testId="lead360-refresh" />
          <button onClick={openEdit} className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] bg-white border border-[#E4E4E7] hover:bg-[#FAFAFA] rounded-xl" data-testid="lead360-edit">
            <Pencil size={13} /> Edit
          </button>
          {canReassign ? (
            <button onClick={() => setShowReassign(true)} className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] bg-white border border-[#E4E4E7] hover:bg-[#FAFAFA] rounded-xl" data-testid="lead360-reassign">
              <ArrowsClockwise size={13} /> Reassign
            </button>
          ) : null}
          {!lead.customerId ? (
            <button onClick={handleConvert} className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] bg-[#16A34A] hover:bg-[#15803D] text-white rounded-xl font-semibold" data-testid="lead360-convert">
              <UserPlus size={13} weight="bold" /> Convert
            </button>
          ) : (
            <Link to={`/admin/customers/${lead.customerId}/360`} className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] bg-[#16A34A] hover:bg-[#15803D] text-white rounded-xl font-semibold" data-testid="lead360-open-customer">
              <UserCircle size={13} weight="bold" /> Open customer
            </Link>
          )}
          <button onClick={handleDelete} className="p-2 hover:bg-[#FEE2E2] text-[#DC2626] rounded-xl" data-testid="lead360-delete">
            <Trash size={14} />
          </button>
        </div>
      </div>

      {/* Hero header */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 mb-4" style={{ borderTopColor: theme.hex, borderTopWidth: 3 }} data-testid="lead360-hero">
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white flex items-center justify-center font-bold text-lg shrink-0">
            {((lead.firstName || lead.name || '?').slice(0, 1)).toUpperCase()}
            {((lead.lastName || ' ').slice(0, 1)).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h1 className="text-xl sm:text-2xl font-bold text-[#18181B] leading-tight truncate" data-testid="lead360-name">
                {lead.firstName} {lead.lastName}
                {!lead.firstName && !lead.lastName ? (lead.name || '—') : null}
              </h1>
              <LeadHealthBadge health={health} size="md" testId="lead360-health-badge" />
              {priority ? <LeadPriorityBadge priority={priority} size="md" testId="lead360-priority-badge" /> : null}
              <LeadSlaBadge lead={lead} />
              <LeadSiteTemperatureBadge lastSeen={siteLastSeen} size="sm" showLabel />
              <Select value={lead.status} onValueChange={handleChangeStatus}>
                <SelectTrigger className="h-7 w-auto bg-transparent border-0 p-0" data-testid="lead360-status-select">
                  <span
                    className="text-[11px] font-bold uppercase tracking-wider px-2 py-1 rounded-md inline-flex items-center gap-1"
                    style={{ backgroundColor: theme.soft, color: theme.text }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: theme.dot }}></span>
                    {statusLabel(lang, lead.status)}
                  </span>
                </SelectTrigger>
                <SelectContent>
                  {LEAD_PIPELINE.map(s => (
                    <SelectItem key={s} value={s}>{statusLabel(lang, s)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-[12px]">
              <div>
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#A1A1AA]">Phone</div>
                {lead.phone ? (
                  <a href={`tel:${String(lead.phone).replace(/\s+/g,'')}`} className="text-[#18181B] hover:text-[#4F46E5] font-semibold tabular-nums inline-flex items-center gap-1" data-testid="lead360-phone">
                    <Phone size={11} /> {lead.phone}
                  </a>
                ) : <span className="text-[#A1A1AA]">—</span>}
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#A1A1AA]">Email</div>
                {lead.email ? (
                  <a href={`mailto:${lead.email}`} className="text-[#18181B] hover:text-[#4F46E5] font-medium truncate inline-flex items-center gap-1" data-testid="lead360-email">
                    <EnvelopeSimple size={11} /> <span className="truncate">{lead.email}</span>
                  </a>
                ) : <span className="text-[#A1A1AA]">—</span>}
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#A1A1AA]">Source</div>
                <span className="text-[#18181B] inline-flex items-center gap-1"><Tag size={11} /> {sourceLabel(lang, lead.source)}</span>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#A1A1AA]">Manager</div>
                {manager ? (
                  <span className="text-[#18181B] inline-flex items-center gap-1 truncate" data-testid="lead360-manager">
                    <UserCircle size={11} /> <span className="truncate">{manager.name || manager.email}</span>
                  </span>
                ) : <span className="text-[#A1A1AA] italic">unassigned</span>}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[#A1A1AA] mt-3">
              <span data-testid="lead360-created-at">Created: {formatWhen(lead.created_at)}</span>
              <span>·</span>
              <span data-testid="lead360-last-contact-at">
                Last contact: {formatWhen(lead.lastContactAt || health?.last_contact)}
              </span>
              <span>·</span>
              <span data-testid="lead360-status-changed-at">
                Status changed: {formatWhen(lead.statusChangedAt)}
              </span>
              {(lead.budgetEur || lead.budgetUsd) ? (<><span>·</span><span className="text-[#15803D] font-semibold">€{Number(lead.budgetEur || lead.budgetUsd).toLocaleString()}</span></>) : null}
            </div>
          </div>
        </div>
      </div>

      {/* Main layout: left content + right sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          {/* Tabs */}
          <div className="flex items-center gap-1 mb-3 border-b border-[#E4E4E7] overflow-x-auto" data-testid="lead360-tabs">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`inline-flex items-center gap-1.5 px-3 py-2 text-[13px] border-b-2 transition-colors whitespace-nowrap ${tab === key ? 'border-[#18181B] text-[#18181B] font-semibold' : 'border-transparent text-[#71717A] hover:text-[#18181B]'}`}
                data-testid={`lead360-tab-${key}`}
              >
                <Icon size={14} />
                {label}
                {key === 'calls'    && counts?.recent_calls ? <span className="text-[10px] bg-[#F4F4F5] text-[#52525B] px-1.5 py-0.5 rounded-full">{counts.recent_calls}</span> : null}
                {key === 'timeline' && counts?.timeline     ? <span className="text-[10px] bg-[#F4F4F5] text-[#52525B] px-1.5 py-0.5 rounded-full">{counts.timeline}</span> : null}
                {key === 'notes'    && counts?.notes        ? <span className="text-[10px] bg-[#F4F4F5] text-[#52525B] px-1.5 py-0.5 rounded-full">{counts.notes}</span> : null}
                {key === 'cars'     && counts?.related_cars ? <span className="text-[10px] bg-[#F4F4F5] text-[#52525B] px-1.5 py-0.5 rounded-full">{counts.related_cars}</span> : null}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div data-testid={`lead360-tabpanel-${tab}`}>
            {tab === 'overview' ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <KpiTile label="Health" value={health?.score ?? '—'} hint={health?.status} testId="lead360-kpi-health" />
                  <KpiTile label="Open tasks" value={counts?.open_tasks ?? 0} hint={`${health?.overdue_tasks || 0} overdue`} testId="lead360-kpi-tasks" />
                  <KpiTile label="Calls" value={counts?.recent_calls ?? 0} hint="recent" testId="lead360-kpi-calls" />
                  <KpiTile label="Cars" value={counts?.related_cars ?? 0} hint="linked VINs" testId="lead360-kpi-cars" />
                </div>

                {/* Tasks list */}
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="lead360-tasks-panel">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[12px] uppercase tracking-wider font-bold text-[#52525B] inline-flex items-center gap-1.5">
                      <ListChecks size={13} /> Open tasks
                    </div>
                    <span className="text-[10px] text-[#A1A1AA]">{(open_tasks || []).length}</span>
                  </div>
                  {(open_tasks || []).length === 0 ? (
                    <div className="text-[12px] text-[#A1A1AA] italic py-4 text-center">No open tasks. {' '}
                      {health?.next_action?.title ? <span className="font-semibold text-[#52525B]">Suggested: {health.next_action.title}</span> : null}
                    </div>
                  ) : (
                    <ul className="space-y-2">
                      {open_tasks.map(t => (
                        <li key={t.id} className="flex items-center justify-between gap-2 bg-[#FAFAFA] rounded-lg px-3 py-2" data-testid={`lead360-task-${t.id}`}>
                          <div className="min-w-0 flex-1">
                            <div className="text-[13px] font-semibold text-[#18181B] truncate">{t.title || t.description || 'Task'}</div>
                            <div className="text-[11px] text-[#71717A]">Due {formatWhen(t.due_at || t.dueDate)}</div>
                          </div>
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider"
                            style={{ background: (t.priority === 'high') ? '#FEE2E2' : '#F4F4F5', color: (t.priority === 'high') ? '#B91C1C' : '#52525B' }}>
                            {t.priority || 'normal'}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Recent calls preview */}
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="lead360-recent-calls">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-[12px] uppercase tracking-wider font-bold text-[#52525B] inline-flex items-center gap-1.5">
                      <Phone size={13} /> Recent calls
                    </div>
                    {counts?.recent_calls ? (
                      <button onClick={() => setTab('calls')} className="text-[11px] text-[#4F46E5] hover:underline">View all</button>
                    ) : null}
                  </div>
                  {(recent_calls || []).length === 0 ? (
                    <div className="text-[12px] text-[#A1A1AA] italic py-4 text-center">No calls yet</div>
                  ) : (
                    <ul className="space-y-1.5">
                      {(recent_calls || []).slice(0, 5).map((c, i) => (
                        <li key={i} className="flex items-center justify-between gap-2 text-[12px] py-1.5 border-b border-[#F4F4F5] last:border-b-0">
                          <span className="inline-flex items-center gap-1.5">
                            <Phone size={10} className={c.direction === 'outbound' ? 'text-[#10B981]' : 'text-[#06B6D4]'} />
                            <span className="capitalize">{c.direction || 'call'}</span>
                            <span className="text-[#71717A]">· {c.duration || 0}s</span>
                          </span>
                          <span className="text-[10px] text-[#A1A1AA]">{formatWhen(c.created_at || c.start_time)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Timeline preview */}
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="lead360-timeline-preview">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-[12px] uppercase tracking-wider font-bold text-[#52525B] inline-flex items-center gap-1.5">
                      <Clock size={13} /> Recent activity
                    </div>
                    <button onClick={() => setTab('timeline')} className="text-[11px] text-[#4F46E5] hover:underline">View all</button>
                  </div>
                  <LeadTimelinePanel items={(timeline || []).slice(0, 6)} />
                </div>
              </div>
            ) : null}

            {tab === 'calls' ? (
              lead.phone || lead.customerId ? (
                <CallsTab customerId={lead.customerId} customerPhone={lead.phone} leadId={lead.id} />
              ) : (
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-8 text-center text-[#A1A1AA] italic text-[13px]">
                  No phone number set — add one to enable call history
                </div>
              )
            ) : null}

            {tab === 'activity' ? (
              <ActivityTab entityId={id} entityKind="lead" />
            ) : null}

            {tab === 'timeline' ? (
              <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                <LeadTimelinePanel items={timeline} />
              </div>
            ) : null}

            {tab === 'notes' ? (
              <LeadNotesPanel leadId={id} onAfterChange={fetchData} />
            ) : null}

            {tab === 'cars' ? (
              <LeadRelatedCars items={related_cars} />
            ) : null}

            {tab === 'history' ? (
              <ChangeHistoryTab entityType="lead" entityId={id} />
            ) : null}
          </div>
        </div>

        {/* Right sidebar — Next Action + sticky context */}
        <div className="space-y-3">
          <LeadNextActionCard
            health={health}
            lead={lead}
            onCall={(ph) => { window.location.href = `tel:${ph}`; }}
          />

          {/* Quick info card */}
          <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
            <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Vehicle interest</div>
            {lead.vehicleInterest || lead.vin ? (
              <div>
                <div className="text-[13px] font-semibold text-[#18181B] inline-flex items-center gap-1.5">
                  <Car size={13} /> {lead.vehicleInterest || lead.vin}
                </div>
                {lead.vin ? <div className="text-[10px] font-mono text-[#71717A] mt-1">VIN: {lead.vin}</div> : null}
              </div>
            ) : (
              <div className="text-[12px] text-[#A1A1AA] italic">Not specified</div>
            )}
            {(lead.budgetEur || lead.budgetUsd) ? (
              <div className="mt-3 pt-3 border-t border-[#F4F4F5]">
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Budget</div>
                <div className="text-lg font-bold text-[#15803D] tabular-nums mt-0.5">€{Number(lead.budgetEur || lead.budgetUsd).toLocaleString()}</div>
              </div>
            ) : null}
          </div>

          {lead.description ? (
            <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
              <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Description</div>
              <div className="text-[13px] text-[#18181B] whitespace-pre-wrap break-words">{lead.description}</div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Edit modal — reuses LeadCreateModal */}
      <LeadCreateModal
        open={showEdit}
        onOpenChange={(open) => { setShowEdit(open); }}
        formData={formData}
        setFormData={setFormData}
        formErrors={formErrors}
        editingLead={lead}
        onSubmit={submitEdit}
        lang={lang}
      />

      {/* Reassign */}
      {showReassign ? (
        <ReassignDialog
          open={showReassign}
          onClose={() => setShowReassign(false)}
          entity="lead"
          ids={[id]}
          currentManagerId={lead.managerId}
          onSuccess={() => { setShowReassign(false); fetchData(); }}
        />
      ) : null}
    </motion.div>
  );
};

/* Доопр #19 — Site online-activity strip in Lead360 */
function LeadOnlineBadgeStrip({ leadId }) {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!leadId) return;
    let cancelled = false;
    const fetcher = async () => {
      try {
        const r = await axios.get(`${API_URL}/api/v1/site-activity/${leadId}`);
        if (!cancelled) setData(r.data);
      } catch { /* silent */ }
    };
    fetcher();
    const i = setInterval(fetcher, 30000);
    return () => { cancelled = true; clearInterval(i); };
  }, [leadId]);
  if (!data?.data) return null;
  const { badge, data: row } = data;
  if (!badge || badge.status === 'offline') return null;
  return (
    <div className="mb-3 flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 border border-emerald-200">
      <OnlineActivityBadge status={badge.status} minutesAgo={badge.minutes_ago} />
      <span className="text-[12px] text-emerald-900">
        <b>{eventLabel(row.last_event, lang)}</b>
        {typeof badge.minutes_ago === 'number' ? ` · ${minutesAgoLabel(badge.minutes_ago, lang)}` : ''}
      </span>
    </div>
  );
}

export default Lead360;
