/**
 * Exceptions Dashboard — "AUTO first, HUMAN only on exception" UX.
 *
 * Surfaces shipments that currently need manual review, grouped by reason:
 *   • stale          — tracking update > 3h
 *   • no_data        — trackingActive but no source/position
 *   • no_vessel      — active stage is vessel but no MMSI/IMO/name
 *   • no_container   — active vessel stage has no container bound (soft)
 *   • stuck_progress — progress >= 0.99 for > 24h, not delivered
 *
 * Manager's goal on this page: clear the queue. Each shipment has a one-click
 * deep-link to /admin/vesselfinder with its ID pre-loaded for fast bind/fix.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { useLang, getLocale } from '../../i18n';
import {
  Warning,
  WarningCircle,
  Clock,
  Anchor,
  Package,
  ArrowClockwise,
  Broom,
  CheckCircle,
  ArrowRight,
  Robot,
  Lightning,
} from '@phosphor-icons/react';
// AdminPageHeader replaced with custom inline header (June 2026) — refresh
// pinned top-right invariant. Keep this comment so future edits don't
// reintroduce the import without revisiting the layout contract.

const API_URL =
  process.env.REACT_APP_BACKEND_URL ||
  import.meta?.env?.REACT_APP_BACKEND_URL ||
  '';

const REASON_META = {
  stale: {
    label: 'Stale',
    description: 'No updates > 3 hours',
    Icon: Clock,
    color: 'rose',
  },
  no_data: {
    label: 'No data',
    description: 'Tracking enabled, but no source/position',
    Icon: WarningCircle,
    color: 'slate',
  },
  no_vessel: {
    label: 'No vessel',
    description: 'Active Sea Stage Without Assigned Vessel',
    Icon: Anchor,
    color: 'amber',
  },
  no_container: {
    label: 'No container',
    description: 'Active Sea Stage Without Container',
    Icon: Package,
    color: 'indigo',
  },
  stuck_progress: {
    label: 'Stuck',
    description: 'Progress ≥ 99% already > 24 hours',
    Icon: Warning,
    color: 'purple',
  },
};

function fmtAgo(iso, t) {
  // `t` is the translation function passed from the component (useLang).
  // It MUST be passed explicitly because this helper lives at module scope
  // and has no access to the hook.  Falls back to plain english labels.
  const tr = typeof t === 'function' ? t : (k) => k;
  if (!iso) return '—';
  const ms = new Date(iso).getTime();
  if (!Number.isFinite(ms)) return '—';
  const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 60) return `${Math.round(s)} ${tr('r9_seconds_ago') || 'seconds ago'}`;
  if (s < 3600) return `${Math.round(s / 60)} ${tr('r9_minutes_ago') || 'minutes ago'}`;
  if (s < 86400) return `${Math.round(s / 3600)} ${tr('r9_hours_ago') || 'hours ago'}`;
  return `${Math.round(s / 86400)} ${tr('r9_days_ago') || 'days ago'}`;
}

export default function ExceptionsDashboardPage() {
  const { t } = useLang();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeBucket, setActiveBucket] = useState('all');
  const [err, setErr] = useState(null);
  // Resolver queue
  const [resolverQueue, setResolverQueue] = useState(null);
  const [resolverBusy, setResolverBusy] = useState(false);
  const [resolverBusyId, setResolverBusyId] = useState(null);
  const [resolverMsg, setResolverMsg] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [e, q] = await Promise.allSettled([
        axios.get(`${API_URL}/api/admin/shipments/exceptions`),
        axios.get(`${API_URL}/api/admin/resolver/queue`),
      ]);
      if (e.status === 'fulfilled') setData(e.value.data);
      if (q.status === 'fulfilled') setResolverQueue(q.value.data);
      if (e.status === 'rejected') throw e.reason;
    } catch (e) {
      setErr(e?.response?.data?.detail || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const runResolverFor = useCallback(async (shipmentId) => {
    setResolverBusyId(shipmentId);
    setResolverMsg(null);
    try {
      const r = await axios.post(`${API_URL}/api/admin/shipments/${shipmentId}/resolver/run`);
      const d = r.data?.persisted || {};
      const report = r.data?.report || {};
      const parts = [];
      if (d.containerChanged) parts.push(`📦 container: ${d.container}`);
      if (d.vesselChanged) parts.push(`⚓ vessel: ${d.vesselName}`);
      if (!parts.length) {
        const confC = Math.round((report.container?.confidence || 0) * 100);
        const confV = Math.round((report.vessel?.confidence || 0) * 100);
        parts.push(`${t('r9_nothing_new')}container ${confC}%, vessel ${confV}%)`);
      }
      setResolverMsg({ kind: 'ok', text: `${shipmentId}: ${parts.join(' · ')}` });
      await reload();
    } catch (e) {
      setResolverMsg({ kind: 'err', text: `${shipmentId}: ${e?.response?.data?.detail || String(e)}` });
    } finally {
      setResolverBusyId(null);
    }
  }, [reload]);

  const runResolverQueue = useCallback(async () => {
    setResolverBusy(true);
    setResolverMsg(null);
    try {
      const r = await axios.post(`${API_URL}/api/admin/resolver/run-queue?limit=20`);
      const d = r.data || {};
      setResolverMsg({ kind: 'ok',
        text: `${t('r9_batch_processed')}${d.processed}${t('r9_new_bindings')}${d.resolved}` });
      await reload();
    } catch (e) {
      setResolverMsg({ kind: 'err', text: e?.response?.data?.detail || String(e) });
    } finally {
      setResolverBusy(false);
    }
  }, [reload]);

  useEffect(() => {
    reload();
    const id = setInterval(reload, 60_000);
    return () => clearInterval(id);
  }, [reload]);

  const buckets = data?.buckets || {};
  const counts = data?.counts || {};
  // Merged & deduped list for "all" view
  const allItems = (() => {
    const seen = new Set();
    const out = [];
    Object.values(buckets).forEach((arr) =>
      (arr || []).forEach((it) => {
        if (!seen.has(it.id)) {
          seen.add(it.id);
          out.push(it);
        }
      })
    );
    return out;
  })();
  const itemsToShow = activeBucket === 'all' ? allItems : buckets[activeBucket] || [];

  return (
    <div className="space-y-4 sm:space-y-5" data-testid="exceptions-dashboard">
      {/*
        Header — Refresh always pinned top-RIGHT. The "computedAt" timestamp
        sits inline next to refresh (right side) on both viewports so the
        date never falls under the title block on mobile.
      */}
      <header
        className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5"
        data-testid="exceptions-header"
      >
        <div className="flex items-start gap-3 sm:gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Warning size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight break-words">
              {t('exceptionsDashboardTitle')}
            </h1>
            <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed break-words">
              {t('adm_shipments_requiring_manual_intervention')}
            </p>
            {/* Timestamp moved INTO the title block on mobile (tiny, muted)
                so it stays near the title yet not blocking refresh placement. */}
            {data?.computedAt && (
              <p className="mt-1 sm:hidden text-[11px] text-[#A1A1AA] tabular-nums">
                {new Date(data.computedAt).toLocaleTimeString(getLocale())}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {data?.computedAt && (
              <span className="hidden sm:inline text-[11px] text-[#A1A1AA] tabular-nums whitespace-nowrap">
                {new Date(data.computedAt).toLocaleTimeString(getLocale())}
              </span>
            )}
            <button
              onClick={reload}
              disabled={loading}
              data-testid="exceptions-refresh-btn"
              aria-label={t('adm_refresh_3')}
              className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white disabled:opacity-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 shrink-0 transition-colors"
            >
              <ArrowClockwise size={16} weight="bold" className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>
      </header>

      {/* Bucket selector chips — 2 cols mobile, wrap row on sm+ */}
      <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
        <BucketChip
          label={t('adm_all')}
          Icon={Broom}
          count={allItems.length}
          active={activeBucket === 'all'}
          onClick={() => setActiveBucket('all')}
          color="slate"
        />
        {Object.keys(REASON_META).map((key) => {
          const meta = REASON_META[key];
          return (
            <BucketChip
              key={key}
              label={meta.label}
              description={meta.description}
              Icon={meta.Icon}
              color={meta.color}
              count={counts[key] || 0}
              active={activeBucket === key}
              onClick={() => setActiveBucket(key)}
            />
          );
        })}
      </div>

      {/* Error */}
      {err && (
        <div className="rounded-xl border border-[#FCA5A5] bg-[#FEF2F2] px-3 py-2.5 text-sm text-[#7F1D1D]">
          {err}
        </div>
      )}

      {/* ══════════════════ AUTO RESOLVER QUEUE ══════════════════ */}
      {resolverQueue && resolverQueue.total > 0 && (
        <div className="rounded-xl border-2 border-indigo-200 bg-gradient-to-br from-indigo-50 via-white to-white p-5 shadow-sm" data-testid="resolver-queue">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-indigo-600">
                <Robot size={20} weight="fill" className="text-white" />
              </div>
              <div>
                <h2 className="text-base font-bold text-indigo-900 flex items-center gap-2">
                  {t('adm_auto_resolver_queue')}
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] uppercase tracking-wide bg-indigo-100 text-indigo-700 rounded">
                    multi-source
                  </span>
                </h2>
                <p className="text-xs text-indigo-800 mt-0.5">
                  {t('adm_shipments_without')} <b>container</b> {t('adm_or')} <b>vessel</b> {t('adm3_cc8fbb20a2')}
                </p>
              </div>
            </div>
            <button
              onClick={runResolverQueue}
              disabled={resolverBusy}
              data-testid="run-resolver-queue-btn"
              className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-50 shadow-sm"
            >
              <Lightning size={14} weight="fill" className={resolverBusy ? 'animate-pulse' : ''} />
              {resolverBusy ? 'Resolving…' : 'Run resolver for all'}
            </button>
          </div>

          {/* summary chips */}
          <div className="flex flex-wrap gap-2 mb-3">
            <span className="inline-flex items-center gap-1 rounded-full bg-white border border-indigo-200 px-2.5 py-1 text-[11px] font-semibold text-indigo-900">
              {t('adm_total')} <b>{resolverQueue.total}</b>
            </span>
            {resolverQueue.buckets?.missing_container > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-1 text-[11px] text-amber-800">
                {t('adm_no_container_2')} <b>{resolverQueue.buckets.missing_container}</b>
              </span>
            )}
            {resolverQueue.buckets?.missing_vessel > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 border border-sky-200 px-2.5 py-1 text-[11px] text-sky-800">
                {t('adm_no_vessel_2')} <b>{resolverQueue.buckets.missing_vessel}</b>
              </span>
            )}
            {resolverQueue.buckets?.missing_both > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 border border-rose-200 px-2.5 py-1 text-[11px] text-rose-800">
                {t('adm_both')} <b>{resolverQueue.buckets.missing_both}</b>
              </span>
            )}
          </div>

          {/* message */}
          {resolverMsg && (
            <div className={`rounded-md border px-3 py-1.5 mb-3 text-xs ${
              resolverMsg.kind === 'ok'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-rose-50 border-rose-200 text-rose-800'
            }`}>
              {resolverMsg.text}
            </div>
          )}

          {/* rows */}
          <div className="rounded-lg border border-indigo-100 bg-white overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-indigo-50/60 border-b border-indigo-100">
                <tr>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">{t('adm_vin_shipment')}</th>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">{t('missingLabel')}</th>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">{t('currentContainer')}</th>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">{t('currentVessel')}</th>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold text-indigo-700 uppercase tracking-wide">{t('lastResolver')}</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-50">
                {(resolverQueue.items || []).map((it) => {
                  const r = it.resolver || {};
                  const actions = r.actions || [];
                  const cHit = r.container || {};
                  const vHit = r.vessel || {};
                  return (
                    <tr key={it.id} className="hover:bg-indigo-50/30" data-testid={`resolver-row-${it.id}`}>
                      <td className="px-3 py-2.5 align-top">
                        <div className="font-mono text-[11px] text-slate-900">{it.vin || '—'}</div>
                        <div className="font-mono text-[10px] text-slate-400">{it.id}</div>
                        {it.vehicleTitle && <div className="text-[11px] text-slate-700 mt-0.5">{it.vehicleTitle}</div>}
                      </td>
                      <td className="px-3 py-2.5 align-top">
                        <div className="flex flex-col gap-0.5">
                          {(it.missing || []).map((m) => (
                            <span
                              key={m}
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold w-fit ${
                                m === 'container' ? 'bg-indigo-100 text-indigo-800' : 'bg-sky-100 text-sky-800'
                              }`}
                            >
                              {m === 'container' ? '📦' : '⚓'} {m}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 align-top">
                        {it.container ? (
                          <div className="font-mono text-[11px] text-indigo-700">{it.container}</div>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">—</span>
                        )}
                        {it.containerConfidence != null && (
                          <div className="text-[10px] text-slate-500 mt-0.5">conf {Math.round(it.containerConfidence * 100)}%</div>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-top">
                        {it.vessel?.name ? (
                          <>
                            <div className="text-[11px] text-sky-700 font-medium">{it.vessel.name}</div>
                            {it.vessel.mmsi && <div className="text-[10px] font-mono text-slate-400">MMSI {it.vessel.mmsi}</div>}
                          </>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-top text-[10px] text-slate-600 max-w-xs">
                        {r.lastRun ? (
                          <>
                            <div className="font-medium text-slate-700">{new Date(r.lastRun).toLocaleString(getLocale(), {day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'})}</div>
                            {actions.slice(0, 2).map((a, i) => (
                              <div key={i} className="text-[10px] text-slate-500 mt-0.5 truncate" title={a}>• {a}</div>
                            ))}
                          </>
                        ) : (
                          <span className="text-slate-400 italic">{t('adm_never')}</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-top text-right whitespace-nowrap">
                        <button
                          onClick={() => runResolverFor(it.id)}
                          disabled={resolverBusyId === it.id}
                          data-testid={`run-resolver-${it.id}`}
                          className="inline-flex items-center gap-1 rounded bg-indigo-600 px-2.5 py-1 text-[10px] font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
                        >
                          <Robot size={11} />
                          {resolverBusyId === it.id ? '…' : 'Resolve'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty */}
      {!loading && itemsToShow.length === 0 && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-8 text-center" data-testid="exceptions-empty">
          <CheckCircle size={32} weight="fill" className="text-emerald-500 mx-auto mb-2" />
          <div className="text-sm font-semibold text-emerald-800">{t('queueEmpty')}</div>
          <div className="text-xs text-emerald-700 mt-1">
            {t('adm_the_system_operates_in_automatic_mode_manual_inter')}
          </div>
        </div>
      )}

      {/* Items */}
      {itemsToShow.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{t('adm_vin_shipment')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{t('adm_vessel_container')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{t('progressLabel')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{t('issuesLabel')}</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">{t('lastUpdate')}</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {itemsToShow.map((it) => (
                <tr key={it.id} className="hover:bg-slate-50" data-testid={`exception-row-${it.id}`}>
                  <td className="px-4 py-3">
                    <div className="font-mono text-xs text-slate-900">{it.vin || '—'}</div>
                    <div className="font-mono text-[10px] text-slate-400">{it.id}</div>
                    {it.vehicleTitle && (
                      <div className="text-xs text-slate-700 mt-0.5">{it.vehicleTitle}</div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {it.currentVessel?.name ? (
                      <div className="text-xs text-slate-900 flex items-center gap-1">
                        <Anchor size={12} weight="fill" className="text-sky-600" />
                        <span className="font-medium">{it.currentVessel.name}</span>
                        {it.currentVessel.mmsi && <span className="text-[10px] text-slate-400 font-mono">· {it.currentVessel.mmsi}</span>}
                      </div>
                    ) : (
                      <div className="text-xs text-amber-600 italic">{t('adm_not_assigned')}</div>
                    )}
                    {it.currentContainer?.number ? (
                      <div className="text-[11px] text-slate-600 font-mono flex items-center gap-1 mt-0.5">
                        <Package size={11} className="text-indigo-500" />
                        {it.currentContainer.number}
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-400 italic mt-0.5">{t('adm_container_not_assigned')}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 w-36">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, Math.round((it.progress || 0) * 100)))}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-slate-700 w-8 text-right">
                        {Math.round((it.progress || 0) * 100)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(it.issues || []).map((iss) => {
                        const m = REASON_META[iss];
                        if (!m) return null;
                        const I = m.Icon;
                        return (
                          <span
                            key={iss}
                            className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-${m.color}-50 text-${m.color}-700 border border-${m.color}-200`}
                          >
                            <I size={10} /> {m.label}
                          </span>
                        );
                      })}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-xs text-slate-700">{fmtAgo(it.lastTrackingUpdate, t)}</div>
                    {it.ageHours !== null && it.ageHours !== undefined && (
                      <div className="text-[10px] text-slate-400">{it.ageHours} {t('adm3_dd70ac60ce')}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/admin/vesselfinder?shipmentId=${it.id}`}
                      className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-blue-700"
                    >
                      {t('adm_open')} <ArrowRight size={12} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function BucketChip({ label, description, Icon, count, active, color, onClick }) {
  // Map semantic colors to dot accent (no dynamic tailwind classes — those break JIT)
  const dotByColor = {
    slate: '#71717A',
    rose: '#DC2626',
    amber: '#F59E0B',
    indigo: '#6366F1',
    violet: '#8B5CF6',
    emerald: '#16A34A',
    blue: '#3B82F6',
    sky: '#0EA5E9',
  };
  const dot = dotByColor[color] || '#71717A';
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 h-10 px-3 rounded-xl border text-left transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10 w-full sm:w-auto ${
        active
          ? 'bg-[#18181B] border-[#18181B] text-white'
          : 'bg-white border-[#E4E4E7] text-[#18181B] hover:bg-zinc-50'
      }`}
      data-testid={`exceptions-bucket-${label.toLowerCase()}`}
      title={description || label}
    >
      <Icon size={14} weight={active ? 'fill' : 'duotone'} className={active ? 'text-white' : ''} style={!active ? { color: dot } : undefined} />
      <span className="font-semibold text-[12.5px] truncate">{label}</span>
      <span className={`ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10.5px] font-semibold ${
        active
          ? 'bg-white/15 text-white'
          : 'bg-[#F4F4F5] text-[#71717A]'
      }`}>
        {count}
      </span>
    </button>
  );
}
