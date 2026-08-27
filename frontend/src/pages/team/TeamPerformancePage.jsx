/**
 * BIBI Cars - Team Performance Page
 * Analytics and metrics for team lead
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import BackButton from '../../components/ui/BackButton';
import Breadcrumb from '../../components/ui/Breadcrumb';
import RefreshButton from '../../components/ui/RefreshButton';
import {
  ChartLineUp,
  ChartBar,
  Users,
  Clock,
  Phone,
  CreditCard,
  Truck,
  Target
} from '@phosphor-icons/react';

const TeamPerformancePage = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPerformance();
  }, []);

  const fetchPerformance = async () => {
    try {
      const [perfRes, managersRes] = await Promise.all([
        axios.get(`${API_URL}/api/team/performance`).catch(() => ({ data: null })),
        axios.get(`${API_URL}/api/team/managers`).catch(() => 
          axios.get(`${API_URL}/api/users?role=manager`)
        ),
      ]);
      setMetrics(perfRes.data);
      const managersData = Array.isArray(managersRes.data) ? managersRes.data : (managersRes.data?.data || managersRes.data?.managers || []);
      setManagers(managersData);
    } catch (err) {
      console.error('Error:', err);
      setManagers([]);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  const sortedByScore = [...managers].sort((a, b) => (b.performanceScore || 0) - (a.performanceScore || 0));
  const sortedByStale = [...managers].sort((a, b) => (b.staleLeads || 0) - (a.staleLeads || 0));
  const sortedByOverdue = [...managers].sort((a, b) => (b.unpaidInvoices || 0) - (a.unpaidInvoices || 0));
  const sortedByShipment = [...managers].sort((a, b) => (b.shipmentIssues || 0) - (a.shipmentIssues || 0));

  return (
    <motion.div 
      data-testid="team-performance-page"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <Breadcrumb items={[
        { label: 'Team Dashboard', to: '/team' },
        { label: 'Team Performance' },
      ]} />

      {/* Header */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <ChartLineUp size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('teamPerformance')}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('teamPerformanceDesc') || t('adm3_b718e2fb4d')}
            </p>
          </div>
        </div>
        <div className="shrink-0 self-start">
          <RefreshButton onClick={fetchPerformance} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="team-performance-refresh-btn" />
        </div>
      </div>

      {/* Team Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard 
          icon={ChartLineUp} 
          label={t('avgManagerScore')} 
          value={metrics?.averageScore || Math.round(managers.reduce((s, m) => s + (m.performanceScore || 0), 0) / (managers.length || 1))}
          color="#4F46E5"
        />
        <MetricCard 
          icon={Clock} 
          label={t('avgResponseTime')} 
          value={metrics?.avgFirstResponse || '—'}
          suffix={t('minShort') || t('adm3_bd967c92c8')}
          color="#059669"
        />
        <MetricCard 
          icon={Target} 
          label={t('staleLeadRate')} 
          value={metrics?.staleLeadRate || Math.round(managers.reduce((s, m) => s + (m.staleLeads || 0), 0) / (managers.length || 1) * 10)}
          suffix="%"
          color="#D97706"
        />
        <MetricCard 
          icon={Phone} 
          label={t('contactRate')} 
          value={metrics?.contactRate || '78'}
          suffix="%"
          color="#0891B2"
        />
        <MetricCard 
          icon={CreditCard} 
          label={t('paymentConv')} 
          value={metrics?.paymentConversion || '65'}
          suffix="%"
          color="#7C3AED"
        />
        <MetricCard 
          icon={Truck} 
          label={t('shipmentIssueRate')} 
          value={metrics?.shipmentIssueRate || Math.round(managers.reduce((s, m) => s + (m.shipmentIssues || 0), 0))}
          color="#DB2777"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Manager Performance Ranking */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center gap-2">
            <ChartBar size={20} className="text-[#18181B]" weight="duotone" />
            <h3 className="font-semibold text-[#18181B]">{t('managerPerfRanking')}</h3>
          </div>
          <div className="p-5 space-y-3">
            {sortedByScore.slice(0, 5).map((m, idx) => (
              <div key={m._id || idx} className="flex items-center gap-3">
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  idx === 0 ? 'bg-[#FEF3C7] text-[#D97706]' :
                  idx === 1 ? 'bg-[#F4F4F5] text-[#71717A]' :
                  idx === 2 ? 'bg-[#FEF3C7] text-[#92400E]' :
                  'bg-[#F4F4F5] text-[#71717A]'
                }`}>
                  {idx + 1}
                </span>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-[#18181B]">{m.name || t('managerAlerts')}</span>
                    <span className="text-sm font-bold text-[#18181B]">{m.performanceScore || 0}</span>
                  </div>
                  <div className="h-2 bg-[#F4F4F5] rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-[#4F46E5] rounded-full transition-all"
                      style={{ width: `${m.performanceScore || 0}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stale Leads by Manager */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center gap-2">
            <Clock size={20} className="text-[#D97706]" weight="duotone" />
            <h3 className="font-semibold text-[#18181B]">{t('staleLeadsByMgr')}</h3>
          </div>
          <div className="p-5 space-y-3">
            {sortedByStale.filter(m => (m.staleLeads || 0) > 0).slice(0, 5).map((m, idx) => (
              <div key={m._id || idx} className="flex items-center justify-between">
                <span className="text-sm text-[#18181B]">{m.name || 'Manager'}</span>
                <span className={`px-3 py-1 text-sm font-bold rounded-full ${
                  (m.staleLeads || 0) > 3 ? 'bg-[#FEF2F2] text-[#DC2626]' :
                  (m.staleLeads || 0) > 1 ? 'bg-[#FEF3C7] text-[#D97706]' :
                  'bg-[#F4F4F5] text-[#71717A]'
                }`}>
                  {m.staleLeads || 0}
                </span>
              </div>
            ))}
            {sortedByStale.filter(m => (m.staleLeads || 0) > 0).length === 0 && (
              <p className="text-sm text-[#71717A] text-center py-4">{t('noStaleLeads') || t('noResultsGeneric')}</p>
            )}
          </div>
        </div>

        {/* Overdue Invoices by Manager */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center gap-2">
            <CreditCard size={20} className="text-[#DC2626]" weight="duotone" />
            <h3 className="font-semibold text-[#18181B]">{t('overdueInvByMgr')}</h3>
          </div>
          <div className="p-5 space-y-3">
            {sortedByOverdue.filter(m => (m.unpaidInvoices || 0) > 0).slice(0, 5).map((m, idx) => (
              <div key={m._id || idx} className="flex items-center justify-between">
                <span className="text-sm text-[#18181B]">{m.name || 'Manager'}</span>
                <span className="px-3 py-1 text-sm font-bold bg-[#FEF2F2] text-[#DC2626] rounded-full">
                  {m.unpaidInvoices || 0}
                </span>
              </div>
            ))}
            {sortedByOverdue.filter(m => (m.unpaidInvoices || 0) > 0).length === 0 && (
              <p className="text-sm text-[#71717A] text-center py-4">{t('noOverdueInvoices') || t('noResultsGeneric')}</p>
            )}
          </div>
        </div>

        {/* Shipment Issues by Manager */}
        <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E4E4E7] flex items-center gap-2">
            <Truck size={20} className="text-[#0891B2]" weight="duotone" />
            <h3 className="font-semibold text-[#18181B]">{t('shipmentIssuesByMgr')}</h3>
          </div>
          <div className="p-5 space-y-3">
            {sortedByShipment.filter(m => (m.shipmentIssues || 0) > 0).slice(0, 5).map((m, idx) => (
              <div key={m._id || idx} className="flex items-center justify-between">
                <span className="text-sm text-[#18181B]">{m.name || t('managerAlerts')}</span>
                <span className="px-3 py-1 text-sm font-bold bg-[#FEF3C7] text-[#D97706] rounded-full">
                  {m.shipmentIssues || 0}
                </span>
              </div>
            ))}
            {sortedByShipment.filter(m => (m.shipmentIssues || 0) > 0).length === 0 && (
              <p className="text-sm text-[#71717A] text-center py-4">{t('noShipmentIssues') || t('noResultsGeneric')}</p>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

const MetricCard = ({ icon: Icon, label, value, suffix, color }) => (
  <div className="bg-white rounded-xl p-4 border border-[#E4E4E7]">
    <div className="flex items-center gap-2 mb-2">
      <Icon size={18} style={{ color }} weight="duotone" />
      <span className="text-xs font-medium text-[#71717A]">{label}</span>
    </div>
    <div className="text-2xl font-bold text-[#18181B]">
      {value}{suffix && <span className="text-sm font-normal text-[#71717A] ml-1">{suffix}</span>}
    </div>
  </div>
);

export default TeamPerformancePage;
