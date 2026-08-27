/**
 * AutomationExceptionsPage — Phase E UI
 * =====================================
 *
 * Surface low-confidence resolver hits & transfer rejects in a single
 * table so managers can approve (Confirm) or dismiss (Reject) each one.
 *
 * Columns: VIN · Container · Current Vessel · Candidate · Reason · Confidence · Actions.
 * Status filters: pending (default) · confirmed · rejected · all.
 * Refreshes every 30 s + after every action.
 *
 * Endpoints used:
 *   GET  /api/admin/identity/exceptions?status_filter=...
 *   POST /api/admin/identity/exceptions/{id}/confirm
 *   POST /api/admin/identity/exceptions/{id}/reject
 *   GET  /api/admin/identity/exceptions/count  (for badge elsewhere)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

import { useLang } from '../../i18n';
const API =
  process.env.REACT_APP_BACKEND_URL ||
  import.meta?.env?.REACT_APP_BACKEND_URL ||
  '';

const STATUS_TABS = [
  { id: 'pending', label: 'Awaiting', color: '#f59e0b' },
  { id: 'confirmed', label: 'Confirmed', color: '#10b981' },
  { id: 'rejected', label: 'Rejected', color: '#ef4444' },
  { id: 'all', label: 'All', color: '#64748b' },
];

const KIND_LABELS = {
  low_confidence_vessel: 'Low confidence (vessel)',
  transfer_rejected: 'Transhipment rejected',
};

const REASON_LABELS = {
  low_confidence: 'Confidence < 0.75',
  teleport: 'Vessel \'teleported\'',
  progress_regression: 'Progress reverted',
  low_confidence_vessel: 'Confidence < 0.85',
};

function fmtConfidence(v) {
  if (v == null) return <span className="text-[#A1A1AA] text-xs">—</span>;
  const pct = Math.round(Number(v) * 100);
  let bg = '#A1A1AA';
  if (pct >= 85) bg = '#16A34A';
  else if (pct >= 50) bg = '#F59E0B';
  else bg = '#DC2626';
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold text-white"
      style={{ background: bg }}
    >
      {pct}%
    </span>
  );
}

function authHeaders() {
  const t = localStorage.getItem('auth_token') || localStorage.getItem('token');
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function AutomationExceptionsPage() {
  const { t } = useLang();
  const [status, setStatus] = useState('pending');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [actingId, setActingId] = useState(null);
  const [counts, setCounts] = useState({ pending: 0 });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(
        `${API}/api/admin/identity/exceptions?status_filter=${status}&limit=100`,
        { headers: authHeaders() },
      );
      setItems(r.data.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  }, [status]);

  const loadCount = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/admin/identity/exceptions/count`, {
        headers: authHeaders(),
      });
      setCounts({ pending: r.data.pending || 0 });
    } catch {}
  }, []);

  useEffect(() => {
    load();
    loadCount();
  }, [load, loadCount]);

  useEffect(() => {
    const t = setInterval(() => {
      load();
      loadCount();
    }, 30000);
    return () => clearInterval(t);
  }, [load, loadCount]);

  const confirmOne = async (id) => {
    setActingId(id);
    try {
      await axios.post(
        `${API}/api/admin/identity/exceptions/${id}/confirm`,
        {},
        { headers: authHeaders() },
      );
      toast.success(t('adm_confirmed_the_system_performed_the_action'));
      await load();
      await loadCount();
    } catch (e) {
      toast.error(`${t('r9_error')}: ${e.response?.data?.detail || e.message}`);
    } finally {
      setActingId(null);
    }
  };

  const rejectOne = async (id) => {
    setActingId(id);
    try {
      await axios.post(
        `${API}/api/admin/identity/exceptions/${id}/reject`,
        {},
        { headers: authHeaders() },
      );
      toast(t('adm3_f8591051d0'), { icon: '🚫' });
      await load();
      await loadCount();
    } catch (e) {
      toast.error(`${t('r9_error')}: ${e.response?.data?.detail || e.message}`);
    } finally {
      setActingId(null);
    }
  };

  const summary = useMemo(() => {
    const by = { low: 0, medium: 0, high: 0 };
    for (const it of items) {
      const c = (it.data || {}).finalConfidence ?? (it.data?.vessel?.confidence) ?? 0;
      if (c >= 0.85) by.high++;
      else if (c >= 0.5) by.medium++;
      else by.low++;
    }
    return by;
  }, [items]);

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* ── Page header ───────────────────────────────────────── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0">
          <h1
            className="text-xl sm:text-2xl md:text-3xl font-bold text-[#18181B] leading-tight"
            style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
          >
            {t('adm_exception_center')}
          </h1>
          <div className="mt-1 text-[12px] sm:text-sm text-[#71717A] leading-relaxed">
            Resolver + Transfer detector · {counts.pending} {t('r9_await_action')}
          </div>
        </div>
        {/* Status tabs — horizontal scroll on mobile */}
        <div className="flex flex-nowrap gap-1.5 sm:gap-2 -mx-1 sm:mx-0 px-1 sm:px-0 overflow-x-auto sm:overflow-visible no-scrollbar">
          {STATUS_TABS.map((tab) => {
            const isActive = status === tab.id;
            return (
              <button
                key={tab.id}
                data-testid={`tab-${tab.id}`}
                onClick={() => setStatus(tab.id)}
                className={`inline-flex items-center h-9 sm:h-10 px-3 sm:px-4 shrink-0 rounded-xl text-[13px] sm:text-sm font-medium transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10 ${
                  isActive
                    ? 'bg-[#18181B] text-white'
                    : 'border border-[#E4E4E7] bg-white text-[#18181B] hover:bg-zinc-50'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-[#FCA5A5] bg-[#FEF2F2] px-3 py-2.5 text-[13px] text-[#7F1D1D]">
          {t('r9_error')}: {error}
        </div>
      )}

      {/* ── Items: MOBILE cards · DESKTOP table ────────────────── */}
      <section className="rounded-2xl border border-[#E4E4E7] bg-white overflow-hidden">
        {/* MOBILE — cards */}
        <div className="sm:hidden divide-y divide-[#F4F4F5]">
          {loading && items.length === 0 && (
            <div className="px-4 py-10 text-center text-sm text-[#71717A]">{t('adm_loading_3')}</div>
          )}
          {!loading && items.length === 0 && (
            <div className="px-4 py-10 text-center text-sm text-[#A1A1AA]">
              {status === 'pending' ? t('adm3_5bba2a834b') : t('adm3_221781f248')}
            </div>
          )}
          {items.map((it) => {
            const sh = it.shipment || {};
            const data = it.data || {};
            const candName =
              data.newName ||
              (data.vessel && data.vessel.value && data.vessel.value.name) ||
              (data.vessel && data.vessel.name) ||
              '—';
            const candMmsi =
              data.newMmsi ||
              (data.vessel && data.vessel.value && data.vessel.value.mmsi) ||
              (data.vessel && data.vessel.mmsi) ||
              null;
            const conf =
              data.finalConfidence ??
              data.confidence ??
              (data.vessel && data.vessel.confidence) ??
              null;
            const cur = sh.currentVessel || {};
            const reasonKey = it.reason || it.kind;
            return (
              <div key={it._id} className="px-4 py-3.5 space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <code className="font-mono text-[11.5px] text-[#18181B] truncate block">{sh.vin || '—'}</code>
                    <code className="font-mono text-[10.5px] text-[#A1A1AA] truncate block">{sh.container || '—'}</code>
                  </div>
                  {fmtConfidence(conf)}
                </div>
                <div className="grid grid-cols-2 gap-3 text-[11.5px]">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">{t('adm_current_vessel')}</div>
                    <div className="font-semibold text-[#18181B] truncate">{cur.name || '—'}</div>
                    <div className="text-[10px] text-[#A1A1AA] font-mono">MMSI {cur.mmsi || '—'}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold">{t('adm_candidate')}</div>
                    <div className="font-semibold text-[#18181B] truncate">{candName}</div>
                    <div className="text-[10px] text-[#A1A1AA] font-mono">MMSI {candMmsi || '—'}</div>
                  </div>
                </div>
                <div className="text-[11.5px] text-[#71717A]">
                  <span className="text-[#18181B] font-medium">{KIND_LABELS[it.kind] || it.kind}</span>
                  <span className="mx-1 text-[#D4D4D8]">·</span>
                  {REASON_LABELS[reasonKey] || reasonKey || '—'}
                </div>
                <div className="flex items-center justify-between gap-2 pt-1">
                  <span className="text-[10.5px] text-[#A1A1AA]">
                    {it.createdAt ? new Date(it.createdAt).toLocaleString() : '—'}
                  </span>
                  {it.status === 'pending' ? (
                    <div className="flex gap-2">
                      <button
                        data-testid={`confirm-${it._id}`}
                        disabled={actingId === it._id}
                        onClick={() => confirmOne(it._id)}
                        className="inline-flex items-center h-8 px-3 rounded-xl bg-[#18181B] text-[11px] font-medium text-white hover:bg-[#27272A] transition-colors disabled:opacity-40"
                      >
                        {t('adm_confirm')}
                      </button>
                      <button
                        data-testid={`reject-${it._id}`}
                        disabled={actingId === it._id}
                        onClick={() => rejectOne(it._id)}
                        className="inline-flex items-center h-8 px-3 rounded-xl border border-[#E4E4E7] bg-white text-[11px] font-medium text-[#18181B] hover:bg-zinc-50 transition-colors disabled:opacity-40"
                      >
                        {t('adm_decline')}
                      </button>
                    </div>
                  ) : (
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-[#E4E4E7] bg-white text-[10.5px] font-semibold ${it.status === 'confirmed' ? 'text-[#18181B]' : 'text-[#71717A]'}`}>
                      <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: it.status === 'confirmed' ? '#16A34A' : '#DC2626' }} />
                      {it.status}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* DESKTOP — table */}
        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full text-sm" data-testid="exceptions-table">
            <thead className="bg-zinc-50 text-[#71717A]">
              <tr>
                <Th>VIN</Th>
                <Th>{t('adm_container_3')}</Th>
                <Th>{t('adm_current_vessel')}</Th>
                <Th>{t('adm_candidate')}</Th>
                <Th>{t('adm_reason_2')}</Th>
                <Th>{t('confidenceLabel')}</Th>
                <Th>{t('adm_when')}</Th>
                <Th>{t('actionsUk')}</Th>
              </tr>
            </thead>
            <tbody>
              {loading && items.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-[#71717A]">{t('adm_loading_3')}</td>
                </tr>
              )}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-[#A1A1AA]">
                    {status === 'pending' ? t('adm3_5bba2a834b') : t('adm3_221781f248')}
                  </td>
                </tr>
              )}
              {items.map((it) => {
                const sh = it.shipment || {};
                const data = it.data || {};
                const candName =
                  data.newName ||
                  (data.vessel && data.vessel.value && data.vessel.value.name) ||
                  (data.vessel && data.vessel.name) ||
                  '—';
                const candMmsi =
                  data.newMmsi ||
                  (data.vessel && data.vessel.value && data.vessel.value.mmsi) ||
                  (data.vessel && data.vessel.mmsi) ||
                  null;
                const conf =
                  data.finalConfidence ??
                  data.confidence ??
                  (data.vessel && data.vessel.confidence) ??
                  null;
                const cur = sh.currentVessel || {};
                const reasonKey = it.reason || it.kind;
                return (
                  <tr key={it._id} className="border-t border-[#F4F4F5] hover:bg-zinc-50/60">
                    <Td><code className="font-mono text-[11.5px] text-[#18181B]">{sh.vin || '—'}</code></Td>
                    <Td><code className="font-mono text-[11.5px] text-[#18181B]">{sh.container || '—'}</code></Td>
                    <Td>
                      <div className="font-semibold text-[#18181B]">{cur.name || '—'}</div>
                      <div className="text-[10.5px] text-[#A1A1AA] font-mono">MMSI {cur.mmsi || '—'}</div>
                    </Td>
                    <Td>
                      <div className="font-semibold text-[#18181B]">{candName}</div>
                      <div className="text-[10.5px] text-[#A1A1AA] font-mono">MMSI {candMmsi || '—'}</div>
                    </Td>
                    <Td>
                      <div className="text-[12.5px] text-[#18181B]">{KIND_LABELS[it.kind] || it.kind}</div>
                      <div className="text-[10.5px] text-[#71717A]">{REASON_LABELS[reasonKey] || reasonKey || '—'}</div>
                    </Td>
                    <Td>{fmtConfidence(conf)}</Td>
                    <Td><span className="text-[11.5px] text-[#71717A]">{it.createdAt ? new Date(it.createdAt).toLocaleString() : '—'}</span></Td>
                    <Td>
                      {it.status === 'pending' ? (
                        <div className="flex gap-2">
                          <button
                            data-testid={`confirm-${it._id}`}
                            disabled={actingId === it._id}
                            onClick={() => confirmOne(it._id)}
                            className="inline-flex items-center h-8 px-3 rounded-xl bg-[#18181B] text-[11.5px] font-medium text-white hover:bg-[#27272A] transition-colors disabled:opacity-40"
                          >
                            {t('adm_confirm')}
                          </button>
                          <button
                            data-testid={`reject-${it._id}`}
                            disabled={actingId === it._id}
                            onClick={() => rejectOne(it._id)}
                            className="inline-flex items-center h-8 px-3 rounded-xl border border-[#E4E4E7] bg-white text-[11.5px] font-medium text-[#18181B] hover:bg-zinc-50 transition-colors disabled:opacity-40"
                          >
                            {t('adm_decline')}
                          </button>
                        </div>
                      ) : (
                        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-[#E4E4E7] bg-white text-[10.5px] font-semibold ${it.status === 'confirmed' ? 'text-[#18181B]' : 'text-[#71717A]'}`}>
                          <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: it.status === 'confirmed' ? '#16A34A' : '#DC2626' }} />
                          {it.status}
                        </span>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div className="text-[12.5px] text-[#71717A] leading-relaxed">
        {t('adm_legend_confidence')} <span className="text-[#DC2626] font-medium">low {summary.low}</span> ·{' '}
        <span className="text-[#F59E0B] font-medium">medium {summary.medium}</span> ·{' '}
        <span className="text-[#16A34A] font-medium">high {summary.high}</span>
      </div>
    </div>
  );
}

function Th({ children }) {
  return (
    <th className="text-left px-3.5 py-2.5 text-[10.5px] font-semibold uppercase tracking-wider">
      {children}
    </th>
  );
}

function Td({ children }) {
  return <td className="px-3.5 py-3 align-middle">{children}</td>;
}
