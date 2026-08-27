/**
 * OverviewKpiStrip.jsx
 * Sticky always-visible KPI strip for /insights.
 * 6 tiles:
 *   Revenue MTD · Active Leads · Win Rate · Avg Cycle Time · Composite Risk Score · Critical Alerts
 *
 * Each tile is clickable — it scrolls to the relevant vertical/section anchor.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { TrendUp, TrendDown, Minus, CurrencyDollar, UsersThree, Target, Clock, Shield, Lightning } from '@phosphor-icons/react';
import { safeGet, fmtMoney, fmtCompact, fmtPct, fmtDuration, deltaClass, riskBandClass } from './shared/insightsApi';
import InsightsHelpTooltip from './shared/InsightsHelpTooltip';
import { useLang } from '../../i18n';

const TileSkeleton = () => (
  <div className="h-[88px] animate-pulse rounded-2xl border border-zinc-200 bg-zinc-50" />
);

const Tile = ({ icon: Icon, label, tip, value, delta, deltaSuffix = '%', tone, onClick, testId }) => {
  const deltaIcon = delta === null || delta === undefined || isNaN(delta)
    ? null
    : delta > 0 ? <TrendUp size={11} weight="bold" /> : delta < 0 ? <TrendDown size={11} weight="bold" /> : <Minus size={11} weight="bold" />;
  const toneClass = tone === 'critical' ? 'border-red-300 bg-red-50/40' :
                    tone === 'warn' ? 'border-amber-300 bg-amber-50/40' :
                    tone === 'good' ? 'border-emerald-300 bg-emerald-50/40' :
                    'border-zinc-200 bg-white';
  return (
    <InsightsHelpTooltip text={tip} side="bottom" align="start">
      <button
        type="button"
        onClick={onClick}
        data-testid={testId}
        className={`group relative flex h-[88px] w-full flex-col justify-between rounded-2xl border ${toneClass} px-4 py-3 text-left shadow-sm transition-[box-shadow,border-color] duration-150 hover:border-zinc-300 hover:shadow-md active:scale-[0.99]`}
      >
        <div className="flex items-center justify-between">
          <span className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">{label}</span>
          {Icon && <Icon size={14} weight="duotone" className="text-zinc-400" />}
        </div>
        <div className="flex items-end justify-between gap-2">
          <span className="text-xl font-semibold tabular-nums text-zinc-900 sm:text-[22px]">{value}</span>
          {delta !== null && delta !== undefined && !isNaN(delta) && (
            <span className={`inline-flex items-center gap-0.5 text-[11px] font-medium tabular-nums ${deltaClass(delta)}`}>
              {deltaIcon}
              {delta > 0 ? '+' : ''}{Number(delta).toFixed(deltaSuffix === '%' ? 0 : 1)}{deltaSuffix}
            </span>
          )}
        </div>
      </button>
    </InsightsHelpTooltip>
  );
};

const OverviewKpiStrip = ({ period = 30, role, onJumpTo }) => {
  const { t } = useLang();
  const [data, setData] = useState({
    revenueMtd: null, revenueDelta: null,
    activeLeads: null, leadsDelta: null,
    winRate: null, winRateDelta: null,
    avgCycle: null,
    riskScore: null,
    criticalAlerts: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      // Aggregate from multiple endpoints in parallel.
      const [kpi, owner, alerts, escalations] = await Promise.all([
        safeGet('/api/admin/kpi/dashboard'),
        safeGet('/api/owner-dashboard', { days: period }),
        safeGet('/api/alerts/critical', { limit: 100 }),
        safeGet('/api/escalations/stats'),
      ]);
      if (!alive) return;

      const kd = kpi.data || {};
      const od = owner.data || {};
      const alertsCount = Array.isArray(alerts.data?.alerts) ? alerts.data.alerts.length
                       : Array.isArray(alerts.data) ? alerts.data.length : 0;
      const escStats = escalations.data || {};

      // Composite risk score: 0–100. Heuristic from available signals
      // (no mock — derived from real critical alerts + open escalations + conversion drop).
      const openEsc = Number(escStats.open || escStats.openCount || 0);
      const breached = Number(escStats.breached || 0);
      const convDrop = Math.max(0, -Number(kd.trends?.conversion ?? 0));
      const baseRisk = Math.min(100, alertsCount * 4 + openEsc * 2 + breached * 5 + convDrop * 2);

      setData({
        revenueMtd: od.totalRevenue ?? od.revenue ?? od.revenueMtd ?? 0,
        revenueDelta: od.revenueDeltaPct ?? od.trends?.revenue ?? null,
        activeLeads: kd.leadsCreated ?? 0,
        leadsDelta: kd.trends?.leads ?? null,
        winRate: kd.conversionRate ?? 0,
        winRateDelta: kd.trends?.conversion ?? null,
        avgCycle: od.avgCycleDays ?? kd.avgResponseTime ? (kd.avgResponseTime / 60 / 24) : null,
        riskScore: Math.round(baseRisk),
        criticalAlerts: alertsCount,
      });
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [period]);

  const riskTone = useMemo(() => {
    if (data.riskScore === null) return 'neutral';
    if (data.riskScore >= 70) return 'critical';
    if (data.riskScore >= 40) return 'warn';
    return 'good';
  }, [data.riskScore]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => <TileSkeleton key={i} />)}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="insights-kpi-strip">
      <Tile icon={CurrencyDollar} label={t('ins_kpi_revenue_mtd')}      tip={t('ins_tip_revenue_mtd')}      value={fmtMoney(data.revenueMtd)}                       delta={data.revenueDelta}  tone={data.revenueDelta < 0 ? 'warn' : undefined}                                       onClick={() => onJumpTo?.('revenue')}  testId="insights-kpi-revenue-mtd" />
      <Tile icon={UsersThree}     label={t('ins_kpi_active_leads')}     tip={t('ins_tip_active_leads')}     value={fmtCompact(data.activeLeads)}                    delta={data.leadsDelta}                                                                                          onClick={() => onJumpTo?.('pipeline')} testId="insights-kpi-active-leads" />
      <Tile icon={Target}         label={t('ins_kpi_win_rate')}         tip={t('ins_tip_win_rate')}         value={fmtPct(data.winRate)}                            delta={data.winRateDelta} deltaSuffix="pp" tone={data.winRateDelta < 0 ? 'warn' : data.winRateDelta > 0 ? 'good' : undefined}    onClick={() => onJumpTo?.('pipeline')} testId="insights-kpi-win-rate" />
      <Tile icon={Clock}          label={t('ins_kpi_avg_cycle')}        tip={t('ins_tip_avg_cycle')}        value={data.avgCycle ? fmtDuration(data.avgCycle) : '—'} delta={null}                                                                                                    onClick={() => onJumpTo?.('pipeline')} testId="insights-kpi-avg-cycle-time" />
      <Tile icon={Shield}         label={t('ins_kpi_risk_score')}       tip={t('ins_tip_risk_score')}       value={fmtCompact(data.riskScore)}                      delta={null}              tone={riskTone}                                                                                  onClick={() => onJumpTo?.('risk')}     testId="insights-kpi-composite-risk-score" />
      <Tile icon={Lightning}      label={t('ins_kpi_critical_alerts')}  tip={t('ins_tip_critical_alerts')}  value={fmtCompact(data.criticalAlerts)}                 delta={null}              tone={data.criticalAlerts > 0 ? 'critical' : 'neutral'}                                          onClick={() => onJumpTo?.('risk')}     testId="insights-kpi-critical-alerts" />
    </div>
  );
};

export default OverviewKpiStrip;
