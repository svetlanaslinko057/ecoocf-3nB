/**
 * BIBI Cars — Wave 14 — Operations 360 (i18n-enabled)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  ChartLine, ArrowsClockwise, Warning, UsersThree, ClockCounterClockwise,
  Lifebuoy, TrendUp, Heartbeat, CurrencyEur, ReceiptX, Truck, Lightning,
  ArrowSquareOut, Flag, Users, ChartPieSlice,
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

const SEG_CLS = {
  critical:   { cls: 'bg-red-50 text-red-700 border-red-200',           dot: '#DC2626' },
  at_risk:    { cls: 'bg-orange-50 text-orange-800 border-orange-200',  dot: '#EA580C' },
  delay_risk: { cls: 'bg-amber-50 text-amber-800 border-amber-200',     dot: '#F59E0B' },
  delayed:    { cls: 'bg-orange-50 text-orange-800 border-orange-200',  dot: '#EA580C' },
  warning:    { cls: 'bg-amber-50 text-amber-800 border-amber-200',     dot: '#F59E0B' },
  on_track:   { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: '#10B981' },
  healthy:    { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: '#10B981' },
  delivered:  { cls: 'bg-sky-50 text-sky-700 border-sky-200',           dot: '#0284C7' },
  cancelled:  { cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',       dot: '#71717A' },
};

const Segment = ({ value, score, t }) => {
  const cfg = SEG_CLS[value] || SEG_CLS.healthy;
  const label = value ? (t(`w360_seg_${value}`) !== `w360_seg_${value}` ? t(`w360_seg_${value}`) : value.replace(/_/g, ' ')) : '—';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${cfg.cls}`}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {label}
      {typeof score === 'number' ? <span className="tabular-nums opacity-70">{score}</span> : null}
    </span>
  );
};

const KpiTile = ({ icon: Icon, label, value, hint, tone = 'neutral', onClick, testId, tooltip }) => {
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

const Operations360 = () => {
  const navigate = useNavigate();
  const { t } = useLang();
  const [tab, setTab] = useState('dashboard');
  const [dashboard, setDashboard]   = useState(null);
  const [bottlenecks, setBottlenecks] = useState(null);
  const [team, setTeam]             = useState({ items: [], total: 0 });
  const [sla, setSla]               = useState(null);
  const [risk, setRisk]             = useState({ items: [], total: 0, by_kind: {}, by_segment: {} });
  const [loading, setLoading]       = useState({ dashboard: true, bottlenecks: false, team: false, sla: false, risk: false });
  const [kindFilter, setKindFilter] = useState('');

  const TABS = useMemo(() => ([
    { key: 'dashboard',   label: t('w14_tab_dashboard'),   icon: ChartLine,             tooltip: t('tip_w14_tab_dashboard') },
    { key: 'bottlenecks', label: t('w14_tab_bottlenecks'), icon: Lightning,             tooltip: t('tip_w14_tab_bottlenecks') },
    { key: 'team',        label: t('w14_tab_team'),        icon: UsersThree,            tooltip: t('tip_w14_tab_team') },
    { key: 'sla',         label: t('w14_tab_sla'),         icon: ClockCounterClockwise, tooltip: t('tip_w14_tab_sla') },
    { key: 'risk',        label: t('w14_tab_risk'),        icon: Lifebuoy,              tooltip: t('tip_w14_tab_risk') },
  ]), [t]);

  const KIND_LABEL = useMemo(() => ({
    lead_cold:  t('w14_kind_lead_cold'),
    financial:  t('w14_kind_financial'),
    delivery:   t('w14_kind_delivery'),
  }), [t]);

  const load = useCallback(async (key) => {
    setLoading((l) => ({ ...l, [key]: true }));
    try {
      const r = await axios.get(`${API_URL}/api/operations/${key === 'dashboard' ? 'dashboard' : key === 'bottlenecks' ? 'bottlenecks' : key}`);
      const data = r.data?.data ?? r.data;
      if (key === 'dashboard')   setDashboard(data);
      if (key === 'bottlenecks') setBottlenecks(data);
      if (key === 'team')        setTeam({ items: r.data?.items || [], total: r.data?.total || 0 });
      if (key === 'sla')         setSla(data);
      if (key === 'risk')        setRisk({
        items: r.data?.items || [], total: r.data?.total || 0,
        by_kind: r.data?.by_kind || {}, by_segment: r.data?.by_segment || {},
      });
    } catch (err) {
      toast.error(err.response?.data?.detail || t('w14_load_failed').replace('{key}', key));
    } finally { setLoading((l) => ({ ...l, [key]: false })); }
  }, [t]);

  useEffect(() => { load('dashboard'); }, [load]);
  useEffect(() => { if (tab !== 'dashboard') load(tab); }, [tab, load]);

  const refreshAll = () => {
    load('dashboard');
    if (tab !== 'dashboard') load(tab);
  };

  const tiles = dashboard?.tiles || {};
  const ccy   = dashboard?.currency || 'EUR';

  const filteredRisk = useMemo(() => {
    if (!kindFilter) return risk.items;
    return risk.items.filter((it) => it.risk_kind === kindFilter);
  }, [risk.items, kindFilter]);

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}
                className="min-h-full space-y-4" data-testid="operations360-page">
      <PageHeader
        icon={ChartPieSlice}
        title={t('w14_title')}
        subtitle={dashboard?.scope?.all
          ? t('w360_scope_all')
          : t('w360_scope_managers').replace('{n}', dashboard?.scope?.managers || 0)}
        actions={
          <RefreshButton onClick={refreshAll} testId="operations360-refresh" />
        }
        testId="operations360-header"
      />

      <RoleZoneBadge variant="wave360" />

      <PageTabs tabs={TABS} active={tab} onChange={setTab} testId="operations360-tabs" />

      <div className="space-y-4">
        <div className="p-0 space-y-4">
          {/* ====== DASHBOARD ====== */}
          {tab === 'dashboard' ? (
            loading.dashboard && !dashboard ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  <KpiTile icon={Users}       label={t('w14_kpi_active_leads')}    value={tiles.active_leads || 0}   hint={t('w14_kpi_new_mtd').replace('{n}', tiles.new_leads_mtd || 0)} tooltip={t('tip_w14_kpi_active_leads')} testId="kpi-active-leads" />
                  <KpiTile icon={Flag}        label={t('w14_kpi_active_deals')}    value={tiles.active_deals || 0}   tooltip={t('tip_w14_kpi_active_deals')} testId="kpi-active-deals" />
                  <KpiTile icon={CurrencyEur} label={t('w14_kpi_revenue_mtd')}     value={fmt(tiles.revenue_mtd, ccy)} tone="good" tooltip={t('tip_w14_kpi_revenue_mtd')} testId="kpi-revenue-mtd" />
                  <KpiTile icon={TrendUp}     label={t('w14_kpi_profit_mtd')}      value={fmt(tiles.profit_mtd, ccy)}  tone={(tiles.profit_mtd || 0) >= 0 ? 'good' : 'bad'} tooltip={t('tip_w14_kpi_profit_mtd')} testId="kpi-profit-mtd" />
                  <KpiTile icon={ReceiptX}    label={t('w14_kpi_outstanding')}     value={fmt(tiles.outstanding, ccy)} tone={(tiles.outstanding || 0) > 0 ? 'warn' : 'good'} tooltip={t('tip_w14_kpi_outstanding')} testId="kpi-outstanding" />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KpiTile icon={Lifebuoy}    label={t('w14_kpi_collections')}     value={tiles.collections || 0}     hint={t('w14_kpi_collections_hint')} tone={tiles.collections ? 'warn' : 'good'} tooltip={t('tip_w14_kpi_collections')} onClick={() => navigate('/admin/finance')} testId="kpi-collections" />
                  <KpiTile icon={Truck}       label={t('w14_kpi_cars_in_transit')} value={tiles.cars_in_transit || 0} tooltip={t('tip_w14_kpi_cars_in_transit')} onClick={() => navigate('/admin/delivery')} testId="kpi-cars-in-transit" />
                  <KpiTile icon={Warning}     label={t('w14_kpi_critical_deliveries')} value={tiles.critical_deliveries || 0} tone={tiles.critical_deliveries ? 'bad' : 'good'} tooltip={t('tip_w14_kpi_critical_deliveries')} onClick={() => navigate('/admin/delivery')} testId="kpi-critical-deliveries" />
                  <KpiTile icon={Heartbeat}   label={t('w14_kpi_at_risk_deals')}   value={tiles.at_risk_deals || 0}   tone={tiles.at_risk_deals ? 'warn' : 'good'} tooltip={t('tip_w14_kpi_at_risk_deals')} onClick={() => setTab('risk')} testId="kpi-at-risk-deals" />
                </div>
              </>
            )
          ) : null}

          {/* ====== BOTTLENECKS ====== */}
          {tab === 'bottlenecks' ? (
            loading.bottlenecks && !bottlenecks ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : !bottlenecks || bottlenecks.total_active_deals === 0 ? (
              <div className="py-12 text-center text-[#71717A] text-sm">{t('w14_bot_none_active')}</div>
            ) : (
              <>
                <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4" data-testid="bottleneck-headline">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">{t('w14_bot_top_now')}</div>
                  {bottlenecks.top_bottleneck ? (
                    <>
                      <div className="text-2xl font-bold text-[#18181B] mt-1">{bottlenecks.top_bottleneck.label}</div>
                      <div className="text-[12px] text-[#71717A] mt-1">
                        {t('w14_bot_x_of_y')
                          .replace('{count}', bottlenecks.top_bottleneck.count)
                          .replace('{total}', bottlenecks.total_active_deals)
                          .replace('{pct}', Math.round((bottlenecks.top_bottleneck.count / bottlenecks.total_active_deals) * 100))}
                      </div>
                    </>
                  ) : (
                    <div className="text-base text-emerald-700 font-semibold mt-1">{t('w14_bot_none_detected')}</div>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {bottlenecks.ranked.map((b) => {
                    const pct = bottlenecks.total_active_deals ? Math.round((b.count / bottlenecks.total_active_deals) * 100) : 0;
                    return (
                      <div key={b.key} className="bg-white border border-[#E4E4E7] rounded-2xl p-3" data-testid={`bottleneck-row-${b.key}`}>
                        <div className="flex items-center justify-between">
                          <div className="text-[12px] font-semibold text-[#18181B]">{b.label}</div>
                          <div className="text-[14px] font-bold tabular-nums text-[#18181B]">{b.count}</div>
                        </div>
                        <div className="mt-2 h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                          <div className={`h-full ${b.count ? 'bg-[#18181B]' : 'bg-transparent'}`} style={{ width: `${pct}%` }} />
                        </div>
                        <div className="text-[11px] text-[#71717A] mt-1">{pct}% {t('w14_bot_of_active')}</div>
                      </div>
                    );
                  })}
                </div>

                {Object.keys(bottlenecks.by_stage || {}).length > 0 ? (
                  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
                    <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mb-2">{t('w14_bot_by_stage')}</div>
                    <div className="space-y-2">
                      {Object.entries(bottlenecks.by_stage).sort((a,b) => b[1] - a[1]).map(([stage, n]) => {
                        const pct = bottlenecks.total_active_deals ? Math.round((n / bottlenecks.total_active_deals) * 100) : 0;
                        return (
                          <div key={stage} className="flex items-center gap-3">
                            <div className="w-44 text-[12px] text-[#52525B] uppercase tracking-wider">{stage.replace(/_/g, ' ')}</div>
                            <div className="flex-1 h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                              <div className="h-full bg-[#18181B]" style={{ width: `${pct}%` }} />
                            </div>
                            <div className="w-12 text-right tabular-nums text-[12px] font-semibold text-[#18181B]">{n}</div>
                            <div className="w-10 text-right text-[11px] text-[#71717A]">{pct}%</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </>
            )
          ) : null}

          {/* ====== TEAM ====== */}
          {tab === 'team' ? (
            <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="team-table">
              <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                <div className="col-span-3">{t('w14_team_manager')}</div>
                <div className="col-span-1 text-right">{t('w14_team_leads')}</div>
                <div className="col-span-1 text-right">{t('w14_team_conv')}</div>
                <div className="col-span-1 text-right">{t('w14_team_deals')}</div>
                <div className="col-span-2 text-right">{t('w14_team_revenue')}</div>
                <div className="col-span-1 text-right">{t('w14_team_outstanding')}</div>
                <div className="col-span-1 text-right">{t('w14_team_coll')}</div>
                <div className="col-span-1 text-right">{t('w14_team_delays')}</div>
                <div className="col-span-1 text-right">{t('w14_team_score')}</div>
              </div>
              {loading.team ? (
                <div className="py-10 flex justify-center"><div className="w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
              ) : team.items.length === 0 ? (
                <div className="py-12 text-center text-[#71717A] text-sm">{t('w14_team_empty')}</div>
              ) : (
                <div className="divide-y divide-[#F4F4F5]">
                  {team.items.map((r) => {
                    const scoreTone = r.ops_score >= 80 ? 'text-emerald-700' : r.ops_score >= 60 ? 'text-amber-700' : 'text-red-700';
                    return (
                      <div key={r.manager_id || 'unassigned'} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`team-row-${r.manager_id || 'unassigned'}`}>
                        <div className="col-span-3 min-w-0">
                          <div className="font-medium text-[#18181B] truncate">{r.manager_name}</div>
                          <div className="text-[11px] text-[#71717A] truncate">{r.email || (r.role ? r.role.replace('_', ' ') : '')}</div>
                        </div>
                        <div className="col-span-1 text-right tabular-nums">{r.leads}</div>
                        <div className="col-span-1 text-right tabular-nums">{r.conversion_rate != null ? `${r.conversion_rate}%` : '—'}</div>
                        <div className="col-span-1 text-right tabular-nums">{r.deals}<span className="text-[10px] text-[#A1A1AA]"> ({r.deals_delivered}d)</span></div>
                        <div className="col-span-2 text-right tabular-nums">{fmt(r.revenue, ccy)}</div>
                        <div className="col-span-1 text-right tabular-nums">{fmt(r.outstanding, ccy)}</div>
                        <div className={`col-span-1 text-right tabular-nums ${r.collections ? 'font-semibold text-red-700' : ''}`}>{r.collections}</div>
                        <div className={`col-span-1 text-right tabular-nums ${r.delivery_delays ? 'font-semibold text-amber-700' : ''}`}>{r.delivery_delays}</div>
                        <div className={`col-span-1 text-right tabular-nums font-bold ${scoreTone}`}>{r.ops_score}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}

          {/* ====== SLA MONITOR ====== */}
          {tab === 'sla' ? (
            loading.sla && !sla ? (
              <div className="flex justify-center py-16"><div className="w-7 h-7 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
            ) : (
              <>
                <div className="bg-[#FAFAFA] border border-[#E4E4E7] rounded-2xl p-4 flex items-center gap-3 flex-wrap" data-testid="sla-summary">
                  <Warning size={20} weight="bold" className={sla?.total ? 'text-red-600' : 'text-emerald-600'} />
                  <div className="text-base font-semibold text-[#18181B]">{t('w14_sla_active').replace('{n}', sla?.total || 0)}</div>
                  <div className="text-[11px] text-[#71717A]">{t('w14_sla_across').replace('{n}', sla?.rules?.length || 0)}</div>
                </div>

                <div className="space-y-3">
                  {(sla?.rules || []).map((rule) => (
                    <div key={rule.id} className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid={`sla-rule-${rule.id}`}>
                      <div className="flex items-center justify-between px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA]">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${rule.count ? 'bg-red-500' : 'bg-emerald-500'}`} />
                          <div className="text-[13px] font-semibold text-[#18181B]">{rule.label}</div>
                          <div className="text-[11px] text-[#71717A]">{t('w14_sla_threshold')}: {rule.limit_label}</div>
                        </div>
                        <div className={`text-[13px] font-bold tabular-nums ${rule.count ? 'text-red-700' : 'text-emerald-700'}`}>{rule.count}</div>
                      </div>
                      {rule.count > 0 ? (
                        <div className="divide-y divide-[#F4F4F5]">
                          {rule.items.map((it) => (
                            <div key={it.id || it.label} className="flex items-center gap-2 px-4 py-2 text-[13px]" data-testid={`sla-item-${it.id || it.label}`}>
                              <button onClick={() => it.href && navigate(it.href)} className="flex-1 min-w-0 text-left truncate font-medium text-[#18181B] hover:underline">
                                {it.label} <ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" />
                              </button>
                              {it.manager ? <span className="text-[11px] text-[#71717A] truncate max-w-[140px]">{it.manager}</span> : null}
                              <span className="text-[12px] font-semibold text-red-700 tabular-nums">
                                {it.age_days != null ? `${it.age_days}d` : it.age_hours != null ? `${it.age_hours}h` : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="px-4 py-3 text-[12px] text-emerald-700">{t('w14_sla_no_violations_rule')}</div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )
          ) : null}

          {/* ====== RISK CENTER ====== */}
          {tab === 'risk' ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <KpiTile icon={Lifebuoy} label={t('w14_risk_total')}     value={risk.total} tone={risk.total ? 'warn' : 'good'} testId="risk-total" onClick={() => setKindFilter('')} />
                <KpiTile icon={Users}    label={t('w14_risk_cold_leads')} value={risk.by_kind?.lead_cold  || 0} tone={risk.by_kind?.lead_cold ? 'warn' : 'good'} testId="risk-cold-leads" onClick={() => setKindFilter('lead_cold')} />
                <KpiTile icon={CurrencyEur} label={t('w14_risk_financial')} value={risk.by_kind?.financial  || 0} tone={risk.by_kind?.financial ? 'warn' : 'good'} testId="risk-financial" onClick={() => setKindFilter('financial')} />
                <KpiTile icon={Truck}    label={t('w14_risk_delivery')}    value={risk.by_kind?.delivery   || 0} tone={risk.by_kind?.delivery ? 'warn' : 'good'} testId="risk-delivery" onClick={() => setKindFilter('delivery')} />
              </div>

              <div className="flex items-center gap-2 text-[12px]" data-testid="risk-filters">
                <span className="text-[#52525B] font-semibold">{t('w360_filter')}:</span>
                {[
                  { id: '',          label: t('w360_all') },
                  { id: 'lead_cold', label: t('w14_risk_cold_leads') },
                  { id: 'financial', label: t('w14_risk_financial') },
                  { id: 'delivery',  label: t('w14_risk_delivery') },
                ].map((opt) => {
                  const active = kindFilter === opt.id;
                  return (
                    <button key={opt.id || 'all'} onClick={() => setKindFilter(opt.id)}
                            className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold border ${active ? 'bg-[#18181B] text-white border-[#18181B]' : 'bg-white text-[#52525B] border-[#E4E4E7] hover:bg-[#F4F4F5]'}`}
                            data-testid={`risk-chip-${opt.id || 'all'}`}>{opt.label}</button>
                  );
                })}
              </div>

              <div className="bg-white border border-[#E4E4E7] rounded-2xl overflow-x-auto" data-testid="risk-table">
                <div className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2 border-b border-[#E4E4E7] bg-[#FAFAFA] text-[10px] uppercase tracking-wider font-bold text-[#71717A]">
                  <div className="col-span-3">{t('w14_risk_entity')}</div>
                  <div className="col-span-2">{t('w14_risk_kind')}</div>
                  <div className="col-span-2">{t('w14_team_manager')}</div>
                  <div className="col-span-1 text-right">{t('w14_risk_score')}</div>
                  <div className="col-span-2">{t('w14_risk_segment')}</div>
                  <div className="col-span-2">{t('w14_risk_top_reason')}</div>
                </div>
                {loading.risk ? (
                  <div className="py-10 flex justify-center"><div className="w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" /></div>
                ) : filteredRisk.length === 0 ? (
                  <div className="py-12 text-center text-[#71717A] text-sm">{t('w14_risk_empty')}</div>
                ) : (
                  <div className="divide-y divide-[#F4F4F5]">
                    {filteredRisk.map((it) => (
                      <div key={`${it.entity_type}-${it.entity_id}`} className="grid grid-cols-12 gap-2 min-w-[720px] px-4 py-2.5 items-center text-[13px]" data-testid={`risk-row-${it.entity_id}`}>
                        <div className="col-span-3 min-w-0">
                          <button onClick={() => it.href && navigate(it.href)} className="block w-full text-left truncate font-medium text-[#18181B] hover:underline">
                            {it.label} <ArrowSquareOut size={10} className="inline ml-0.5 text-[#A1A1AA]" />
                          </button>
                          <div className="text-[11px] text-[#71717A] truncate uppercase tracking-wider">{it.entity_type}</div>
                        </div>
                        <div className="col-span-2 text-[12px] text-[#52525B]">{KIND_LABEL[it.risk_kind] || it.risk_kind}</div>
                        <div className="col-span-2 text-[12px] text-[#52525B] truncate">{it.manager || '—'}</div>
                        <div className="col-span-1 text-right tabular-nums font-semibold">{it.score}</div>
                        <div className="col-span-2"><Segment value={it.segment} t={t} /></div>
                        <div className="col-span-2 text-[12px] text-[#52525B] truncate" title={(it.reasons || []).join(' · ')}>{(it.reasons && it.reasons[0]) || ''}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
};

export default Operations360;
