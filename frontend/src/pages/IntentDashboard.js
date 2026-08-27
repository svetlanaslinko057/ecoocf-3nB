/**
 * Intent Dashboard Page
 *
 * Admin page for monitoring user intent scores and HOT leads.
 *
 * Visual language aligned with the rest of the admin shell:
 *   • <AdminPageHeader/> for consistent breadcrumb-style title + action zone.
 *   • Monochrome KPI tiles (white card, gray border, muted icon).
 *   • Single accent colour (black `#18181B`) for primary buttons.
 *   • Subtle status tints (red/amber/blue) live ONLY inside compact pill badges,
 *     never on whole card backgrounds — so the page no longer looks like a rainbow.
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_URL } from '../App';
import { useLang, getLocale } from '../i18n';
import { toast } from 'sonner';
import {
  Fire,
  ThermometerHot,
  Snowflake,
  Users,
  Phone,
  ChartLineUp,
  Lightning,
  Robot,
  ArrowsClockwise,
} from '@phosphor-icons/react';
import ManagerAIWidget from '../components/crm/ManagerAIWidget';
import { motion } from 'framer-motion';
import { AdminPageHeader } from '../components/ui/AdminPagePrimitives';
import RefreshButton from '../components/ui/RefreshButton';

const IntentDashboard = () => {
  const { t } = useLang();
  const [analytics, setAnalytics] = useState(null);
  const [hotLeads, setHotLeads] = useState([]);
  const [allScores, setAllScores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showAIPanel, setShowAIPanel] = useState(false);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [analyticsRes, hotRes, scoresRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/intent/analytics`),
        axios.get(`${API_URL}/api/admin/intent/hot-leads`),
        axios.get(`${API_URL}/api/admin/intent/scores?limit=50`),
      ]);
      setAnalytics(analyticsRes.data);
      setHotLeads(hotRes.data);
      setAllScores(scoresRes.data.items || []);
    } catch (err) {
      toast.error(t('adm_data_loading_error'));
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const markNotified = async (userId) => {
    try {
      await axios.post(`${API_URL}/api/admin/intent/mark-notified/${userId}`);
      toast.success(t('adm_marked_as_processed'));
      fetchData();
    } catch (err) {
      toast.error(t('adm_error_2'));
    }
  };

  // Compact monochrome intent pill — only the small dot keeps a tint to
  // preserve at-a-glance scanning, the rest of the badge is neutral.
  const getIntentBadge = (level, score) => {
    const cfg = level === 'hot'
      ? { Icon: Fire,           tint: 'text-rose-600',  label: 'HOT'  }
      : level === 'warm'
      ? { Icon: ThermometerHot, tint: 'text-amber-600', label: 'WARM' }
      : { Icon: Snowflake,      tint: 'text-blue-600',  label: 'COLD' };
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#F4F4F5] text-[#3F3F46] whitespace-nowrap"
        data-testid={`intent-badge-${level}`}
      >
        <cfg.Icon size={12} weight="fill" className={cfg.tint} />
        {cfg.label} <span className="text-[#71717A] font-medium">{score}</span>
      </span>
    );
  };

  if (loading) {
    return (
      <div className="space-y-4 sm:space-y-5 animate-pulse" data-testid="intent-dashboard-loading">
        <div className="h-8 bg-[#F4F4F5] rounded w-48" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-[#FAFAFA] rounded-2xl border border-[#E4E4E7]" />
          ))}
        </div>
        <div className="h-64 bg-[#FAFAFA] rounded-2xl border border-[#E4E4E7]" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-5 min-w-0 max-w-full overflow-x-hidden" data-testid="intent-dashboard">
      <AdminPageHeader
        icon={ChartLineUp}
        title={t('intentDashboardTitle')}
        subtitle={t('intentDashboardSubtitle')}
        testId="intent-header"
        actions={(
          <RefreshButton
            onClick={fetchData}
            ariaLabel={t('adm_refresh_3') || t('refresh') || 'Refresh'}
            testId="intent-refresh"
          />
        )}
      />

      {/* Stats Cards — 2x2 mobile / 4 col desktop, monochrome */}
      {analytics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatCard icon={Fire}           label={t('hotLeads')}            value={analytics.levels?.hot ?? 0}  tint="rose"  testId="stat-hot"  />
          <StatCard icon={ThermometerHot} label={t('warmUsers')}           value={analytics.levels?.warm ?? 0} tint="amber" testId="stat-warm" />
          <StatCard icon={Snowflake}      label={t('coldUsers')}           value={analytics.levels?.cold ?? 0} tint="blue"  testId="stat-cold" />
          <StatCard icon={Lightning}      label={t('autoLeads')}           value={analytics.autoLeadsCreated || 0} tint="muted" testId="stat-autoleads" />
        </div>
      )}

      {/* Additional Stats */}
      {analytics && (
        <div className="grid grid-cols-2 gap-3 sm:gap-4">
          <StatCard label={t('totalUsersWithIntent')} value={analytics.total ?? 0}                     tint="muted" />
          <StatCard label={t('averageScore')}         value={(analytics.avgScore ?? 0).toFixed(1)}     tint="muted" />
        </div>
      )}

      {/* HOT Leads Section */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden min-w-0">
        <div className="px-4 sm:px-5 py-3 sm:py-3.5 border-b border-[#E4E4E7] flex items-center gap-2">
          <Fire size={16} weight="fill" className="text-rose-500 flex-shrink-0" />
          <h2 className="text-[14px] sm:text-[15px] font-semibold text-[#18181B] truncate">
            {t('adm_hot_leads_urgent')}
          </h2>
          <span className="ml-auto px-2 py-0.5 bg-[#F4F4F5] text-[#3F3F46] text-[12px] font-bold rounded-full flex-shrink-0">
            {hotLeads.length}
          </span>
        </div>

        {hotLeads.length === 0 ? (
          <div className="p-6 sm:p-8 text-center text-[#71717A]" data-testid="no-hot-leads">
            <Fire size={36} className="mx-auto text-[#D4D4D8] mb-2" />
            <p className="text-[14px] font-medium text-[#3F3F46]">{t('adm_no_hot_leads')}</p>
            <p className="text-[12.5px] mt-1">{t('adm_users_gain_score_through_favorites_compare_history')}</p>
          </div>
        ) : (
          <div className="divide-y divide-[#F4F4F5]">
            {hotLeads.map((lead, idx) => (
              <motion.div
                key={lead.userId}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.04 }}
                className="p-3 sm:p-4 hover:bg-[#FAFAFA] transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center gap-3 min-w-0">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="w-9 h-9 rounded-full bg-[#F4F4F5] flex items-center justify-center flex-shrink-0">
                      <Fire size={16} weight="fill" className="text-rose-500" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] sm:text-sm font-semibold text-[#18181B] truncate">
                        {lead.context?.name || `User ${lead.userId.substring(0, 8)}`}
                      </div>
                      <div className="text-[11.5px] sm:text-xs text-[#71717A] truncate">
                        {lead.context?.email || lead.context?.phone || lead.userId}
                      </div>
                    </div>
                    {getIntentBadge(lead.level, lead.score)}
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="hidden sm:block text-right text-[11px] text-[#71717A]">
                      <div>♥ {lead.favoritesCount} • ⚖ {lead.comparesCount} • 📋 {lead.historyRequestsCount}</div>
                      <div className="text-[#A1A1AA]">
                        {lead.lastActivityAt && new Date(lead.lastActivityAt).toLocaleString(getLocale())}
                      </div>
                    </div>

                    <IconBtn
                      onClick={() => { setSelectedUser(lead); setShowAIPanel(true); }}
                      title={t('adm_ai_recommendation')}
                      testId={`ai-btn-${lead.userId}`}
                    >
                      <Robot size={14} weight="bold" />
                    </IconBtn>

                    <IconBtn
                      onClick={() => markNotified(lead.userId)}
                      title={lead.managerNotified ? t('adm3_a09359ab42') : t('adm3_2c812dc8ac')}
                      active={lead.managerNotified}
                    >
                      <Phone size={14} weight={lead.managerNotified ? 'fill' : 'bold'} />
                    </IconBtn>
                  </div>
                </div>

                {(lead.context?.favoriteVins?.length > 0 || lead.context?.compareVins?.length > 0) && (
                  <div className="mt-2 ml-12 text-[11.5px] text-[#71717A] truncate">
                    {lead.context.favoriteVins?.length > 0 && (
                      <span className="mr-3">Favorites: {lead.context.favoriteVins.slice(0, 2).join(', ')}</span>
                    )}
                    {lead.context.compareVins?.length > 0 && (
                      <span>Compare: {lead.context.compareVins.slice(0, 2).join(', ')}</span>
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* All Users Table */}
      <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden min-w-0">
        <div className="px-4 sm:px-5 py-3 sm:py-3.5 border-b border-[#E4E4E7] flex items-center gap-2">
          <Users size={16} className="text-[#71717A] flex-shrink-0" />
          <h2 className="text-[14px] sm:text-[15px] font-semibold text-[#18181B]">
            {t('adm_all_users_with_intent_score')}
          </h2>
        </div>

        {allScores.length === 0 ? (
          <div className="p-6 sm:p-8 text-center text-[#71717A]">
            <Users size={36} className="mx-auto text-[#D4D4D8] mb-2" />
            <p className="text-[13px]">{t('adm_no_data_2')}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-[13px]" data-testid="intent-scores-table">
              <thead className="bg-[#FAFAFA]">
                <tr>
                  <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">{t('adm_user')}</th>
                  <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">{t('adm_intent')}</th>
                  <th className="px-3 py-2.5 text-center text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">♥</th>
                  <th className="px-3 py-2.5 text-center text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">⚖</th>
                  <th className="px-3 py-2.5 text-center text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">📋</th>
                  <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">{t('adm_last_activity')}</th>
                  <th className="px-3 py-2.5 text-right text-[11px] font-semibold text-[#71717A] uppercase tracking-wide">{t('adm_actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F4F4F5]">
                {allScores.map((score) => (
                  <tr key={score.userId} className="hover:bg-[#FAFAFA]">
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <div className="font-medium text-[#18181B] truncate max-w-[180px]">
                        {score.context?.name || score.userId.substring(0, 12)}
                      </div>
                      <div className="text-[11.5px] text-[#71717A] truncate max-w-[180px]">
                        {score.context?.email || '—'}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">{getIntentBadge(score.level, score.score)}</td>
                    <td className="px-3 py-2.5 text-center">{score.favoritesCount || 0}</td>
                    <td className="px-3 py-2.5 text-center">{score.comparesCount || 0}</td>
                    <td className="px-3 py-2.5 text-center">{score.historyRequestsCount || 0}</td>
                    <td className="px-3 py-2.5 text-[#71717A] whitespace-nowrap">
                      {score.lastActivityAt ? new Date(score.lastActivityAt).toLocaleDateString(getLocale()) : '—'}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <IconBtn
                        onClick={() => { setSelectedUser(score); setShowAIPanel(true); }}
                        title={t('adm_ai_recommendation')}
                      >
                        <Robot size={14} />
                      </IconBtn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* AI Panel Slide-over */}
      {showAIPanel && selectedUser && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowAIPanel(false)} />
          <div className="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-xl">
            <div className="p-4 border-b border-[#E4E4E7] flex items-center justify-between">
              <h3 className="font-semibold text-[#18181B]">{t('adm_ai_recommendation')}</h3>
              <button
                onClick={() => setShowAIPanel(false)}
                className="text-[#71717A] hover:text-[#18181B] text-lg leading-none"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="p-4 overflow-y-auto h-[calc(100%-60px)]">
              <div className="mb-4">
                <div className="text-[12px] text-[#71717A]">{t('adm_user_2')}</div>
                <div className="font-medium text-[#18181B]">{selectedUser.context?.name || selectedUser.userId}</div>
                <div className="mt-1">{getIntentBadge(selectedUser.level, selectedUser.score)}</div>
              </div>
              <ManagerAIWidget userId={selectedUser.userId} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ───────────────────────────────────────────────────────────────────────
// Monochrome KPI tile — replaces the old rainbow `StatCard`.
//   • White card, gray border (no coloured wash on the whole box).
//   • Icon is muted gray; only an optional tiny status dot keeps a tint.
//   • Value is the dominant element, rendered in admin-dark `#18181B`.
// ───────────────────────────────────────────────────────────────────────
const TINT = {
  rose:  'text-rose-500',
  amber: 'text-amber-500',
  blue:  'text-blue-500',
  muted: 'text-[#A1A1AA]',
};

const StatCard = ({ icon: Icon, label, value, tint = 'muted', testId }) => (
  <div
    className="bg-white border border-[#E4E4E7] rounded-2xl p-3 sm:p-4 min-w-0 overflow-hidden hover:border-[#D4D4D8] transition-colors"
    data-testid={testId}
  >
    <div className="flex items-center justify-between gap-2 mb-1.5">
      <span className="text-[10.5px] sm:text-[11px] font-semibold uppercase tracking-[0.10em] text-[#71717A] truncate">
        {label}
      </span>
      {Icon && <Icon size={14} weight="bold" className={`${TINT[tint] || TINT.muted} flex-shrink-0`} />}
    </div>
    <div className="text-[22px] sm:text-[26px] font-semibold tabular-nums leading-tight text-[#18181B] truncate" title={String(value)}>
      {value}
    </div>
  </div>
);

// Small neutral icon-only button used for row-level actions.
const IconBtn = ({ children, active = false, onClick, title, testId }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    data-testid={testId}
    className={`inline-flex items-center justify-center w-8 h-8 rounded-lg border transition-colors ${
      active
        ? 'bg-[#18181B] text-white border-[#18181B]'
        : 'bg-white text-[#52525B] border-[#E4E4E7] hover:bg-[#FAFAFA] hover:border-[#D4D4D8]'
    }`}
  >
    {children}
  </button>
);

export default IntentDashboard;
