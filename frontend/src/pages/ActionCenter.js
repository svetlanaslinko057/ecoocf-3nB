/**
 * BIBI Cars — Wave 17 — Action Center
 *
 * Execution layer on top of Operations360 / Forecast360 / Contract360 /
 * Delivery360. Every risk / bottleneck can be promoted to an Action with
 * owner, priority, due_at, status and full audit trail.
 *
 * Four tabs:
 *   1. Inbox        — all open actions (severity sorted)
 *   2. My Actions   — assigned to me, bucketed Overdue / Today / Week / Later
 *   3. Team         — per-owner load + SLA score (TL / admin)
 *   4. Analytics    — Created / Resolved / Avg time / Overdue % with daily chart
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  Lightning, ArrowsClockwise, Plus, Warning, CheckCircle, ArrowSquareOut,
  Clock, Pause, PlayCircle, ArrowFatLineUp, ArrowCounterClockwise,
  ChatCircleDots, Tray, User, UsersThree, ChartLine, Sparkle,
} from '@phosphor-icons/react';

import { API_URL } from '../App';
import { useLang } from '../i18n';
import { HelpTooltip } from '../components/ui/HelpTooltip';
import RefreshButton from '../components/ui/RefreshButton';
import { PageHeader, PageTabs, HeaderActionButton } from '../components/ui/PageHeader';
import RoleZoneBadge from '../components/ui/RoleZoneBadge';
import WhiteDatePicker from '../components/ui/WhiteDatePicker';
import { Select } from '../components/ui/Select';

const fmt   = (n, ccy = 'EUR') => { try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(Number(n || 0)); } catch { return `${ccy} ${Number(n || 0).toFixed(0)}`; } };
const fmtN  = (n) => new Intl.NumberFormat('en-US').format(Number(n || 0));
const fmtDT = (iso) => { if (!iso) return '—'; try { return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return iso; } };

const PRIO_TONE = {
  critical: { bg: 'bg-red-50',     border: 'border-red-200',     text: 'text-red-700',     bar: 'bg-red-500' },
  high:     { bg: 'bg-orange-50',  border: 'border-orange-200',  text: 'text-orange-700',  bar: 'bg-orange-500' },
  medium:   { bg: 'bg-yellow-50',  border: 'border-yellow-200',  text: 'text-yellow-700',  bar: 'bg-yellow-500' },
  low:      { bg: 'bg-slate-50',   border: 'border-slate-200',   text: 'text-slate-700',   bar: 'bg-slate-400' },
};
const STATUS_TONE = {
  open:        'bg-blue-100 text-blue-700',
  in_progress: 'bg-indigo-100 text-indigo-700',
  snoozed:     'bg-zinc-100 text-zinc-600',
  resolved:    'bg-emerald-100 text-emerald-700',
  cancelled:   'bg-zinc-200 text-zinc-600',
};
const SOURCE_TONE = {
  operations: 'bg-indigo-100 text-indigo-700',
  contract:   'bg-cyan-100 text-cyan-700',
  delivery:   'bg-purple-100 text-purple-700',
  forecast:   'bg-amber-100 text-amber-700',
  finance:    'bg-red-100 text-red-700',
  manual:     'bg-slate-100 text-slate-700',
};
const PrioBadge = ({ value }) => { const t = PRIO_TONE[value] || PRIO_TONE.low; return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${t.bg} ${t.border} ${t.text}`}>{value}</span>; };
const StatusBadge = ({ value }) => <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${STATUS_TONE[value] || 'bg-slate-100 text-slate-700'}`}>{(value || '').replace('_', ' ')}</span>;
const SourceBadge = ({ value }) => <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${SOURCE_TONE[value] || 'bg-slate-100 text-slate-700'}`}>{value}</span>;

const KpiTile = ({ icon: Icon, label, value, hint, tone = 'neutral', onClick, testId, tooltip }) => {
  const cls = { neutral: 'bg-white border-[#E4E4E7]', good: 'bg-emerald-50 border-emerald-200', warn: 'bg-amber-50 border-amber-200', bad: 'bg-red-50 border-red-200', accent: 'bg-indigo-50 border-indigo-200' }[tone] || 'bg-white border-[#E4E4E7]';
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
  { key: 'inbox',     label: t('w17_tab_inbox'),     icon: Tray,         tooltip: t('tip_w17_tab_inbox') },
  { key: 'my',        label: t('w17_tab_my'),        icon: User,         tooltip: t('tip_w17_tab_my') },
  { key: 'team',      label: t('w17_tab_team'),      icon: UsersThree,   tooltip: t('tip_w17_tab_team') },
  { key: 'analytics', label: t('w17_tab_analytics'), icon: ChartLine,    tooltip: t('tip_w17_tab_analytics') },
]);

export default function ActionCenter() {
  const navigate = useNavigate();
  const { t } = useLang();
  const TABS = useMemo(() => TABS_FACTORY(t), [t]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') || 'inbox');
  const [data, setData] = useState({});
  const [loading, setLoading] = useState({});
  const [detail, setDetail] = useState(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ title: '', priority: 'medium', description: '', due_at: '' });

  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);
  const setData_ = (k, v) => setData((p) => ({ ...p, [k]: v }));
  const setLoad_ = (k, v) => setLoading((p) => ({ ...p, [k]: v }));

  const load = useCallback(async (key) => {
    setLoad_(key, true);
    try {
      const { data: res } = await axios.get(`${API_URL}/api/actions/${key}`, { headers });
      setData_(key, res?.data || null);
    } catch (e) { toast.error(`Failed to load ${key}`); }
    finally { setLoad_(key, false); }
  }, [headers]);

  useEffect(() => {
    setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set('tab', tab); return next; });
    load(tab);
  }, [tab, load, setSearchParams]);

  const refresh = () => load(tab);
  const syncSources = useCallback(async () => {
    try {
      const { data: res } = await axios.post(`${API_URL}/api/actions/sync`, {}, { headers });
      const r = res?.data || {};
      toast.success(`Synced — created ${r.created}, updated ${r.updated}, reopened ${r.reopened}, closed ${r.closed_stale}`);
      load(tab);
    } catch (e) { toast.error('Sync failed'); }
  }, [headers, tab, load]);

  const doAction = useCallback(async (id, action, body) => {
    try {
      const { data: res } = await axios.post(`${API_URL}/api/actions/${id}/${action}`, body || {}, { headers });
      const a = res?.data;
      if (a) {
        toast.success(`${action.replace('_', ' ')} → ${a.status}`);
        setDetail(a);
        load(tab);
      }
    } catch (e) { toast.error(`${action} failed: ${e?.response?.data?.detail || e.message}`); }
  }, [headers, tab, load]);

  const createManual = async () => {
    if (!draft.title) { toast.error('Title is required'); return; }
    try {
      const { data: res } = await axios.post(`${API_URL}/api/actions`, { source: 'manual', type: 'manual', ...draft }, { headers });
      toast.success('Action created');
      setDraft({ title: '', priority: 'medium', description: '', due_at: '' });
      setCreating(false);
      load(tab);
    } catch (e) { toast.error('Create failed'); }
  };

  const inbox = data.inbox, my = data.my, team = data.team, analytics = data.analytics;

  return (
    <div className="min-h-full bg-[#FAFAFA]/0" data-testid="action-center">
      {/* HEADER */}
      <PageHeader
        icon={Lightning}
        title={t('w17_title')}
        subtitle={t('w17_subtitle')}
        actions={(
          <>
            <HeaderActionButton icon={Sparkle} label={t('w17_sync')} onClick={syncSources} testId="action-sync" responsiveIconOnly />
            <HeaderActionButton icon={Plus} label={t('w17_new')} onClick={() => setCreating(true)} variant="primary" testId="action-create" responsiveIconOnly />
            <RefreshButton onClick={refresh} testId="action-refresh" />
          </>
        )}
        testId="action-center-header"
      />

      <div className="mb-4"><RoleZoneBadge variant="wave360" /></div>

      {/* TABS */}
      <PageTabs
        tabs={TABS}
        active={tab}
        onChange={setTab}
        testId="action-tabs"
      />

      <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="space-y-5">

        {/* ========================= INBOX ========================= */}
        {tab === 'inbox' ? (loading.inbox && !inbox ? <Spinner /> : inbox ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="inbox-kpis">
              <KpiTile icon={Tray}     label={t('w17_kpi_open')}      value={fmtN(inbox.total)} hint={t('w17_kpi_at_stake').replace('{v}', fmt(inbox.impact_total, inbox.currency))} tone={inbox.total > 0 ? 'warn' : 'good'} tooltip={t('tip_w17_kpi_open')} />
              <KpiTile icon={Warning}  label={t('w17_kpi_overdue')}   value={fmtN(inbox.overdue)} tone={inbox.overdue > 0 ? 'bad' : 'good'} tooltip={t('tip_w17_kpi_overdue')} />
              <KpiTile icon={Lightning} label={t('w17_kpi_critical')} value={fmtN(inbox.by_priority?.critical || 0)} hint={fmt(inbox.impact_critical, inbox.currency)} tone={(inbox.by_priority?.critical || 0) > 0 ? 'bad' : 'good'} tooltip={t('tip_w17_kpi_critical')} />
              <KpiTile icon={Clock}    label={t('w17_kpi_high')}      value={fmtN(inbox.by_priority?.high || 0)} tone={(inbox.by_priority?.high || 0) > 0 ? 'warn' : 'neutral'} tooltip={t('tip_w17_kpi_high')} />
            </div>
            <ActionTable items={inbox.items || []} onClick={(a) => setDetail(a)} ccy={inbox.currency} testId="inbox-table" t={t} />
          </>
        ) : null) : null}

        {/* ========================= MY ============================ */}
        {tab === 'my' ? (loading.my && !my ? <Spinner /> : my ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="my-kpis">
              <KpiTile icon={Warning}  label={t('w17_bk_overdue')}  value={fmtN(my.buckets?.overdue?.total || 0)}   tone={(my.buckets?.overdue?.total || 0) > 0 ? 'bad' : 'good'} />
              <KpiTile icon={Clock}    label={t('w17_bk_today')}    value={fmtN(my.buckets?.today?.total || 0)}     tone="warn" />
              <KpiTile icon={Sparkle}  label={t('w17_bk_week')}     value={fmtN(my.buckets?.this_week?.total || 0)} tone="accent" />
              <KpiTile icon={Tray}     label={t('w17_bk_later')}    value={fmtN(my.buckets?.later?.total || 0)}     tone="neutral" />
            </div>
            {['overdue', 'today', 'this_week', 'later'].map((bk) => {
              const b = my.buckets?.[bk]; if (!b || !b.total) return null;
              const bucketLabel = bk === 'overdue' ? t('w17_bk_overdue') : bk === 'today' ? t('w17_bk_today') : bk === 'this_week' ? t('w17_bk_week') : t('w17_bk_later');
              return (
                <div key={bk} data-testid={`my-bucket-${bk}`}>
                  <div className="flex items-baseline justify-between mb-2 px-1">
                    <h3 className="text-[14px] font-bold text-[#18181B]">{bucketLabel}</h3>
                    <span className="text-[11px] text-[#71717A]">{(b.total === 1 ? t('w17_bk_action_one') : t('w17_bk_actions')).replace('{n}', b.total)}</span>
                  </div>
                  <ActionTable items={b.items || []} onClick={(a) => setDetail(a)} ccy={my.currency} testId={`my-table-${bk}`} hideOwner t={t} />
                </div>
              );
            })}
            {my.total === 0 ? <div className="bg-white border border-[#E4E4E7] rounded-2xl p-6 text-center text-sm text-[#71717A]">{t('w17_inbox_zero')}</div> : null}
          </>
        ) : null) : null}

        {/* ========================= TEAM ========================== */}
        {tab === 'team' ? (loading.team && !team ? <Spinner /> : team ? (
          <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
            <table className="w-full text-[13px]" data-testid="team-table">
              <thead className="bg-[#FAFAFA] text-left text-[10px] uppercase tracking-wider text-[#71717A]">
                <tr>
                  <th className="px-4 py-3">{t('w17_t_owner')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_open')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_in_progress')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_snoozed')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_kpi_overdue')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_escalated')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_resolved_today')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_avg_resolution')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_open_eur')}</th>
                  <th className="px-4 py-3 text-right">{t('w17_t_sla')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F4F4F5]">
                {(team.items || []).length === 0 ? <tr><td colSpan={10} className="px-4 py-6 text-center text-sm text-[#71717A]">{t('w17_t_empty')}</td></tr>
                : (team.items || []).map((r) => (
                  <tr key={r.owner_id || r.owner_name} className="hover:bg-[#FAFAFA]" data-testid={`team-row-${r.owner_id || 'unassigned'}`}>
                    <td className="px-4 py-3 font-medium text-[#18181B]">{r.owner_name}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.open)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.in_progress)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.snoozed)}</td>
                    <td className={`px-4 py-3 text-right tabular-nums ${r.overdue > 0 ? 'text-red-700 font-bold' : ''}`}>{fmtN(r.overdue)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.escalated)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.resolved_today)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{r.avg_resolution_hours != null ? `${r.avg_resolution_hours}h` : '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmt(r.impact_open, team.currency)}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-bold tabular-nums ${r.sla_score >= 80 ? 'bg-emerald-100 text-emerald-700' : r.sla_score >= 60 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>{r.sla_score}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null) : null}

        {/* ========================= ANALYTICS ===================== */}
        {tab === 'analytics' ? (loading.analytics && !analytics ? <Spinner /> : analytics ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="analytics-kpis">
              <KpiTile icon={Plus}        label={t('w17_a_created').replace('{n}', analytics.window_days)} value={fmtN(analytics.created)}  tone="neutral" />
              <KpiTile icon={CheckCircle} label={t('w17_a_resolved')}   value={fmtN(analytics.resolved)} tone="good" />
              <KpiTile icon={Clock}       label={t('w17_a_avg_res')}    value={analytics.avg_resolution_hours == null ? '—' : `${analytics.avg_resolution_hours}h`} tone="neutral" />
              <KpiTile icon={Tray}        label={t('w17_a_open_now')}   value={fmtN(analytics.open_now)} tone={analytics.open_now > 0 ? 'warn' : 'good'} />
              <KpiTile icon={Warning}     label={t('w17_a_overdue_pct')} value={`${analytics.overdue_pct}%`} hint={t('w17_a_overdue_hint').replace('{n}', analytics.overdue_now)} tone={analytics.overdue_pct > 25 ? 'bad' : analytics.overdue_pct > 10 ? 'warn' : 'good'} />
            </div>
            <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="analytics-chart">
              <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w17_a_daily')}</div>
              <div className="flex items-end gap-1 h-32">
                {(analytics.daily || []).map((d, i) => {
                  const maxV = Math.max(1, ...(analytics.daily || []).map((x) => Math.max(x.created, x.resolved)));
                  const cH = (d.created / maxV) * 100;
                  const rH = (d.resolved / maxV) * 100;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-stretch gap-0.5" title={`${d.date}: created ${d.created} · resolved ${d.resolved}`}>
                      <div className="w-full bg-indigo-200 rounded-t" style={{ height: `${cH}%` }} />
                      <div className="w-full bg-emerald-200 rounded-b" style={{ height: `${rH}%` }} />
                    </div>
                  );
                })}
              </div>
              <div className="flex items-center gap-3 mt-2 text-[11px] text-[#71717A]">
                <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 bg-indigo-200 rounded" />{t('w17_a_legend_created')}</span>
                <span className="inline-flex items-center gap-1"><span className="inline-block w-3 h-3 bg-emerald-200 rounded" />{t('w17_a_legend_resolved')}</span>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="analytics-by-source">
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w17_a_by_source')}</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(analytics.by_source || {}).map(([s, n]) => (
                    <div key={s} className="inline-flex items-center gap-2 px-3 py-1.5 border border-[#E4E4E7] rounded-xl"><SourceBadge value={s} /><span className="font-semibold tabular-nums text-[13px]">{n}</span></div>
                  ))}
                </div>
              </div>
              <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="analytics-by-priority">
                <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w17_a_by_priority')}</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(analytics.by_priority || {}).map(([p, n]) => (
                    <div key={p} className="inline-flex items-center gap-2 px-3 py-1.5 border border-[#E4E4E7] rounded-xl"><PrioBadge value={p} /><span className="font-semibold tabular-nums text-[13px]">{n}</span></div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : null) : null}
      </motion.div>

      {/* DETAIL DRAWER */}
      {detail ? (
        <ActionDrawer action={detail} onClose={() => setDetail(null)} onAction={doAction} onNavigate={navigate} />
      ) : null}

      {/* CREATE MODAL */}
      {creating ? (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setCreating(false)} data-testid="create-modal">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-[#18181B] mb-3">{t('w17_form_new')}</h3>
            <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{t('w17_form_title')}</label>
            <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="w-full mt-1 mb-3 px-3 py-2 border border-[#E4E4E7] rounded-lg text-[14px]" placeholder={t('w17_form_title_ph')} data-testid="draft-title" />
            <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{t('w17_form_description')}</label>
            <textarea value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} className="w-full mt-1 mb-3 px-3 py-2 border border-[#E4E4E7] rounded-lg text-[13px] h-20" placeholder={t('w17_form_description_ph')} data-testid="draft-description" />
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{t('w17_form_priority')}</label>
                <Select
                  value={draft.priority}
                  onChange={(e) => setDraft({ ...draft, priority: e.target.value })}
                  size="md"
                  className="w-full mt-1"
                  testId="draft-priority"
                >
                  {['critical', 'high', 'medium', 'low'].map((p) => <option key={p} value={p}>{p}</option>)}
                </Select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{t('w17_form_due')}</label>
                <div className="mt-1">
                  <WhiteDatePicker
                    value={draft.due_at ? draft.due_at.slice(0, 10) : ''}
                    onChange={(e) => {
                      const iso = e?.target?.value || '';
                      setDraft({ ...draft, due_at: iso ? new Date(`${iso}T23:59:59`).toISOString() : '' });
                    }}
                    data-testid="draft-due"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-2">
              <button onClick={() => setCreating(false)} className="px-3 py-2 border border-[#E4E4E7] rounded-lg text-[12px] font-semibold">{t('w17_btn_cancel')}</button>
              <button onClick={createManual} className="px-3 py-2 bg-[#18181B] text-white rounded-lg text-[12px] font-semibold" data-testid="draft-submit">{t('w17_btn_create')}</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

const Spinner = () => <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>;

const ActionTable = ({ items, onClick, ccy, testId, hideOwner, t }) => {
  if (!items.length) return <div className="bg-white border border-[#E4E4E7] rounded-2xl p-6 text-center text-sm text-[#71717A]">{t ? t('w17_no_actions') : 'No actions here.'}</div>;
  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
      <table className="w-full text-[13px]" data-testid={testId}>
        <thead className="bg-[#FAFAFA] text-left text-[10px] uppercase tracking-wider text-[#71717A]">
          <tr>
            <th className="px-4 py-3">{t ? t('w17_col_priority') : 'Priority'}</th>
            <th className="px-4 py-3">{t ? t('w17_col_source') : 'Source'}</th>
            <th className="px-4 py-3">{t ? t('w17_col_title') : 'Title'}</th>
            {hideOwner ? null : <th className="px-4 py-3">{t ? t('w17_col_owner') : 'Owner'}</th>}
            <th className="px-4 py-3">{t ? t('w17_col_status') : 'Status'}</th>
            <th className="px-4 py-3 text-right">{t ? t('w17_col_impact') : 'Impact'}</th>
            <th className="px-4 py-3">{t ? t('w17_col_due') : 'Due'}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#F4F4F5]">
          {items.map((a) => {
            const overdue = a.is_overdue;
            return (
              <tr key={a.id} className={`hover:bg-[#FAFAFA] cursor-pointer ${overdue ? 'bg-red-50/30' : ''}`} onClick={() => onClick(a)} data-testid={`action-row-${a.id}`}>
                <td className="px-4 py-3"><PrioBadge value={a.priority} /></td>
                <td className="px-4 py-3"><SourceBadge value={a.source} /></td>
                <td className="px-4 py-3 font-medium text-[#18181B] truncate max-w-[280px]">{a.title}{a.href ? <ArrowSquareOut size={10} className="inline ml-1 text-[#A1A1AA]" /> : null}</td>
                {hideOwner ? null : <td className="px-4 py-3 text-[12px]">{a.owner_name || '—'}</td>}
                <td className="px-4 py-3"><StatusBadge value={a.status} /></td>
                <td className="px-4 py-3 text-right tabular-nums">{fmt(a.impact, ccy)}</td>
                <td className={`px-4 py-3 text-[12px] ${overdue ? 'text-red-700 font-semibold' : 'text-[#71717A]'}`}>{fmtDT(a.due_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const ActionDrawer = ({ action, onClose, onAction, onNavigate }) => {
  const a = action;
  const [comment, setComment] = useState('');
  const [snoozeUntil, setSnoozeUntil] = useState('');
  const canStart    = ['open', 'snoozed'].includes(a.status);
  const canResolve  = ['open', 'in_progress', 'snoozed'].includes(a.status);
  const canSnooze   = ['open', 'in_progress'].includes(a.status);
  const canEscalate = ['open', 'in_progress'].includes(a.status);
  const canReopen   = ['resolved', 'snoozed', 'cancelled'].includes(a.status);

  return (
    <div className="fixed inset-0 z-40 bg-black/40 flex justify-end" onClick={onClose} data-testid="action-drawer">
      <div className="bg-white w-full max-w-xl h-full overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="p-5 border-b border-[#E4E4E7] sticky top-0 bg-white z-10">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <PrioBadge value={a.priority} /> <SourceBadge value={a.source} /> <StatusBadge value={a.status} />
                {a.escalated ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700"><ArrowFatLineUp size={10} weight="bold" /> Escalated</span> : null}
              </div>
              <h2 className="text-lg font-bold text-[#18181B]">{a.title}</h2>
              {a.description ? <p className="text-[13px] text-[#52525B] mt-1">{a.description}</p> : null}
            </div>
            <button onClick={onClose} className="text-[#71717A] hover:text-[#18181B] text-xl">×</button>
          </div>
        </div>
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3 text-[12px]">
            <div><div className="text-[10px] uppercase text-[#71717A] tracking-wider font-bold">Owner</div><div className="text-[13px]">{a.owner_name || '—'}</div></div>
            <div><div className="text-[10px] uppercase text-[#71717A] tracking-wider font-bold">Due</div><div className="text-[13px]">{fmtDT(a.due_at)}</div></div>
            <div><div className="text-[10px] uppercase text-[#71717A] tracking-wider font-bold">Impact</div><div className="text-[13px] tabular-nums font-semibold">{fmt(a.impact, a.currency)}</div></div>
            <div><div className="text-[10px] uppercase text-[#71717A] tracking-wider font-bold">Entity</div><div className="text-[13px]">{a.entity_type} {a.entity_id ? <span className="text-[#71717A]">{a.entity_id}</span> : null}</div></div>
            {a.href ? <div className="col-span-2"><button onClick={() => onNavigate(a.href)} className="text-[12px] text-[#18181B] underline inline-flex items-center gap-1">Open source <ArrowSquareOut size={10} /></button></div> : null}
          </div>

          <div className="flex flex-wrap gap-2">
            {canStart    ? <button onClick={() => onAction(a.id, 'start')} className="inline-flex items-center gap-1 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-[12px] font-semibold hover:bg-indigo-700" data-testid="drawer-start"><PlayCircle size={12} weight="bold" /> Start</button> : null}
            {canResolve  ? <button onClick={() => onAction(a.id, 'resolve', { comment, outcome: 'resolved' })} className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-[12px] font-semibold hover:bg-emerald-700" data-testid="drawer-resolve"><CheckCircle size={12} weight="bold" /> Resolve</button> : null}
            {canSnooze   ? <button onClick={() => { const dt = snoozeUntil || new Date(Date.now() + 24 * 3600 * 1000).toISOString(); onAction(a.id, 'snooze', { snooze_until: dt, comment }); }} className="inline-flex items-center gap-1 px-3 py-1.5 bg-zinc-500 text-white rounded-lg text-[12px] font-semibold hover:bg-zinc-600" data-testid="drawer-snooze"><Pause size={12} weight="bold" /> Snooze 1d</button> : null}
            {canEscalate ? <button onClick={() => onAction(a.id, 'escalate', { to_step: 'team_lead', comment })} className="inline-flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded-lg text-[12px] font-semibold hover:bg-red-700" data-testid="drawer-escalate"><ArrowFatLineUp size={12} weight="bold" /> Escalate</button> : null}
            {canReopen   ? <button onClick={() => onAction(a.id, 'reopen', { comment: comment || 'Reopened' })} className="inline-flex items-center gap-1 px-3 py-1.5 border border-[#E4E4E7] text-[#52525B] rounded-lg text-[12px] font-semibold hover:bg-[#FAFAFA]" data-testid="drawer-reopen"><ArrowCounterClockwise size={12} weight="bold" /> Reopen</button> : null}
          </div>

          <div className="border-t border-[#F4F4F5] pt-3">
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Add a comment (optional, sent with action)" className="w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-[13px] h-16" data-testid="drawer-comment" />
            <button onClick={() => { if (comment) { onAction(a.id, 'comment', { comment }); setComment(''); } }} className="mt-1 text-[11px] text-[#18181B] inline-flex items-center gap-1"><ChatCircleDots size={12} weight="bold" /> Post comment</button>
          </div>

          <div className="border-t border-[#F4F4F5] pt-3" data-testid="drawer-events">
            <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">Timeline ({(a.events || []).length})</div>
            <div className="space-y-2">
              {(a.events || []).slice().reverse().map((e, i) => (
                <div key={i} className="flex items-start gap-2 text-[12px]">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#18181B] mt-1.5" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold capitalize">{e.kind.replace(/_/g, ' ')}</span>
                      <span className="text-[11px] text-[#71717A]">{fmtDT(e.at)}</span>
                    </div>
                    {e.note ? <div className="text-[12px] text-[#52525B]">{e.note}</div> : null}
                    {e.actor_name ? <div className="text-[11px] text-[#71717A]">{e.actor_name}</div> : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
