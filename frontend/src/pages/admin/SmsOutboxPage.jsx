/**
 * Master-Admin → SMS Outbox
 *
 * Зеркальная копия EmailOutboxPage для SMS-канала.
 * Показывает историю всех попыток отправки SMS (sent/dry_run/failed),
 * текущий провайдер (textbelt / textbelt_free / dry_run) и позволяет
 * отправить тестовое SMS из UI.
 *
 * Endpoints:
 *   GET  /api/admin/sms-outbox?limit=200&event=&status=
 *   POST /api/admin/notifications/sms/test  { to, message }
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Smartphone,
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
  queued:  { label: 'queued',  color: 'bg-zinc-100   text-zinc-700    ring-zinc-200',    icon: Smartphone },
};

// Provider hints resolved at render-time via t() so the help text follows the active locale.
const PROVIDER_STYLE = {
  textbelt:      { label: 'textbelt (paid)',  hintKey: null,                chip: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  textbelt_free: { label: 'textbelt (free)',  hintKey: 'outboxSmsFreeDesc', chip: 'bg-sky-50 text-sky-700 ring-sky-200' },
  dry_run:       { label: 'dry_run',          hintKey: 'outboxSmsDisabled', chip: 'bg-amber-50 text-amber-700 ring-amber-200' },
};

export default function SmsOutboxPage({ embedded = false }) {
  const { t } = useLang();
  const [items, setItems] = useState([]);
  const [provider, setProvider] = useState('dry_run');
  const [loading, setLoading] = useState(true);
  const [filterEvent, setFilterEvent] = useState('');
  const [selected, setSelected] = useState(null);

  // Test SMS form state
  const [testPhone, setTestPhone] = useState('');
  const [testMsg, setTestMsg] = useState('BIBI Cars: SMS test ✓');
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/sms-outbox?limit=200`, { headers: authHeaders() });
      setItems(r.data?.items || []);
      setProvider(r.data?.provider || 'dry_run');
    } catch {
      toast.error('Failed to load SMS outbox');
    } finally {
      setLoading(false);
    }
  }, []);

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
    const phone = (testPhone || '').trim();
    if (!phone) {
      toast.error(t('outboxEnterPhone'));
      return;
    }
    setSending(true);
    try {
      const r = await axios.post(
        `${API_URL}/api/admin/notifications/sms/test`,
        { to: phone, message: testMsg || 'BIBI Cars: SMS test' },
        { headers: authHeaders() },
      );
      const mode = r.data?.mode || provider;
      const ok = r.data?.success;
      const err = r.data?.outbox?.provider_error || r.data?.error;
      if (ok) {
        toast.success(t('outboxSmsSent').replace('{mode}', mode));
      } else if (mode === 'dry_run') {
        toast.info(t('outboxSmsDryRun'));
      } else {
        toast.error(t('outboxSendError').replace('{err}', err || 'unknown'));
      }
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'SMS test failed');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className={embedded ? '' : 'p-6 max-w-[1280px] mx-auto'}>
      {/* ─── Test SMS panel ─── */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden mb-4">
        <div className="px-4 sm:px-5 py-4 border-b border-[#F4F4F5] flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Send className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] sm:text-[16px] font-semibold text-[#18181B] leading-tight">
              Send test SMS
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
        <div className="px-4 sm:px-5 py-4 flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="text-[11.5px] uppercase tracking-wider text-[#71717A] font-semibold">
              Phone (E.164)
            </label>
            <input
              type="tel"
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
              placeholder="+359875313158"
              className="mt-1 w-full h-10 px-3 rounded-xl border border-[#E4E4E7] bg-white text-[14px] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
              data-testid="sms-test-phone"
            />
          </div>
          <div className="flex-[2] min-w-[240px]">
            <label className="text-[11.5px] uppercase tracking-wider text-[#71717A] font-semibold">
              Message (≤ 320 chars)
            </label>
            <input
              type="text"
              value={testMsg}
              onChange={(e) => setTestMsg(e.target.value)}
              maxLength={320}
              className="mt-1 w-full h-10 px-3 rounded-xl border border-[#E4E4E7] bg-white text-[14px] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15"
              data-testid="sms-test-message"
            />
          </div>
          <button
            type="button"
            onClick={sendTest}
            disabled={sending || !testPhone}
            className="h-10 px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white text-[13px] font-semibold disabled:opacity-50 inline-flex items-center gap-1.5"
            data-testid="sms-test-send"
          >
            <Send className={`w-3.5 h-3.5 ${sending ? 'animate-pulse' : ''}`} />
            {sending ? 'Sending…' : 'Send test'}
          </button>
        </div>
      </div>

      {/* ─── Outbox ─── */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
        <div className="px-4 sm:px-5 py-4 border-b border-[#F4F4F5]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
                <Smartphone className="w-4 h-4" />
              </div>
              <h2 className="text-[15px] sm:text-[16px] font-semibold text-[#18181B] leading-tight truncate">
                SMS outbox
              </h2>
            </div>
            <button
              onClick={load}
              data-testid="sms-refresh"
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
                data-testid="sms-filter-event"
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
                <th className="text-left px-5 py-2.5 font-semibold">Message</th>
                <th className="text-left px-5 py-2.5 font-semibold">Time</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && !loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-[#A1A1AA] text-[13px]">
                    SMS outbox empty — no events have been triggered yet.
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
                    <td className="px-5 py-3 text-[13px] text-[#18181B] truncate max-w-[420px]">{e.message}</td>
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
              SMS outbox empty.
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
                  {e.message || e.event}
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
                <h2 className="font-semibold text-[#18181B] mt-0.5 leading-tight">
                  → {selected.to}
                </h2>
                <p className="text-[12px] text-[#71717A] mt-0.5">{selected.event} · {selected.provider}</p>
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
              <div className="border border-[#E4E4E7] rounded-xl p-4 bg-white text-[13.5px] text-[#18181B] whitespace-pre-wrap">
                {selected.message}
              </div>
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
