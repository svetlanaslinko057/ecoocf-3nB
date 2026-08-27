/**
 * BIBI Cars - Response Time Dashboard
 * Tracking and metrics for manager response times
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  Clock,
  Timer,
  Lightning,
  Warning,
  CheckCircle,
  User,
  ChartLineUp,
  TrendUp,
  TrendDown,
} from '@phosphor-icons/react';
import RefreshButton from '../../components/ui/RefreshButton';

const ResponseTimeDashboard = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  useEffect(() => {
    fetchMetrics();
  }, [days]);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/response-time/team?days=${days}`);
      setMetrics(res.data);
    } catch (err) {
      console.error('Error fetching response time metrics:', err);
      // Mock data for demo
      setMetrics({
        teamAvgSeconds: 245,
        teamAvgMinutes: 4.1,
        totalEvents: 156,
        withinSLAPercentage: 87,
        byManager: [
          { managerId: '1', avgResponseSeconds: 180, avgResponseMinutes: 3, totalEvents: 45, slaPercentage: 95, pendingResponses: 1 },
          { managerId: '2', avgResponseSeconds: 220, avgResponseMinutes: 3.7, totalEvents: 38, slaPercentage: 89, pendingResponses: 0 },
          { managerId: '3', avgResponseSeconds: 320, avgResponseMinutes: 5.3, totalEvents: 42, slaPercentage: 78, pendingResponses: 3 },
          { managerId: '4', avgResponseSeconds: 260, avgResponseMinutes: 4.3, totalEvents: 31, slaPercentage: 84, pendingResponses: 2 },
        ],
        byEventType: {
          lead_assigned: { avg: 210, count: 89, slaPercent: 92 },
          first_call: { avg: 380, count: 45, slaPercent: 78 },
          callback: { avg: 520, count: 22, slaPercent: 85 },
        },
        trends: [
          { date: '2026-03-28', avgSeconds: 280, count: 18 },
          { date: '2026-03-29', avgSeconds: 260, count: 22 },
          { date: '2026-03-30', avgSeconds: 240, count: 25 },
          { date: '2026-03-31', avgSeconds: 230, count: 21 },
          { date: '2026-04-01', avgSeconds: 245, count: 28 },
          { date: '2026-04-02', avgSeconds: 220, count: 24 },
          { date: '2026-04-03', avgSeconds: 210, count: 18 },
        ],
      });
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600 * 10) / 10}h`;
  };

  const getSLAColor = (percentage) => {
    if (percentage >= 90) return { bg: '#DCFCE7', text: '#15803D', border: '#86EFAC' };
    if (percentage >= 75) return { bg: '#FEF9C3', text: '#A16207', border: '#FDE047' };
    return { bg: '#FEE2E2', text: '#DC2626', border: '#FECACA' };
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <motion.div 
      data-testid="response-time-dashboard"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Timer size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('responseMetrics')}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('responseTimeGoal')}: 5 {t('minutes')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 self-start">
          <RefreshButton onClick={fetchMetrics} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="response-time-refresh-btn" />
          <div className="flex gap-1">
            {[7, 14, 30].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                  days === d
                    ? 'bg-[#18181B] text-white'
                    : 'bg-white border border-[#E4E4E7] text-[#71717A] hover:bg-[#F4F4F5]'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[#F4F4F5] rounded-xl">
              <Timer size={20} className="text-[#18181B]" weight="duotone" />
            </div>
            <span className="text-sm text-[#71717A]">{t('avgResponseTime')}</span>
          </div>
          <div className="text-3xl font-bold text-[#18181B]">{metrics?.teamAvgMinutes}m</div>
          <div className="text-xs text-[#71717A] mt-1">{metrics?.teamAvgSeconds}s</div>
        </div>

        <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[#DCFCE7] rounded-xl">
              <CheckCircle size={20} className="text-[#15803D]" weight="duotone" />
            </div>
            <span className="text-sm text-[#71717A]">{t('adm_sla')}</span>
          </div>
          <div className="text-3xl font-bold text-[#15803D]">{metrics?.withinSLAPercentage}%</div>
          <div className="text-xs text-[#71717A] mt-1">{t('withinSLA') || 'Within SLA'}</div>
        </div>

        <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[#F4F4F5] rounded-xl">
              <ChartLineUp size={20} className="text-[#71717A]" weight="duotone" />
            </div>
            <span className="text-sm text-[#71717A]">{t('totalEvents') || 'Total Events'}</span>
          </div>
          <div className="text-3xl font-bold text-[#18181B]">{metrics?.totalEvents}</div>
          <div className="text-xs text-[#71717A] mt-1">{days}d</div>
        </div>

        <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 bg-[#FEF3C7] rounded-xl">
              <Lightning size={20} className="text-[#D97706]" weight="duotone" />
            </div>
            <span className="text-sm text-[#71717A]">{t('fastResponse')}</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendDown size={20} className="text-[#15803D]" />
            <span className="text-3xl font-bold text-[#18181B]">-12%</span>
          </div>
          <div className="text-xs text-[#71717A] mt-1">{t('improvement') || 'vs last period'}</div>
        </div>
      </div>

      {/* Trend Chart (simplified) */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5">
        <h3 className="font-semibold text-[#18181B] mb-4">{t('trends') || 'Response Time Trend'}</h3>
        <div className="h-40 flex items-end gap-2">
          {metrics?.trends?.map((day, idx) => (
            <div key={idx} className="flex-1 flex flex-col items-center gap-1">
              <div 
                className="w-full bg-[#4F46E5] rounded-t opacity-80 hover:opacity-100 transition-opacity"
                style={{ height: `${Math.min(100, (day.avgSeconds / 400) * 100)}%` }}
                title={`${formatTime(day.avgSeconds)} (${day.count} events)`}
              ></div>
              <span className="text-xs text-[#71717A]">{day.date.split('-')[2]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* By Event Type */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] p-5">
        <h3 className="font-semibold text-[#18181B] mb-4">{t('byEventType') || 'By Event Type'}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(metrics?.byEventType || {}).map(([type, data]) => {
            const colors = getSLAColor(data.slaPercent);
            return (
              <div 
                key={type}
                className="p-4 rounded-xl border"
                style={{ borderColor: colors.border, backgroundColor: colors.bg }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium capitalize" style={{ color: colors.text }}>
                    {type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs px-2 py-1 rounded-full" style={{ backgroundColor: colors.text + '20', color: colors.text }}>
                    {data.slaPercent}% SLA
                  </span>
                </div>
                <div className="text-2xl font-bold" style={{ color: colors.text }}>{formatTime(data.avg)}</div>
                <div className="text-xs mt-1" style={{ color: colors.text }}>{data.count} {t('events') || 'events'}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Manager Rankings */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
        <div className="p-5 border-b border-[#E4E4E7]">
          <h3 className="font-semibold text-[#18181B]">{t('managerRanking') || 'Manager Rankings'}</h3>
        </div>
        <div className="divide-y divide-[#E4E4E7]">
          {metrics?.byManager?.map((manager, idx) => {
            const colors = getSLAColor(manager.slaPercentage);
            return (
              <div key={idx} className="px-5 py-4 flex items-center justify-between hover:bg-[#FAFAFA]">
                <div className="flex items-center gap-4">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    idx === 0 ? 'bg-[#FEF3C7] text-[#D97706]' : 'bg-[#F4F4F5] text-[#71717A]'
                  }`}>
                    {idx + 1}
                  </div>
                  <div>
                    <div className="font-medium text-[#18181B]">{t('managerAlerts')} {manager.managerId}</div>
                    <div className="text-xs text-[#71717A]">{manager.totalEvents} {t('totalEvents').toLowerCase()}</div>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <div className="font-semibold text-[#18181B]">{formatTime(manager.avgResponseSeconds)}</div>
                    <div className="text-xs text-[#71717A]">{t('avgResponseTime')}</div>
                  </div>
                  <div 
                    className="px-3 py-1 rounded-full text-sm font-medium"
                    style={{ backgroundColor: colors.bg, color: colors.text }}
                  >
                    {manager.slaPercentage}%
                  </div>
                  {manager.pendingResponses > 0 && (
                    <div className="flex items-center gap-1 text-[#D97706]">
                      <Warning size={16} weight="fill" />
                      <span className="text-sm">{manager.pendingResponses}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
};

export default ResponseTimeDashboard;
