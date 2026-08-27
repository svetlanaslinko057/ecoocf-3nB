/**
 * Risk Dashboard Page — mobile-first redesign.
 *
 *   • Unified header with action row that wraps on mobile (Live chip +
 *     Pause/Resume + Daily check + Refresh).
 *   • Overall risk indicator becomes a single AdminCard with stacked
 *     content on small screens (no horizontal squeeze).
 *   • Risk cards (Suspicious sessions / Critical invoices / etc.) use
 *     AdminStat — consistent across pages, no card-in-card.
 *   • Critical Alerts / Staff Risk Analysis lists use plain inset rows
 *     inside one outer AdminCard (no border-in-border).
 *   • Modal uses single-card layout with stacked sections.
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useLang } from '../../i18n';
import RefreshButton from '../../components/ui/RefreshButton';
import {
  Shield,
  AlertTriangle,
  AlertCircle,
  Users,
  UserX,
  Activity,
  RefreshCw,
  Eye,
  XCircle,
  CheckCircle,
  Monitor,
  Wifi,
} from 'lucide-react';

import {
  AdminPageHeader,
  AdminCard,
  AdminStat,
} from '../../components/ui/AdminPagePrimitives';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const RISK_COLORS = {
  low:      { bg: 'bg-emerald-50',  border: 'border-emerald-300', text: 'text-emerald-700', icon: CheckCircle },
  medium:   { bg: 'bg-amber-50',    border: 'border-amber-300',   text: 'text-amber-700',   icon: AlertTriangle },
  high:     { bg: 'bg-orange-50',   border: 'border-orange-300',  text: 'text-orange-700',  icon: AlertCircle },
  critical: { bg: 'bg-rose-50',     border: 'border-rose-300',    text: 'text-rose-700',    icon: XCircle },
};

const RiskDashboardPage = () => {
  const { t, lang } = useLang();
  const [loading, setLoading] = useState(true);
  const [criticalAlerts, setCriticalAlerts] = useState([]);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [selectedRisk, setSelectedRisk] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const fetchData = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const [alertsRes, dashboardRes] = await Promise.all([
        axios.get(`${API_URL}/api/alerts/critical?limit=20`, { headers }).catch(() => ({ data: { alerts: [] } })),
        axios.get(`${API_URL}/api/owner-dashboard`, { headers }).catch(() => ({ data: null })),
      ]);
      setCriticalAlerts(alertsRes.data?.alerts || []);
      setDashboardStats(dashboardRes.data);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Failed to fetch risk data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    if (autoRefresh) {
      const interval = setInterval(fetchData, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchData, autoRefresh]);

  const runDailyCheck = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API_URL}/api/risk/daily-check`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchData();
    } catch (err) {
      console.error('Daily check failed:', err);
    }
  };

  const assessManager = async (managerId) => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`${API_URL}/api/risk/manager/${managerId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSelectedRisk(res.data);
    } catch (err) {
      console.error('Manager assessment failed:', err);
    }
  };

  const risk = dashboardStats?.risk || {
    suspiciousSessions: 0,
    criticalInvoices: 0,
    riskyShipments: 0,
    integrationsDown: 0,
  };

  const totalRiskScore =
    risk.suspiciousSessions * 20 +
    risk.criticalInvoices * 15 +
    risk.riskyShipments * 10 +
    risk.integrationsDown * 25;

  const overallRiskLevel =
    totalRiskScore >= 70 ? 'critical' :
    totalRiskScore >= 50 ? 'high' :
    totalRiskScore >= 30 ? 'medium' : 'low';

  const riskStyle = RISK_COLORS[overallRiskLevel];
  const RiskIcon = riskStyle.icon;

  return (
    <div className="space-y-4 sm:space-y-5" data-testid="risk-dashboard">
      {/*
        Risk Dashboard header — custom inline layout (June 2026).
        Mobile (< sm):
          ┌─────────────────────────────────────────────┐
          │ [icon] Risk Dashboard          [Refresh]    │
          │        Risk and alerts monitoring           │
          ├─────────────────────────────────────────────┤
          │ [● Live]  [Pause]  [Daily check]            │   ← toolbar
          └─────────────────────────────────────────────┘
        Desktop (≥ sm): everything inline on a single row.
      */}
      <header
        className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5"
        data-testid="risk-header"
      >
        <div className="flex items-start gap-3 sm:gap-4">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Shield className="w-[18px] h-[18px]" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight break-words">
              {t('riskDashboardTitle') || t('adm2_42cdb12fba') || 'Risk Dashboard'}
            </h1>
            <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed break-words">
              {t('riskDashboardSubtitle') || t('adm2_9d77ef153f')}
            </p>
          </div>
          {/* Desktop toolbar (Live + Pause + Daily check + Refresh) inline right. */}
          <div className="hidden sm:flex items-center gap-2 shrink-0">
            <span
              className={[
                'inline-flex items-center gap-1.5 px-2.5 h-8 rounded-full text-[11.5px] font-semibold',
                autoRefresh
                  ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                  : 'bg-zinc-100 text-zinc-500 ring-1 ring-zinc-200',
              ].join(' ')}
            >
              <Wifi className="w-3 h-3" />
              {autoRefresh ? 'Live' : (t('paused') || 'Paused')}
            </span>
            <button
              type="button"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className="inline-flex items-center justify-center h-9 px-3.5 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[12.5px] font-medium text-[#18181B] focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
            >
              {autoRefresh ? (t('pause') || 'Pause') : (t('resume') || 'Resume')}
            </button>
            <button
              type="button"
              onClick={runDailyCheck}
              data-testid="daily-check-btn"
              className="inline-flex items-center justify-center gap-1.5 h-9 px-3.5 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[12.5px] font-medium text-[#18181B] focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>{lang === 'uk' ? t('adm2_662670c22d') : 'Daily check'}</span>
            </button>
            <RefreshButton
              onClick={fetchData}
              loading={loading}
              ariaLabel={lang === 'uk' ? t('adm2_b6bf91f845') : 'Refresh'}
              testId="refresh-btn"
            />
          </div>
          {/* Mobile-only refresh pinned top-RIGHT. */}
          <div className="sm:hidden shrink-0">
            <RefreshButton
              onClick={fetchData}
              loading={loading}
              ariaLabel={lang === 'uk' ? t('adm2_b6bf91f845') : 'Refresh'}
              testId="refresh-btn-mobile"
            />
          </div>
        </div>
        {/* Mobile-only toolbar row: Live chip + Pause + Daily check. */}
        <div className="mt-4 sm:hidden flex flex-wrap items-center gap-2">
          <span
            className={[
              'inline-flex items-center gap-1.5 px-2.5 h-8 rounded-full text-[11.5px] font-semibold',
              autoRefresh
                ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
                : 'bg-zinc-100 text-zinc-500 ring-1 ring-zinc-200',
            ].join(' ')}
          >
            <Wifi className="w-3 h-3" />
            {autoRefresh ? 'Live' : (t('paused') || 'Paused')}
          </span>
          <button
            type="button"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className="inline-flex items-center justify-center h-9 px-3.5 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[12.5px] font-medium text-[#18181B] focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
          >
            {autoRefresh ? (t('pause') || 'Pause') : (t('resume') || 'Resume')}
          </button>
          <button
            type="button"
            onClick={runDailyCheck}
            data-testid="daily-check-btn-mobile"
            className="inline-flex items-center justify-center gap-1.5 h-9 px-3.5 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[12.5px] font-medium text-[#18181B] focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>{lang === 'uk' ? t('adm2_662670c22d') : 'Daily check'}</span>
          </button>
        </div>
      </header>

      {/* Overall risk indicator — stacked on mobile */}
      <AdminCard className={`${riskStyle.bg} ${riskStyle.border}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-12 h-12 rounded-xl bg-white border ${riskStyle.border} flex items-center justify-center shrink-0`}>
              <RiskIcon className={`w-6 h-6 ${riskStyle.text}`} />
            </div>
            <div className="min-w-0">
              <h2 className={`text-[14px] font-semibold ${riskStyle.text} uppercase tracking-wide`}>
                {lang === 'uk' ? t('adm2_cdb840f566') : 'Risk Level'}: {overallRiskLevel}
              </h2>
              <p className="text-[12px] text-[#52525B] mt-0.5">
                {lang === 'uk' ? t('adm2_8f1615ca97') : 'Overall system assessment'}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className={`text-[36px] sm:text-[40px] leading-none font-bold tabular-nums ${riskStyle.text}`}>
              {totalRiskScore}
            </p>
            <p className="text-[11px] text-[#71717A] mt-1">
              {lang === 'uk' ? t('adm2_b71f1aa544') : 'Total score'}
            </p>
          </div>
        </div>
        <p className="text-[11px] text-[#A1A1AA] mt-3">
          {lang === 'uk' ? t('adm2_0bad20a575') : 'Last updated'}: {lastUpdate.toLocaleTimeString()}
        </p>
      </AdminCard>

      {/* Risk category KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-3">
        <AdminStat
          label={lang === 'uk' ? t('adm2_ff906bba54') : 'Suspicious sessions'}
          value={risk.suspiciousSessions}
          icon={Monitor}
          tone={risk.suspiciousSessions > 0 ? 'warning' : 'default'}
        />
        <AdminStat
          label={lang === 'uk' ? t('adm2_18ac0c5698') : 'Critical invoices'}
          value={risk.criticalInvoices}
          icon={AlertCircle}
          tone={risk.criticalInvoices > 0 ? 'negative' : 'default'}
        />
        <AdminStat
          label={lang === 'uk' ? t('adm2_9c07c1c8aa') : 'Risky shipments'}
          value={risk.riskyShipments}
          icon={AlertTriangle}
          tone={risk.riskyShipments > 0 ? 'warning' : 'default'}
        />
        <AdminStat
          label={lang === 'uk' ? t('adm2_down_d9dcc4a164') : 'Integrations down'}
          value={risk.integrationsDown}
          icon={XCircle}
          tone={risk.integrationsDown > 0 ? 'negative' : 'default'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-5">
        {/* Critical alerts */}
        <AdminCard>
          <h3 className="text-[14.5px] font-semibold text-[#18181B] mb-3 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-500" />
            {lang === 'uk' ? t('adm2_417e68f5e3') : 'Critical alerts'}
            {criticalAlerts.length > 0 && (
              <span className="bg-rose-500 text-white text-[10.5px] px-1.5 py-0.5 rounded-full font-semibold">
                {criticalAlerts.length}
              </span>
            )}
          </h3>
          <div className="space-y-2 max-h-[360px] overflow-y-auto" data-testid="alerts-feed" style={{ WebkitOverflowScrolling: 'touch' }}>
            {criticalAlerts.length > 0 ? (
              criticalAlerts.map((alert, idx) => (
                <AlertItem key={idx} alert={alert} lang={lang} />
              ))
            ) : (
              <div className="text-center py-8">
                <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                <p className="text-[#71717A] text-[12.5px]">
                  {lang === 'uk' ? t('adm2_32dd984c47') : 'No critical alerts'}
                </p>
              </div>
            )}
          </div>
        </AdminCard>

        {/* Staff risk analysis */}
        <AdminCard>
          <h3 className="text-[14.5px] font-semibold text-[#18181B] mb-3 flex items-center gap-2">
            <Users className="w-4 h-4 text-[#3B82F6]" />
            {lang === 'uk' ? t('adm2_b5fcea47ef') : 'Staff risk analysis'}
          </h3>
          {dashboardStats?.people?.underperformers?.length > 0 ? (
            <div className="space-y-2" data-testid="manager-risks">
              {dashboardStats.people.underperformers.map((manager, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => assessManager(manager.id)}
                  className="w-full text-left bg-[#FAFAFA] rounded-xl p-3 hover:bg-[#F4F4F5] transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-9 h-9 bg-white rounded-full flex items-center justify-center shrink-0 border border-[#E4E4E7]">
                        <UserX className="w-4 h-4 text-[#71717A]" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[13px] text-[#18181B] font-medium truncate">{manager.name || 'Manager'}</p>
                        <p className="text-[11.5px] text-[#71717A] truncate">{manager.email}</p>
                      </div>
                    </div>
                    <Eye className="w-4 h-4 text-[#A1A1AA] shrink-0" />
                  </div>
                  {manager.issues && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {manager.issues.map((issue, i) => (
                        <span key={i} className="bg-rose-100 text-rose-700 text-[10.5px] px-1.5 py-0.5 rounded font-medium">
                          {issue}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
              <p className="text-[#71717A] text-[12.5px]">
                {lang === 'uk' ? t('adm2_5760d498c8') : 'No staff issues detected'}
              </p>
            </div>
          )}
        </AdminCard>
      </div>

      {selectedRisk && (
        <RiskModal risk={selectedRisk} onClose={() => setSelectedRisk(null)} lang={lang} />
      )}
    </div>
  );
};

// Alert item
const AlertItem = ({ alert, lang }) => {
  const { t } = useLang();
  const priorityBorder = alert.priority === 'critical' ? 'border-l-rose-500' : 'border-l-orange-500';
  return (
    <div className={`bg-[#FAFAFA] border-l-[3px] ${priorityBorder} rounded-r-xl p-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[12.5px] text-[#18181B] font-medium leading-tight">{alert.title}</p>
          <p className="text-[12px] text-[#52525B] mt-0.5 leading-relaxed">{alert.message}</p>
          {alert.manager && (
            <p className="text-[11px] text-[#A1A1AA] mt-1.5">
              {lang === 'uk' ? t('adm2_d2ae4c4732') : 'Manager'}: {alert.manager.name}
            </p>
          )}
        </div>
        <span className="text-[10.5px] text-[#A1A1AA] tabular-nums whitespace-nowrap shrink-0">
          {new Date(alert.time).toLocaleTimeString()}
        </span>
      </div>
    </div>
  );
};

// Modal
const RiskModal = ({ risk, onClose, lang }) => {
  const { t } = useLang();
  const riskStyle = RISK_COLORS[risk.riskLevel] || RISK_COLORS.low;
  const RiskIcon = riskStyle.icon;
  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl p-5 max-w-lg w-full border border-[#E4E4E7] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[16px] font-semibold text-[#18181B]">
            {lang === 'uk' ? t('adm2_91f9e26abb') : 'Risk Assessment'}
          </h3>
          <button onClick={onClose} className="text-[#A1A1AA] hover:text-[#18181B]">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <div className={`${riskStyle.bg} ${riskStyle.border} border rounded-xl p-3 mb-4`}>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <RiskIcon className={`w-6 h-6 ${riskStyle.text} shrink-0`} />
              <div className="min-w-0">
                <p className={`text-[13px] font-bold ${riskStyle.text} uppercase`}>{risk.riskLevel}</p>
                <p className="text-[11.5px] text-[#71717A] truncate">{risk.entityType}</p>
              </div>
            </div>
            <p className={`text-[28px] font-bold tabular-nums ${riskStyle.text}`}>{risk.riskScore}</p>
          </div>
        </div>

        <div className="mb-4">
          <h4 className="text-[12px] font-semibold uppercase tracking-wider text-[#71717A] mb-2">
            {lang === 'uk' ? t('adm2_806072cf8f') : 'Risk factors'}
          </h4>
          <div className="space-y-1.5">
            {risk.factors && risk.factors.length > 0 ? risk.factors.map((factor, idx) => (
              <div key={idx} className="bg-[#FAFAFA] rounded-lg px-3 py-2 flex items-center justify-between gap-2">
                <span className="text-[12.5px] text-[#3F3F46] min-w-0 truncate">{factor.description}</span>
                <span className="text-[12px] text-amber-600 font-semibold tabular-nums shrink-0">+{factor.weight}</span>
              </div>
            )) : (
              <p className="text-[#71717A] text-[12.5px]">{t('adm_no_factors_detected')}</p>
            )}
          </div>
        </div>

        {risk.recommendations?.length > 0 && (
          <div>
            <h4 className="text-[12px] font-semibold uppercase tracking-wider text-[#71717A] mb-2">
              {lang === 'uk' ? t('adm2_94b60e618a') : 'Recommendations'}
            </h4>
            <ul className="space-y-1.5">
              {risk.recommendations.map((rec, idx) => (
                <li key={idx} className="flex items-start gap-2 text-[12.5px] text-[#52525B]">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default RiskDashboardPage;
