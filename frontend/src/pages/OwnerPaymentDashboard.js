/**
 * Owner Payment Analytics Dashboard
 * 
 * /admin/owner-dashboard
 * 
 * Complete payment analytics for owner role
 */

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../App';
import { useLang } from '../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  CurrencyDollar,
  TrendUp,
  TrendDown,
  ChartLineUp,
  ChartPieSlice,
  Users,
  Invoice,
  Truck,
  Warning,
  ArrowsClockwise,
  CaretDown,
  Check,
  Clock,
  ShieldWarning,
  User,
  Handshake,
  Package
} from '@phosphor-icons/react';
import WhiteSelect from '../components/ui/WhiteSelect';
import RefreshButton from '../components/ui/RefreshButton';

// KPI Card Component
const KPICard = ({ title, value, subtitle, icon: Icon, iconColor, trend, trendLabel }) => (
  <motion.div 
    className="bg-white rounded-xl border border-[#E4E4E7] p-3 sm:p-5 hover:shadow-sm transition-all min-w-0 overflow-hidden"
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    data-testid={`kpi-${title.toLowerCase().replace(/\s/g, '-')}`}
  >
    <div className="flex items-start justify-between gap-2">
      <div className={`p-1.5 sm:p-2.5 rounded-lg bg-${iconColor}-50 flex-shrink-0`}>
        <Icon size={18} weight="duotone" className={`text-${iconColor}-600 sm:hidden`} />
        <Icon size={22} weight="duotone" className={`text-${iconColor}-600 hidden sm:block`} />
      </div>
      {trend !== undefined && (
        <div className={`flex items-center gap-0.5 text-[11px] sm:text-xs font-medium whitespace-nowrap ${trend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
          {trend >= 0 ? <TrendUp size={12} /> : <TrendDown size={12} />}
          {Math.abs(trend)}%
        </div>
      )}
    </div>
    <div className="mt-2 sm:mt-3 min-w-0">
      <p className="font-bold text-[#18181B] truncate text-[20px] sm:text-2xl lg:text-[28px] leading-tight" title={String(value)} style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif', letterSpacing: '-0.02em' }}>
        {value}
      </p>
      <p className="text-[11.5px] sm:text-[13px] text-[#71717A] mt-0.5 sm:mt-1 truncate" title={title}>{title}</p>
      {subtitle && <p className="text-[10.5px] sm:text-[11px] text-[#A1A1AA] mt-0.5 truncate" title={subtitle}>{subtitle}</p>}
    </div>
  </motion.div>
);

// Funnel Stage
const FunnelStage = ({ label, value, total, color, icon: Icon }) => {
  const { t } = useLang();
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
      <div className={`p-1.5 sm:p-2 rounded-lg bg-${color}-100 flex-shrink-0`}>
        <Icon size={16} className={`text-${color}-600`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-[12.5px] sm:text-sm font-medium text-[#18181B] truncate">{label}</span>
          <span className="text-[12.5px] sm:text-sm font-bold text-[#18181B] whitespace-nowrap">{value}</span>
        </div>
        <div className="h-1.5 sm:h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
          <div 
            className={`h-full bg-${color}-500 rounded-full transition-all duration-500`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
      <span className="text-[11px] sm:text-xs text-[#71717A] w-8 sm:w-10 text-right whitespace-nowrap">{percentage}%</span>
    </div>
  );
};

// Risk Alert
const RiskAlert = ({ type, count, severity, description }) => {
  const { t } = useLang();
  const severityConfig = {
    critical: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', icon: ShieldWarning },
    warning: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', icon: Warning },
    info: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', icon: Clock },
  };
  const config = severityConfig[severity] || severityConfig.info;
  const Icon = config.icon;
  
  return (
    <div className={`${config.bg} ${config.border} border rounded-xl p-3 sm:p-4 flex items-center gap-3`}>
      <Icon size={20} weight="duotone" className={`${config.text} flex-shrink-0`} />
      <div className="flex-1 min-w-0">
        <p className={`font-semibold text-[13px] sm:text-sm ${config.text} truncate`}>{type}</p>
        <p className="text-[11.5px] sm:text-xs text-[#71717A] truncate">{description}</p>
      </div>
      <div className={`px-2.5 py-1 rounded-full ${config.bg} ${config.text} font-bold text-[12px] sm:text-sm whitespace-nowrap`}>{count}</div>
    </div>
  );
};

// Team Member Row
const TeamMemberRow = ({ member, rank }) => {
  const { t } = useLang();
  return (
    <div className="flex items-center gap-2.5 sm:gap-3 p-2.5 sm:p-3 hover:bg-[#F4F4F5] rounded-xl transition-colors min-w-0">
      <span className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#18181B] text-white flex items-center justify-center text-[12px] sm:text-sm font-bold flex-shrink-0">
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-[#18181B] truncate text-[13px] sm:text-sm">{member.managerName}</p>
        <p className="text-[11px] sm:text-xs text-[#71717A] truncate">{member.email}</p>
      </div>
      <div className="text-right flex-shrink-0">
        <p className="font-semibold text-[#18181B] text-[13px] sm:text-sm whitespace-nowrap">${member.revenue?.toLocaleString() || 0}</p>
        <p className="text-[11px] sm:text-xs text-[#71717A] whitespace-nowrap">{member.totalDeals} {t('adm3_f9b5bd9d5b')}</p>
      </div>
      <div className="hidden sm:flex items-center gap-2 flex-shrink-0">
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          member.paidRate >= 80 ? 'bg-emerald-100 text-emerald-700' :
          member.paidRate >= 50 ? 'bg-amber-100 text-amber-700' :
          'bg-red-100 text-red-700'
        }`}>
          {member.paidRate}% paid
        </span>
        {member.overdueCount > 0 && (
          <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
            {member.overdueCount} overdue
          </span>
        )}
      </div>
    </div>
  );
};

const OwnerPaymentDashboard = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/api/owner-dashboard?days=${period}`);
      setData(res.data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
      toast.error(t('adm_data_loading_error'));
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin w-8 h-8 border-2 border-[#18181B] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12 text-[#71717A]">
        {t('adm_no_data_2')}
      </div>
    );
  }

  const { revenue = {}, funnel = {}, shipping = {}, risk = {}, team = [] } = data || {};

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      className="space-y-4 md:space-y-6 min-w-0 max-w-full overflow-x-hidden"
      data-testid="owner-payment-dashboard"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4 min-w-0">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold text-[#18181B] leading-tight whitespace-nowrap" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
            {t('adm_payment_analytics')}
          </h1>
          <p className="text-xs sm:text-sm text-[#71717A] mt-1">{t('adm_financial_activity_overview')}</p>
        </div>
        <div className="flex items-center gap-2 sm:gap-3 w-full sm:w-auto">
          <div className="flex-1 sm:flex-none sm:w-[150px] min-w-0">
            <WhiteSelect value={period} onChange={(e) => setPeriod(Number(e.target.value))} data-testid="period-select">
              <option value={7}>{t('adm_7_days')}</option>
              <option value={14}>{t('adm_14_days')}</option>
              <option value={30}>{t('adm_30_days')}</option>
              <option value={90}>{t('adm_90_days')}</option>
            </WhiteSelect>
          </div>
          <RefreshButton
            onClick={fetchDashboard}
            ariaLabel={t('adm_reload') || 'Refresh'}
            testId="refresh-btn"
          />
        </div>
      </div>

      {/* Revenue KPIs — 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KPICard
          title={t('adm_total_revenue')}
          value={`$${(revenue.totalRevenue || 0).toLocaleString()}`}
          icon={CurrencyDollar}
          iconColor="emerald"
          trend={revenue.revenueGrowth}
        />
        <KPICard
          title={t('adm_paid_invoices')}
          value={revenue.totalPaidInvoices || 0}
          subtitle={t('adm_for_period')}
          icon={Check}
          iconColor="blue"
        />
        <KPICard
          title={t('adm_awaiting_payment')}
          value={revenue.totalUnpaidInvoices || 0}
          subtitle={t('adm_open_invoices')}
          icon={Clock}
          iconColor="amber"
        />
        <KPICard
          title={t('adm_overdue_amount')}
          value={`$${(revenue.overdueAmount || 0).toLocaleString()}`}
          subtitle={t('r9_avg_delay_days', { delayDays: revenue.avgPaymentDelayDays || 0 })}
          icon={Warning}
          iconColor="red"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 sm:gap-4 lg:gap-6 min-w-0">
        {/* Funnel */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-[#E4E4E7] p-4 sm:p-5 min-w-0 overflow-hidden">
          <h2 className="text-base sm:text-lg font-semibold text-[#18181B] mb-3 sm:mb-4" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
            {t('adm_sales_funnel')}
          </h2>
          <div className="space-y-2.5 sm:space-y-3">
            <FunnelStage
              label={t('adm_contracts_created')}
              value={funnel.contractsCreated || 0}
              total={funnel.contractsCreated || 1}
              color="violet"
              icon={Handshake}
            />
            <FunnelStage
              label={t('adm_contracts_signed')}
              value={funnel.contractsSigned || 0}
              total={funnel.contractsCreated || 1}
              color="indigo"
              icon={Check}
            />
            <FunnelStage
              label={t('adm_invoices_sent')}
              value={funnel.invoicesSent || 0}
              total={funnel.contractsCreated || 1}
              color="blue"
              icon={Invoice}
            />
            <FunnelStage
              label={t('adm_invoices_paid')}
              value={funnel.invoicesPaid || 0}
              total={funnel.contractsCreated || 1}
              color="emerald"
              icon={CurrencyDollar}
            />
            <FunnelStage
              label={t('adm_deliveries_started')}
              value={funnel.shipmentsStarted || 0}
              total={funnel.contractsCreated || 1}
              color="amber"
              icon={Truck}
            />
            <FunnelStage
              label={t('adm_delivered')}
              value={funnel.delivered || 0}
              total={funnel.contractsCreated || 1}
              color="teal"
              icon={Package}
            />
          </div>
        </div>

        {/* Risk Alerts */}
        <div className="bg-white rounded-xl border border-[#E4E4E7] p-4 sm:p-5 min-w-0 overflow-hidden">
          <h2 className="text-base sm:text-lg font-semibold text-[#18181B] mb-3 sm:mb-4" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
            {t('adm_risks_and_alerts')}
          </h2>
          <div className="space-y-2.5 sm:space-y-3">
            {(risk.criticalOverdueInvoices || 0) > 0 && (
              <RiskAlert
                type={t('adm3_ef0fbd6ff8')}
                count={risk.criticalOverdueInvoices}
                severity="critical"
                description={t('adm_invoices_overdue_by_more_than_5_days')}
              />
            )}
            {(risk.stalledShipments || 0) > 0 && (
              <RiskAlert
                type={t('adm3_afcda1a038')}
                count={risk.stalledShipments}
                severity="warning"
                description={t('adm_no_updates_for_more_than_7_days')}
              />
            )}
            {(risk.riskyManagers || 0) > 0 && (
              <RiskAlert
                type={t('adm3_bf981b96b0')}
                count={risk.riskyManagers}
                severity="warning"
                description={t('adm_3_overdue_invoices')}
              />
            )}
            {(risk.totalAtRiskAmount || 0) > 0 && (
              <RiskAlert
                type={t('adm3_d48546035e')}
                count={`$${(risk.totalAtRiskAmount || 0).toLocaleString()}`}
                severity="info"
                description={t('adm_total_overdue_amount')}
              />
            )}
            {!(risk.criticalOverdueInvoices || 0) && !(risk.stalledShipments || 0) && !(risk.riskyManagers || 0) && (
              <div className="text-center py-6 sm:py-8 text-[#71717A]">
                <Check size={36} className="mx-auto mb-2 text-emerald-500" />
                <p className="text-[13px] sm:text-sm">{t('adm_no_critical_risks')}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Shipping Stats — 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KPICard
          title={t('adm_active_deliveries')}
          value={shipping.activeShipments || 0}
          icon={Truck}
          iconColor="blue"
        />
        <KPICard
          title={t('adm_delayed')}
          value={shipping.delayedShipments || 0}
          icon={Warning}
          iconColor="amber"
        />
        <KPICard
          title={t('adm_ontime_rate')}
          value={`${shipping.onTimeDeliveryRate || 0}%`}
          icon={ChartLineUp}
          iconColor="emerald"
        />
        <KPICard
          title={t('adm_avg_transit')}
          value={t('r9_transit_days', { transitDays: shipping.avgTransitDays || 0 })}
          icon={Clock}
          iconColor="violet"
        />
      </div>

      {/* Team Performance */}
      <div className="bg-white rounded-xl border border-[#E4E4E7] p-4 sm:p-5 min-w-0 overflow-hidden">
        <h2 className="text-base sm:text-lg font-semibold text-[#18181B] mb-3 sm:mb-4" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
          {t('adm_team_revenue_rating')}
        </h2>
        <div className="space-y-1 sm:space-y-1.5">
          {team && team.length > 0 ? (
            team.slice(0, 10).map((member, idx) => (
              <TeamMemberRow key={member.managerId} member={member} rank={idx + 1} />
            ))
          ) : (
            <div className="text-center py-6 sm:py-8 text-[#71717A]">
              <Users size={36} className="mx-auto mb-2" />
              <p className="text-[13px] sm:text-sm">{t('adm_no_team_data_2')}</p>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default OwnerPaymentDashboard;
