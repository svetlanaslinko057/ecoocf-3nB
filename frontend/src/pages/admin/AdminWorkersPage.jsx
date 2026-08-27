/**
 * AdminWorkersPage.jsx — supervised worker control panel.
 *
 * Can be used standalone OR embedded inside the System hub (`embedded` prop).
 * In embedded mode the outer page chrome (title bar, full-bleed background)
 * is omitted because SystemPage already provides them.
 *
 * Polls /api/admin/workers every 10s.
 *
 * Actions per row (with hover tooltips, 3-lang aware):
 *   Restart — stop + relaunch, restart counter reset
 *   Stop    — graceful shutdown
 *   Start   — launch a stopped/crashed worker
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  ArrowsClockwise,
  StopCircle,
  PlayCircle,
  ShieldWarning,
  CheckCircle,
  ClockClockwise,
  WarningCircle,
} from '@phosphor-icons/react';
import { API_URL } from '../../App';
import { useLang } from '../../i18n';
import {
  InsightsCard,
  InsightsLoading,
  InsightsEmpty,
  MetricChip,
} from '../../components/insights/shared/InsightsCard';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../components/ui/tooltip';

// Hover tooltip — no icon, just hover the wrapped element.
const HoverTip = ({ text, side = 'top', children }) => {
  if (!text) return children;
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-xs bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg"
        >
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const stateTone = (state) => {
  switch (state) {
    case 'running':    return { tone: 'positive', icon: CheckCircle };
    case 'starting':   return { tone: 'info',     icon: ClockClockwise };
    case 'crashed':    return { tone: 'negative', icon: WarningCircle };
    case 'stopped':    return { tone: 'warning',  icon: StopCircle };
    case 'registered': return { tone: 'neutral',  icon: ClockClockwise };
    default:           return { tone: 'neutral',  icon: ShieldWarning };
  }
};

const fmtTime = (ts) => {
  if (!ts) return '—';
  try {
    const ms = typeof ts === 'number' ? ts * 1000 : Date.parse(ts);
    if (isNaN(ms)) return String(ts);
    return new Date(ms).toLocaleString();
  } catch { return String(ts); }
};

const summaryTipKey = (key) => {
  // Тултип для каждой плитки сводки. Если ключ незнаком — generic подсказка.
  switch (key) {
    case 'total':      return 'ins_workers_sum_tip_total';
    case 'running':    return 'ins_workers_sum_tip_running';
    case 'crashed':    return 'ins_workers_sum_tip_crashed';
    case 'stopped':    return 'ins_workers_sum_tip_stopped';
    case 'starting':   return 'ins_workers_sum_tip_starting';
    case 'registered': return 'ins_workers_sum_tip_registered';
    default:           return null;
  }
};

const AdminWorkersPage = ({ embedded = false }) => {
  const { t } = useLang();
  const [workers, setWorkers] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState({});
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API_URL}/api/admin/workers`);
      setWorkers(Array.isArray(data?.workers) ? data.workers : []);
      setSummary(data?.summary || {});
      setError(null);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load workers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const act = async (name, action) => {
    setBusy((b) => ({ ...b, [name]: action }));
    try {
      await axios.post(`${API_URL}/api/admin/workers/${encodeURIComponent(name)}/${action}`);
      await load();
    } catch (e) {
      setError(`${action}(${name}) failed: ${e?.response?.data?.detail || e?.message}`);
    } finally {
      setBusy((b) => {
        const { [name]: _, ...rest } = b;
        return rest;
      });
    }
  };

  // ───── Inner content (same for embedded & standalone) ─────────────────
  const content = (
    <div className="space-y-5" data-testid="admin-workers-page">
      {/* Summary tiles */}
      <div
        className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6"
        data-testid="admin-workers-summary"
      >
        {Object.entries(summary).map(([k, v]) => {
          const tipKey = summaryTipKey(k);
          const tip = tipKey ? t(tipKey) : null;
          return (
            <HoverTip key={k} text={tip} side="top">
              <div className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 shadow-sm cursor-default">
                <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">
                  {k}
                </div>
                <div className="mt-1 text-2xl font-semibold tabular-nums text-zinc-900">
                  {v}
                </div>
              </div>
            </HoverTip>
          );
        })}
      </div>

      {error && (
        <div
          className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
          data-testid="admin-workers-error"
        >
          {error}
        </div>
      )}

      <InsightsCard testId="admin-workers-table-card" padded={false}>
        {loading ? (
          <div className="p-5"><InsightsLoading rows={6} /></div>
        ) : workers.length === 0 ? (
          <div className="p-5"><InsightsEmpty title="No workers registered" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="admin-workers-table">
              <thead>
                <tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-2 text-left font-medium">{t('ins_workers_col_name')}</th>
                  <th className="px-4 py-2 text-left font-medium">{t('ins_workers_col_state')}</th>
                  <th className="px-4 py-2 text-right font-medium">{t('ins_workers_col_restarts')}</th>
                  <th className="px-4 py-2 text-left font-medium">{t('ins_workers_col_critical')}</th>
                  <th className="px-4 py-2 text-left font-medium">{t('ins_workers_col_started')}</th>
                  <th className="px-4 py-2 text-left font-medium">{t('ins_workers_col_error')}</th>
                  <th className="px-4 py-2 text-right font-medium">{t('ins_workers_col_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {workers.map((w) => {
                  const meta = stateTone(w.state);
                  const Icon = meta.icon;
                  const isBusy = !!busy[w.name];
                  return (
                    <tr
                      key={w.name}
                      className="border-b border-zinc-50 hover:bg-zinc-50"
                      data-testid={`admin-workers-row-${w.name}`}
                    >
                      <td className="px-4 py-2 font-medium text-zinc-900">
                        <HoverTip text={t('ins_workers_tip_name')} side="right">
                          <span className="cursor-default">{w.name}</span>
                        </HoverTip>
                      </td>
                      <td className="px-4 py-2">
                        <HoverTip text={t(`ins_workers_state_${w.state}`) || t('ins_workers_tip_state_generic')} side="top">
                          <span className="inline-flex items-center gap-1 cursor-default">
                            <Icon
                              size={13}
                              weight="duotone"
                              className={
                                meta.tone === 'positive' ? 'text-emerald-600' :
                                meta.tone === 'negative' ? 'text-red-600' :
                                meta.tone === 'warning'  ? 'text-amber-600' :
                                'text-zinc-500'
                              }
                            />
                            <MetricChip value={w.state} tone={meta.tone} />
                          </span>
                        </HoverTip>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        <HoverTip text={t('ins_workers_tip_restarts')} side="top">
                          <span className="cursor-default">
                            {w.restarts ?? 0}
                            {w.max_restarts != null ? ` / ${w.max_restarts}` : ''}
                          </span>
                        </HoverTip>
                      </td>
                      <td className="px-4 py-2">
                        {w.critical
                          ? <HoverTip text={t('ins_workers_tip_critical_yes')} side="top">
                              <span><MetricChip value="critical" tone="negative" /></span>
                            </HoverTip>
                          : <HoverTip text={t('ins_workers_tip_critical_no')} side="top">
                              <span className="text-zinc-400 cursor-default">no</span>
                            </HoverTip>}
                      </td>
                      <td className="px-4 py-2 text-xs text-zinc-600">{fmtTime(w.started_at)}</td>
                      <td className="px-4 py-2 text-xs text-red-700">
                        {w.last_error ? (
                          <HoverTip text={String(w.last_error)} side="top">
                            <span className="cursor-help">
                              {String(w.last_error).slice(0, 60)}
                              {String(w.last_error).length > 60 ? '…' : ''}
                            </span>
                          </HoverTip>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <div className="inline-flex items-center gap-1">
                          <HoverTip text={t('ins_workers_tip_restart')} side="top">
                            <button
                              type="button"
                              disabled={isBusy}
                              onClick={() => act(w.name, 'restart')}
                              className="inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                              data-testid={`admin-workers-restart-${w.name}`}
                            >
                              <ArrowsClockwise size={11} weight="bold" />
                              {busy[w.name] === 'restart' ? '…' : t('ins_workers_btn_restart')}
                            </button>
                          </HoverTip>
                          {w.state === 'running' || w.state === 'starting' ? (
                            <HoverTip text={t('ins_workers_tip_stop')} side="top">
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => act(w.name, 'stop')}
                                className="inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                                data-testid={`admin-workers-stop-${w.name}`}
                              >
                                <StopCircle size={11} weight="bold" />
                                {busy[w.name] === 'stop' ? '…' : t('ins_workers_btn_stop')}
                              </button>
                            </HoverTip>
                          ) : (
                            <HoverTip text={t('ins_workers_tip_start')} side="top">
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => act(w.name, 'start')}
                                className="inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
                                data-testid={`admin-workers-start-${w.name}`}
                              >
                                <PlayCircle size={11} weight="bold" />
                                {busy[w.name] === 'start' ? '…' : t('ins_workers_btn_start')}
                              </button>
                            </HoverTip>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </InsightsCard>

      <p className="text-[11px] text-zinc-500">{t('ins_workers_autorefresh')}</p>
    </div>
  );

  // ───── Embedded mode: no chrome ──────────────────────────────────────
  if (embedded) {
    return (
      <div className="space-y-4">
        <div>
          <HoverTip text={t('ins_workers_tip_page')} side="bottom">
            <h2
              className="text-lg sm:text-xl font-bold text-gray-900 leading-tight cursor-default"
              style={{ fontFamily: 'Mazzard, Mazzard H, system-ui, sans-serif' }}
            >
              {t('ins_workers_title')}
            </h2>
          </HoverTip>
          <p className="text-xs sm:text-sm text-gray-500 mt-1">
            {t('ins_workers_subtitle')}
          </p>
        </div>
        {content}
      </div>
    );
  }

  // ───── Standalone (legacy /admin/workers route) ──────────────────────
  return (
    <div className="min-h-screen bg-zinc-50 pb-12">
      <div className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-[1600px] px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <ShieldWarning size={22} weight="duotone" />
            <h1
              className="text-xl font-semibold tracking-tight text-zinc-900 sm:text-2xl"
              style={{ fontFamily: 'Mazzard, Mazzard H, system-ui, sans-serif' }}
            >
              {t('ins_workers_title')}
            </h1>
          </div>
          <p className="mt-0.5 text-xs text-zinc-500">{t('ins_workers_subtitle')}</p>
        </div>
      </div>
      <div className="mx-auto max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8">
        {content}
      </div>
    </div>
  );
};

export default AdminWorkersPage;
