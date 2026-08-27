/**
 * BIBI Cars — Wave 18 — Communication & Notification Center
 *
 * First delivery channel layer. Every notification is produced by the
 * Action lifecycle (Wave 17), not from raw risk feeds. Plus a built-in
 * SLA Escalation Engine (Wave 18.1) that scans overdue actions and
 * promotes them up the chain:
 *
 *   > 24h → remind owner    (action_overdue)
 *   > 72h → escalate to TL   (re-assign + action_escalated)
 *   > 7d  → escalate to admin (action_critical_overdue + priority=critical)
 *
 * Four tabs:
 *   1. Inbox        — caller's notifications (paged, mark-read, dismiss)
 *   2. Preferences  — channel toggles + mute + digest mode
 *   3. Analytics    — per-channel/per-event volume, delivery & read rates
 *   4. SLA Engine   — dispatch-rule catalogue + on-demand escalation scan
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  Bell, BellRinging, ArrowsClockwise, CheckCircle, X, Sliders, ChartLine,
  Lightning, Tray, Check, Envelope, ChatCircleDots, Phone, ChatTeardropDots,
  ArrowSquareOut, Warning, ShieldCheck, Clock, ToggleRight, ToggleLeft,
  PaperPlaneTilt, MoonStars,
} from '@phosphor-icons/react';

import { API_URL } from '../App';
import RefreshButton from '../components/ui/RefreshButton';
import { PageHeader, PageTabs, HeaderActionButton } from '../components/ui/PageHeader';
import RoleZoneBadge from '../components/ui/RoleZoneBadge';
import { useLang } from '../i18n';
import { HelpTooltip } from '../components/ui/HelpTooltip';

const fmtN  = (n) => new Intl.NumberFormat('en-US').format(Number(n || 0));
const fmtDT = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso; }
};
const fmtAgo = (iso) => {
  if (!iso) return '';
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  } catch { return ''; }
};

const PRIO_TONE = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high:     'bg-orange-100 text-orange-700 border-orange-200',
  medium:   'bg-yellow-100 text-yellow-700 border-yellow-200',
  low:      'bg-slate-100 text-slate-700 border-slate-200',
};
const CHANNEL_ICON = {
  in_app:   { Icon: Bell,             label: 'In-App' },
  email:    { Icon: Envelope,         label: 'Email' },
  telegram: { Icon: PaperPlaneTilt,   label: 'Telegram' },
  slack:    { Icon: ChatCircleDots,   label: 'Slack' },
  sms:      { Icon: Phone,            label: 'SMS' },
};
const EVENT_LABEL = {
  action_created:           'Action created',
  action_assigned:          'Action assigned',
  action_started:           'Action started',
  action_snoozed:           'Action snoozed',
  action_escalated:         'Action escalated',
  action_reopened:          'Action reopened',
  action_resolved:          'Action resolved',
  action_cancelled:         'Action cancelled',
  action_commented:         'New comment',
  action_overdue:           'Action overdue',
  action_critical_overdue:  'Critical overdue',
};
const EVENT_TONE = {
  action_created:           'bg-blue-100 text-blue-700',
  action_assigned:          'bg-indigo-100 text-indigo-700',
  action_started:           'bg-sky-100 text-sky-700',
  action_snoozed:           'bg-zinc-100 text-zinc-600',
  action_escalated:         'bg-amber-100 text-amber-700',
  action_reopened:          'bg-purple-100 text-purple-700',
  action_resolved:          'bg-emerald-100 text-emerald-700',
  action_cancelled:         'bg-zinc-200 text-zinc-600',
  action_commented:         'bg-slate-100 text-slate-700',
  action_overdue:           'bg-orange-100 text-orange-700',
  action_critical_overdue:  'bg-red-100 text-red-700',
};

const PrioBadge = ({ value }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${PRIO_TONE[value] || PRIO_TONE.low}`}>{value || 'low'}</span>
);
const EventBadge = ({ value }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${EVENT_TONE[value] || 'bg-slate-100 text-slate-700'}`}>
    {EVENT_LABEL[value] || value}
  </span>
);
const ChannelBadge = ({ value }) => {
  const { Icon, label } = CHANNEL_ICON[value] || CHANNEL_ICON.in_app;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-900 text-white">
      <Icon size={10} weight="bold" /> {label}
    </span>
  );
};

const KpiTile = ({ icon: Icon, label, value, hint, tone = 'neutral', onClick, testId, tooltip }) => {
  const cls = {
    neutral: 'bg-white border-[#E4E4E7]',
    good:    'bg-emerald-50 border-emerald-200',
    warn:    'bg-amber-50 border-amber-200',
    bad:     'bg-red-50 border-red-200',
    accent:  'bg-indigo-50 border-indigo-200',
  }[tone] || 'bg-white border-[#E4E4E7]';
  const inter = onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : '';
  const tile = (
    <div className={`border rounded-2xl p-4 ${cls} ${inter}`} onClick={onClick} data-testid={testId}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-[#71717A]"><Icon size={14} weight="bold" /> {label}</div>
      <div className="text-[22px] font-bold text-[#18181B] mt-1 tabular-nums">{value}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5">{hint}</div> : null}
    </div>
  );
  return tooltip ? <HelpTooltip text={tooltip}>{tile}</HelpTooltip> : tile;
};

const TABS_FACTORY = (t) => ([
  { key: 'inbox',       label: t('w18_tab_inbox'),        icon: Tray,         tooltip: t('tip_w18_tab_inbox') },
  { key: 'preferences', label: t('w18_tab_preferences'),  icon: Sliders,      tooltip: t('tip_w18_tab_preferences') },
  { key: 'analytics',   label: t('w18_tab_analytics'),    icon: ChartLine,    tooltip: t('tip_w18_tab_analytics') },
  { key: 'sla',         label: t('w18_tab_sla'),          icon: ShieldCheck,  tooltip: t('tip_w18_tab_sla') },
]);

const TabButton = ({ tab, active, onClick }) => {
  const Icon = tab.icon;
  const btn = (
    <button
      onClick={onClick}
      data-testid={`notif-tab-${tab.key}`}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
        active
          ? 'bg-[#18181B] text-white shadow-sm'
          : 'bg-white text-[#52525B] border border-[#E4E4E7] hover:bg-[#FAFAFA]'
      }`}
    >
      <Icon size={16} weight={active ? 'fill' : 'bold'} />
      {tab.label}
    </button>
  );
  return tab.tooltip ? <HelpTooltip text={tab.tooltip} side="bottom">{btn}</HelpTooltip> : btn;
};

export default function NotificationCenter() {
  const navigate = useNavigate();
  const { t } = useLang();
  const TABS = useMemo(() => TABS_FACTORY(t), [t]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') || 'inbox');

  // Token guard — mirror App.js storage key (avoids "Failed to load" toast
  // on initial render before AuthProvider finishes wiring axios defaults).
  const token = localStorage.getItem('token');
  const authHeaders = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const [inbox, setInbox]       = useState(null);
  const [prefs, setPrefs]       = useState(null);
  const [rules, setRules]       = useState(null);
  const [analytics, setAnal]    = useState(null);
  const [loading, setLoading]   = useState({});
  const [onlyUnread, setOnlyUnread] = useState(false);

  const setTabAndUrl = (k) => { setTab(k); setSearchParams({ tab: k }); };
  const setBusy = (k, v) => setLoading((p) => ({ ...p, [k]: v }));

  // ── data fetchers ─────────────────────────────────────────────────
  const fetchInbox = useCallback(async () => {
    if (!token) return;
    setBusy('inbox', true);
    try {
      const r = await axios.get(`${API_URL}/api/notifications/inbox`, {
        params: { only_unread: onlyUnread, limit: 200 }, headers: authHeaders,
      });
      setInbox(r.data?.data || null);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed to load inbox'); }
    finally { setBusy('inbox', false); }
  }, [onlyUnread, token, authHeaders]);

  const fetchPrefs = useCallback(async () => {
    if (!token) return;
    setBusy('prefs', true);
    try {
      const r = await axios.get(`${API_URL}/api/notifications/preferences`, { headers: authHeaders });
      setPrefs(r.data?.data || null);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed to load preferences'); }
    finally { setBusy('prefs', false); }
  }, [token, authHeaders]);

  const fetchRules = useCallback(async () => {
    if (!token) return;
    setBusy('rules', true);
    try {
      const r = await axios.get(`${API_URL}/api/notifications/rules`, { headers: authHeaders });
      setRules(r.data || null);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed to load rules'); }
    finally { setBusy('rules', false); }
  }, [token, authHeaders]);

  const fetchAnalytics = useCallback(async () => {
    if (!token) return;
    setBusy('analytics', true);
    try {
      const r = await axios.get(`${API_URL}/api/notifications/analytics`, { params: { days: 30 }, headers: authHeaders });
      setAnal(r.data?.data || null);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed to load analytics'); }
    finally { setBusy('analytics', false); }
  }, [token, authHeaders]);

  // ── refresh per tab ───────────────────────────────────────────────
  useEffect(() => {
    if (tab === 'inbox')       fetchInbox();
    if (tab === 'preferences') fetchPrefs();
    if (tab === 'analytics')   fetchAnalytics();
    if (tab === 'sla')         { fetchRules(); fetchAnalytics(); }
  }, [tab, fetchInbox, fetchPrefs, fetchAnalytics, fetchRules]);

  // re-fetch inbox when toggle changes
  useEffect(() => { if (tab === 'inbox') fetchInbox(); }, [onlyUnread]); // eslint-disable-line

  // ── actions ───────────────────────────────────────────────────────
  const markRead = async (id) => {
    try {
      await axios.post(`${API_URL}/api/notifications/${id}/read`, {}, { headers: authHeaders });
      fetchInbox();
    } catch (e) { toast.error('Could not mark as read'); }
  };
  const markAllRead = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/notifications/read-all`, {}, { headers: authHeaders });
      toast.success(`Marked ${r.data?.marked || 0} as read`);
      fetchInbox();
    } catch (e) { toast.error('Could not mark all as read'); }
  };
  const dismiss = async (id) => {
    try {
      await axios.post(`${API_URL}/api/notifications/${id}/dismiss`, {}, { headers: authHeaders });
      fetchInbox();
    } catch (e) { toast.error('Could not dismiss'); }
  };
  const patchPref = async (patch) => {
    try {
      const r = await axios.patch(`${API_URL}/api/notifications/preferences`, patch, { headers: authHeaders });
      setPrefs(r.data?.data || null);
      toast.success('Preferences updated');
    } catch (e) { toast.error('Failed to update preferences'); }
  };
  const togglePref = (channel) => {
    if (!prefs) return;
    const next = { ...(prefs.channels || {}), [channel]: !prefs.channels?.[channel] };
    patchPref({ channels: next });
  };
  const runEscalationScan = async () => {
    setBusy('scan', true);
    try {
      const r = await axios.post(`${API_URL}/api/notifications/escalation/scan`, {}, { headers: authHeaders });
      const d = r.data?.data || {};
      toast.success(
        `Scanned ${d.scanned}. Reminded ${d.reminded} · TL escalations ${d.escalated_to_tl} · Admin ${d.escalated_to_admin}`,
        { duration: 6000 }
      );
      fetchAnalytics();
      fetchInbox();
    } catch (e) { toast.error('Escalation scan failed'); }
    finally { setBusy('scan', false); }
  };

  // ── derived KPIs (inbox tab) ──────────────────────────────────────
  const inboxKpi = useMemo(() => {
    const d = inbox || {};
    const items = d.items || [];
    const critical = items.filter((it) => it.priority === 'critical').length;
    const overdue  = items.filter((it) => it.event === 'action_overdue' || it.event === 'action_critical_overdue').length;
    return {
      total:   d.total || 0,
      unread:  d.unread || 0,
      critical,
      overdue,
    };
  }, [inbox]);

  return (
    <div className="min-h-full" data-testid="notification-center-page">
      <PageHeader
        icon={BellRinging}
        title={(
          <span className="inline-flex items-center gap-3">
            {t('w18_title')}
            {(inboxKpi.unread > 0) && (
              <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 rounded-full bg-red-500 text-white text-[11px] font-bold">
                {inboxKpi.unread}
              </span>
            )}
          </span>
        )}
        subtitle={t('w18_subtitle')}
        actions={(
          <>
            <HeaderActionButton
              icon={Lightning}
              label={t('w17_title')}
              onClick={() => navigate('/admin/actions')}
              testId="notif-go-actions"
              responsiveIconOnly
            />
            <HeaderActionButton
              icon={ShieldCheck}
              label={loading.scan ? `${t('w18_run_scan')}…` : t('w18_run_scan')}
              onClick={runEscalationScan}
              variant="primary"
              disabled={loading.scan}
              testId="notif-run-scan"
              responsiveIconOnly
            />
          </>
        )}
        testId="notification-center-header"
      />

      <div className="mb-4"><RoleZoneBadge variant="wave360" /></div>

      <PageTabs
        tabs={TABS}
        active={tab}
        onChange={(k) => setTabAndUrl(k)}
        testId="notification-center-tabs"
      />

      {/* ── tab content ─────────────────────────────────────────── */}
      <div className="space-y-6">
        {tab === 'inbox' && (
          <InboxTab
            data={inbox} kpi={inboxKpi}
            loading={loading.inbox}
            onlyUnread={onlyUnread} setOnlyUnread={setOnlyUnread}
            markRead={markRead} markAllRead={markAllRead} dismiss={dismiss}
            refresh={fetchInbox} t={t}
          />
        )}
        {tab === 'preferences' && (
          <PreferencesTab prefs={prefs} loading={loading.prefs} togglePref={togglePref} patchPref={patchPref} />
        )}
        {tab === 'analytics' && (
          <AnalyticsTab data={analytics} loading={loading.analytics} refresh={fetchAnalytics} />
        )}
        {tab === 'sla' && (
          <SlaTab rules={rules} analytics={analytics} loading={loading.rules}
                  runScan={runEscalationScan} scanning={loading.scan} />
        )}
      </div>
    </div>
  );
}

