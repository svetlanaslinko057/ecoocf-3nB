/**
 * Master-Admin → Email Outbox
 *
 * Полный UI для email-канала (Resend / SMTP / dry_run):
 *   1. Карточка отправки тестового письма + chip-индикатор провайдера + лимиты Resend free-tier
 *   2. Таблица истории email_outbox с фильтром по event, статусами, drawer с HTML и provider_response
 *
 * Endpoints:
 *   GET  /api/admin/email-outbox?limit=200&event=&status=
 *   POST /api/admin/notifications/email/test  { to, subject?, html?, text? }
 *   GET  /api/admin/notifications/email/usage  { free_tier:{daily/monthly} }
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Mail,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Eye,
  Filter,
  X,
  Send,
  Info,
} from 'lucide-react';

import WhiteSelect from '../../components/ui/WhiteSelect';
import { useLang } from '../../i18n/LanguageContext';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const STATUS_STYLE = {
  sent:    { label: 'sent',    color: 'bg-emerald-50 text-emerald-700 ring-emerald-200', icon: CheckCircle2 },
  dry_run: { label: 'dry-run', color: 'bg-amber-50   text-amber-700   ring-amber-200',   icon: Eye },
  failed:  { label: 'failed',  color: 'bg-rose-50    text-rose-700    ring-rose-200',    icon: XCircle },
  queued:  { label: 'queued',  color: 'bg-zinc-100   text-zinc-700    ring-zinc-200',    icon: Mail },
};

// Provider hints resolved at render-time via t() so the help text follows the active locale.
const PROVIDER_STYLE = {
  resend:  { label: 'resend',  hintKey: 'outboxLiveResend',          chip: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  smtp:    { label: 'smtp',    hintKey: 'outboxLiveSmtp',            chip: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  dry_run: { label: 'dry_run', hintKey: 'outboxEmailNotConfigured',  chip: 'bg-amber-50 text-amber-700 ring-amber-200' },
};

export default function EmailOutboxPage({ embedded = false }) {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [provider, setProvider] = useState('dry_run');
  const [loading, setLoading] = useState(true);
  const [filterEvent, setFilterEvent] = useState('');
  const [selected, setSelected] = useState(null);

  // Test form state
  const [testTo, setTestTo] = useState('');
  const [testSubject, setTestSubject] = useState('BIBI Cars · test email');
  const [sending, setSending] = useState(false);

  // Free-tier usage counters (Resend: 100/day, 3000/month)
  const [usage, setUsage] = useState({
    daily_limit: 100, monthly_limit: 3000,
    daily_used: 0, monthly_used: 0,
    daily_remaining: 100, monthly_remaining: 3000,
  });

  const loadUsage = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/admin/notifications/email/usage`, { headers: authHeaders() });
      if (r.data?.free_tier) setUsage(r.data.free_tier);
    } catch { /* silent */ }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/email-outbox?limit=200`, { headers: authHeaders() });
      setItems(r.data?.items || []);
      setProvider(r.data?.provider || 'dry_run');
    } catch {
      toast.error('Failed to load email outbox');
    } finally {
      setLoading(false);
    }
    loadUsage();
  }, [loadUsage]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, [load]);

  const filtered = useMemo(
    () => items.filter((x) => !filterEvent || x.event === filterEvent),
    [items, filterEvent],
  );
  const events = Array.from(new Set(items.map((x) => x.event))).filter(Boolean);
  const pStyle = PROVIDER_STYLE[provider] || PROVIDER_STYLE.dry_run;

  const sendTest = async () => {
    const to = (testTo || '').trim();
    if (!to || !to.includes('@')) {
      toast.error(t('outboxEnterValidEmail'));
      return;
    }
    setSending(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/notifications/email/test`,
        { to, subject: testSubject || 'BIBI Cars · test email' },
        { headers: authHeaders() },
      );
      const mode = r.data?.mode || provider;
      const ok = r.data?.success;
      const err = r.data?.outbox?.provider_error;
      if (ok && mode !== 'dry_run') {
        toast.success(t('outboxEmailSent').replace('{mode}', mode));
      } else if (mode === 'dry_run') {
        toast.info(t('outboxEmailDryRun'));
      } else {
        toast.error(t('outboxErrorGeneric').replace('{err}', err || 'unknown'));
      }
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Email test failed');
    } finally {
      setSending(false);
    }
  };

  // Free-tier progress styling
  const dailyPct = Math.min(100, Math.round((usage.daily_used / usage.daily_limit) * 100));
  const monthlyPct = Math.min(100, Math.round((usage.monthly_used / usage.monthly_limit) * 100));
  const dailyBar = dailyPct > 90 ? 'bg-rose-500' : dailyPct > 70 ? 'bg-amber-500' : 'bg-emerald-500';
  const monthlyBar = monthlyPct > 90 ? 'bg-rose-500' : monthlyPct > 70 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className={embedded ? '' : 'p-6 max-w-[1280px] mx-auto'}>
      {/* ─── Test email panel ─── */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden mb-4">
        <div className="px-4 sm:px-5 py-4 border-b border-[#F4F4F5] flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Send className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] sm:text-[16px] font-semibold text-[#18181B] leading-tight">
              Send test email
            </h2>
            <p className="text-[12px] text-[#71717A] mt-0.5 flex items-center gap-1.5 flex-wrap">
              <span>Provider:</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ring-1 ${pStyle.chip}`}>
                {pStyle.label}
              </span>
              {pStyle.hintKey && (
                <span className="inline-flex items-center gap-1 text-[#71717A]">
                  <Info className="w-3 h-3" />
                  {t(pStyle.hintKey)}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Free-tier progress (Resend) — visible whenever provider is resend OR dry_run */}
        {(provider === 'resend' || provider === 'dry_run') && (
          <div className="px-4 sm:px-5 py-3 border-b border-[#F4F4F5] bg-zinc-50/40 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-[11px] uppercase tracking-wider text-[#71717A] font-semibold">Daily</span>
                <span className="text-[12px] text-[#3F3F46] tabular-nums">
                  {usage.daily_used} / {usage.daily_limit}
                  <span className="text-[#A1A1AA] ml-1">({usage.daily_remaining} left)</span>
                </span>
              </div>
              <div className="w-full h-1.5 bg-zinc-200 rounded-full overflow-hidden">
                <div className={`h-full ${dailyBar} transition-all`} style={{ width: `${dailyPct}%` }} />
              </div>
            </div>
            <div>
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-[11px] uppercase tracking-wider text-[#71717A] font-semibold">Monthly</span>
                <span className="text-[12px] text-[#3F3F46] tabular-nums">
                  {usage.monthly_used} / {usage.monthly_limit}
                  <span className="text-[#A1A1AA] ml-1">({usage.monthly_remaining} left)</span>
                </span>
              </div>
              <div className="w-full h-1.5 bg-zinc-200 rounded-full overflow-hidden">
                <div className={`h-full ${monthlyBar} transition-all`} style={{ width: `${monthlyPct}%` }} />
              </div>
            </div>
          </div>
        )}

        <div className="px-4 sm:px-5 py-4 flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="text-[11.5px] uppercase tracking-wider text-[#71717A] font-semibold">
              Recipient (email)
            </label>
            <input
              type="email"
              value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              placeholder="you@example.com"
              className="mt-1 w-full h-10 px-3 rounded-xl border border-[#E4E4E7] bg-white text-[14px] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
              data-testid="email-test-to"
            />
          </div>
          <div className="flex-[2] min-w-[240px]">
            <label className="text-[11.5px] uppercase tracking-wider text-[#71717A] font-semibold">
              Subject
            </label>
            <input
              type="text"
              value={testSubject}
              onChange={(e) => setTestSubject(e.target.value)}
              className="mt-1 w-full h-10 px-3 rounded-xl border border-[#E4E4E7] bg-white text-[14px] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
              data-testid="email-test-subject"
            />
          </div>
          <button
            type="button"
            onClick={sendTest}
            disabled={sending || !testTo}
            className="h-10 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white text-[13px] font-semibold disabled:opacity-50 inline-flex items-center gap-1.5"
            data-testid="email-test-send"
          >
            <Send className={`w-3.5 h-3.5 ${sending ? 'animate-pulse' : ''}`} />
            {sending ? 'Sending…' : 'Send test'}
          </button>
        </div>
      </div>

      {/* ─── Outbox table ─── */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b border-[#F4F4F5]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
                <Mail className="w-4 h-4" />
              </div>
              <h2 className="text-[15px] sm:text-[16px] font-semibold text-[#18181B] leading-tight truncate">
                Email outbox
              </h2>
            </div>
            <button
              onClick={load}
              data-testid="email-refresh"
              disabled={loading}
              aria-label="Refresh"
              className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white disabled:opacity-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 shrink-0 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} strokeWidth={2.5} />
            </button>
          </div>

          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-[#71717A] shrink-0" />
            <div className="min-w-[160px] flex-1 sm:flex-none">
              <WhiteSelect
                value={filterEvent}
                onChange={(e) => setFilterEvent(e.target.value)}
                data-testid="email-filter-event"
              >
                <option value="">All events</option>
                {events.map((e) => <option key={e} value={e}>{e}</option>)}
              </WhiteSelect>
            </div>
            {filterEvent && (
              <button
                type="button"
                onClick={() => setFilterEvent('')}
                className="inline-flex items-center gap-1 text-[11.5px] text-[#71717A] hover:text-[#18181B]"
              >
                <X className="w-3 h-3" /> clear
              </button>
            )}
            <span className="ml-auto text-[11.5px] text-[#71717A]">
              {filtered.length}{items.length !== filtered.length ? ` / ${items.length}` : ''} events
            </span>
          </div>
        </div>

        {/* Table (≥ sm) */}
        <div className="hidden sm:block">
          <table className="w-full text-sm">
            <thead className="bg-[#FAFAFA] text-[10.5px] uppercase tracking-[0.12em] text-[#71717A]">
              <tr>
                <th className="text-left px-5 py-2.5 font-semibold">Status</th>
                <th className="text-left px-5 py-2.5 font-semibold">Event</th>
                <th className="text-left px-5 py-2.5 font-semibold">Recipient</th>
                <th className="text-left px-5 py-2.5 font-semibold">Subject</th>
                <th className="text-left px-5 py-2.5 font-semibold">Time</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && !loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-[#A1A1AA] text-[13px]">
                    Outbox is empty — events have not been triggered yet.
                  </td>
                </tr>
              ) : filtered.map((e) => {
                const s = STATUS_STYLE[e.status] || STATUS_STYLE.queued;
                const Icon = s.icon;
                return (
                  <tr
                    key={e.id}
                    onClick={() => setSelected(e)}
                    className="border-t border-[#F4F4F5] hover:bg-[#FAFAFA] cursor-pointer"
                  >
                    <td className="px-5 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ring-1 ${s.color}`}>
                        <Icon className="w-3 h-3" /> {s.label}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-[12.5px] text-[#3F3F46] font-medium">{e.event}</td>
                    <td className="px-5 py-3 text-[13px] text-[#3F3F46]">{e.to}</td>
                    <td className="px-5 py-3 text-[13px] text-[#18181B] truncate max-w-[420px]">{e.subject}</td>
                    <td className="px-5 py-3 text-[11.5px] text-[#71717A] tabular-nums">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Eye className="w-4 h-4 text-[#A1A1AA] inline" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Stacked (mobile) */}
        <div className="sm:hidden divide-y divide-[#F4F4F5]">
          {filtered.length === 0 && !loading ? (
            <div className="px-4 py-10 text-center text-[#A1A1AA] text-[13px]">
              Outbox is empty.
            </div>
          ) : filtered.map((e) => {
            const s = STATUS_STYLE[e.status] || STATUS_STYLE.queued;
            const Icon = s.icon;
            return (
              <button
                key={e.id}
                type="button"
                onClick={() => setSelected(e)}
                className="w-full text-left px-4 py-3 hover:bg-[#FAFAFA] focus:outline-none focus-visible:bg-[#FAFAFA]"
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] font-semibold ring-1 ${s.color}`}>
                    <Icon className="w-3 h-3" /> {s.label}
                  </span>
                  <span className="text-[10.5px] text-[#71717A] tabular-nums">
                    {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                  </span>
                </div>
                <p className="text-[13.5px] text-[#18181B] font-semibold leading-tight truncate">
                  {e.subject || e.event}
                </p>
                <p className="text-[12px] text-[#71717A] mt-0.5 truncate">
                  → {e.to} <span className="text-[#D4D4D8] mx-1">·</span> {e.event}
                </p>
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── Drawer ─── */}
      {selected && (
        <div className="fixed inset-0 z-40 flex" onClick={() => setSelected(null)}>
          <div className="flex-1 bg-zinc-900/40" />
          <aside
            className="w-full max-w-2xl bg-white shadow-2xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b border-[#E4E4E7] px-5 py-4 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] text-[#A1A1AA] truncate">{selected.id}</p>
                <h2 className="font-semibold text-[#18181B] mt-0.5 leading-tight">{selected.subject}</h2>
                <p className="text-[12px] text-[#71717A] mt-0.5">→ {selected.to} · {selected.provider || ''}</p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="shrink-0 p-1.5 rounded-lg hover:bg-[#FAFAFA]"
                aria-label="Close"
              >
                <X className="w-4 h-4 text-[#71717A]" />
              </button>
            </div>
            <div className="p-5 space-y-3">
              <div
                className="border border-[#E4E4E7] rounded-xl p-4 bg-white prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: selected.html || '' }}
              />
              {selected.provider_response && (
                <pre className="bg-zinc-50 border border-[#E4E4E7] rounded-xl p-3 text-[11.5px] text-[#3F3F46] overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(selected.provider_response, null, 2)}
                </pre>
              )}
              {selected.provider_error && (
                <pre className="bg-rose-50 border border-rose-100 rounded-xl p-3 text-[11.5px] text-rose-700 overflow-x-auto whitespace-pre-wrap">
                  {selected.provider_error}
                </pre>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
