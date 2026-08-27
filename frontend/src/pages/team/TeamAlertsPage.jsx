/**
 * BIBI Cars - Team Alerts Feed
 * Real-time alerts stream for team lead
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { format } from 'date-fns';
import { uk } from 'date-fns/locale';
import BackButton from '../../components/ui/BackButton';
import Breadcrumb from '../../components/ui/Breadcrumb';
import RefreshButton from '../../components/ui/RefreshButton';
import {
  Bell,
  Warning,
  Fire,
  CreditCard,
  Truck,
  Shield,
  User,
  Clock,
  Check,
  X,
  Funnel
} from '@phosphor-icons/react';

const TeamAlertsPage = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('all');

  useEffect(() => {
    fetchAlerts();
  }, [activeFilter]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/team/alerts`;
      if (activeFilter !== 'all') url += `?type=${activeFilter}`;

      const res = await axios.get(url).catch(() =>
        axios.get(`${API_URL}/api/alerts`)
      );
      const alertsData = Array.isArray(res.data) ? res.data : (res.data?.data || res.data?.alerts || []);
      setAlerts(alertsData);
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkRead = async (alertId) => {
    try {
      await axios.patch(`${API_URL}/api/alerts/${alertId}/read`);
      fetchAlerts();
    } catch (err) {
      toast.error(t('actionError'));
    }
  };

  const handleDismiss = async (alertId) => {
    try {
      await axios.delete(`${API_URL}/api/alerts/${alertId}`);
      toast.success(t('alertDismissed'));
      fetchAlerts();
    } catch (err) {
      toast.error(t('actionError'));
    }
  };

  const filters = [
    { id: 'all', labelKey: 'allFilter', icon: Bell },
    { id: 'critical', labelKey: 'criticalAlerts', icon: Warning, color: '#DC2626' },
    { id: 'manager', labelKey: 'managerAlerts', icon: User, color: '#4F46E5' },
    { id: 'payments', labelKey: 'paymentsAlerts', icon: CreditCard, color: '#059669' },
    { id: 'shipment', labelKey: 'shipmentAlerts', icon: Truck, color: '#D97706' },
    { id: 'security', labelKey: 'securityAlerts', icon: Shield, color: '#7C3AED' },
  ];

  const getAlertIcon = (type) => {
    switch (type) {
      case 'hot_lead_missed': return Fire;
      case 'payment_overdue': return CreditCard;
      case 'shipment_stalled': return Truck;
      case 'session_suspicious': return Shield;
      case 'manager_inactive': return User;
      default: return Warning;
    }
  };

  const getAlertColor = (severity) => {
    switch (severity) {
      case 'critical': return { bg: '#FEF2F2', text: '#DC2626', border: '#FECACA' };
      case 'high': return { bg: '#FEF3C7', text: '#D97706', border: '#FDE68A' };
      case 'medium': return { bg: '#EEF2FF', text: '#4F46E5', border: '#C7D2FE' };
      default: return { bg: '#F4F4F5', text: '#71717A', border: '#E4E4E7' };
    }
  };

  return (
    <motion.div 
      data-testid="team-alerts-page"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <Breadcrumb items={[
        { label: 'Team Dashboard', to: '/team' },
        { label: 'Alerts Feed' },
      ]} />

      {/* Header */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Bell size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('teamAlertsFeed')}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('teamAlertsLiveFeed')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 self-start">
          <RefreshButton onClick={fetchAlerts} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="team-alerts-refresh-btn" />
          <div className="flex items-center gap-2 px-3 py-2 bg-[#FEF2F2] text-[#DC2626] rounded-xl text-sm">
            <Bell size={16} weight="fill" />
            <span className="font-medium whitespace-nowrap">{alerts.filter(a => !a.isRead).length} {t('unread')}</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {filters.map(filter => (
          <button
            key={filter.id}
            onClick={() => setActiveFilter(filter.id)}
            className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors flex items-center gap-2 ${
              activeFilter === filter.id
                ? 'bg-[#18181B] text-white'
                : 'bg-white border border-[#E4E4E7] text-[#71717A] hover:bg-[#F4F4F5]'
            }`}
          >
            <filter.icon size={16} style={{ color: activeFilter === filter.id ? 'white' : filter.color }} />
            {t(filter.labelKey)}
          </button>
        ))}
      </div>

      {/* Alerts List */}
      <div className="space-y-3">
        {loading ? (
          <div className="bg-white rounded-2xl border border-[#E4E4E7] p-8 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full mx-auto"></div>
          </div>
        ) : alerts.length === 0 ? (
          <div className="bg-white rounded-2xl border border-[#E4E4E7] p-12 text-center">
            <Check size={48} className="text-[#059669] mx-auto mb-4" weight="duotone" />
            <p className="text-lg font-medium text-[#18181B]">{t('allClear')}</p>
            <p className="text-sm text-[#71717A]">{t('noNewAlerts')}</p>
          </div>
        ) : (
          alerts.map((alert, idx) => {
            const Icon = getAlertIcon(alert.type);
            const colors = getAlertColor(alert.severity);
            return (
              <motion.div
                key={alert._id || idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className={`bg-white rounded-2xl border p-5 ${
                  !alert.isRead ? 'border-l-4' : ''
                }`}
                style={{ 
                  borderColor: !alert.isRead ? colors.text : '#E4E4E7',
                  borderLeftColor: !alert.isRead ? colors.text : undefined
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div 
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ backgroundColor: colors.bg }}
                    >
                      <Icon size={20} style={{ color: colors.text }} weight="duotone" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-[#18181B]">{alert.title || alert.message}</h4>
                        <span 
                          className="px-2 py-0.5 text-xs font-medium rounded-full"
                          style={{ backgroundColor: colors.bg, color: colors.text }}
                        >
                          {alert.severity || 'info'}
                        </span>
                      </div>
                      <p className="text-sm text-[#71717A] mb-2">{alert.description || alert.message}</p>
                      <div className="flex items-center gap-4 text-xs text-[#A1A1AA]">
                        {alert.managerName && (
                          <span className="flex items-center gap-1">
                            <User size={12} /> {alert.managerName}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <Clock size={12} /> 
                          {alert.createdAt ? format(new Date(alert.createdAt), 'dd MMM, HH:mm', { locale: uk }) : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!alert.isRead && (
                      <button
                        onClick={() => handleMarkRead(alert._id)}
                        className="p-2 text-[#71717A] hover:text-[#059669] hover:bg-[#ECFDF5] rounded-lg transition-colors"
                        title={t('markAsReadAction')}
                      >
                        <Check size={16} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDismiss(alert._id)}
                      className="p-2 text-[#71717A] hover:text-[#DC2626] hover:bg-[#FEF2F2] rounded-lg transition-colors"
                      title={t('dismiss')}
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              </motion.div>
            );
          })
        )}
      </div>
    </motion.div>
  );
};

export default TeamAlertsPage;

