/**
 * InsightsPage.jsx — single role-aware Analytics & Insights hub.
 *
 * Replaces: /admin/analytics, /admin/owner-dashboard, /admin/journey,
 *           /admin/risk, /admin/escalations, /admin/documents,
 *           /admin/contracts/accounting, /admin/intent
 *
 * URL: /admin/insights  (with deep-link via ?tab=traffic|pipeline|revenue|team|risk)
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ChartBar, ChartLineUp, CurrencyDollar, UsersThree, ShieldCheck, ChartPie } from '@phosphor-icons/react';
import { useAuth } from '../App';
import { useLang } from '../i18n';
import OverviewKpiStrip from '../components/insights/OverviewKpiStrip';
import RiskAlertsVertical from '../components/insights/verticals/RiskAlertsVertical';
import TrafficVertical from '../components/insights/verticals/TrafficVertical';
import PipelineVertical from '../components/insights/verticals/PipelineVertical';
import RevenueVertical from '../components/insights/verticals/RevenueVertical';
import TeamManagersVertical from '../components/insights/verticals/TeamManagersVertical';
import InsightsHelpTooltip from '../components/insights/shared/InsightsHelpTooltip';
import { scopeForRole, tabsForRole } from '../components/insights/shared/insightsApi';

const TAB_META = {
  traffic:  { labelKey: 'ins_tab_traffic',  tipKey: 'ins_tip_tab_traffic',  icon: ChartBar,       testId: 'insights-tab-traffic' },
  pipeline: { labelKey: 'ins_tab_pipeline', tipKey: 'ins_tip_tab_pipeline', icon: ChartLineUp,    testId: 'insights-tab-pipeline' },
  revenue:  { labelKey: 'ins_tab_revenue',  tipKey: 'ins_tip_tab_revenue',  icon: CurrencyDollar, testId: 'insights-tab-revenue' },
  team:     { labelKey: 'ins_tab_team',     tipKey: 'ins_tip_tab_team',     icon: UsersThree,     testId: 'insights-tab-team' },
  risk:     { labelKey: 'ins_tab_risk',     tipKey: 'ins_tip_tab_risk',     icon: ShieldCheck,    testId: 'insights-tab-risk' },
};

const InsightsPage = () => {
  const { user } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const role = user?.role || 'manager';
  const scope = scopeForRole(role);
  const allowed = useMemo(() => tabsForRole(role), [role]);

  const initial = (searchParams.get('tab') || allowed[0] || 'risk');
  const [tab, setTab] = useState(allowed.includes(initial) ? initial : allowed[0]);
  const [period, setPeriod] = useState(Number(searchParams.get('days')) || 30);

  useEffect(() => {
    const p = new URLSearchParams(searchParams);
    p.set('tab', tab);
    p.set('days', String(period));
    setSearchParams(p, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, period]);

  const jumpTo = (target) => {
    if (!allowed.includes(target)) return;
    setTab(target);
    // scroll to top section of the new tab
    requestAnimationFrame(() => {
      const el = document.getElementById('insights-content');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const scopeBadge = {
    company:  { label: t('ins_scope_company'),  explainer: t('ins_subtitle_company') },
    team:     { label: t('ins_scope_team'),     explainer: t('ins_subtitle_team') },
    personal: { label: t('ins_scope_personal'), explainer: t('ins_subtitle_personal') },
  }[scope];

  return (
    <div className="min-h-screen bg-[#FAFAFA] p-6 pb-12" data-testid="insights-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <ChartPie size={20} weight="bold" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold tracking-tight text-[#18181B] leading-tight" style={{ fontFamily: 'Mazzard, Mazzard H, system-ui, sans-serif' }}>{t('ins_title')}</h1>
              <span data-testid="insights-scope-badge" className="inline-flex items-center rounded-md border border-[#E4E4E7] bg-white px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#52525B]">{scopeBadge.label}</span>
            </div>
            <p className="mt-0.5 text-[12px] text-[#71717A]">{scopeBadge.explainer}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="bg-white border border-[#E4E4E7] rounded-xl p-1 inline-flex" data-testid="insights-period-selector">
            {[
              { d: 7,  k: 'ins_period_7d' },
              { d: 30, k: 'ins_period_30d' },
              { d: 90, k: 'ins_period_90d' },
            ].map(({ d, k }) => (
              <button key={d} onClick={() => setPeriod(d)} className={`px-3 py-1.5 text-[12px] font-semibold rounded-lg transition-colors ${period===d?'bg-[#18181B] text-white':'text-[#52525B] hover:bg-[#FAFAFA]'}`}>{t(k)}</button>
            ))}
          </div>
        </div>
      </div>

      <div>
        {/* KPI Strip */}
        <OverviewKpiStrip period={period} role={role} onJumpTo={jumpTo} />

        {/* Tabs */}
        <div className="mt-5 overflow-x-auto" data-testid="insights-vertical-tabs">
          <div className="inline-flex min-w-full gap-1 rounded-2xl border border-[#E4E4E7] bg-white p-1">
            {allowed.map(k => {
              const meta = TAB_META[k];
              const Icon = meta.icon;
              const active = tab === k;
              return (
                <InsightsHelpTooltip key={k} text={t(meta.tipKey)} side="bottom" align="center" delay={250}>
                  <button onClick={() => setTab(k)} data-testid={meta.testId}
                    className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150 ${active ? 'bg-zinc-900 text-white shadow-sm' : 'text-zinc-700 hover:bg-zinc-100'}`}>
                    <Icon size={15} weight="duotone" />
                    <span>{t(meta.labelKey)}</span>
                  </button>
                </InsightsHelpTooltip>
              );
            })}
          </div>
        </div>

        {/* Vertical Content */}
        <div id="insights-content" className="mt-5">
          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.15 }}>
              {tab === 'traffic'  && <TrafficVertical scope={scope} period={period} />}
              {tab === 'pipeline' && <PipelineVertical scope={scope} period={period} />}
              {tab === 'revenue'  && <RevenueVertical scope={scope} period={period} />}
              {tab === 'team'     && <TeamManagersVertical scope={scope} period={period} />}
              {tab === 'risk'     && <RiskAlertsVertical scope={scope} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default InsightsPage;
