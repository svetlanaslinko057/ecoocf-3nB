/**
 * BIBI Cars — Wave 12C — Forecasting 360
 *
 * Pure deterministic forecaster surface (no AI). Sits on top of the
 * existing Lead → Deal → Finance → Delivery stack and answers three
 * questions on Overview:
 *   • How much? — weighted revenue across 30/60/90 horizons
 *   • When?     — cash in/out per week across 13 weeks
 *   • What can derail it? — top 5 at-risk forecast lines
 *
 * Drill-down tabs: Revenue / Cash Flow / Pipeline / Capacity / Risk.
 * Every deal row is click-through to Deal 360.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  ChartLine, ArrowsClockwise, CurrencyEur, TrendUp, Warning, ArrowSquareOut,
  Calendar, UsersThree, ChartPieSlice, Lifebuoy, Heartbeat, ChartLineUp, Boat,
} from '@phosphor-icons/react';

import { API_URL } from '../App';
import RefreshButton from '../components/ui/RefreshButton';
import { PageHeader, PageTabs } from '../components/ui/PageHeader';
import RoleZoneBadge from '../components/ui/RoleZoneBadge';
import { HelpTooltip } from '../components/ui/HelpTooltip';
import { useLang } from '../i18n';

const fmt = (n, ccy = 'EUR') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};

const KpiTile = ({ icon: Icon, label, value, hint, tone = 'neutral', testId, onClick, tooltip }) => {
  const toneCls = {
    neutral: 'bg-white border-[#E4E4E7]',
    good:    'bg-emerald-50 border-emerald-200',
    warn:    'bg-amber-50 border-amber-200',
    bad:     'bg-red-50 border-red-200',
  }[tone] || 'bg-white border-[#E4E4E7]';
  const interactive = onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : '';
  const tile = (
    <div className={`border rounded-2xl p-4 ${toneCls} ${interactive}`} onClick={onClick} data-testid={testId}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
        <Icon size={14} weight="bold" /> {label}
      </div>
      <div className="text-2xl font-bold text-[#18181B] mt-1 tabular-nums">{value}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5">{hint}</div> : null}
    </div>
  );
  return tooltip ? <HelpTooltip text={tooltip}>{tile}</HelpTooltip> : tile;
};

const TABS_FACTORY = (t) => ([
  { key: 'overview',  label: t('w12c_tab_overview'),  icon: ChartLine,       tooltip: t('tip_w12c_tab_overview') },
  { key: 'revenue',   label: t('w12c_tab_revenue'),   icon: TrendUp,         tooltip: t('tip_w12c_tab_revenue') },
  { key: 'cashflow',  label: t('w12c_tab_cashflow'),  icon: CurrencyEur,     tooltip: t('tip_w12c_tab_cashflow') },
  { key: 'pipeline',  label: t('w12c_tab_pipeline'),  icon: ChartPieSlice,   tooltip: t('tip_w12c_tab_pipeline') },
  { key: 'capacity',  label: t('w12c_tab_capacity'),  icon: UsersThree,      tooltip: t('tip_w12c_tab_capacity') },
  { key: 'risk',      label: t('w12c_tab_risk'),      icon: Lifebuoy,        tooltip: t('tip_w12c_tab_risk') },
]);

// ─── Charts (lightweight, no extra deps) ─────────────────────────────────
const Bars = ({ rows, valueKey = 'weighted', labelKey = 'period', ccy = 'EUR' }) => {
  const max = Math.max(1, ...rows.map((r) => Number(r[valueKey] || 0)));
  return (
    <div className="space-y-2">
      {rows.map((r, i) => {
        const v = Number(r[valueKey] || 0);
        const pct = Math.round((v / max) * 100);
        return (
          <div key={r[labelKey] || i} className="flex items-center gap-3">
            <div className="w-40 text-[12px] text-[#52525B] uppercase tracking-wider truncate">{(r[labelKey] || '').toString().replace(/_/g, ' ')}</div>
            <div className="flex-1 h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
              <div className="h-full bg-[#18181B]" style={{ width: `${pct}%` }} />
            </div>
            <div className="w-28 text-right tabular-nums text-[12px] font-semibold text-[#18181B]">{fmt(v, ccy)}</div>
            {r.deals != null ? <div className="w-12 text-right text-[11px] text-[#71717A]">{r.deals}d</div> : null}
          </div>
        );
      })}
    </div>
  );
};

const WeekColumns = ({ weeks, ccy }) => {
  const maxIn  = Math.max(1, ...weeks.map((w) => Number(w.cash_in || 0)));
  const maxOut = Math.max(1, ...weeks.map((w) => Number(w.cash_out || 0)));
  const max    = Math.max(maxIn, maxOut);
  return (
    <div className="flex items-end gap-1 overflow-x-auto pb-2" data-testid="cashflow-chart">
      {weeks.map((w, idx) => {
        const start = new Date(w.start);
        const label = `${(start.getMonth() + 1).toString().padStart(2, '0')}/${start.getDate().toString().padStart(2, '0')}`;
        const inH  = max ? Math.max(2, Math.round((w.cash_in  / max) * 120)) : 2;
        const outH = max ? Math.max(2, Math.round((w.cash_out / max) * 120)) : 2;
        return (
          <div key={idx} className="flex-1 min-w-[36px] flex flex-col items-center text-center">
            <div className="flex items-end gap-0.5 h-[130px]">
              <div title={fmt(w.cash_in, ccy)}  className="w-3 bg-emerald-500 rounded-t" style={{ height: `${inH}px` }} />
              <div title={fmt(w.cash_out, ccy)} className="w-3 bg-red-500     rounded-t" style={{ height: `${outH}px` }} />
            </div>
            <div className="text-[10px] text-[#71717A] mt-1 tabular-nums">{label}</div>
            <div className={`text-[10px] tabular-nums ${w.net >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>{w.net >= 0 ? '+' : ''}{(w.net / 1000).toFixed(0)}k</div>
          </div>
        );
      })}
    </div>
  );
};

const SEG_CLS = {
  warning:    { cls: 'bg-amber-50 text-amber-800 border-amber-200',    dot: '#F59E0B' },
  at_risk:    { cls: 'bg-orange-50 text-orange-800 border-orange-200', dot: '#EA580C' },
  critical:   { cls: 'bg-red-50 text-red-700 border-red-200',          dot: '#DC2626' },
  delay_risk: { cls: 'bg-amber-50 text-amber-800 border-amber-200',    dot: '#F59E0B' },
  delayed:    { cls: 'bg-orange-50 text-orange-800 border-orange-200', dot: '#EA580C' },
};

const SegBadge = ({ value }) => {
  if (!value) return <span className="text-[#A1A1AA]">—</span>;
  const cfg = SEG_CLS[value] || { cls: 'bg-zinc-100 text-zinc-700 border-zinc-200', dot: '#71717A' };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${cfg.cls}`}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {value.replace(/_/g, ' ')}
    </span>
  );
};

// ─── Page ─────────────────────────────────────────────────────────────────
const Forecasting360 = () => {
  const navigate = useNavigate();
  const { t } = useLang();
  const TABS = useMemo(() => TABS_FACTORY(t), [t]);
  const [tab, setTab] = useState('overview');
  const [data, setData]   = useState({ overview: null, revenue: null, cashflow: null, pipeline: null, capacity: null, risk: null });
  const [loading, setLoading] = useState({ overview: true });

  const load = useCallback(async (key) => {
    setLoading((l) => ({ ...l, [key]: true }));
    try {
      const slug = key === 'cashflow' ? 'cash-flow' : key;
      const r = await axios.get(`${API_URL}/api/forecast/${slug}`);
      setData((d) => ({ ...d, [key]: r.data?.data || null }));
    } catch (err) {
      toast.error(err.response?.data?.detail || `Failed to load ${key} forecast`);
    } finally { setLoading((l) => ({ ...l, [key]: false })); }
  }, []);

  useEffect(() => { load('overview'); }, [load]);
  useEffect(() => {
    if (tab !== 'overview' && !data[tab]) load(tab);
  }, [tab, load, data]);

  const refreshAll = () => {
    load('overview');
    if (tab !== 'overview') load(tab);
  };

  const ccy = data.overview?.currency || 'EUR';

  const overviewHorizons = useMemo(() => {
    if (!data.overview?.how_much?.horizons) return [];
    return Object.entries(data.overview.how_much.horizons)
      .sort((a, b) => Number(a[0]) - Number(b[0]))
      .map(([days, b]) => ({ days, ...b }));
  }, [data.overview]);

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
                className="min-h-full space-y-4" data-testid="forecast360-page">
      <PageHeader
        icon={ChartLineUp}
        title={t('w12c_title')}
        subtitle={`${t('w12c_subtitle')} · ${data.overview?.scope?.all
          ? t('w360_scope_all')
          : t('w360_scope_managers').replace('{n}', data.overview?.scope?.managers || 0)}`}
        actions={<RefreshButton onClick={refreshAll} testId="forecast360-refresh" />}
        testId="forecast360-header"
      />

      <div className="mb-4"><RoleZoneBadge variant="wave360" /></div>

      <PageTabs tabs={TABS} active={tab} onChange={setTab} testId="forecast360-tabs" />

      <div className="space-y-4">
        <div className="p-0 space-y-4">

          {/* ===== OVERVIEW ===== */}
          {tab === 'overview' ? (
            loading.overview && !data.overview ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : data.overview ? (
              <>
                {/* HOW MUCH */}
                <div data-testid="overview-how-much">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w12c_how_much')}</div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {overviewHorizons.map((h) => (
                      <KpiTile
                        key={h.days}
                        icon={TrendUp}
                        label={t('w12c_next_days').replace('{n}', h.days)}
                        value={fmt(h.weighted, ccy)}
                        hint={t('w12c_deals_weighted').replace('{n}', h.deals)}
                        tone={h.weighted > 0 ? 'good' : 'neutral'}
                        testId={`overview-horizon-${h.days}`}
                        onClick={() => setTab('revenue')}
                      />
                    ))}
                  </div>
                </div>

                {/* WHEN */}
                <div data-testid="overview-when">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w12c_when')}</div>
                  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                    <WeekColumns weeks={data.overview.when?.weeks || []} ccy={ccy} />
                    <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-[#F4F4F5]">
                      <div><div className="text-[10px] uppercase text-[#71717A]">{t('w12c_cash_in_13w')}</div><div className="text-[14px] font-semibold text-emerald-700 tabular-nums">{fmt(data.overview.when?.totals?.cash_in, ccy)}</div></div>
                      <div><div className="text-[10px] uppercase text-[#71717A]">{t('w12c_cash_out_13w')}</div><div className="text-[14px] font-semibold text-red-700 tabular-nums">{fmt(data.overview.when?.totals?.cash_out, ccy)}</div></div>
                      <div><div className="text-[10px] uppercase text-[#71717A]">{t('w12c_net')}</div><div className={`text-[14px] font-semibold tabular-nums ${(data.overview.when?.totals?.net || 0) >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>{fmt(data.overview.when?.totals?.net, ccy)}</div></div>
                    </div>
                  </div>
                </div>

                {/* WHAT CAN DERAIL IT */}
                <div data-testid="overview-derail">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w12c_derail')}</div>
                  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                      <KpiTile icon={Warning}    label={t('w12c_risk_total')}    value={fmt(data.overview.derail?.risk_total, ccy)} tone={(data.overview.derail?.risk_total || 0) > 0 ? 'warn' : 'good'} testId="derail-risk-total" />
                      <KpiTile icon={Heartbeat}  label={t('w12c_risk_share')}    value={`${data.overview.derail?.risk_share_pct || 0}%`} tone={(data.overview.derail?.risk_share_pct || 0) > 30 ? 'bad' : (data.overview.derail?.risk_share_pct || 0) > 10 ? 'warn' : 'good'} testId="derail-risk-share" />
                      <KpiTile icon={CurrencyEur} label={t('w14_risk_financial')} value={fmt(data.overview.derail?.by_kind?.financial, ccy)} tone={(data.overview.derail?.by_kind?.financial || 0) > 0 ? 'warn' : 'good'} testId="derail-financial" />
                      <KpiTile icon={Boat}       label={t('w14_risk_delivery')}  value={fmt(data.overview.derail?.by_kind?.delivery,  ccy)} tone={(data.overview.derail?.by_kind?.delivery  || 0) > 0 ? 'warn' : 'good'} testId="derail-delivery" />
                    </div>
                    {(data.overview.derail?.top_items || []).length === 0 ? (
                      <div className="text-sm text-[#71717A] py-2">{t('w12c_no_derail')}</div>
                    ) : (
                      <div className="divide-y divide-[#F4F4F5]" data-testid="derail-top-items">
                        {(data.overview.derail?.top_items || []).map((it) => (
                          <button key={it.deal_id} onClick={() => navigate(`/admin/deals/${it.deal_id}/360`)}
                                  className="w-full grid grid-cols-12 gap-2 py-2 items-center text-left text-[13px] hover:bg-[#FAFAFA] px-2 -mx-2 rounded">
                            <div className="col-span-4 truncate font-medium text-[#18181B]">{it.deal_title}<ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" /></div>
                            <div className="col-span-2 text-[12px] text-[#52525B] capitalize">{it.risk_kind}</div>
                            <div className="col-span-2"><SegBadge value={it.segment} /></div>
                            <div className="col-span-2 text-right tabular-nums font-semibold text-red-700">{fmt(it.at_risk, ccy)}</div>
                            <div className="col-span-2 text-[11px] text-[#71717A] truncate">{(it.reasons || [])[0]}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </>
            ) : null
          ) : null}

          {/* ===== REVENUE ===== */}
          {tab === 'revenue' ? (
            loading.revenue && !data.revenue ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : data.revenue ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {Object.entries(data.revenue.horizons || {}).sort((a, b) => Number(a[0]) - Number(b[0])).map(([days, b]) => (
                    <KpiTile key={days} icon={ChartLineUp} label={(t('fc_next_days') || 'Next {n} days').replace('{n}', days)} value={fmt(b.weighted, ccy)} hint={`${b.deals} ${t('fc_col_deals').toLowerCase()} · ${t('fc_col_gross').toLowerCase()} ${fmt(b.gross, ccy)}`} tone={b.weighted > 0 ? 'good' : 'neutral'} testId={`revenue-horizon-${days}`} />
                  ))}
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="revenue-by-stage">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">{t('fc_weighted_by_stage') || 'Weighted revenue by stage'}</div>
                  {Object.keys(data.revenue.by_stage || {}).length === 0 ? (
                    <div className="text-sm text-[#71717A]">{t('fc_no_open_deals')}</div>
                  ) : (
                    <Bars rows={Object.entries(data.revenue.by_stage).map(([stage, v]) => ({ period: stage, ...v }))} ccy={ccy} />
                  )}
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="revenue-table">
                  <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                    <div className="col-span-4">{t('fc_col_deal_manager')}</div>
                    <div className="col-span-2">{t('fc_col_stage')}</div>
                    <div className="col-span-1 text-right">{t('fc_col_prob') || 'Prob.'}</div>
                    <div className="col-span-2 text-right">{t('fc_col_gross')}</div>
                    <div className="col-span-2 text-right">{t('fc_col_weighted')}</div>
                    <div className="col-span-1 text-right">{t('fc_col_days')}</div>
                  </div>
                  {(data.revenue.items || []).length === 0 ? (
                    <div className="py-12 text-center text-[#71717A] text-sm">{t('fc_no_open_contrib')}</div>
                  ) : (
                    <div className="divide-y divide-[#F4F4F5]">
                      {data.revenue.items.map((it) => (
                        <button key={it.deal_id} onClick={() => navigate(`/admin/deals/${it.deal_id}/360`)}
                                className="w-full grid grid-cols-12 gap-2 px-4 py-2 items-center text-left text-[13px] hover:bg-[#FAFAFA]"
                                data-testid={`revenue-row-${it.deal_id}`}>
                          <div className="col-span-4 min-w-0">
                            <div className="truncate font-medium text-[#18181B]">{it.deal_title}<ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" /></div>
                            <div className="text-[11px] text-[#71717A] truncate">{it.manager_name || '—'}</div>
                          </div>
                          <div className="col-span-2 text-[12px] text-[#52525B] uppercase tracking-wider">{(it.stage || '').replace(/_/g, ' ')}</div>
                          <div className="col-span-1 text-right tabular-nums">{Math.round(it.probability * 100)}%</div>
                          <div className="col-span-2 text-right tabular-nums">{fmt(it.gross, ccy)}</div>
                          <div className="col-span-2 text-right tabular-nums font-semibold">{fmt(it.weighted, ccy)}</div>
                          <div className="col-span-1 text-right tabular-nums text-[#52525B]">{it.days_out}d</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : null
          ) : null}

          {/* ===== CASH FLOW ===== */}
          {tab === 'cashflow' ? (
            loading.cashflow && !data.cashflow ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : data.cashflow ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <KpiTile icon={TrendUp}      label={`${t('fc_col_cash_in')} (13w)`}  value={fmt(data.cashflow.totals?.cash_in, ccy)}  tone="good" tooltip={t('tip_w12c_tab_cashflow')} testId="cashflow-in" />
                  <KpiTile icon={CurrencyEur}  label={`${t('fc_col_cash_out')} (13w)`} value={fmt(data.cashflow.totals?.cash_out, ccy)} tone={(data.cashflow.totals?.cash_out || 0) > 0 ? 'warn' : 'neutral'} tooltip={t('tip_w12c_tab_cashflow')} testId="cashflow-out" />
                  <KpiTile icon={ChartLine}    label={t('fc_col_net')}            value={fmt(data.cashflow.totals?.net, ccy)} tone={(data.cashflow.totals?.net || 0) >= 0 ? 'good' : 'bad'} tooltip={t('tip_w12c_tab_cashflow')} testId="cashflow-net" />
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">{t('fc_weekly_13') || 'Weekly cash flow · next 13 weeks'}</div>
                  <WeekColumns weeks={data.cashflow.weeks || []} ccy={ccy} />
                  <div className="flex items-center gap-4 mt-2 text-[11px] text-[#71717A]">
                    <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 bg-emerald-500 rounded-sm" /> {t('fc_col_cash_in')}</span>
                    <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 bg-red-500 rounded-sm" /> {t('fc_col_cash_out')}</span>
                  </div>
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto">
                  <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                    <div className="col-span-3">{t('fc_col_week')}</div>
                    <div className="col-span-1 text-right">{t('fc_col_deals')}</div>
                    <div className="col-span-2 text-right">{t('fc_col_cash_in')}</div>
                    <div className="col-span-2 text-right">{t('fc_col_cash_out')}</div>
                    <div className="col-span-2 text-right">{t('fc_col_net')}</div>
                    <div className="col-span-2 text-right">{t('fc_col_running')}</div>
                  </div>
                  <div className="divide-y divide-[#F4F4F5]">
                    {(data.cashflow.weeks || []).map((w) => (
                      <div key={w.week} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 items-center text-[13px]" data-testid={`cashflow-week-${w.week}`}>
                        <div className="col-span-3 text-[12px] text-[#52525B]">{new Date(w.start).toLocaleDateString()} – {new Date(w.end).toLocaleDateString()}</div>
                        <div className="col-span-1 text-right tabular-nums">{w.deals_in}</div>
                        <div className="col-span-2 text-right tabular-nums text-emerald-700">{fmt(w.cash_in, ccy)}</div>
                        <div className="col-span-2 text-right tabular-nums text-red-700">{fmt(w.cash_out, ccy)}</div>
                        <div className={`col-span-2 text-right tabular-nums font-semibold ${w.net >= 0 ? 'text-emerald-700' : 'text-red-700'}`}>{fmt(w.net, ccy)}</div>
                        <div className="col-span-2 text-right tabular-nums">{fmt(w.running_balance, ccy)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : null
          ) : null}

          {/* ===== PIPELINE ===== */}
          {tab === 'pipeline' ? (
            loading.pipeline && !data.pipeline ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : data.pipeline ? (
              <>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="pipeline-by-stage">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">{t('fc_by_stage_weighted') || 'By stage (weighted)'}</div>
                  {data.pipeline.by_stage.length === 0 ? <div className="text-sm text-[#71717A]">{t('fc_no_pipeline')}</div> :
                    <Bars rows={data.pipeline.by_stage.map((s) => ({ period: s.stage, ...s }))} ccy={ccy} />}
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="pipeline-by-month">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">{t('fc_by_month_weighted') || 'By month (weighted)'}</div>
                  {data.pipeline.by_month.length === 0 ? <div className="text-sm text-[#71717A]">{t('no_data')}</div> :
                    <Bars rows={data.pipeline.by_month} ccy={ccy} />}
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="pipeline-by-quarter">
                  <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-3">{t('fc_by_quarter_weighted') || 'By quarter (weighted)'}</div>
                  {data.pipeline.by_quarter.length === 0 ? <div className="text-sm text-[#71717A]">{t('no_data')}</div> :
                    <Bars rows={data.pipeline.by_quarter} ccy={ccy} />}
                </div>
              </>
            ) : null
          ) : null}

          {/* ===== CAPACITY ===== */}
          {tab === 'capacity' ? (
            loading.capacity && !data.capacity ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : data.capacity ? (
              <>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="capacity-managers">
                  <div className="px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] flex items-center justify-between">
                    <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{t('fc_capacity_managers_header').replace('{n}', data.capacity.manager_target)}</div>
                  </div>
                  {data.capacity.managers.length === 0 ? <div className="py-10 text-center text-[#71717A] text-sm">{t('fc_no_active_managers')}</div> :
                    <div className="divide-y divide-[#F4F4F5]">
                      {data.capacity.managers.map((m) => {
                        const tone = m.status === 'overloaded' ? 'text-red-700' : m.status === 'high' ? 'text-amber-700' : m.status === 'healthy' ? 'text-emerald-700' : 'text-[#52525B]';
                        return (
                          <div key={m.manager_id || 'unassigned'} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`capacity-mgr-${m.manager_id || 'unassigned'}`}>
                            <div className="col-span-3 font-medium text-[#18181B] truncate">{m.manager_name}</div>
                            <div className="col-span-1 text-right tabular-nums">{m.open_deals}/{m.target}</div>
                            <div className="col-span-5 px-2"><div className="h-2 bg-[#F4F4F5] rounded-full overflow-hidden"><div className={`h-full ${m.utilization >= 100 ? 'bg-red-500' : m.utilization >= 80 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${m.utilization}%` }} /></div></div>
                            <div className={`col-span-1 text-right tabular-nums font-bold ${tone}`}>{m.utilization}%</div>
                            <div className="col-span-2 text-right tabular-nums">{fmt(m.weighted_pipeline, ccy)}</div>
                          </div>
                        );
                      })}
                    </div>
                  }
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="capacity-carriers">
                  <div className="px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA]">
                    <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">{t('fc_capacity_carriers_header').replace('{n}', data.capacity.carrier_target)}</div>
                  </div>
                  {data.capacity.carriers.length === 0 ? <div className="py-10 text-center text-[#71717A] text-sm">{t('fc_no_active_carriers')}</div> :
                    <div className="divide-y divide-[#F4F4F5]">
                      {data.capacity.carriers.map((c) => {
                        const tone = c.status === 'overloaded' ? 'text-red-700' : c.status === 'high' ? 'text-amber-700' : c.status === 'healthy' ? 'text-emerald-700' : 'text-[#52525B]';
                        return (
                          <div key={c.carrier_id || 'unassigned'} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`capacity-car-${c.carrier_id || 'unassigned'}`}>
                            <div className="col-span-4 font-medium text-[#18181B] truncate">{c.carrier_name}</div>
                            <div className="col-span-1 text-right tabular-nums">{c.open_loads}/{c.target}</div>
                            <div className="col-span-5 px-2"><div className="h-2 bg-[#F4F4F5] rounded-full overflow-hidden"><div className={`h-full ${c.utilization >= 100 ? 'bg-red-500' : c.utilization >= 80 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${c.utilization}%` }} /></div></div>
                            <div className={`col-span-2 text-right tabular-nums font-bold ${tone}`}>{c.utilization}%</div>
                          </div>
                        );
                      })}
                    </div>
                  }
                </div>
              </>
            ) : null
          ) : null}

          {/* ===== RISK ===== */}
          {tab === 'risk' ? (
            loading.risk && !data.risk ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : data.risk ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KpiTile icon={ChartLineUp}  label={t('w12c_risk_forecast_total')} value={fmt(data.risk.forecast_total, ccy)} testId="risk-forecast-total" />
                  <KpiTile icon={Warning}      label={t('w12c_risk_at_risk')}        value={fmt(data.risk.risk_total, ccy)} tone={data.risk.risk_total > 0 ? 'warn' : 'good'} testId="risk-at-risk" />
                  <KpiTile icon={Heartbeat}    label={t('w12c_risk_share')}          value={`${data.risk.risk_share_pct}%`} tone={data.risk.risk_share_pct > 30 ? 'bad' : data.risk.risk_share_pct > 10 ? 'warn' : 'good'} testId="risk-share" />
                  <KpiTile icon={Boat}         label={t('w12c_risk_deals_at_risk')}  value={data.risk.total} testId="risk-count" />
                </div>
                <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="risk-table">
                  <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                    <div className="col-span-4">{t('w12c_risk_col_deal_manager')}</div>
                    <div className="col-span-2">{t('w12c_risk_col_kind')}</div>
                    <div className="col-span-2">{t('w12c_risk_col_segment')}</div>
                    <div className="col-span-1 text-right">{t('w12c_risk_col_weighted')}</div>
                    <div className="col-span-1 text-right">{t('w12c_risk_col_at_risk')}</div>
                    <div className="col-span-2">{t('w12c_risk_col_reason')}</div>
                  </div>
                  {data.risk.items.length === 0 ? (
                    <div className="py-12 text-center text-[#71717A] text-sm">{t('w12c_risk_empty')}</div>
                  ) : (
                    <div className="divide-y divide-[#F4F4F5]">
                      {data.risk.items.map((it) => (
                        <button key={it.deal_id} onClick={() => navigate(`/admin/deals/${it.deal_id}/360`)}
                                className="w-full grid grid-cols-12 gap-2 px-4 py-2 items-center text-left text-[13px] hover:bg-[#FAFAFA]"
                                data-testid={`risk-row-${it.deal_id}`}>
                          <div className="col-span-4 min-w-0">
                            <div className="truncate font-medium text-[#18181B]">{it.deal_title}<ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" /></div>
                            <div className="text-[11px] text-[#71717A] truncate">{it.manager_name || '—'}</div>
                          </div>
                          <div className="col-span-2 text-[12px] text-[#52525B] capitalize">{it.risk_kind}</div>
                          <div className="col-span-2"><SegBadge value={it.segment} /></div>
                          <div className="col-span-1 text-right tabular-nums">{fmt(it.weighted, ccy)}</div>
                          <div className="col-span-1 text-right tabular-nums font-semibold text-red-700">{fmt(it.at_risk, ccy)}</div>
                          <div className="col-span-2 text-[11px] text-[#71717A] truncate">{(it.reasons || [])[0]}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : null
          ) : null}

        </div>
      </div>
    </motion.div>
  );
};

export default Forecasting360;
