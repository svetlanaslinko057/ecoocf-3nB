/**
 * BIBI Cars - Team Managers Page
 * Manager Load Board with detailed view
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL, useAuth } from '../../App';
import { useLang } from '../../i18n';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Users,
  MagnifyingGlass,
  Eye,
  ArrowsClockwise,
  Phone,
  ListChecks,
  Warning,
  Fire,
  Clock,
  ChartLineUp,
  CaretDown,
  Funnel
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import BackButton from '../../components/ui/BackButton';
import Breadcrumb from '../../components/ui/Breadcrumb';
import RefreshButton from '../../components/ui/RefreshButton';
import RoleZoneBadge from '../../components/ui/RoleZoneBadge';

const TeamManagersPage = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('performanceScore');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    fetchManagers();
  }, []);

  const fetchManagers = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/team/managers`);
      const data = Array.isArray(res.data) ? res.data : (res.data?.data || res.data?.managers || []);
      setManagers(data);
    } catch (err) {
      console.error('Error fetching managers:', err);
      // Fallback to users API
      try {
        const fallback = await axios.get(`${API_URL}/api/users?role=manager`);
        const fallbackData = Array.isArray(fallback.data) ? fallback.data : (fallback.data?.data || []);
        setManagers(fallbackData);
      } catch (e) {
        toast.error(t('loadError'));
        setManagers([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReassignLeads = async (managerId) => {
    toast.info(t('functionInDev'));
  };

  const handleForceTaskReview = async (managerId) => {
    toast.info(t('functionInDev'));
  };

  const filteredManagers = managers
    .filter(m => 
      (m.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.email || '').toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      const aVal = a[sortBy] || 0;
      const bVal = b[sortBy] || 0;
      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full"></div>
      </div>
    );
  }

  return (
    <motion.div 
      data-testid="team-managers-page"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <Breadcrumb items={[
        { label: 'Team Dashboard', to: '/team' },
        { label: 'Managers' },
      ]} />

      {/* Header */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Users size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('managerLoadBoard')}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('teamLoadControl')}
            </p>
          </div>
        </div>
        <div className="shrink-0 self-start">
          <RefreshButton onClick={fetchManagers} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="team-managers-refresh-btn" />
        </div>
      </div>

      {/* Shared HR zone marker + cross-link to Staff registry */}
      <RoleZoneBadge
        variant="hr"
        link={{ href: '/admin/staff', label: 'Open Staff registry' }}
      />

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A]" />
          <input
            type="text"
            placeholder={t('searchManager')}
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5] focus:border-transparent"
          />
        </div>
        <WhiteSelect value={sortBy} onChange={e => setSortBy(e.target.value)}>
          <option value="performanceScore">{t('byRating')}</option>
          <option value="activeLeads">{t('byLeads')}</option>
          <option value="overdueTasks">{t('byOverdue')}</option>
          <option value="staleLeads">{t('byStale')}</option>
        </WhiteSelect>
        <button
          onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
          className="p-2.5 border border-[#E4E4E7] rounded-xl hover:bg-[#F4F4F5]"
        >
          <CaretDown size={18} className={`transition-transform ${sortOrder === 'asc' ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Managers Table */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[#F4F4F5]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-[#71717A] uppercase">{t('manager')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('performance')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('activeLeads')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('hotLeads')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('staleLeads')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('overdueTasks')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('callsToday')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('dealsWon')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('unpaidInvoices')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('shipmentStatus')}</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E4E4E7]">
              {filteredManagers.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-sm text-[#71717A]">
                    {t('managersNotFound')}
                  </td>
                </tr>
              ) : (
                filteredManagers.map((m, idx) => (
                  <motion.tr
                    key={m._id || m.managerId || idx}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: idx * 0.03 }}
                    className="hover:bg-[#FAFAFA] transition-colors"
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#F4F4F5] rounded-full flex items-center justify-center text-sm font-bold text-[#18181B]">
                          {(m.name || 'M')[0]}
                        </div>
                        <div>
                          <div className="font-semibold text-[#18181B]">{m.name || m.email || t('manager')}</div>
                          <div className="text-xs text-[#71717A]">{m.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={`px-3 py-1 text-xs font-bold rounded-full ${
                        (m.band || '').toLowerCase() === 'high' ? 'bg-[#ECFDF5] text-[#059669]' :
                        (m.band || '').toLowerCase() === 'medium' ? 'bg-[#FEF3C7] text-[#D97706]' :
                        (m.band || '').toLowerCase() === 'low' ? 'bg-[#FEF2F2] text-[#DC2626]' :
                        'bg-[#F4F4F5] text-[#71717A]'
                      }`}>
                        {m.band?.toUpperCase() || 'N/A'} {m.performanceScore || 0}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center font-medium">{m.activeLeads || 0}</td>
                    <td className="px-4 py-4 text-center">
                      {m.hotLeads > 0 ? (
                        <span className="inline-flex items-center gap-1 text-[#DC2626] font-bold">
                          <Fire size={14} weight="fill" /> {m.hotLeads}
                        </span>
                      ) : (
                        <span className="text-[#71717A]">0</span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={m.staleLeads > 2 ? 'text-[#D97706] font-bold' : 'text-[#71717A]'}>
                        {m.staleLeads || 0}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={m.overdueTasks > 0 ? 'text-[#DC2626] font-bold' : 'text-[#71717A]'}>
                        {m.overdueTasks || 0}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className="inline-flex items-center gap-1">
                        <Phone size={14} className="text-[#71717A]" /> {m.callsToday || 0}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center font-medium text-[#059669]">{m.dealsWon || 0}</td>
                    <td className="px-4 py-4 text-center">
                      <span className={m.unpaidInvoices > 0 ? 'text-[#DC2626] font-bold' : 'text-[#71717A]'}>
                        {m.unpaidInvoices || 0}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      {m.shipmentIssues > 0 ? (
                        <span className="text-[#D97706] font-bold">{m.shipmentIssues}</span>
                      ) : (
                        <span className="text-[#059669]">OK</span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-center gap-1">
                        <Link
                          to={`/team/managers/${m._id || m.managerId}`}
                          className="p-2 text-[#71717A] hover:text-[#18181B] hover:bg-[#F4F4F5] rounded-lg transition-colors"
                          title={t('viewProfile')}
                        >
                          <Eye size={18} />
                        </Link>
                        <button
                          onClick={() => handleReassignLeads(m._id || m.managerId)}
                          className="p-2 text-[#71717A] hover:text-[#D97706] hover:bg-[#FEF3C7] rounded-lg transition-colors"
                          title={t('reassignLeads')}
                        >
                          <ArrowsClockwise size={18} />
                        </button>
                        <button
                          onClick={() => handleForceTaskReview(m._id || m.managerId)}
                          className="p-2 text-[#71717A] hover:text-[#DC2626] hover:bg-[#FEF2F2] rounded-lg transition-colors"
                          title={t('forceTaskReview')}
                        >
                          <ListChecks size={18} />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );
};

export default TeamManagersPage;
