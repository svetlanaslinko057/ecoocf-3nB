/**
 * RingostatStatsPanel — operational KPI dashboard.
 *
 * Pulls from:
 *   GET /api/admin/ringostat/stats/overview?days=N
 *   GET /api/admin/ringostat/stats/managers?days=N
 *
 * Shows:
 *   • 4 top KPI tiles (Total / Answered / Missed / Answer rate)
 *   • Daily trend (last N days)
 *   • Per-manager performance table (answer rate, avg duration, recency)
 *
 * Window selector: 7 / 14 / 30 / 90 days.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Phone, ArrowDownLeft, ArrowUpRight, Clock, Users, ChartLine } from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const apiFetch = (path, init = {}) => {
  const token = (typeof window !== 'undefined' && localStorage.getItem('token')) || '';
  const headers = {
    ...(init.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
};

const fmt = (n) => {
  if (n === null || n === undefined) return '—';
  const num = Number(n);
  if (Number.isNaN(num)) return String(n);
  return num.toLocaleString('en-US');
};

const fmtDuration = (sec) => {
  if (!sec) return '0s';
  const s = Math.round(sec);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
};

const KPI = ({ label, value, hint, accent, icon: Icon, testid }) => (
  <div
    className="bg-white border border-[#E4E4E7] rounded-2xl px-4 py-3.5"
    data-testid={testid}
  >
    <div className="flex items-start justify-between mb-1">
      <p className="text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A]">
        {label}
      </p>
      {Icon ? <Icon size={14} weight="duotone" className="text-[#A1A1AA]" /> : null}
    </div>
    <p
      className={`text-2xl font-bold tabular-nums leading-none ${
        accent === 'good'
          ? 'text-emerald-600'
          : accent === 'warn'
          ? 'text-amber-600'
          : accent === 'bad'
          ? 'text-red-600'
          : 'text-[#18181B]'
      }`}
    >
      {value}
    </p>
    {hint ? (
      <p className="text-[10.5px] text-[#71717A] mt-1.5">{hint}</p>
    ) : null}
  </div>
);

const RingostatStatsPanel = () => {
  const { t } = useLang();
  const tn = (key, vars = {}) =>
    Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)), t(key));
  const [days, setDays] = useState(7);
  const [overview, setOverview] = useState(null);
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ovRes, mgrRes] = await Promise.all([
        apiFetch(`/api/admin/ringostat/stats/overview?days=${days}`),
        apiFetch(`/api/admin/ringostat/stats/managers?days=${days}`),
      ]);
      if (!ovRes.ok || !mgrRes.ok) {
        throw new Error(`HTTP ${ovRes.status}/${mgrRes.status}`);
      }
      const ov = await ovRes.json();
      const mgr = await mgrRes.json();
      setOverview(ov);
      setManagers(mgr.managers || []);
      setErr(null);
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 30000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const totals = overview?.totals || {};
  const answerRate = overview?.answer_rate ?? 0;

  // Pre-compute max for the bar chart
  const maxDay = Math.max(1, ...(overview?.by_day || []).map((d) => d.total || 0));

  return (
    <div className="space-y-5" data-testid="ringostat-stats-panel">
      {/* Header — window selector */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          <h2 className="text-base sm:text-lg font-bold tracking-tight text-[#18181B]">
            {tn('rs_call_performance_last_days_tpl', { n: days })}
          </h2>
          <p className="text-[11.5px] text-[#71717A] mt-0.5">
            {t('rs_live_kpi_subtitle')}
          </p>
        </div>
        <div className="inline-flex items-center bg-white border border-[#E4E4E7] rounded-xl p-0.5 shrink-0 self-start">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`px-3 h-8 text-[11.5px] font-semibold rounded-lg transition-colors ${
                days === d
                  ? 'bg-[#18181B] text-white'
                  : 'text-[#52525B] hover:text-[#18181B]'
              }`}
              data-testid={`stats-window-${d}`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="px-3 py-2.5 rounded-xl bg-[#FEF2F2] border border-[#FCA5A5] text-xs text-[#7F1D1D]">
          load error: {err}
        </div>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPI
          label={t('rs_kpi_total_calls')}
          value={fmt(totals.all)}
          icon={Phone}
          hint={`${fmt(totals.inbound)} ${t('rs_kpi_inbound')} · ${fmt(totals.outbound)} ${t('rs_kpi_outbound')}`}
          testid="kpi-total"
        />
        <KPI
          label={t('rs_kpi_answered')}
          value={fmt(totals.answered)}
          icon={ArrowDownLeft}
          accent="good"
          hint={`${t('rs_kpi_avg')} ${fmtDuration(overview?.avg_duration_sec)}`}
          testid="kpi-answered"
        />
        <KPI
          label={t('rs_kpi_missed')}
          value={fmt(totals.missed)}
          icon={ArrowUpRight}
          accent={(totals.missed || 0) > (totals.answered || 0) ? 'bad' : 'warn'}
          hint={(totals.missed || 0) ? t('rs_kpi_needs_callback') : t('rs_kpi_none')}
          testid="kpi-missed"
        />
        <KPI
          label={t('rs_kpi_answer_rate')}
          value={`${answerRate.toFixed(1)}%`}
          icon={ChartLine}
          accent={answerRate >= 80 ? 'good' : answerRate >= 50 ? 'warn' : 'bad'}
          hint={t('rs_kpi_formula_answered')}
          testid="kpi-answer-rate"
        />
      </div>

      {/* Daily trend */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5">
        <div className="flex items-center gap-2 mb-3">
          <ChartLine size={16} weight="duotone" className="text-[#18181B]" />
          <h3 className="text-[13.5px] font-bold tracking-tight text-[#18181B]">
            {t('rs_daily_volume')}
          </h3>
          <span className="ml-auto text-[10px] uppercase tracking-wider text-[#A1A1AA]">
            {t('rs_green_red_legend')}
          </span>
        </div>
        {!overview?.by_day || overview.by_day.length === 0 ? (
          <p className="text-xs text-[#A1A1AA] py-8 text-center">
            {loading ? t('rs_loading') : t('rs_no_activity_window')}
          </p>
        ) : (
          <div className="flex items-end gap-1 h-32" data-testid="stats-daily-chart">
            {overview.by_day.map((d) => {
              const total = d.total || 0;
              const answered = d.answered || 0;
              const missed = d.missed || 0;
              const totalH = (total / maxDay) * 100;
              const answeredH = total ? (answered / total) * totalH : 0;
              const missedH = total ? (missed / total) * totalH : 0;
              return (
                <div
                  key={d.day}
                  className="flex-1 flex flex-col items-center gap-1 min-w-0 group"
                  title={`${d.day}: total=${total}, answered=${answered}, missed=${missed}`}
                >
                  <div className="w-full h-full flex flex-col-reverse rounded overflow-hidden">
                    <div
                      className="bg-emerald-500"
                      style={{ height: `${answeredH}%` }}
                    />
                    <div
                      className="bg-red-400"
                      style={{ height: `${missedH}%` }}
                    />
                    <div
                      className="bg-[#E4E4E7]"
                      style={{
                        height: `${Math.max(0, totalH - answeredH - missedH)}%`,
                      }}
                    />
                  </div>
                  <span className="text-[9px] text-[#71717A] tabular-nums truncate w-full text-center">
                    {d.day.slice(5)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Per-manager table */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5">
        <div className="flex items-center gap-2 mb-3">
          <Users size={16} weight="duotone" className="text-[#18181B]" />
          <h3 className="text-[13.5px] font-bold tracking-tight text-[#18181B]">
            {t('rs_per_manager_perf')}
          </h3>
          <span className="ml-auto text-[10px] uppercase tracking-wider text-[#A1A1AA]">
            {tn('rs_agents_tpl', { n: managers.length })}
          </span>
        </div>
        {managers.length === 0 ? (
          <p className="text-xs text-[#A1A1AA] py-6 text-center">
            {loading ? t('rs_loading') : t('rs_no_managers_in_window')}
          </p>
        ) : (
          <div className="overflow-x-auto -mx-2">
            <table className="w-full text-[12px] tabular-nums">
              <thead className="text-[10.5px] uppercase tracking-wider text-[#71717A]">
                <tr className="border-b border-[#F4F4F5]">
                  <th className="text-left font-semibold px-2 py-2">{t('rs_th_manager')}</th>
                  <th className="text-left font-semibold px-2 py-2">{t('rs_th_ext')}</th>
                  <th className="text-right font-semibold px-2 py-2">{t('rs_th_total')}</th>
                  <th className="text-right font-semibold px-2 py-2">{t('rs_th_answered')}</th>
                  <th className="text-right font-semibold px-2 py-2">{t('rs_th_missed')}</th>
                  <th className="text-right font-semibold px-2 py-2">{t('rs_th_answer_pct')}</th>
                  <th className="text-right font-semibold px-2 py-2">{t('rs_th_avg_dur')}</th>
                  <th className="text-left font-semibold px-2 py-2 hidden md:table-cell">{t('rs_th_last_call')}</th>
                </tr>
              </thead>
              <tbody>
                {managers.map((m) => {
                  const rate = m.answer_rate || 0;
                  const rateColor =
                    rate >= 80
                      ? 'text-emerald-600'
                      : rate >= 50
                      ? 'text-amber-600'
                      : rate > 0
                      ? 'text-red-600'
                      : 'text-[#71717A]';
                  return (
                    <tr
                      key={m.manager_id || 'unassigned'}
                      className="border-b border-[#F4F4F5] last:border-b-0 hover:bg-[#FAFAFA]"
                      data-testid={`stats-mgr-row-${m.manager_id || 'unassigned'}`}
                    >
                      <td className="px-2 py-2 font-medium text-[#18181B] truncate max-w-[200px]">
                        {m.manager_name}
                      </td>
                      <td className="px-2 py-2 text-[#52525B] font-mono">
                        {m.extension || '—'}
                      </td>
                      <td className="px-2 py-2 text-right font-semibold text-[#18181B]">
                        {fmt(m.total)}
                      </td>
                      <td className="px-2 py-2 text-right text-emerald-700">
                        {fmt(m.answered)}
                      </td>
                      <td className="px-2 py-2 text-right text-red-600">
                        {fmt(m.missed)}
                      </td>
                      <td className={`px-2 py-2 text-right font-semibold ${rateColor}`}>
                        {rate.toFixed(1)}%
                      </td>
                      <td className="px-2 py-2 text-right text-[#52525B]">
                        {fmtDuration(m.avg_duration_sec)}
                      </td>
                      <td className="px-2 py-2 text-[#71717A] text-[11px] hidden md:table-cell">
                        {m.last_call_at
                          ? new Date(m.last_call_at).toLocaleString()
                          : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default RingostatStatsPanel;