// ── tab: Inbox ─────────────────────────────────────────────────────
function InboxTab({ data, kpi, loading, onlyUnread, setOnlyUnread, markRead, markAllRead, dismiss, refresh, t }) {
  const items = data?.items || [];
  const _t = t || ((k) => k);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiTile icon={Tray}    label={_t('w18_kpi_total')}    value={fmtN(kpi.total)}                    tooltip={_t('tip_w18_kpi_total')} testId="kpi-total" />
        <KpiTile icon={Bell}    label={_t('w18_kpi_unread')}   value={fmtN(kpi.unread)}    tone={kpi.unread ? 'accent' : 'neutral'} tooltip={_t('tip_w18_kpi_unread')} testId="kpi-unread" />
        <KpiTile icon={Warning} label={_t('w18_kpi_critical')} value={fmtN(kpi.critical)}  tone={kpi.critical ? 'bad' : 'neutral'} tooltip={_t('tip_w18_kpi_critical')} testId="kpi-critical" />
        <KpiTile icon={Clock}   label={_t('w18_kpi_overdue')}  value={fmtN(kpi.overdue)}   tone={kpi.overdue ? 'warn' : 'neutral'} tooltip={_t('tip_w18_kpi_overdue')} testId="kpi-overdue" />
      </div>

      <div className="flex items-center justify-between bg-white border border-[#E4E4E7] rounded-xl px-4 py-3">
        <label className="inline-flex items-center gap-2 cursor-pointer text-sm">
          <input type="checkbox" checked={onlyUnread} onChange={(e) => setOnlyUnread(e.target.checked)}
                 className="rounded border-[#E4E4E7]" data-testid="notif-only-unread" />
          {_t('w18_show_only_unread')}
        </label>
        <div className="flex items-center gap-2">
          <button onClick={markAllRead} data-testid="notif-mark-all-read"
                  className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-[#E4E4E7] hover:bg-[#FAFAFA]">
            <Check size={12} weight="bold" /> {_t('w18_mark_all_read')}
          </button>
          <RefreshButton onClick={refresh} loading={loading} size="sm" testId="notif-refresh-inbox" />
        </div>
      </div>

      {loading && !data && <div className="text-center py-12 text-[#71717A]">{_t('w18_loading_inbox')}</div>}

      {!loading && items.length === 0 && (
        <div className="bg-white border border-dashed border-[#E4E4E7] rounded-2xl p-12 text-center">
          <CheckCircle size={40} weight="duotone" className="mx-auto text-emerald-500 mb-3" />
          <div className="text-base font-medium text-[#18181B]">{_t('w18_all_caught_up')}</div>
          <div className="text-sm text-[#71717A] mt-1">{_t('w18_no_notifications_match')}</div>
        </div>
      )}

      {items.length > 0 && (
        <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
          <ul className="divide-y divide-[#F1F1F2]">
            {items.map((n) => (
              <motion.li key={n.id}
                initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                className={`group p-4 flex items-start gap-3 hover:bg-[#FAFAFA] transition-colors ${n.read_at ? 'opacity-70' : ''}`}
                data-testid={`notif-row-${n.id}`}>
                <div className="flex-shrink-0 mt-1">
                  {!n.read_at && <div className="w-2 h-2 rounded-full bg-blue-500" />}
                  {n.read_at && <div className="w-2 h-2 rounded-full bg-transparent" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <EventBadge value={n.event} />
                    <PrioBadge value={n.priority} />
                    <ChannelBadge value={n.channel} />
                    <span className="text-[11px] text-[#71717A] ml-auto">{fmtAgo(n.created_at)}</span>
                  </div>
                  <div className="text-sm font-semibold text-[#18181B] mt-1.5">{n.title}</div>
                  <div className="text-sm text-[#52525B] mt-0.5">{n.body}</div>
                  {n.href && (
                    <button
                      onClick={() => { if (!n.read_at) markRead(n.id); window.location.href = n.href; }}
                      className="inline-flex items-center gap-1 text-[12px] font-medium text-indigo-600 hover:text-indigo-700 mt-2"
                    >
                      Open action <ArrowSquareOut size={11} weight="bold" />
                    </button>
                  )}
                </div>
                <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {!n.read_at && (
                    <button onClick={() => markRead(n.id)} title="Mark as read"
                            data-testid={`notif-read-${n.id}`}
                            className="p-1.5 rounded hover:bg-emerald-50 text-emerald-600">
                      <Check size={14} weight="bold" />
                    </button>
                  )}
                  <button onClick={() => dismiss(n.id)} title="Dismiss"
                          data-testid={`notif-dismiss-${n.id}`}
                          className="p-1.5 rounded hover:bg-red-50 text-red-600">
                    <X size={14} weight="bold" />
                  </button>
                </div>
              </motion.li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── tab: Preferences ───────────────────────────────────────────────
function PreferencesTab({ prefs, loading, togglePref, patchPref }) {
  if (loading && !prefs) return <div className="text-center py-12 text-[#71717A]">Loading preferences…</div>;
  if (!prefs) return null;

  const channels = prefs.channels || {};
  const channelList = [
    { key: 'in_app',   phase: 1, info: 'Always on. The bell icon in your header shows live counts.' },
    { key: 'email',    phase: 1, info: 'Delivered via the backend email outbox. Required for action_assigned and overdue.' },
    { key: 'telegram', phase: 2, info: 'Phase 2 channel. Stub — queues notifications until Telegram bridge is enabled.' },
    { key: 'slack',    phase: 2, info: 'Phase 2 channel. Stub — queues notifications until Slack bridge is enabled.' },
    { key: 'sms',      phase: 3, info: 'Phase 3 channel. Stub — high-priority alerts only.' },
  ];

  return (
    <div className="space-y-5 max-w-3xl">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Channels</div>
        <div className="text-sm text-[#52525B] mt-1">
          Toggle which channels you want to receive notifications on. <strong>In-App is always on</strong> (your inbox).
        </div>
        <div className="mt-4 divide-y divide-[#F1F1F2]">
          {channelList.map((c) => {
            const { Icon, label } = CHANNEL_ICON[c.key];
            const enabled = !!channels[c.key];
            const locked = c.key === 'in_app';
            return (
              <div key={c.key} className="flex items-center justify-between py-3 gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${enabled ? 'bg-indigo-50 text-indigo-600' : 'bg-slate-100 text-slate-400'}`}>
                    <Icon size={18} weight="bold" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#18181B] flex items-center gap-2">
                      {label}
                      <span className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] bg-slate-100 px-1.5 py-0.5 rounded">
                        Phase {c.phase}
                      </span>
                    </div>
                    <div className="text-[12px] text-[#71717A] mt-0.5">{c.info}</div>
                  </div>
                </div>
                <button
                  onClick={() => !locked && togglePref(c.key)}
                  disabled={locked}
                  data-testid={`pref-toggle-${c.key}`}
                  className={`flex-shrink-0 inline-flex items-center gap-1 ${locked ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                  title={locked ? 'In-App is always enabled' : ''}
                >
                  {enabled
                    ? <ToggleRight size={32} weight="fill" className="text-emerald-500" />
                    : <ToggleLeft  size={32} weight="fill" className="text-slate-300" />}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Digest mode</div>
        <div className="text-sm text-[#52525B] mt-1">
          Bundle notifications instead of receiving them individually. Critical alerts always come through immediately.
        </div>
        <div className="mt-3 inline-flex bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl p-1">
          {['realtime', 'daily', 'weekly'].map((m) => (
            <button key={m}
              onClick={() => patchPref({ digest: m })}
              data-testid={`pref-digest-${m}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg capitalize transition-all ${
                prefs.digest === m ? 'bg-white shadow-sm text-[#18181B]' : 'text-[#71717A] hover:text-[#18181B]'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider font-bold text-[#71717A]">
          <MoonStars size={12} weight="fill" /> Mute notifications
        </div>
        <div className="text-sm text-[#52525B] mt-1">
          Temporarily mute email/telegram/slack/sms. Your In-App inbox is unaffected.
        </div>
        <div className="mt-3 flex items-center gap-2">
          {[
            { label: '1 hour',  hours: 1 },
            { label: '4 hours', hours: 4 },
            { label: '1 day',   hours: 24 },
            { label: 'Unmute',  hours: 0 },
          ].map((opt) => (
            <button key={opt.label}
              onClick={() => {
                const v = opt.hours === 0 ? null : new Date(Date.now() + opt.hours * 3600 * 1000).toISOString();
                patchPref({ mute_until: v });
              }}
              data-testid={`pref-mute-${opt.hours}`}
              className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-[#E4E4E7] hover:bg-[#FAFAFA] text-[#18181B]"
            >
              {opt.label}
            </button>
          ))}
          {prefs.mute_until && (
            <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
              Muted until {fmtDT(prefs.mute_until)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── tab: Analytics ─────────────────────────────────────────────────
function AnalyticsTab({ data, loading, refresh }) {
  const { t } = useLang();
  const _t = t || ((k) => k);
  if (loading && !data) return <div className="text-center py-12 text-[#71717A]">Loading analytics…</div>;
  if (!data) return null;

  const channels = Object.entries(data.by_channel || {}).sort(([, a], [, b]) => b - a);
  const events   = Object.entries(data.by_event   || {}).sort(([, a], [, b]) => b - a);
  const max = (rows) => rows.reduce((m, [, v]) => Math.max(m, v), 1);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <KpiTile icon={Tray}        label="Total sent" value={fmtN(data.total)}                     testId="kpi-anal-total" />
        <KpiTile icon={CheckCircle} label="Delivered"  value={fmtN(data.delivered)} tone="good"     testId="kpi-anal-delivered" />
        <KpiTile icon={Check}       label="Read"       value={fmtN(data.read)}      tone="accent"   testId="kpi-anal-read" />
        <KpiTile icon={Warning}     label="Failed"     value={fmtN(data.failed)}    tone={data.failed ? 'bad' : 'neutral'} testId="kpi-anal-failed" />
        <KpiTile icon={ChartLine}   label="Read rate"  value={`${data.read_rate ?? 0}%`} hint={`${data.delivery_rate ?? 0}% delivery`} testId="kpi-anal-rate" />
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{_t('w18_by_channel')}</div>
              <div className="text-sm text-[#52525B]">{_t('w18_last_days').replace('{n}', data.window_days)}</div>
            </div>
            <RefreshButton onClick={refresh} size="sm" testId="notif-analytics-refresh" />
          </div>
          {channels.length === 0 && <div className="text-sm text-[#71717A] py-8 text-center">{_t('w18_no_data_yet')}</div>}
          {channels.map(([ch, n]) => (
            <div key={ch} className="mt-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <ChannelBadge value={ch} />
                <span className="font-mono tabular-nums">{fmtN(n)}</span>
              </div>
              <div className="h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                <div className="h-full bg-[#18181B]" style={{ width: `${(n / max(channels)) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>

        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{_t('w18_by_event')}</div>
          <div className="text-sm text-[#52525B]">{_t('w18_last_days_top10').replace('{n}', data.window_days)}</div>
          {events.length === 0 && <div className="text-sm text-[#71717A] py-8 text-center">{_t('w18_no_data_yet')}</div>}
          {events.slice(0, 10).map(([ev, n]) => (
            <div key={ev} className="mt-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <EventBadge value={ev} />
                <span className="font-mono tabular-nums">{fmtN(n)}</span>
              </div>
              <div className="h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500" style={{ width: `${(n / max(events)) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── tab: SLA Engine + Rules ────────────────────────────────────────
function SlaTab({ rules, analytics, loading, runScan, scanning }) {
  const dispatchByEvent = useMemo(() => {
    const r = rules?.rules || [];
    const m = {};
    r.forEach((rl) => { m[rl.event] = m[rl.event] || []; m[rl.event].push(rl); });
    return m;
  }, [rules]);
  if (loading && !rules) return <div className="text-center py-12 text-[#71717A]">Loading…</div>;
  const sla = rules?.sla_thresholds_hours || {};

  return (
    <div className="space-y-5">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider font-bold text-[#71717A]">
              <ShieldCheck size={14} weight="fill" /> Wave 18.1 · SLA Escalation Engine
            </div>
            <h3 className="text-lg font-bold text-[#18181B] mt-1">Three-tier automatic promotion of overdue actions</h3>
            <p className="text-sm text-[#52525B] mt-1 max-w-2xl">
              An idempotent scan walks every open / in_progress action with a due date in the past.
              Dedup markers live on the action itself, so running the scan twice produces zero duplicates.
            </p>
          </div>
          <button onClick={runScan} disabled={scanning} data-testid="sla-run-scan"
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-[#18181B] text-white text-sm font-medium hover:bg-[#27272A] disabled:opacity-50">
            <ShieldCheck size={14} weight="bold" /> {scanning ? 'Scanning…' : 'Run SLA Scan'}
          </button>
        </div>

        <div className="mt-4 grid sm:grid-cols-3 gap-3">
          <ThresholdCard tier="1" hours={sla.remind_owner}        title="Remind owner"
            desc="Notify the action owner (in-app + email)." tone="warn" />
          <ThresholdCard tier="2" hours={sla.escalate_team_lead}  title="Escalate to Team Lead"
            desc="Reassign + bump priority to high. Owner, previous owner and team lead notified." tone="bad" />
          <ThresholdCard tier="3" hours={sla.escalate_admin}      title="Escalate to Admin"
            desc="Reassign to admin, priority becomes critical. action_critical_overdue fires." tone="bad" />
        </div>
      </div>

      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Dispatch rules</div>
        <div className="text-sm text-[#52525B] mt-1">
          Which recipient roles receive which event, and over which channels. 11 events · {rules?.rules?.length || 0} rules.
        </div>
        <div className="mt-4 grid md:grid-cols-2 gap-3">
          {Object.entries(dispatchByEvent).map(([ev, list]) => (
            <div key={ev} className="border border-[#F1F1F2] rounded-xl p-3" data-testid={`sla-rule-${ev}`}>
              <div className="flex items-center justify-between gap-2">
                <EventBadge value={ev} />
                <span className="text-[10px] text-[#71717A] font-mono">{list.length} rule{list.length === 1 ? '' : 's'}</span>
              </div>
              {list.length === 0 && (
                <div className="text-[12px] text-[#71717A] mt-2 italic">Internal state — no notification.</div>
              )}
              {list.map((r, i) => (
                <div key={i} className="mt-2 flex items-center justify-between text-[12px]">
                  <span className="font-semibold text-[#18181B] capitalize">{r.recipient.replace('_', ' ')}</span>
                  <div className="flex gap-1 flex-wrap">
                    {r.channels.map((ch) => <ChannelBadge key={ch} value={ch} />)}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {analytics && (
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Delivery health (last {analytics.window_days}d)</div>
          <div className="grid sm:grid-cols-4 gap-3 mt-3">
            <KpiTile icon={Tray}        label="Sent"      value={fmtN(analytics.total)} />
            <KpiTile icon={CheckCircle} label="Delivered" value={`${analytics.delivery_rate ?? 0}%`} tone="good" />
            <KpiTile icon={Check}       label="Read"      value={`${analytics.read_rate ?? 0}%`}     tone="accent" />
            <KpiTile icon={Warning}     label="Failed"    value={fmtN(analytics.failed)} tone={analytics.failed ? 'bad' : 'neutral'} />
          </div>
        </div>
      )}
    </div>
  );
}

const ThresholdCard = ({ tier, hours, title, desc, tone }) => {
  const cls = { warn: 'bg-amber-50 border-amber-200', bad: 'bg-red-50 border-red-200' }[tone] || 'bg-white border-[#E4E4E7]';
  return (
    <div className={`border rounded-xl p-3 ${cls}`}>
      <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Tier {tier}</div>
      <div className="text-lg font-bold text-[#18181B] mt-1">{hours ?? '—'}h overdue</div>
      <div className="text-[12px] font-semibold text-[#18181B] mt-2">{title}</div>
      <div className="text-[11px] text-[#52525B] mt-1">{desc}</div>
    </div>
  );
};
