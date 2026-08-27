/**
 * KPI Dashboard
 * 
 * /admin/kpi
 * 
 * - Manager stats aggregation
 * - KPI alerts (HOT leads missed, low conversion, etc.)
 * - Manager rating system (gold/silver/bronze/needs_improvement)
 * - Team KPI dashboard
 * - Owner dashboard with full overview
 * - Leaderboard
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLang } from '../../i18n';
import { 
  ChartLine, 
  Trophy, 
  Medal,
  Warning,
  TrendUp,
  TrendDown,
  Phone,
  Target,
  Fire,
  Users,
  CurrencyCircleDollar,
  Clock,
  ArrowRight,
  Crown,
  Star
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import { AdminPageHeader } from '../../components/ui/AdminPagePrimitives';
import SectionTabs from '../../components/ui/SectionTabs';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Rating Badge
const RatingBadge = ({ rating }) => {
  const { t } = useLang();
  const badges = {
    gold: { bg: 'bg-amber-100', text: 'text-amber-700', icon: Crown, label: t('adm_gold') },
    silver: { bg: 'bg-zinc-100', text: 'text-zinc-600', icon: Medal, label: t('adm_silver') },
    bronze: { bg: 'bg-orange-100', text: 'text-orange-700', icon: Medal, label: t('adm_bronze') },
    needs_improvement: { bg: 'bg-red-100', text: 'text-red-700', icon: Warning, label: t('adm_needs_work') },
  };
  
  const badge = badges[rating] || badges.needs_improvement;
  const Icon = badge.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${badge.bg} ${badge.text}`}>
      <Icon size={14} weight="fill" />
      {badge.label}
    </span>
  );
};

// Stats Card
const StatCard = ({ icon: Icon, title, value, subtitle, trend, color = 'zinc' }) => (
  <div className="bg-white rounded-2xl border border-zinc-200 p-6">
    <div className="flex items-start justify-between">
      <div className={`p-3 rounded-xl bg-${color}-100`}>
        <Icon size={24} className={`text-${color}-600`} weight="fill" />
      </div>
      {trend !== undefined && (
        <div className={`flex items-center gap-1 text-sm font-medium
          ${trend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
          {trend >= 0 ? <TrendUp size={16} /> : <TrendDown size={16} />}
          {Math.abs(trend)}%
        </div>
      )}
    </div>
    <div className="mt-4">
      <h3 className="text-3xl font-bold text-zinc-900">{value}</h3>
      <p className="text-sm text-zinc-500 mt-1">{title}</p>
      {subtitle && <p className="text-xs text-zinc-400 mt-1">{subtitle}</p>}
    </div>
  </div>
);

// Alert Card
const AlertCard = ({ alert }) => {
  const severityColors = {
    HIGH: 'border-red-200 bg-red-50',
    MEDIUM: 'border-amber-200 bg-amber-50',
    LOW: 'border-blue-200 bg-blue-50',
  };

  const severityText = {
    HIGH: 'text-red-700',
    MEDIUM: 'text-amber-700', 
    LOW: 'text-blue-700',
  };

  return (
    <div className={`rounded-xl border p-4 ${severityColors[alert.severity] || severityColors.LOW}`}>
      <div className="flex items-start gap-3">
        <Warning size={20} className={severityText[alert.severity] || severityText.LOW} />
        <div className="flex-1">
          <p className={`font-medium ${severityText[alert.severity] || severityText.LOW}`}>
            {alert.type.replace(/_/g, ' ')}
          </p>
          <p className="text-sm text-zinc-600 mt-1">{alert.message}</p>
          {alert.manager && (
            <p className="text-xs text-zinc-500 mt-2">
              {t('r9_manager_label')}: {alert.manager}
            </p>
          )}
        </div>
        <span className={`px-2 py-0.5 rounded text-xs font-medium uppercase
          ${alert.severity === 'HIGH' ? 'bg-red-100 text-red-700' : 
            alert.severity === 'MEDIUM' ? 'bg-amber-100 text-amber-700' : 
            'bg-blue-100 text-blue-700'}`}>
          {alert.severity}
        </span>
      </div>
    </div>
  );
};

// Leaderboard Item
const LeaderboardItem = ({ manager, rank, isCurrentUser }) => {
  const { t } = useLang();
  return (
  <div className={`flex items-center gap-4 p-4 rounded-xl transition-colors
    ${isCurrentUser ? 'bg-violet-50 border border-violet-200' : 'bg-zinc-50 hover:bg-zinc-100'}`}>
    {/* Rank */}
    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold
      ${rank === 1 ? 'bg-amber-400 text-white' : 
        rank === 2 ? 'bg-zinc-400 text-white' : 
        rank === 3 ? 'bg-orange-400 text-white' : 
        'bg-zinc-200 text-zinc-600'}`}>
      {rank <= 3 ? <Trophy size={20} weight="fill" /> : rank}
    </div>

    {/* Manager Info */}
    <div className="flex-1">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-zinc-900">{manager.name || manager.managerId}</span>
        <RatingBadge rating={manager.rating} />
      </div>
      <div className="flex items-center gap-4 mt-1 text-sm text-zinc-500">
        <span>{manager.dealsCount ?? manager.conversions ?? 0} {t('adm3_f9b5bd9d5b')}</span>
        <span>{manager.conversionRate ? (manager.conversionRate * 100).toFixed(0) : (manager.leads ? Math.round(((manager.conversions || 0) / manager.leads) * 100) : 0)}{'% conversion'}</span>
        <span>${manager.revenue || 0} {t('adm3_c08be56d4d')}</span>
      </div>
    </div>

    {/* Score */}
    <div className="text-right">
      <p className="text-2xl font-bold text-zinc-900">{manager.score || 0}</p>
      <p className="text-xs text-zinc-500">{t('adm_points_2')}</p>
    </div>
  </div>
  );
};

// Manager Card (for team view)
const ManagerCard = ({ manager, onClick }) => (
  <div 
    onClick={() => onClick?.(manager)}
    className="bg-white rounded-xl border border-zinc-200 p-4 hover:shadow-md transition-all cursor-pointer"
  >
    <div className="flex items-start justify-between mb-3">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-zinc-200 flex items-center justify-center text-xl font-bold text-zinc-600">
          {manager.name?.charAt(0) || 'M'}
        </div>
        <div>
          <h3 className="font-semibold text-zinc-900">{manager.name || manager.managerId}</h3>
          <RatingBadge rating={manager.rating} />
        </div>
      </div>
      {manager.isOnline && (
        <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
      )}
    </div>

    {/* KPI Metrics */}
    <div className="grid grid-cols-3 gap-2 mt-4">
      <div className="text-center p-2 rounded-lg bg-zinc-50">
        <p className="text-lg font-bold text-zinc-900">{manager.leadsCount || 0}</p>
        <p className="text-xs text-zinc-500">{t('adm_leads_3')}</p>
      </div>
      <div className="text-center p-2 rounded-lg bg-zinc-50">
        <p className="text-lg font-bold text-zinc-900">{manager.callsToday || 0}</p>
        <p className="text-xs text-zinc-500">{t('adm_calls_3')}</p>
      </div>
      <div className="text-center p-2 rounded-lg bg-zinc-50">
        <p className="text-lg font-bold text-emerald-600">{manager.dealsCount || 0}</p>
        <p className="text-xs text-zinc-500">{t('adm_deals_2')}</p>
      </div>
    </div>

    {/* Hot Leads Warning */}
    {manager.hotLeadsMissed > 0 && (
      <div className="mt-3 p-2 rounded-lg bg-red-50 border border-red-100 flex items-center gap-2 text-sm text-red-700">
        <Fire size={16} weight="fill" />
        {manager.hotLeadsMissed} {t('r9_hot_leads_missed_plural')}
      </div>
    )}
  </div>
);

export default function KPIDashboard() {
  const { t } = useLang();
  const [dashboard, setDashboard] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [teamStats, setTeamStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('overview'); // overview, team, alerts

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [dashboardRes, leaderboardRes, alertsRes, teamRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/kpi/dashboard`),
        axios.get(`${API_URL}/api/admin/kpi/leaderboard`),
        axios.get(`${API_URL}/api/admin/kpi/alerts`),
        axios.get(`${API_URL}/api/admin/kpi/team`).catch(() => ({ data: [] })),
      ]);

      setDashboard(dashboardRes.data);
      // Backend returns { managers: [...] } — coerce to array shape the UI expects
      const lb = leaderboardRes.data;
      setLeaderboard(Array.isArray(lb) ? lb : (lb?.managers || []));
      const al = alertsRes.data;
      setAlerts(Array.isArray(al) ? al : (al?.alerts || []));
      setTeamStats(teamRes.data?.teamStats || teamRes.data || {});
    } catch (err) {
      console.error('Failed to load KPI data:', err);
      toast.error(t('loadError'));
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-zinc-900 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-5" data-testid="kpi-dashboard">
      <AdminPageHeader
        icon={ChartLine}
        title={t('kpiDashboard')}
        subtitle={t('teamPerformanceTitle')}
        testId="kpi-header"
        actions={(
          <SectionTabs
            tabs={[
              { id: 'overview', label: t('adm2_b32ea18d30') || 'Overview' },
              { id: 'team',     label: t('adm2_85bd6ff189') || 'Team' },
              { id: 'alerts',   label: t('adm2_4eb7b87ef0') || 'Alerts', badge: alerts.length || undefined },
            ]}
            activeId={view}
            onChange={setView}
            testIdPrefix="kpi-view"
            ariaLabel="KPI view"
            className="-mx-1 sm:mx-0"
          />
        )}
      />

      {/* Overview Stats */}
      {view === 'overview' && dashboard && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={Target}
              title={t('adm_conversion')}
              value={`${((dashboard.conversionRate || 0) * 100).toFixed(1)}%`}
              subtitle={t('adm_leads_deals')}
              trend={dashboard.conversionTrend}
              color="emerald"
            />
            <StatCard
              icon={Phone}
              title={t('adm_calls_today_2')}
              value={dashboard.callsToday || 0}
              subtitle={`${dashboard.avgCallDuration || 0} ${t('r9_min_avg')}`}
              color="blue"
            />
            <StatCard
              icon={Fire}
              title={t('adm_hot_leads')}
              value={dashboard.hotLeads || 0}
              subtitle={`${dashboard.hotLeadsMissed || 0} ${t('r9_missed')}`}
              color="red"
            />
            <StatCard
              icon={CurrencyCircleDollar}
              title={t('adm_revenue_2')}
              value={`$${(dashboard.revenue || 0).toLocaleString()}`}
              subtitle={t('adm_for_this_month')}
              trend={dashboard.revenueTrend}
              color="violet"
            />
          </div>

          {/* Leaderboard */}
          <div className="bg-white rounded-2xl border border-zinc-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-zinc-900 flex items-center gap-2">
                <Trophy size={24} className="text-amber-500" weight="fill" />
                {t('adm_leaderboard')}
              </h2>
            </div>
            
            {leaderboard.length === 0 ? (
              <p className="text-zinc-500 text-center py-8">{t('adm_no_data_to_display')}</p>
            ) : (
              <div className="space-y-3">
                {leaderboard.slice(0, 10).map((manager, idx) => (
                  <LeaderboardItem 
                    key={manager.managerId || idx} 
                    manager={manager} 
                    rank={idx + 1}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Team View */}
      {view === 'team' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {teamStats.length === 0 ? (
            <div className="col-span-full bg-white rounded-2xl border border-zinc-200 p-12 text-center">
              <Users size={48} className="mx-auto mb-4 text-zinc-300" />
              <p className="text-zinc-500">{t('adm_no_team_data')}</p>
            </div>
          ) : (
            teamStats.map((manager, idx) => (
              <ManagerCard key={manager.managerId || idx} manager={manager} />
            ))
          )}
        </div>
      )}

      {/* Alerts View */}
      {view === 'alerts' && (
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <div className="bg-white rounded-2xl border border-zinc-200 p-12 text-center">
              <Star size={48} className="mx-auto mb-4 text-emerald-300" weight="fill" />
              <p className="text-zinc-500">{t('adm_no_critical_alerts_everything_is_under_control')}</p>
            </div>
          ) : (
            alerts.map((alert, idx) => (
              <AlertCard key={idx} alert={alert} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
