/**
 * BIBI Cars - Team Leads Page
 * View and manage all team leads with filters
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
  Users,
  Fire,
  Clock,
  MagnifyingGlass,
  Funnel,
  ArrowsClockwise,
  Phone,
  Eye,
  Warning,
  Globe,
  Tag
} from '@phosphor-icons/react';

const TeamLeadsPage = () => {
  const { t } = useLang();
  const { user } = useAuth();
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchLeads();
  }, [activeTab]);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/team/leads`;
      if (activeTab === 'hot') url = `${API_URL}/api/team/leads/hot`;
      else if (activeTab === 'stale') url = `${API_URL}/api/team/leads/stale`;
      else if (activeTab === 'unassigned') url += '?status=unassigned';
      else if (activeTab === 'reassignment') url = `${API_URL}/api/team/reassignments`;

      const res = await axios.get(url).catch(() => 
        axios.get(`${API_URL}/api/leads`)
      );
      const leadsData = Array.isArray(res.data) ? res.data : (res.data?.data || res.data?.leads || res.data?.items || []);
      setLeads(leadsData);
    } catch (err) {
      console.error('Error fetching leads:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReassign = async (leadId) => {
    try {
      await axios.post(`${API_URL}/api/team/leads/${leadId}/reassign`);
      toast.success(t('leadReassigned') || 'Lead reassigned');
      fetchLeads();
    } catch (err) {
      toast.error(t('actionError'));
    }
  };

  const handleForceCallback = async (leadId) => {
    try {
      await axios.post(`${API_URL}/api/tasks`, {
        type: 'callback_attempt',
        leadId,
        priority: 'high',
        title: t('adm_forced_callback_team_lead')
      });
      toast.success(t('callbackCreated') || 'Callback task created');
    } catch (err) {
      toast.error(t('actionError'));
    }
  };

  const tabs = [
    { id: 'all', labelKey: 'allFilter', count: null },
    { id: 'hot', labelKey: 'hotFilter', count: leads.filter(l => l.score >= 70).length, color: '#DC2626' },
    { id: 'stale', labelKey: 'staleFilter', count: leads.filter(l => l.isStale).length, color: '#D97706' },
    { id: 'unassigned', labelKey: 'unassignedFilter', count: null },
    { id: 'reassignment', labelKey: 'reassignmentNeeded', count: null, color: '#7C3AED' },
  ];

  const filteredLeads = leads.filter(l =>
    (l.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (l.email || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (l.phone || '').includes(searchQuery)
  );

  return (
    <motion.div 
      data-testid="team-leads-page"
      initial={{ opacity: 0, y: 10 }} 
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <Breadcrumb items={[
        { label: 'Team Dashboard', to: '/team' },
        { label: 'Team Leads' },
      ]} />

      {/* Header */}
      <div className="flex flex-row items-start justify-between gap-3 sm:gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Users size={18} weight="duotone" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
              {t('teamLeads')}
            </h1>
            <p className="text-xs sm:text-sm text-[#71717A] mt-1 break-words">
              {t('teamLeadsSubtitle')}
            </p>
          </div>
        </div>
        <div className="shrink-0 self-start">
          <RefreshButton onClick={fetchLeads} loading={loading} ariaLabel={t('adm_refresh_3') || 'Refresh'} testId="team-leads-refresh-btn" />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors flex items-center gap-2 ${
              activeTab === tab.id
                ? 'bg-[#18181B] text-white'
                : 'bg-white border border-[#E4E4E7] text-[#71717A] hover:bg-[#F4F4F5]'
            }`}
          >
            {t(tab.labelKey)}
            {tab.count !== null && tab.count > 0 && (
              <span className={`px-1.5 py-0.5 text-xs rounded-full ${
                activeTab === tab.id ? 'bg-white/20' : ''
              }`} style={{ backgroundColor: tab.color ? `${tab.color}20` : '', color: tab.color }}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <MagnifyingGlass size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A]" />
        <input
          type="text"
          placeholder={t('searchByNameEmailPhone')}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#4F46E5] focus:border-transparent"
        />
      </div>

      {/* Leads Table */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin w-8 h-8 border-2 border-[#4F46E5] border-t-transparent rounded-full mx-auto"></div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[#F4F4F5]">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-[#71717A] uppercase">{t('lead')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('source')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('filterCountry')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('score')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('managerAlerts')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('lastContact')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('tableAge')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('status')}</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">SLA</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-[#71717A] uppercase">{t('actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E4E4E7]">
                {filteredLeads.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-sm text-[#71717A]">
                      {t('noLeadsFound')}
                    </td>
                  </tr>
                ) : (
                  filteredLeads.map((lead, idx) => (
                    <motion.tr
                      key={lead._id || idx}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: idx * 0.02 }}
                      className="hover:bg-[#FAFAFA] transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div>
                          <div className="font-medium text-[#18181B]">{lead.name || 'N/A'}</div>
                          <div className="text-xs text-[#71717A]">{lead.email || lead.phone}</div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="px-2 py-1 bg-[#F4F4F5] text-[#71717A] text-xs rounded-lg">
                          {lead.source || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="inline-flex items-center gap-1 text-sm">
                          <Globe size={14} className="text-[#71717A]" />
                          {lead.country || 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex items-center gap-1 font-bold ${
                          (lead.score || 0) >= 70 ? 'text-[#DC2626]' :
                          (lead.score || 0) >= 40 ? 'text-[#D97706]' : 'text-[#71717A]'
                        }`}>
                          {(lead.score || 0) >= 70 && <Fire size={14} weight="fill" />}
                          {lead.score || 0}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center text-sm">
                        {lead.managerName || lead.manager?.name || t('unassigned')}
                      </td>
                      <td className="px-4 py-3 text-center text-xs text-[#71717A]">
                        {lead.lastContactAt ? format(new Date(lead.lastContactAt), 'dd MMM, HH:mm', { locale: uk }) : t('never')}
                      </td>
                      <td className="px-4 py-3 text-center text-sm text-[#71717A]">
                        {lead.ageInDays || 0}d
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          lead.status === 'new' ? 'bg-[#F4F4F5] text-[#18181B]' :
                          lead.status === 'contacted' ? 'bg-[#ECFDF5] text-[#059669]' :
                          lead.status === 'qualified' ? 'bg-[#FEF3C7] text-[#D97706]' :
                          'bg-[#F4F4F5] text-[#71717A]'
                        }`}>
                          {lead.status || 'new'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {lead.isStale || lead.slaBreached ? (
                          <Warning size={18} className="text-[#DC2626] mx-auto" weight="fill" />
                        ) : (
                          <span className="text-[#059669] text-xs">OK</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => handleReassign(lead._id)}
                            className="p-2 text-[#71717A] hover:text-[#18181B] hover:bg-[#F4F4F5] rounded-lg transition-colors"
                            title={t('reassign')}
                          >
                            <ArrowsClockwise size={16} />
                          </button>
                          <button
                            onClick={() => handleForceCallback(lead._id)}
                            className="p-2 text-[#71717A] hover:text-[#059669] hover:bg-[#ECFDF5] rounded-lg transition-colors"
                            title={t('forceCallback')}
                          >
                            <Phone size={16} />
                          </button>
                        </div>
                      </td>
                    </motion.tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default TeamLeadsPage;
