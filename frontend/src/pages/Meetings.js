/**
 * Meetings — calendar + list view.  Доопр #8.
 *
 * Views:
 *   - List  (default): table with filters + .ics export per meeting.
 *   - Week  : 7-day grid view.
 *   - Month : 6-row month grid (à la Google Calendar) for situational awareness.
 *
 * Lifecycle:
 *   - Create a meeting: title, start, duration, type, customer/lead/deal,
 *     manager (admin/team_lead only), location, "Notes BEFORE meeting".
 *   - Complete a meeting: mandatory "Result / comment AFTER meeting" + "Next step".
 *   - Cancel → soft cancel.
 *
 * Visibility (enforced by backend):
 *   - Manager  → own meetings.
 *   - TeamLead → all meetings of their team (currently scoped via require_manager_or_admin).
 *   - Admin    → everything.
 *
 * Each meeting exports a .ics file (compatible with Google Calendar / Outlook /
 * Apple Calendar — covers the "integration with Google Meet" hint in the spec).
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useLang } from '../i18n';
import {
  CalendarCheck, Plus, RefreshCw, X, Save, Download, CheckCircle2,
  XCircle, Phone, Users, Globe, MapPin, Calendar, ChevronLeft, ChevronRight,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function authHeaders() {
  const token = (typeof window !== 'undefined' && window.localStorage)
    ? window.localStorage.getItem('token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function readMe() {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  try { return JSON.parse(window.localStorage.getItem('user') || 'null'); } catch { return null; }
}

const STATUS_BADGE = {
  scheduled: { bg: 'bg-amber-100',   text: 'text-amber-700',   label: 'Scheduled' },
  completed: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Completed' },
  cancelled: { bg: 'bg-rose-100',    text: 'text-rose-700',    label: 'Cancelled' },
  no_show:   { bg: 'bg-zinc-100',    text: 'text-zinc-700',    label: 'No-show' },
};

const TYPES = [
  { value: 'call',      label: 'Call',      icon: Phone },
  { value: 'in_person', label: 'In person', icon: Users },
  { value: 'online',    label: 'Online',    icon: Globe },
  { value: 'other',     label: 'Other',     icon: MapPin },
];

const emptyMeeting = (defaultManagerId = '') => ({
  id: null,
  customerId: '',
  leadId: '',
  dealId: '',
  managerId: defaultManagerId,
  title: '',
  startAt: '',
  durationMin: 30,
  meetingType: 'call',
  location: '',
  notes: '',
});

function toLocalInput(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 16);
}
function fromLocalInput(local) {
  if (!local) return '';
  return new Date(local).toISOString();
}

export default function Meetings() {
  const { t } = useLang();
  const tt = (key, fallback) => { const v = t(key); return (!v || v === key) ? fallback : v; };
  const me = useMemo(() => readMe(), []);
  const myRole = (me?.role || '').toLowerCase();
  const isAdminLike = ['admin', 'master_admin', 'owner', 'team_lead'].includes(myRole);

  const [items, setItems] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [managerFilter, setManagerFilter] = useState('');
  const [view, setView] = useState('list'); // 'list' | 'week' | 'month'
  const [editor, setEditor] = useState(null);
  const [completeFor, setCompleteFor] = useState(null);
  const [completePayload, setCompletePayload] = useState({ result: '', nextStep: '' });
  const [monthCursor, setMonthCursor] = useState(() => {
    const d = new Date(); d.setDate(1); d.setHours(0, 0, 0, 0); return d;
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (status) params.status = status;
      if (managerFilter && isAdminLike) params.managerId = managerFilter;
      const [mtR, cR, mgrR] = await Promise.all([
        axios.get(`${API_URL}/api/meetings`, { params, headers: authHeaders() }),
        axios.get(`${API_URL}/api/customers`, { headers: authHeaders() }).catch(() => ({ data: { items: [] } })),
        isAdminLike
          ? axios.get(`${API_URL}/api/team/managers`, { headers: authHeaders() }).catch(() => ({ data: { items: [] } }))
          : Promise.resolve({ data: { items: [] } }),
      ]);
      setItems(mtR.data?.items || []);
      const cs = cR.data?.items || cR.data?.customers || [];
      setCustomers(Array.isArray(cs) ? cs : []);
      const mgrs = mgrR.data?.items || mgrR.data?.managers || mgrR.data?.data || [];
      setManagers(Array.isArray(mgrs) ? mgrs : []);
    } catch (e) {
      toast.error('Failed to load meetings');
    } finally {
      setLoading(false);
    }
  }, [status, managerFilter, isAdminLike]);

  useEffect(() => { load(); }, [load]);

  const saveMeeting = async () => {
    if (!editor.title) { toast.error('Title is required'); return; }
    if (!editor.startAt) { toast.error('Start date/time is required'); return; }
    if (!editor.customerId && !editor.leadId && !editor.dealId) {
      toast.error('Pick at least one of Customer / Lead / Deal'); return;
    }
    const payload = {
      ...editor,
      startAt: fromLocalInput(editor.startAt),
    };
    try {
      if (editor.id) {
        await axios.patch(`${API_URL}/api/meetings/${editor.id}`, payload, { headers: authHeaders() });
        toast.success('Meeting updated');
      } else {
        await axios.post(`${API_URL}/api/meetings`, payload, { headers: authHeaders() });
        toast.success('Meeting scheduled');
      }
      setEditor(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    }
  };

  const downloadIcs = (m) => {
    const url = `${API_URL}/api/meetings/${m.id}/ics`;
    window.open(url, '_blank');
  };

  const completeMeeting = async () => {
    if (!completePayload.result.trim()) { toast.error('Result / comment is required'); return; }
    if (!completePayload.nextStep.trim()) { toast.error('Next step is required'); return; }
    try {
      await axios.patch(`${API_URL}/api/meetings/${completeFor.id}`, {
        status: 'completed',
        result: completePayload.result,
        nextStep: completePayload.nextStep,
      }, { headers: authHeaders() });
      toast.success('Meeting completed');
      setCompleteFor(null);
      setCompletePayload({ result: '', nextStep: '' });
      await load();
    } catch (e) { toast.error('Failed to complete'); }
  };

  const cancelMeeting = async (m) => {
    if (!window.confirm(`Cancel meeting "${m.title}"?`)) return;
    try {
      await axios.delete(`${API_URL}/api/meetings/${m.id}`, { headers: authHeaders() });
      toast.success('Meeting cancelled');
      await load();
    } catch (e) { toast.error('Failed to cancel'); }
  };

  // ── Week grid view ──────────────────────────────────────────────────
  const today = useMemo(() => new Date(), []);
  const weekDays = useMemo(() => {
    const start = new Date(today);
    start.setHours(0, 0, 0, 0);
    const dow = (start.getDay() + 6) % 7; // 0=Mon
    start.setDate(start.getDate() - dow);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [today]);
  const itemsByDay = useMemo(() => {
    const map = {};
    items.forEach((m) => {
      const d = new Date(m.startAt);
      const key = d.toDateString();
      (map[key] = map[key] || []).push(m);
    });
    return map;
  }, [items]);

  // ── Month grid view ─────────────────────────────────────────────────
  const monthGrid = useMemo(() => {
    const first = new Date(monthCursor);
    first.setDate(1);
    const dow = (first.getDay() + 6) % 7; // start from Monday
    const start = new Date(first);
    start.setDate(start.getDate() - dow);
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [monthCursor]);

  const monthLabel = monthCursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const shiftMonth = (delta) => {
    setMonthCursor((c) => {
      const n = new Date(c);
      n.setMonth(n.getMonth() + delta);
      return n;
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3 flex-wrap">
        <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <CalendarCheck className="w-[18px] h-[18px]" />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight">
            {tt('meetingsTitle', 'Meetings')}
          </h1>
          <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed">
            {tt('meetingsSubtitle', 'Calendar of client meetings (calls, in-person, online). Each meeting exports to .ics (open in Google Calendar / Apple Calendar / Outlook).')}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setEditor(emptyMeeting(myRole === 'manager' ? me?.id : ''))}
            data-testid="new-meeting-btn"
            className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold"
          >
            <Plus className="w-4 h-4" /> {tt('meetingsNew', 'New Meeting')}
          </button>
          <button
            onClick={load}
            aria-label="Refresh"
            className="h-9 w-9 rounded-xl border border-[#E4E4E7] bg-white hover:bg-zinc-50 inline-flex items-center justify-center text-zinc-600"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filter + view toggle */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 p-1 bg-zinc-100 rounded-xl">
          <button
            onClick={() => setView('list')}
            className={`h-8 px-3 rounded-lg text-[12px] font-medium transition-colors ${view === 'list' ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600'}`}
          >{tt('meetingsViewList', 'List')}</button>
          <button
            onClick={() => setView('week')}
            className={`h-8 px-3 rounded-lg text-[12px] font-medium transition-colors ${view === 'week' ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600'}`}
          >{tt('meetingsViewWeek', 'Week')}</button>
          <button
            onClick={() => setView('month')}
            className={`h-8 px-3 rounded-lg text-[12px] font-medium transition-colors ${view === 'month' ? 'bg-white shadow-sm text-zinc-900' : 'text-zinc-600'}`}
          >{tt('meetingsViewMonth', 'Month')}</button>
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-9 px-2 rounded-xl border border-[#E4E4E7] bg-white text-[12.5px]"
          data-testid="meetings-status-filter"
        >
          <option value="">{tt('meetingsAllStatuses', 'All statuses')}</option>
          <option value="scheduled">{tt('meetingsStatusScheduled', 'Scheduled')}</option>
          <option value="completed">{tt('meetingsStatusCompleted', 'Completed')}</option>
          <option value="cancelled">{tt('meetingsStatusCancelled', 'Cancelled')}</option>
          <option value="no_show">{tt('meetingsStatusNoShow', 'No-show')}</option>
        </select>
        {isAdminLike && (
          <select
            value={managerFilter}
            onChange={(e) => setManagerFilter(e.target.value)}
            className="h-9 px-2 rounded-xl border border-[#E4E4E7] bg-white text-[12.5px]"
            data-testid="meetings-manager-filter"
          >
            <option value="">{tt('allManagers', 'All managers')}</option>
            {managers.map((m) => (
              <option key={m.id} value={m.id}>{m.name || m.email}</option>
            ))}
          </select>
        )}
      </div>

      {/* LIST VIEW */}
      {view === 'list' && (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-zinc-600 text-[11.5px] uppercase">
                <tr>
                  <th className="text-left px-4 py-2.5 font-semibold">When</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Title</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Type</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Manager</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Location</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Status</th>
                  <th className="text-right px-4 py-2.5 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {loading && items.length === 0 && (
                  <tr><td colSpan={7} className="text-center py-10 text-zinc-400">Loading…</td></tr>
                )}
                {!loading && items.length === 0 && (
                  <tr><td colSpan={7} className="text-center py-10 text-zinc-400">No meetings.</td></tr>
                )}
                {items.map((m) => {
                  const badge = STATUS_BADGE[m.status] || STATUS_BADGE.scheduled;
                  const tdef = TYPES.find((t) => t.value === m.meetingType) || TYPES[0];
                  const TypeIcon = tdef.icon;
                  const managerName = (managers.find((x) => x.id === m.managerId) || {}).name
                                    || (managers.find((x) => x.id === m.managerId) || {}).email
                                    || m.managerName || '—';
                  return (
                    <tr key={m.id} className="hover:bg-zinc-50" data-testid={`meeting-row-${m.id}`}>
                      <td className="px-4 py-3 text-zinc-900">
                        <div className="font-medium">{new Date(m.startAt).toLocaleString()}</div>
                        <div className="text-[11px] text-zinc-500">{m.durationMin || 30} min</div>
                      </td>
                      <td className="px-4 py-3 text-zinc-900 font-medium">{m.title}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 text-[12px] text-zinc-700">
                          <TypeIcon className="w-3.5 h-3.5" />
                          {tdef.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[12px] text-zinc-700">{managerName}</td>
                      <td className="px-4 py-3 text-[12px] text-zinc-600">{m.location || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold ${badge.bg} ${badge.text}`}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button
                            onClick={() => downloadIcs(m)}
                            title=".ics export"
                            className="h-8 w-8 rounded-lg border border-[#E4E4E7] bg-white hover:bg-zinc-50 text-zinc-600 inline-flex items-center justify-center"
                            data-testid={`meeting-ics-${m.id}`}
                          >
                            <Download className="w-3.5 h-3.5" />
                          </button>
                          {m.status === 'scheduled' && (
                            <button
                              onClick={() => setCompleteFor(m)}
                              title="Complete (add summary)"
                              className="h-8 w-8 rounded-lg border border-emerald-100 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 inline-flex items-center justify-center"
                              data-testid={`meeting-complete-${m.id}`}
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {m.status !== 'cancelled' && (
                            <button
                              onClick={() => cancelMeeting(m)}
                              title="Cancel"
                              className="h-8 w-8 rounded-lg border border-rose-100 bg-rose-50 hover:bg-rose-100 text-rose-700 inline-flex items-center justify-center"
                              data-testid={`meeting-cancel-${m.id}`}
                            >
                              <XCircle className="w-3.5 h-3.5" />
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
      )}

      {/* WEEK VIEW */}
      {view === 'week' && (
        <div className="grid grid-cols-1 sm:grid-cols-7 gap-2">
          {weekDays.map((d) => {
            const key = d.toDateString();
            const dayItems = itemsByDay[key] || [];
            const isToday = d.toDateString() === today.toDateString();
            return (
              <div key={key} className={`bg-white border rounded-xl p-2 min-h-[160px] ${isToday ? 'border-indigo-300 ring-2 ring-indigo-100' : 'border-zinc-200'}`}>
                <div className="text-[11px] uppercase text-zinc-500 font-semibold mb-1">{d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</div>
                <div className="space-y-1.5">
                  {dayItems.length === 0 && (
                    <div className="text-[11px] text-zinc-300">—</div>
                  )}
                  {dayItems.map((m) => {
                    const badge = STATUS_BADGE[m.status] || STATUS_BADGE.scheduled;
                    return (
                      <button
                        key={m.id}
                        onClick={() => setEditor({
                          ...m,
                          startAt: m.startAt,
                          notes: m.notes || '',
                        })}
                        className={`w-full text-left px-2 py-1 rounded-md text-[11px] ${badge.bg} ${badge.text} truncate hover:opacity-90`}
                        title={`${m.title} — ${new Date(m.startAt).toLocaleTimeString()}`}
                      >
                        {new Date(m.startAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} — {m.title}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MONTH VIEW (Google-Calendar-style) */}
      {view === 'month' && (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200">
            <button onClick={() => shiftMonth(-1)} className="h-8 w-8 rounded-lg hover:bg-zinc-100 inline-flex items-center justify-center"><ChevronLeft className="w-4 h-4" /></button>
            <h3 className="text-sm font-semibold text-zinc-900 capitalize">{monthLabel}</h3>
            <button onClick={() => shiftMonth(1)} className="h-8 w-8 rounded-lg hover:bg-zinc-100 inline-flex items-center justify-center"><ChevronRight className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-7 text-[10.5px] uppercase text-zinc-500 font-semibold bg-zinc-50 border-b border-zinc-200">
            {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d) => (
              <div key={d} className="px-2 py-2 text-center">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-px bg-zinc-200">
            {monthGrid.map((d, i) => {
              const sameMonth = d.getMonth() === monthCursor.getMonth();
              const isToday = d.toDateString() === today.toDateString();
              const dayItems = itemsByDay[d.toDateString()] || [];
              return (
                <div
                  key={i}
                  className={`bg-white min-h-[96px] p-1.5 flex flex-col gap-1 ${sameMonth ? '' : 'opacity-40'} ${isToday ? 'ring-2 ring-indigo-300 ring-inset' : ''}`}
                  data-testid={`month-cell-${d.toISOString().slice(0,10)}`}
                >
                  <div className="text-[11px] font-semibold text-zinc-700 flex items-center justify-between">
                    <span>{d.getDate()}</span>
                    {dayItems.length > 0 && (
                      <span className="text-[9px] text-zinc-400">{dayItems.length}</span>
                    )}
                  </div>
                  <div className="space-y-0.5 overflow-hidden">
                    {dayItems.slice(0, 3).map((m) => {
                      const badge = STATUS_BADGE[m.status] || STATUS_BADGE.scheduled;
                      return (
                        <button
                          key={m.id}
                          onClick={() => setEditor({ ...m, startAt: m.startAt, notes: m.notes || '' })}
                          className={`w-full text-left px-1.5 py-0.5 rounded text-[10px] truncate ${badge.bg} ${badge.text} hover:opacity-90`}
                          title={`${m.title} — ${new Date(m.startAt).toLocaleString()}`}
                        >
                          {new Date(m.startAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} {m.title}
                        </button>
                      );
                    })}
                    {dayItems.length > 3 && (
                      <div className="text-[10px] text-zinc-400 pl-1">+ {dayItems.length - 3} more…</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Editor Modal */}
      {editor && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" data-testid="meeting-editor-modal">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[92vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-zinc-200 px-6 py-4 flex items-center justify-between z-10">
              <h2 className="text-lg font-semibold text-zinc-900">
                {editor.id ? 'Edit Meeting' : 'New Meeting'}
              </h2>
              <button onClick={() => setEditor(null)} className="h-8 w-8 rounded-lg hover:bg-zinc-100 inline-flex items-center justify-center"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Title*</label>
                <input
                  value={editor.title}
                  onChange={(e) => setEditor({ ...editor, title: e.target.value })}
                  placeholder="Discovery call with John Smith"
                  className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
                  data-testid="meeting-editor-title"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-zinc-700 mb-2">Start*</label>
                  <input
                    type="datetime-local"
                    value={toLocalInput(editor.startAt)}
                    onChange={(e) => setEditor({ ...editor, startAt: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
                    data-testid="meeting-editor-start"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-2">Duration (min)</label>
                  <input
                    type="number"
                    min="5" step="5"
                    value={editor.durationMin}
                    onChange={(e) => setEditor({ ...editor, durationMin: parseInt(e.target.value || 30, 10) })}
                    className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
                    data-testid="meeting-editor-duration"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Type</label>
                <div className="flex gap-2 flex-wrap">
                  {TYPES.map((t) => {
                    const Icon = t.icon;
                    return (
                      <button
                        key={t.value}
                        type="button"
                        onClick={() => setEditor({ ...editor, meetingType: t.value })}
                        className={`inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border text-[12.5px] font-medium transition-colors ${
                          editor.meetingType === t.value
                            ? 'bg-[#18181B] text-white border-[#18181B]'
                            : 'bg-white text-zinc-700 border-[#E4E4E7] hover:bg-zinc-50'
                        }`}
                        data-testid={`meeting-type-${t.value}`}
                      >
                        <Icon className="w-3.5 h-3.5" /> {t.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {isAdminLike && (
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-2">Manager (owner)</label>
                  <select
                    value={editor.managerId || ''}
                    onChange={(e) => setEditor({ ...editor, managerId: e.target.value })}
                    className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm"
                    data-testid="meeting-editor-manager"
                  >
                    <option value="">— Use my user —</option>
                    {managers.map((m) => (
                      <option key={m.id} value={m.id}>{m.name || m.email}</option>
                    ))}
                  </select>
                  <p className="text-[11px] text-zinc-500 mt-1">Pick a manager who owns this meeting. Defaults to your account.</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Customer</label>
                <select
                  value={editor.customerId}
                  onChange={(e) => setEditor({ ...editor, customerId: e.target.value })}
                  className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm"
                  data-testid="meeting-editor-customer"
                >
                  <option value="">— None —</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.firstName || ''} {c.lastName || ''} {c.email ? `(${c.email})` : ''}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-zinc-500 mt-1">Pick at least one of Customer / Lead / Deal.</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-2">Lead ID</label>
                  <input
                    value={editor.leadId}
                    onChange={(e) => setEditor({ ...editor, leadId: e.target.value })}
                    placeholder="lead_..."
                    className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-2">Deal ID</label>
                  <input
                    value={editor.dealId}
                    onChange={(e) => setEditor({ ...editor, dealId: e.target.value })}
                    placeholder="deal_..."
                    className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Location / Link</label>
                <input
                  value={editor.location || ''}
                  onChange={(e) => setEditor({ ...editor, location: e.target.value })}
                  placeholder="Zoom URL / Google Meet / phone / address"
                  className="w-full h-10 px-3 rounded-xl border border-zinc-300 bg-white text-sm"
                  data-testid="meeting-editor-location"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Comment BEFORE meeting (agenda / notes)</label>
                <textarea
                  value={editor.notes || ''}
                  onChange={(e) => setEditor({ ...editor, notes: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 rounded-xl border border-zinc-300 bg-white text-sm"
                  placeholder="What you plan to discuss with the client…"
                  data-testid="meeting-editor-notes"
                />
              </div>
              {editor.id && editor.status === 'completed' && (editor.result || editor.nextStep) && (
                <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 space-y-2">
                  <div className="text-[12px] uppercase tracking-wider text-emerald-700 font-semibold">Post-meeting summary</div>
                  {editor.result && <div className="text-sm text-emerald-900"><b>Result:</b> {editor.result}</div>}
                  {editor.nextStep && <div className="text-sm text-emerald-900"><b>Next step:</b> {editor.nextStep}</div>}
                </div>
              )}
            </div>
            <div className="sticky bottom-0 bg-white border-t border-zinc-200 px-6 py-4 flex items-center justify-end gap-2">
              <button onClick={() => setEditor(null)} className="h-10 px-4 rounded-xl border border-zinc-300 bg-white hover:bg-zinc-50 text-sm font-medium">Cancel</button>
              <button
                onClick={saveMeeting}
                className="h-10 px-5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-sm font-semibold text-white inline-flex items-center gap-2"
                data-testid="meeting-editor-save"
              >
                <Save className="w-4 h-4" /> {editor.id ? 'Save changes' : 'Schedule meeting'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Complete Modal */}
      {completeFor && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" data-testid="meeting-complete-modal">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full">
            <div className="px-6 py-4 border-b border-zinc-200">
              <h3 className="text-base font-semibold text-zinc-900">Complete meeting</h3>
              <p className="text-[12px] text-zinc-500 mt-0.5">{completeFor.title}</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Result / Comment AFTER meeting*</label>
                <textarea
                  value={completePayload.result}
                  onChange={(e) => setCompletePayload({ ...completePayload, result: e.target.value })}
                  rows={3}
                  placeholder="What was discussed / agreed?"
                  className="w-full px-3 py-2 rounded-xl border border-zinc-300 bg-white text-sm"
                  data-testid="meeting-complete-result"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-2">Next step*</label>
                <textarea
                  value={completePayload.nextStep}
                  onChange={(e) => setCompletePayload({ ...completePayload, nextStep: e.target.value })}
                  rows={2}
                  placeholder="What's the next action / when?"
                  className="w-full px-3 py-2 rounded-xl border border-zinc-300 bg-white text-sm"
                  data-testid="meeting-complete-nextstep"
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-zinc-200 flex items-center justify-end gap-2">
              <button onClick={() => setCompleteFor(null)} className="h-10 px-4 rounded-xl border border-zinc-300 bg-white text-sm font-medium">Cancel</button>
              <button
                onClick={completeMeeting}
                className="h-10 px-5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-sm font-semibold text-white inline-flex items-center gap-2"
                data-testid="meeting-complete-submit"
              >
                <CheckCircle2 className="w-4 h-4" /> Complete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
