/**
 * BIBI Cars — Wave 16 — Executive Center
 *
 * Top-level governance lens over Ops360 / Forecast360 / Contract360 /
 * Finance360 / Delivery360. Pure read-only — no new state, no writes.
 *
 * Five tabs:
 *   1. Dashboard   — what is happening in the company today (15 KPI tiles)
 *   2. Forecast    — 30 / 60 / 90 expected revenue / profit / cash / risk
 *   3. Bottlenecks — unified Type / Severity / Owner / Impact € / Reason / Action
 *   4. Risks       — Lead / Financial / Delivery / Contract — merged feed
 *   5. Team        — Wave14 perf + Forecast Accuracy + Contracts-at-Risk
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  Crown, ArrowsClockwise, Users, Briefcase, CurrencyEur, Truck, Warning, FileText,
  ChartLine, Lifebuoy, UsersThree, ArrowSquareOut, ArrowUp, ArrowDown,
  Lightning, ClockCounterClockwise, ShieldCheck, Target, Buildings,
} from '@phosphor-icons/react';

import { API_URL } from '../App';
import { useLang } from '../i18n';
import { HelpTooltip } from '../components/ui/HelpTooltip';
import RefreshButton from '../components/ui/RefreshButton';
import { PageHeader, PageTabs } from '../components/ui/PageHeader';
import RoleZoneBadge from '../components/ui/RoleZoneBadge';

const fmt = (n, ccy = 'EUR') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};
const fmtN = (n) => new Intl.NumberFormat('en-US').format(Number(n || 0));
const pct = (n) => (n == null ? '—' : `${Number(n).toFixed(1)}%`);

const SEV_TONE = {
  critical:          { bg: 'bg-red-50',     border: 'border-red-200',     text: 'text-red-700' },
  at_risk:           { bg: 'bg-orange-50',  border: 'border-orange-200',  text: 'text-orange-700' },
  unsigned:          { bg: 'bg-orange-50',  border: 'border-orange-200',  text: 'text-orange-700' },
  wrong_version:     { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700' },
  missing_annex:     { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700' },
  delay_risk:        { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-700' },
  warning:           { bg: 'bg-yellow-50',  border: 'border-yellow-200',  text: 'text-yellow-700' },
  delayed:           { bg: 'bg-yellow-50',  border: 'border-yellow-200',  text: 'text-yellow-700' },
  pending_approval:  { bg: 'bg-blue-50',    border: 'border-blue-200',    text: 'text-blue-700' },
  draft:             { bg: 'bg-slate-50',   border: 'border-slate-200',   text: 'text-slate-700' },
  healthy:           { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
  on_track:          { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
  delivered:         { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700' },
  archived:          { bg: 'bg-zinc-100',   border: 'border-zinc-200',    text: 'text-zinc-600' },
};

const TYPE_TONE = {
  operations: 'bg-indigo-100 text-indigo-700',
  financial:  'bg-red-100 text-red-700',
  delivery:   'bg-purple-100 text-purple-700',
  contract:   'bg-cyan-100 text-cyan-700',
  lead:       'bg-yellow-100 text-yellow-700',
};

const SevBadge = ({ value }) => {
  const t = SEV_TONE[value] || SEV_TONE.warning;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${t.bg} ${t.border} ${t.text}`}>
      {(value || '—').replace(/_/g, ' ')}
    </span>
  );
};

const TypeBadge = ({ value }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${TYPE_TONE[value] || 'bg-slate-100 text-slate-700'}`}>
    {(value || '—').replace(/_/g, ' ')}
  </span>
);

const KpiTile = ({ icon: Icon, label, value, hint, tone = 'neutral', onClick, testId, tooltip }) => {
  const cls = {
    neutral:  'bg-white border-[#E4E4E7]',
    good:     'bg-emerald-50 border-emerald-200',
    warn:     'bg-amber-50 border-amber-200',
    bad:      'bg-red-50 border-red-200',
    accent:   'bg-indigo-50 border-indigo-200',
    money:    'bg-[#FAFAFA] border-[#E4E4E7]',
  }[tone] || 'bg-white border-[#E4E4E7]';
  const interactive = onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : '';
  const tile = (
    <div className={`border rounded-2xl p-4 ${cls} ${interactive}`} onClick={onClick} data-testid={testId}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
        <Icon size={14} weight="bold" /> {label}
      </div>
      <div className="text-[22px] font-bold text-[#18181B] mt-1 tabular-nums leading-tight">{value}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5">{hint}</div> : null}
    </div>
  );
  return tooltip ? <HelpTooltip text={tooltip}>{tile}</HelpTooltip> : tile;
};

const TABS_FACTORY = (t) => ([
  { key: 'dashboard',   label: t('w16_tab_dashboard'),   icon: Crown,        tooltip: t('tip_w16_tab_dashboard') },
  { key: 'forecast',    label: t('w16_tab_forecast'),    icon: ChartLine,    tooltip: t('tip_w16_tab_forecast') },
  { key: 'bottlenecks', label: t('w16_tab_bottlenecks'), icon: Lightning,    tooltip: t('tip_w16_tab_bottlenecks') },
  { key: 'risks',       label: t('w16_tab_risks'),       icon: Lifebuoy,     tooltip: t('tip_w16_tab_risks') },
  { key: 'team',        label: t('w16_tab_team'),        icon: UsersThree,   tooltip: t('tip_w16_tab_team') },
]);

export default function ExecutiveCenter() {
  const navigate = useNavigate();
  const { t } = useLang();
  const TABS = useMemo(() => TABS_FACTORY(t), [t]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get('tab') || 'dashboard');
  const [data, setData] = useState({});
  const [loading, setLoading] = useState({});

  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const setData_ = (k, v) => setData((prev) => ({ ...prev, [k]: v }));
  const setLoad_ = (k, v) => setLoading((prev) => ({ ...prev, [k]: v }));

  const load = useCallback(async (key) => {
    setLoad_(key, true);
    try {
      const { data: res } = await axios.get(`${API_URL}/api/executive/${key}`, { headers });
      setData_(key, res?.data || null);
    } catch (e) {
      toast.error(t('w16_load_fail').replace('{key}', key));
    } finally { setLoad_(key, false); }
  }, [headers, t]);

  useEffect(() => {
    setSearchParams((prev) => { const next = new URLSearchParams(prev); next.set('tab', tab); return next; });
    load(tab);
  }, [tab, load, setSearchParams]);

  const refresh = () => load(tab);
  const goto = (path) => navigate(path);

  const dashboard = data.dashboard;
  const forecast  = data.forecast;
  const bottle    = data.bottlenecks;
  const risks     = data.risks;
  const team      = data.team;

  return (
    <div className="min-h-full" data-testid="executive-center">
      {/* HEADER */}
      <PageHeader
        icon={Crown}
        title={t('w16_title')}
        subtitle={t('w16_subtitle')}
        actions={<RefreshButton onClick={refresh} testId="exec-refresh" />}
        testId="executive-center-header"
      />

      <div className="mb-4"><RoleZoneBadge variant="wave360" /></div>

      {/* TABS */}
      <PageTabs
        tabs={TABS}
        active={tab}
        onChange={setTab}
        testId="exec-tabs"
      />

      <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="space-y-5">

        {/* ========================= DASHBOARD ========================= */}
        {tab === 'dashboard' ? (
          loading.dashboard && !dashboard ? <Spinner />
          : dashboard ? (
            <>
              {/* Three answer-blocks: today / money / contracts */}
              <Section title={t('w16_sec_pipeline')} question={t('w16_sec_pipeline_q')}>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="dash-pipeline">
                  <KpiTile icon={Users}     label={t('w16_kpi_active_leads')}     value={fmtN(dashboard.tiles.active_leads)} tone="neutral" tooltip={t('tip_w16_kpi_active_leads')} onClick={() => goto('/admin/leads')} />
                  <KpiTile icon={Buildings} label={t('w16_kpi_active_customers')} value={fmtN(dashboard.tiles.active_customers)} tone="neutral" tooltip={t('tip_w16_kpi_active_customers')} onClick={() => goto('/admin/customers')} />
                  <KpiTile icon={Briefcase} label={t('w16_kpi_active_deals')}     value={fmtN(dashboard.tiles.active_deals)} tone="accent" tooltip={t('tip_w16_kpi_active_deals')} onClick={() => goto('/admin/deals')} />
                  <KpiTile icon={Truck}     label={t('w16_kpi_cars_transit')}     value={fmtN(dashboard.tiles.cars_in_transit)} hint={t('w16_kpi_critical').replace('{n}', dashboard.tiles.critical_deliveries)} tone={dashboard.tiles.critical_deliveries > 0 ? 'bad' : 'neutral'} tooltip={t('tip_w16_kpi_cars_transit')} onClick={() => goto('/admin/operations')} />
                </div>
              </Section>

              <Section title={t('w16_sec_money')} question={t('w16_sec_money_q')}>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="dash-money">
                  <KpiTile icon={CurrencyEur}        label={t('w16_kpi_revenue_mtd')} value={fmt(dashboard.tiles.revenue_mtd,  dashboard.currency)} tone="good" tooltip={t('tip_w16_kpi_revenue_mtd')} onClick={() => goto('/admin/finance')} />
                  <KpiTile icon={ArrowUp}            label={t('w16_kpi_profit_mtd')}  value={fmt(dashboard.tiles.profit_mtd,   dashboard.currency)} tone="good" tooltip={t('tip_w16_kpi_profit_mtd')} />
                  <KpiTile icon={ArrowDown}          label={t('w16_kpi_outstanding')} value={fmt(dashboard.tiles.outstanding,  dashboard.currency)} tone={dashboard.tiles.outstanding > 0 ? 'warn' : 'neutral'} tooltip={t('tip_w16_kpi_outstanding')} onClick={() => goto('/admin/finance?tab=outstanding')} />
                  <KpiTile icon={ClockCounterClockwise} label={t('w16_kpi_collections')} value={fmtN(dashboard.tiles.collections)} hint={t('w16_kpi_coll_hint')} tone={dashboard.tiles.collections > 0 ? 'warn' : 'good'} tooltip={t('tip_w16_kpi_collections')} />
                </div>
              </Section>

              <Section title={t('w16_sec_contracts')} question={t('w16_sec_contracts_q')}>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="dash-contracts">
                  <KpiTile icon={FileText}    label={t('w16_kpi_unsigned')} value={fmtN(dashboard.tiles.unsigned_contracts)} hint={t('w16_kpi_unsigned_hint').replace('{v}', fmt(dashboard.tiles.unsigned_value, dashboard.currency))} tone={dashboard.tiles.unsigned_contracts > 0 ? 'bad' : 'good'} tooltip={t('tip_w16_kpi_unsigned')} onClick={() => goto('/admin/contracts?tab=risk')} />
                  <KpiTile icon={ShieldCheck} label={t('w16_kpi_pending')}  value={fmtN(dashboard.tiles.pending_approvals)}  tone={dashboard.tiles.pending_approvals > 0 ? 'warn' : 'good'} tooltip={t('tip_w16_kpi_pending')} onClick={() => goto('/admin/contracts?tab=approvals')} />
                  <KpiTile icon={ClockCounterClockwise} label={t('w16_kpi_expiring')} value={fmtN(dashboard.tiles.expiring_contracts)} tone={dashboard.tiles.expiring_contracts > 0 ? 'warn' : 'good'} tooltip={t('tip_w16_kpi_expiring')} />
                  <KpiTile icon={Warning}     label={t('w16_kpi_at_risk')}  value={fmt(dashboard.tiles.revenue_at_risk, dashboard.currency)} hint={t('w16_kpi_at_risk_hint')} tone={dashboard.tiles.revenue_at_risk > 0 ? 'bad' : 'good'} tooltip={t('tip_w16_kpi_at_risk')} onClick={() => goto('/admin/forecast?tab=risk')} />
                </div>
              </Section>

              {/* Forecast strip — 30 / 60 / 90 */}
              <Section title={t('w16_sec_outlook')} question={t('w16_sec_outlook_q')}>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="dash-horizons">
                  {['30','60','90'].map((h) => {
                    const b = dashboard.horizons?.[h] || {};
                    return (
                      <div key={h} className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">{t('w16_horizon_days').replace('{n}', h)}</div>
                          <div className="text-[11px] text-[#71717A] tabular-nums">{t('w16_horizon_deals').replace('{n}', b.deals || 0)}</div>
                        </div>
                        <div className="text-[20px] font-bold text-[#18181B] tabular-nums">{fmt(b.weighted, dashboard.currency)}</div>
                        <div className="text-[11px] text-[#71717A] mt-1">{t('w16_horizon_meta').replace('{g}', fmt(b.gross, dashboard.currency)).replace('{p}', fmt(b.profit, dashboard.currency))}</div>
                      </div>
                    );
                  })}
                </div>
              </Section>
            </>
          ) : null
        ) : null}

        {/* ========================= FORECAST ========================== */}
        {tab === 'forecast' ? (
          loading.forecast && !forecast ? <Spinner />
          : forecast ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="forecast-horizons">
                {['30','60','90'].map((h) => {
                  const b = forecast.horizons?.[h] || {};
                  return (
                    <div key={h} className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">+{h} days</div>
                        <div className="text-[11px] text-[#71717A]">{b.deals || 0} deals</div>
                      </div>
                      <div className="text-[24px] font-bold text-[#18181B] tabular-nums mb-2">{fmt(b.expected_revenue, forecast.currency)}</div>
                      <div className="text-[11px] text-[#71717A]">Expected revenue</div>
                      <div className="border-t border-[#F4F4F5] mt-3 pt-3 grid grid-cols-2 gap-2 text-[12px]">
                        <div><div className="text-[10px] uppercase text-[#71717A] tracking-wider font-bold">Profit</div><div className="font-semibold tabular-nums">{fmt(b.expected_profit, forecast.currency)}</div></div>
                        <div><div className="text-[10px] uppercase text-[#71717A] tracking-wider font-bold">Weighted</div><div className="font-semibold tabular-nums">{fmt(b.weighted_revenue, forecast.currency)}</div></div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Cash flow strip */}
              <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5" data-testid="forecast-cashflow">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">13-week cash flow</div>
                  <div className="text-[11px] text-[#71717A]">In {fmt(forecast.cash_in_total, forecast.currency)} · Out {fmt(forecast.cash_out_total, forecast.currency)}</div>
                </div>
                <div className="flex items-end gap-1 h-32" data-testid="forecast-cashflow-bars">
                  {(forecast.weeks || []).map((w, i) => {
                    const maxV = Math.max(1, ...(forecast.weeks || []).map((x) => Math.max(x.cash_in || 0, x.cash_out || 0)));
                    const inH  = ((w.cash_in  || 0) / maxV) * 100;
                    const outH = ((w.cash_out || 0) / maxV) * 100;
                    return (
                      <div key={i} className="flex-1 flex flex-col items-center gap-0.5" title={`W${w.week}: in ${fmt(w.cash_in)} · out ${fmt(w.cash_out)} · net ${fmt(w.net)}`}>
                        <div className="w-full bg-emerald-200 rounded-t" style={{ height: `${inH}%` }} />
                        <div className="w-full bg-red-200 rounded-b" style={{ height: `${outH}%` }} />
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Forecast risk */}
              <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5" data-testid="forecast-risk">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Forecast risk</div>
                  <div className="text-[11px] text-[#71717A]">{fmt(forecast.forecast_risk?.value, forecast.currency)} · {pct(forecast.forecast_risk?.share_pct)} of forecast</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(forecast.forecast_risk?.by_kind || {}).map(([k, v]) => (
                    <div key={k} className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl px-3 py-2 text-[12px]">
                      <span className="text-[#71717A] capitalize">{k}: </span>
                      <span className="font-semibold tabular-nums">{fmt(v, forecast.currency)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null
        ) : null}

        {/* ========================= BOTTLENECKS ======================= */}
        {tab === 'bottlenecks' ? (
          loading.bottlenecks && !bottle ? <Spinner />
          : bottle ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="bottlenecks-kpis">
                <KpiTile icon={Lightning} label="Bottlenecks" value={fmtN(bottle.total)} hint={`${fmt(bottle.impact_total, bottle.currency)} blocked`} tone={bottle.total > 0 ? 'warn' : 'good'} />
                <KpiTile icon={Warning}   label="Critical"    value={fmtN(bottle.by_severity?.critical || 0)} hint={`${fmt(bottle.impact_critical, bottle.currency)} at stake`} tone={(bottle.by_severity?.critical || 0) > 0 ? 'bad' : 'good'} />
                {Object.entries(bottle.by_type || {}).slice(0, 2).map(([t, n]) => (
                  <KpiTile key={t} icon={Target} label={t.replace(/_/g, ' ')} value={fmtN(n)} tone="neutral" />
                ))}
              </div>
              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
                <table className="w-full text-[13px]" data-testid="bottlenecks-table">
                  <thead className="bg-[#FAFAFA] text-left text-[10px] uppercase tracking-wider text-[#71717A]">
                    <tr>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Severity</th>
                      <th className="px-4 py-3">Owner</th>
                      <th className="px-4 py-3">Label</th>
                      <th className="px-4 py-3 text-right">Impact €</th>
                      <th className="px-4 py-3">Reason</th>
                      <th className="px-4 py-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F4F4F5]">
                    {(bottle.items || []).length === 0 ? (
                      <tr><td colSpan={7} className="px-4 py-6 text-center text-sm text-[#71717A]">No bottlenecks. Smooth board.</td></tr>
                    ) : (bottle.items || []).map((r, i) => (
                      <tr key={i} className={`hover:bg-[#FAFAFA] ${r.href ? 'cursor-pointer' : ''}`} onClick={() => r.href && navigate(r.href)} data-testid={`bottleneck-row-${i}`}>
                        <td className="px-4 py-3"><TypeBadge value={r.type} /></td>
                        <td className="px-4 py-3"><SevBadge value={r.severity} /></td>
                        <td className="px-4 py-3 text-[12px]">{r.owner || '—'}</td>
                        <td className="px-4 py-3 font-medium text-[#18181B] truncate max-w-[260px]">{r.label || r.entity_id}{r.href ? <ArrowSquareOut size={10} className="inline ml-1 text-[#A1A1AA]" /> : null}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{fmt(r.impact, bottle.currency)}</td>
                        <td className="px-4 py-3 text-[11px] text-[#71717A] truncate max-w-[220px]">{r.reason}</td>
                        <td className="px-4 py-3 text-[11px] font-semibold text-[#18181B]">{r.action}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null
        ) : null}

        {/* ============================ RISKS ========================== */}
        {tab === 'risks' ? (
          loading.risks && !risks ? <Spinner />
          : risks ? (
            <>
              <div className="grid grid-cols-3 gap-3" data-testid="risks-kpis">
                <KpiTile icon={Warning}   label="Critical"  value={fmtN(risks.summary?.critical || 0)} tone={(risks.summary?.critical || 0) > 0 ? 'bad'  : 'good'} />
                <KpiTile icon={Lifebuoy}  label="At risk"   value={fmtN(risks.summary?.at_risk  || 0)} tone={(risks.summary?.at_risk  || 0) > 0 ? 'warn' : 'good'} />
                <KpiTile icon={ClockCounterClockwise} label="Warning" value={fmtN(risks.summary?.warning || 0)} tone="neutral" />
              </div>
              <div className="bg-white border border-[#E4E4E7] rounded-2xl p-3 flex flex-wrap gap-2 text-[12px]" data-testid="risks-by-kind">
                {Object.entries(risks.by_kind || {}).map(([k, v]) => (
                  <span key={k} className="inline-flex items-center gap-1 px-2 py-1 bg-[#FAFAFA] border border-[#E4E4E7] rounded-lg">
                    <span className="text-[#71717A] uppercase tracking-wider text-[10px] font-bold">{k}</span>
                    <span className="font-semibold tabular-nums">{v}</span>
                  </span>
                ))}
              </div>
              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
                <table className="w-full text-[13px]" data-testid="risks-table">
                  <thead className="bg-[#FAFAFA] text-left text-[10px] uppercase tracking-wider text-[#71717A]">
                    <tr>
                      <th className="px-4 py-3">Kind</th>
                      <th className="px-4 py-3">Segment</th>
                      <th className="px-4 py-3">Entity</th>
                      <th className="px-4 py-3">Owner</th>
                      <th className="px-4 py-3 text-right">Score</th>
                      <th className="px-4 py-3">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F4F4F5]">
                    {(risks.items || []).length === 0 ? (
                      <tr><td colSpan={6} className="px-4 py-6 text-center text-sm text-[#71717A]">No risks tracked.</td></tr>
                    ) : (risks.items || []).map((r, i) => (
                      <tr key={i} className={`hover:bg-[#FAFAFA] ${r.href ? 'cursor-pointer' : ''}`} onClick={() => r.href && navigate(r.href)} data-testid={`risk-row-${i}`}>
                        <td className="px-4 py-3"><TypeBadge value={r.risk_kind?.replace('lead_cold', 'lead') || r.entity_type} /></td>
                        <td className="px-4 py-3"><SevBadge value={r.segment} /></td>
                        <td className="px-4 py-3 font-medium text-[#18181B] truncate max-w-[280px]">{r.label}{r.href ? <ArrowSquareOut size={10} className="inline ml-1 text-[#A1A1AA]" /> : null}</td>
                        <td className="px-4 py-3 text-[12px]">{r.manager || '—'}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{r.score ?? '—'}</td>
                        <td className="px-4 py-3 text-[11px] text-[#71717A] truncate max-w-[260px]">{(r.reasons || [])[0]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null
        ) : null}

        {/* ============================= TEAM ========================== */}
        {tab === 'team' ? (
          loading.team && !team ? <Spinner />
          : team ? (
            <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden">
              <table className="w-full text-[13px]" data-testid="team-table">
                <thead className="bg-[#FAFAFA] text-left text-[10px] uppercase tracking-wider text-[#71717A]">
                  <tr>
                    <th className="px-4 py-3">Manager</th>
                    <th className="px-4 py-3 text-right">Leads</th>
                    <th className="px-4 py-3 text-right">Deals</th>
                    <th className="px-4 py-3 text-right">Conv %</th>
                    <th className="px-4 py-3 text-right">Revenue</th>
                    <th className="px-4 py-3 text-right">Profit</th>
                    <th className="px-4 py-3 text-right">Outstanding</th>
                    <th className="px-4 py-3 text-right">Collections</th>
                    <th className="px-4 py-3 text-right">Contracts@Risk</th>
                    <th className="px-4 py-3 text-right">Forecast accuracy</th>
                    <th className="px-4 py-3 text-right">Ops score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F4F4F5]">
                  {(team.items || []).length === 0 ? (
                    <tr><td colSpan={11} className="px-4 py-6 text-center text-sm text-[#71717A]">No team data yet.</td></tr>
                  ) : (team.items || []).map((r) => (
                    <tr key={r.manager_id || r.manager_name} className="hover:bg-[#FAFAFA]" data-testid={`team-row-${r.manager_id || 'unassigned'}`}>
                      <td className="px-4 py-3 font-medium text-[#18181B]">{r.manager_name}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.leads)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.deals)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{pct(r.conversion_rate)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(r.revenue,  team.currency)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(r.profit,   team.currency)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(r.outstanding, team.currency)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.collections)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmtN(r.contracts_at_risk || 0)}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.forecast_accuracy == null ? '—' : `${r.forecast_accuracy}%`}</td>
                      <td className="px-4 py-3 text-right">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-bold tabular-nums ${
                          r.ops_score >= 80 ? 'bg-emerald-100 text-emerald-700'
                          : r.ops_score >= 60 ? 'bg-amber-100 text-amber-700'
                          : 'bg-red-100 text-red-700'}`}>{r.ops_score}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null
        ) : null}
      </motion.div>
    </div>
  );
}

const Spinner = () => (
  <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
);

const Section = ({ title, question, children }) => (
  <div data-testid={`section-${title.toLowerCase().replace(/\s/g,'-')}`}>
    <div className="flex items-baseline justify-between mb-2 px-1">
      <h3 className="text-[14px] font-bold text-[#18181B]">{title}</h3>
      <span className="text-[11px] text-[#71717A] italic">{question}</span>
    </div>
    {children}
  </div>
);
