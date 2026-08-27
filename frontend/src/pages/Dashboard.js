import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { API_URL, useAuth } from '../App';
import { useLang, getLocale } from '../i18n';
import { motion } from 'framer-motion';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import {
  UsersThree,
  Warning,
  Wallet, 
  Clock,
  Phone,
  FileText,
  ChartPie,
  Heartbeat,
  Lightning,
  UserCircle,
  ClipboardText,
  CurrencyCircleDollar,
  ShieldCheck,
  ArrowsClockwise,
  Pulse,
  Users,
  CheckCircle,
  XCircle,
  HourglassMedium,
  ChatCircleDots,
  EnvelopeSimple,
  PhoneCall,
  UserPlus,
  TrendUp,
  Briefcase,
  Sparkle,
  ArrowRight,
  Fire
} from '@phosphor-icons/react';

const Dashboard = () => {
  const { t, lang } = useLang();
  const { user } = useAuth();
  const [masterData, setMasterData] = useState(null);
  const [period, setPeriod] = useState('day');
  const [loading, setLoading] = useState(true);
  // Висящие Top Deals на апрув — отдельный виджет, чтобы тимлид сразу
  // видел задачу, а не искал её во вкладке. Загружается параллельно
  // с основным дашбордом, ошибка не блокирует страницу.
  const [topDealsPending, setTopDealsPending] = useState(0);
  // ── Wave 7 · "My operational queue" — personal counters on the GLOBAL dashboard.
  //    Lives alongside the master KPIs so the admin/team-lead sees what's on
  //    THEIR plate without having to switch to the per-role Workspace page.
  //    Loads soft — any failure is silently absorbed, the block degrades to "—".
  const [myQueue, setMyQueue] = useState({
    tasks: null,        // open tasks assigned to me
    hotLeads: null,     // hot/active leads assigned to me
    approvals: null,    // approvals waiting on me (wishlist deals etc.)
    loaded: false,
  });

  useEffect(() => {
    fetchMasterDashboard();
    // pending апрувов не зависит от period — тянем отдельно
    axios.get(`${API_URL}/api/team-lead/wishlist-deals`, { params: { status: 'pending' } })
      .then((r) => setTopDealsPending(Number(r?.data?.counts?.pending) || 0))
      .catch(() => setTopDealsPending(0));
  }, [period]);

  // ── My operational queue — independent soft-fail load (Promise.allSettled).
  // Does NOT depend on `period` (these are "right now" counters, not period KPIs).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const me = user?.id || user?.userId || user?.staff_id || null;
      const params = me ? { assignedTo: me, limit: 50 } : { limit: 50 };
      const [tasksRes, leadsRes, dealsRes] = await Promise.allSettled([
        axios.get(`${API_URL}/api/tasks`, { params: { ...params, status: 'pending' } }),
        axios.get(`${API_URL}/api/leads`, { params: { ...params, status: 'hot' } }),
        axios.get(`${API_URL}/api/team-lead/wishlist-deals`, { params: { status: 'pending' } }),
      ]);
      if (cancelled) return;
      const pickCount = (res) => {
        if (res.status !== 'fulfilled') return null;
        const d = res.value?.data;
        if (typeof d?.total === 'number') return d.total;
        if (typeof d?.count === 'number') return d.count;
        if (Array.isArray(d?.items)) return d.items.length;
        if (Array.isArray(d?.data))  return d.data.length;
        if (Array.isArray(d))        return d.length;
        if (typeof d?.counts?.pending === 'number') return d.counts.pending;
        return null;
      };
      setMyQueue({
        tasks:    pickCount(tasksRes),
        hotLeads: pickCount(leadsRes),
        approvals: pickCount(dealsRes),
        loaded:   true,
      });
    })();
    return () => { cancelled = true; };
  }, [user?.id, user?.userId, user?.staff_id]);

  // Convenience — total queue size (skip nulls so "no data" doesn't poison the sum)
  const myQueueTotal = useMemo(() => {
    const vals = [myQueue.tasks, myQueue.hotLeads, myQueue.approvals].filter((v) => typeof v === 'number');
    return vals.reduce((a, b) => a + b, 0);
  }, [myQueue]);

  const fetchMasterDashboard = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/api/dashboard/master?period=${period}`);
      setMasterData(response.data);
    } catch (err) {
      console.error('Master Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !masterData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-[#18181B] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  const { sla, workload, leads, callbacks, deposits, documents, routing, system } = masterData;

  const periodLabels = {
    day: t('today'),
    week: t('week'),
    month: t('month'),
  };

  return (
    <TooltipProvider delayDuration={150}>
    <motion.div 
      data-testid="master-dashboard-page"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6 lg:mb-8">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <ChartPie size={20} weight="bold" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold tracking-tight text-[#18181B] break-words leading-tight" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('controlPanel')}
            </h1>
            <p className="text-[12px] text-[#71717A] mt-0.5 break-words">
              {t('updated')}: {new Date(masterData.generatedAt).toLocaleString(lang === 'uk' ? getLocale() : 'en-US')}
            </p>
          </div>
        </div>
        
        {/* Period Selector — canonical platform segmented control */}
        <div className="period-tabs overflow-x-auto shrink-0 self-start" data-testid="period-selector">
          {['day', 'week', 'month'].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`period-tab whitespace-nowrap ${period === p ? 'active' : ''}`}
              data-testid={`period-${p}`}
            >
              {periodLabels[p]}
            </button>
          ))}
        </div>
      </div>

      {/* ── My operational queue — personal counters on the global dashboard ──
          Compact strip; deliberately NOT a second workspace. Links out to the
          per-role workspace for the full operational surface. */}
      <div className="mb-5 sm:mb-6 rounded-2xl border border-[#E4E4E7] bg-white p-4 sm:p-5" data-testid="my-operational-queue">
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="min-w-0">
            <h2
              className="text-sm sm:text-base font-semibold text-[#18181B] truncate"
              style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
            >
              {t('my_operational_queue')}
            </h2>
            <p className="text-[11px] sm:text-xs text-[#A1A1AA] mt-0.5">
              {myQueue.loaded
                ? (myQueueTotal > 0
                    ? t('items_waiting').replace('{n}', myQueueTotal)
                    : t('nothing_waiting'))
                : t('loading_ellipsis')}
            </p>
          </div>
          <Link
            to="/manager/"
            className="inline-flex items-center gap-1 text-[11px] sm:text-xs font-medium px-2.5 py-1.5 rounded-lg border border-[#E4E4E7] bg-white text-[#18181B] hover:bg-[#FAFAFA]"
            data-testid="my-queue-open-workspace"
          >
            {t('open_my_workspace')}
            <ArrowRight size={12} />
          </Link>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <QueueCounter
            label={t('my_tasks_short')}
            value={myQueue.tasks}
            icon={ClipboardText}
            to="/admin/tasks"
            testId="my-queue-tasks"
          />
          <QueueCounter
            label={t('my_hot_leads_short')}
            value={myQueue.hotLeads}
            icon={Fire}
            to="/admin/leads"
            testId="my-queue-leads"
          />
          <QueueCounter
            label={t('approvals_short')}
            value={myQueue.approvals ?? topDealsPending ?? 0}
            icon={ShieldCheck}
            to="/admin/wishlist-deals"
            testId="my-queue-approvals"
          />
        </div>
      </div>

      {/* KPI Summary Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4 lg:gap-5 mb-6 lg:mb-8" data-testid="kpi-summary-row">
        <KpiCard 
          icon={UserPlus} 
          label={t('newLeads')} 
          value={leads.newCount} 
          color="#18181B"
        />
        <KpiCard 
          icon={HourglassMedium} 
          label={t('overdue')} 
          value={sla.overdueLeads} 
          color={sla.overdueLeads > 0 ? "#DC2626" : "#18181B"}
          alert={sla.overdueLeads > 0}
        />
        <KpiCard 
          icon={CurrencyCircleDollar} 
          label={t('pendingDeposits')} 
          value={deposits.pendingDeposits} 
          color="#18181B"
        />
        <KpiCard 
          icon={ShieldCheck} 
          label={t('forVerification')} 
          value={documents.pendingVerification} 
          color={documents.pendingVerification > 5 ? "#DC2626" : "#18181B"}
          alert={documents.pendingVerification > 5}
        />
        <KpiCard 
          icon={UsersThree} 
          label={t('overloaded')} 
          value={workload.overloadedManagers} 
          color={workload.overloadedManagers > 0 ? "#DC2626" : "#18181B"}
          alert={workload.overloadedManagers > 0}
        />
        <KpiCard 
          icon={Lightning} 
          label={t('failedJobs')} 
          value={system.failedJobs} 
          color={system.failedJobs > 0 ? "#DC2626" : "#18181B"}
        />
      </div>

      {/* Top Deals approval queue — visible alert for the team lead so
          they immediately see that there is curated-wishlist work
          waiting. Empty/healthy state is also shown explicitly. */}
      <Link
        to="/team/wishlist-approvals"
        data-testid="td-approvals-widget"
        className={`block rounded-2xl border p-4 sm:p-5 mb-6 lg:mb-8 transition group ${
          topDealsPending > 0
            ? 'bg-gradient-to-r from-amber-50 to-rose-50 border-amber-200 hover:border-amber-300'
            : 'bg-white border-[#E4E4E7] hover:border-[#A1A1AA]'
        }`}
      >
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 sm:w-14 sm:h-14 rounded-2xl flex items-center justify-center flex-shrink-0 ${
            topDealsPending > 0 ? 'bg-amber-100' : 'bg-[#F4F4F5]'
          }`}>
            <Sparkle
              size={26}
              weight={topDealsPending > 0 ? 'fill' : 'duotone'}
              className={topDealsPending > 0 ? 'text-amber-600' : 'text-[#71717A]'}
            />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-[#18181B] text-base">
                {t('top_deals_approval_queue')}
              </h3>
              {topDealsPending > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full bg-amber-500 text-white">
                  {t('top_deals_action_required')}
                </span>
              )}
            </div>
            <div className="text-sm text-[#71717A] mt-1">
              {topDealsPending > 0 ? (
                <>
                  <span className="font-semibold text-amber-700">
                    {topDealsPending} card{topDealsPending === 1 ? '' : 's'}
                  </span>{' '}
                  {t('top_deals_cards_waiting')}
                </>
              ) : (
                t('top_deals_no_pending')
              )}
            </div>
          </div>
          <div className="text-right">
            <div className={`text-3xl sm:text-4xl font-bold ${topDealsPending > 0 ? 'text-amber-700' : 'text-[#18181B]'}`}>
              {topDealsPending}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-[#71717A]">{t('pending_short')}</div>
          </div>
          <ArrowRight size={20} className="text-[#71717A] group-hover:text-[#18181B] group-hover:translate-x-1 transition hidden sm:block" />
        </div>
      </Link>

      {/* Main Grid - Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-5 mb-4 lg:mb-5">
        {/* SLA Control */}
        <div className="section-card" data-testid="sla-control">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="section-title-clean cursor-help" data-testid="sla-control-title">
                <Clock size={22} weight="duotone" className="text-[#DC2626]" />
                <span>{t('slaControl')}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
              {t('cp_tip_sla')}
            </TooltipContent>
          </Tooltip>
          <div>
            <MetricRow icon={HourglassMedium} label={t('overdueLeads')} value={sla.overdueLeads} alert={sla.overdueLeads > 0} />
            <MetricRow icon={ClipboardText} label={t('overdueTasks')} value={sla.overdueTasks} alert={sla.overdueTasks > 0} />
            <MetricRow icon={PhoneCall} label={t('overdueCallbacks')} value={sla.overdueCallbacks} alert={sla.overdueCallbacks > 0} />
            <MetricRow icon={TrendUp} label={t('avgFirstResponse')} value={`${sla.avgFirstResponseMinutes} ${lang === 'uk' ? t('adm3_24a6c98c78') : 'min'}`} alert={sla.avgFirstResponseMinutes > 30} />
            <MetricRow icon={ChartPie} label={t('missedSlaRate')} value={`${sla.missedSlaRate}%`} alert={sla.missedSlaRate > 15} />
          </div>
        </div>

        {/* Lead Flow */}
        <div className="section-card" data-testid="lead-flow">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="section-title-clean cursor-help" data-testid="lead-flow-title">
                <Users size={22} weight="duotone" className="text-[#4F46E5]" />
                <span>{t('leadFlow')}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
              {t('cp_tip_leadflow')}
            </TooltipContent>
          </Tooltip>
          <div>
            <MetricRow icon={UserPlus} label={t('new')} value={leads.newCount} color="#4F46E5" />
            <MetricRow icon={ArrowsClockwise} label={t('inProgress')} value={leads.inProgressCount} color="#D97706" />
            <MetricRow icon={CheckCircle} label={t('converted')} value={leads.convertedCount} color="#059669" />
            <MetricRow icon={XCircle} label={t('lost')} value={leads.lostCount} color="#DC2626" />
            <MetricRow icon={UserCircle} label={t('unassigned')} value={leads.unassignedCount} alert={leads.unassignedCount > 0} />
          </div>
        </div>

        {/* Callback Control */}
        <div className="section-card" data-testid="callback-control">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="section-title-clean cursor-help" data-testid="callback-control-title">
                <Phone size={22} weight="duotone" className="text-[#7C3AED]" />
                <span>{t('callbackControl')}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
              {t('cp_tip_callback')}
            </TooltipContent>
          </Tooltip>
          <div>
            <MetricRow icon={PhoneCall} label={t('missedCalls')} value={callbacks.missedCalls} alert={callbacks.missedCalls > 0} />
            <MetricRow icon={Phone} label={t('noAnswer')} value={callbacks.noAnswerLeads} alert={callbacks.noAnswerLeads > 3} />
            <MetricRow icon={Clock} label={t('followUpsDue')} value={callbacks.followUpsDue} alert={callbacks.followUpsDue > 0} />
            <MetricRow icon={ChatCircleDots} label={t('callbackScheduled')} value={callbacks.callbacksScheduled} />
            <MetricRow icon={EnvelopeSimple} label={t('smsSent')} value={callbacks.smsTriggered} color="#4F46E5" />
          </div>
        </div>
      </div>

      {/* Main Grid - Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-5">
        {/* Workload Heatmap */}
        <div className="section-card" data-testid="workload-heatmap">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="section-title-clean cursor-help" data-testid="workload-title">
                <Briefcase size={22} weight="duotone" className="text-[#D97706]" />
                <span>{t('workload')}</span>
                <span className="text-[#71717A] font-normal text-sm ml-1">({workload.totalManagers})</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
              {t('cp_tip_workload')}
            </TooltipContent>
          </Tooltip>
          <div className="space-y-2 max-h-52 overflow-y-auto">
            {workload.managers.map((manager) => (
              <div 
                key={manager.managerId}
                className={`flex items-center justify-between p-3 rounded-xl ${getWorkloadBg(manager.status)}`}
              >
                <div className="flex items-center gap-3">
                  <StatusDot status={manager.status} />
                  <span className="text-sm font-medium text-[#18181B] truncate max-w-[100px]">{manager.name}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-[#71717A]">
                  <span>{manager.activeLeads} {lang === 'uk' ? t('adm3_6d0a54f6dd') : 'leads'}</span>
                  <span>{manager.openTasks} {lang === 'uk' ? t('adm3_18a907b888') : 'tasks'}</span>
                  <span className="font-semibold text-[#18181B] bg-white px-2 py-1 rounded-lg">
                    {manager.score}
                  </span>
                </div>
              </div>
            ))}
            {workload.managers.length === 0 && (
              <p className="text-sm text-[#71717A] text-center py-4">{t('noActiveManagers')}</p>
            )}
          </div>
        </div>

        {/* Deposits & Documents */}
        <div className="section-card" data-testid="deposits-docs">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="section-title-clean cursor-help" data-testid="deposits-docs-title">
                <Wallet size={22} weight="duotone" className="text-[#059669]" />
                <span>{t('depositsAndDocs')}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
              {t('cp_tip_deposits')}
            </TooltipContent>
          </Tooltip>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-3">{t('deposits')}</p>
              <div className="space-y-1">
                <MetricRowSimple label={t('pending')} value={deposits.pendingDeposits} />
                <MetricRowSimple label={t('withoutProof')} value={deposits.depositsWithoutProof} alert={deposits.depositsWithoutProof > 0} />
                <MetricRowSimple label={t('verified')} value={deposits.verifiedToday} color="#059669" />
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-3">{t('documents')}</p>
              <div className="space-y-1">
                <MetricRowSimple label={t('forVerification')} value={documents.pendingVerification} alert={documents.pendingVerification > 3} />
                <MetricRowSimple label={t('rejected')} value={documents.rejectedCount} color="#DC2626" />
                <MetricRowSimple label={t('uploaded')} value={documents.uploadedToday} color="#4F46E5" />
              </div>
            </div>
          </div>
        </div>

        {/* Routing & System Health */}
        <div className="section-card" data-testid="routing-health">
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="section-title-clean cursor-help" data-testid="routing-health-title">
                <Pulse size={22} weight="duotone" className="text-[#059669]" />
                <span>{t('routingAndSystem')}</span>
              </div>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" className="max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg">
              {t('cp_tip_routing')}
            </TooltipContent>
          </Tooltip>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-3">{t('routing')}</p>
              <div className="space-y-1">
                <MetricRowSimple label={t('fallback')} value={routing.fallbackAssignments} alert={routing.fallbackAssignments > 5} />
                <MetricRowSimple label={t('reassignRate')} value={`${routing.reassignmentRate}%`} />
                <MetricRowSimple label={t('unassigned')} value={routing.unassignedLeads} alert={routing.unassignedLeads > 0} />
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-[#71717A] mb-3">{t('system')}</p>
              <div className="space-y-1">
                <div className="metric-row">
                  <span className="metric-label">{t('status')}</span>
                  <SystemStatusBadge status={system.systemStatus} />
                </div>
                <MetricRowSimple label={t('queue')} value={system.queueBacklog} />
                <MetricRowSimple label={t('errors')} value={system.failedJobs} alert={system.failedJobs > 0} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
    </TooltipProvider>
  );
};

// Helper Components - Clean style without background blocks

// Compact counter used by the "My operational queue" strip. Renders a value
// (or "—" if unloaded), a small icon and a label. The whole card is a
// <Link> so a single tap jumps to the relevant list filtered for the user.
const QueueCounter = ({ icon: Icon, label, value, to, testId }) => {
  const display = (typeof value === 'number') ? value : '—';
  return (
    <Link
      to={to}
      className="flex items-center gap-3 p-2.5 sm:p-3 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] hover:border-[#A1A1AA] transition-colors min-w-0"
      data-testid={testId}
    >
      <div className="p-2 rounded-lg bg-[#F4F4F5] flex-shrink-0">
        <Icon size={16} weight="duotone" className="text-[#18181B]" />
      </div>
      <div className="min-w-0 flex-1">
        <div
          className="text-lg sm:text-xl font-bold text-[#18181B] leading-tight tabular-nums"
          style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
        >
          {display}
        </div>
        <div className="text-[10px] sm:text-[11px] font-medium uppercase tracking-wider text-[#71717A] truncate">
          {label}
        </div>
      </div>
      <ArrowRight size={12} className="text-[#A1A1AA] flex-shrink-0" />
    </Link>
  );
};

const KpiCard = ({ icon: Icon, label, value, color, alert }) => (
  <div className={`kpi-card p-4 sm:p-5 ${alert ? 'border-[#DC2626]' : ''}`} data-testid={`kpi-${label.toLowerCase().replace(/\s/g, '-')}`}>
    <div className="mb-3 sm:mb-4">
      <Icon size={24} className="sm:hidden" weight="duotone" style={{ color }} />
      <Icon size={28} className="hidden sm:block" weight="duotone" style={{ color }} />
    </div>
    <div className={`text-xl sm:text-2xl lg:text-[2.25rem] font-bold tracking-tight leading-none ${alert ? 'text-[#DC2626]' : 'text-[#18181B]'}`} style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>{value}</div>
    <div className="text-[10px] sm:text-xs font-medium uppercase tracking-wider text-[#71717A] mt-1.5 sm:mt-2">{label}</div>
  </div>
);

const MetricRow = ({ icon: Icon, label, value, color, alert }) => (
  <div className="metric-row">
    <div className="flex items-center gap-2">
      {Icon && <Icon size={16} weight="duotone" className="text-[#A1A1AA]" />}
      <span className="metric-label">{label}</span>
    </div>
    <span className={`metric-value ${alert ? 'alert' : ''}`} style={{ color: !alert && color ? color : undefined }}>
      {value}
    </span>
  </div>
);

const MetricRowSimple = ({ label, value, color, alert }) => (
  <div className="metric-row">
    <span className="metric-label">{label}</span>
    <span className={`metric-value ${alert ? 'alert' : ''}`} style={{ color: !alert && color ? color : undefined }}>
      {value}
    </span>
  </div>
);

const StatusDot = ({ status }) => {
  const { t } = useLang();
  const colors = {
    ok: '#059669',
    busy: '#D97706',
    overloaded: '#DC2626',
    idle: '#71717A',
  };
  return (
    <span className="w-2.5 h-2.5 rounded-full" style={{ background: colors[status] || '#71717A' }} />
  );
};

const getWorkloadBg = (status) => {
  const bgs = {
    ok: 'bg-[#D1FAE5]',
    busy: 'bg-[#FEF3C7]',
    overloaded: 'bg-[#FEE2E2]',
    idle: 'bg-[#F4F4F5]',
  };
  return bgs[status] || 'bg-[#F4F4F5]';
};

const SystemStatusBadge = ({ status }) => {
  const { t } = useLang();
  const configs = {
    healthy: { bg: '#D1FAE5', color: '#059669', label: 'HEALTHY' },
    warning: { bg: '#FEF3C7', color: '#D97706', label: 'WARNING' },
    critical: { bg: '#FEE2E2', color: '#DC2626', label: 'CRITICAL' },
  };
  const config = configs[status] || configs.healthy;
  return (
    <span className="badge" style={{ background: config.bg, color: config.color }}>
      {config.label}
    </span>
  );
};

export default Dashboard;
