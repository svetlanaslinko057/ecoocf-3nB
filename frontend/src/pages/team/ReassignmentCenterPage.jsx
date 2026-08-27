/**
 * BIBI Cars - Reassignment Center
 * Critical screen for lead reassignment management
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { format } from 'date-fns';
import { uk } from 'date-fns/locale';
import {
  ArrowsClockwise,
  Check,
  Clock,
  Eye,
  User,
  Warning,
  Queue,
  Lightning
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import BackButton from '../../components/ui/BackButton';
import Breadcrumb from '../../components/ui/Breadcrumb';
import RefreshButton from '../../components/ui/RefreshButton';

const ReassignmentCenterPage = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [reassignments, setReassignments] = useState([]);
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [reassignRes, managersRes] = await Promise.all([
        axios.get(`${API_URL}/api/team/reassignments`).catch(() => ({ data: [] })),
        axios.get(`${API_URL}/api/team/managers`).catch(() => 
          axios.get(`${API_URL}/api/users?role=manager`)
        ),
      ]);
      const reassignData = reassignRes.data?.data || reassignRes.data || [];
      setReassignments(Array.isArray(reassignData) ? reassignData : []);
      const managersData = managersRes.data?.data || managersRes.data || [];
      setManagers(Array.isArray(managersData) ? managersData : []);
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (id, newManagerId) => {
    try {
      await axios.post(`${API_URL}/api/team/reassignments/${id}/accept`, { newManagerId });
      toast.success(t('reassignmentAccepted'));
      fetchData();
    } catch (err) {
      toast.error(t('actionError'));
    }
  };

  const handleSnooze = async (id, minutes = 15) => {
    try {
      await axios.post(`${API_URL}/api/team/reassignments/${id}/snooze`, { minutes });
      toast.success(`${t('snoozedFor')} ${minutes} ${t('minutes')}`);
      fetchData();
    } catch (err) {
      toast.error(t('actionError'));
    }
  };

  const handleSendToQueue = async (id) => {
    try {
      await axios.post(`${API_URL}/api/team/reassignments/${id}/queue`);
      toast.success(t('sentToQueue'));
      fetchData();
    } catch (err) {
      toast.error(t('actionError'));
    }
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
      data-testid="reassignment-center-page"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <Breadcrumb items={[
        { label: 'Team Dashboard', to: '/team' },
        { label: 'Reassignment Center' },
      ]} />

      {/* Header */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <ArrowsClockwise size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('reassignmentCenter')}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('leadsNeedReassignment')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 self-start">
          <RefreshButton onClick={fetchData} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="reassignment-refresh-btn" />
          <div className="flex items-center gap-2 px-3 py-2 bg-[#FEF3C7] text-[#D97706] rounded-xl text-sm">
            <ArrowsClockwise size={16} weight="duotone" />
            <span className="font-medium whitespace-nowrap">{reassignments.length} {t('pending')}</span>
          </div>
        </div>
      </div>

      {/* Reassignment Cards */}
      {reassignments.length === 0 ? (
        <div className="bg-white rounded-2xl border border-[#E4E4E7] p-12 text-center">
          <Check size={48} className="text-[#059669] mx-auto mb-4" weight="duotone" />
          <p className="text-lg font-medium text-[#18181B]">{t('allClear')}</p>
          <p className="text-sm text-[#71717A]">{t('noReassignmentsNeeded')}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {reassignments.map((item, idx) => (
            <motion.div
              key={item._id || idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              className="bg-white rounded-2xl border border-[#E4E4E7] p-5"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-[#FEF3C7] rounded-xl flex items-center justify-center">
                    <Warning size={24} className="text-[#D97706]" weight="duotone" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#18181B]">
                      {item.leadName || item.lead?.name || t('lead')}
                    </h3>
                    <p className="text-sm text-[#71717A]">
                      {item.leadEmail || item.lead?.email || item.leadPhone || item.lead?.phone}
                    </p>
                  </div>
                </div>
                <span className={`px-3 py-1 text-xs font-medium rounded-full ${
                  item.severity === 'critical' ? 'bg-[#FEF2F2] text-[#DC2626]' :
                  item.severity === 'high' ? 'bg-[#FEF3C7] text-[#D97706]' :
                  'bg-[#F4F4F5] text-[#71717A]'
                }`}>
                  {item.severity || 'medium'}
                </span>
              </div>

              {/* Details */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 p-4 bg-[#F4F4F5] rounded-xl">
                <div>
                  <span className="text-xs text-[#71717A]">{t('currentManager')}</span>
                  <p className="font-medium text-[#18181B]">{item.currentManagerName || item.currentManager?.name || '—'}</p>
                </div>
                <div>
                  <span className="text-xs text-[#71717A]">{t('reason')}</span>
                  <p className="font-medium text-[#D97706]">{item.reason || t('noContact')}</p>
                </div>
                <div>
                  <span className="text-xs text-[#71717A]">{t('timeSinceStale')}</span>
                  <p className="font-medium text-[#18181B]">{item.timeSinceStale || item.staleDuration || '—'}</p>
                </div>
                <div>
                  <span className="text-xs text-[#71717A]">{t('suggestedManager')}</span>
                  <p className="font-medium text-[#059669]">{item.suggestedManagerName || item.suggestedManager?.name || 'Auto'}</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-3">
                <WhiteSelect className="flex-1" defaultValue={item.suggestedManagerId || ''}>
                  <option value="">{t('selectNewManager')}</option>
                  {managers.map(m => (
                    <option key={m._id} value={m._id}>
                      {m.name} ({m.activeLeads || 0} {t('leadsTab').toLowerCase()})
                    </option>
                  ))}
                </WhiteSelect>
                <button
                  onClick={() => handleAccept(item._id, item.suggestedManagerId)}
                  className="px-4 py-2 bg-[#059669] text-white rounded-xl text-sm font-medium hover:bg-[#047857] transition-colors flex items-center gap-2"
                >
                  <Check size={16} weight="bold" /> {t('accept') || 'Accept'}
                </button>
                {/* Wave 7 — snooze/queue stubs hidden until the queue engine is built.
                    Tracked in plan.md → "Snooze / Queue stubs". */}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
};

export default ReassignmentCenterPage;
