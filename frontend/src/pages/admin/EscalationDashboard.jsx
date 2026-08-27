import React, { useState, useEffect, useCallback } from 'react';
import { useLang } from '../../i18n';
import {
  AlertTriangle,
  Clock,
  User,
  Users,
  Crown,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronRight,
  Zap,
  Shield,
} from 'lucide-react';
import { AdminPageHeader } from '../../components/ui/AdminPagePrimitives';
import RefreshButton from '../../components/ui/RefreshButton';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Escalation level colors and icons
const LEVEL_CONFIG = {
  manager_pending: {
    color: 'bg-amber-500',
    textColor: 'text-amber-600',
    bgLight: 'bg-amber-50',
    icon: User,
    label: { uk: 'Manager', en: 'Manager', bg: 'Manager' },
  },
  teamlead_pending: {
    color: 'bg-orange-500',
    textColor: 'text-orange-600',
    bgLight: 'bg-orange-50',
    icon: Users,
    label: { uk: 'Team Lead', en: 'Team Lead', bg: 'Team Lead' },
  },
  owner_pending: {
    color: 'bg-red-500',
    textColor: 'text-red-600',
    bgLight: 'bg-red-50',
    icon: Crown,
    label: { uk: 'Owner', en: 'Owner', bg: 'Owner' },
  },
  resolved: {
    color: 'bg-green-500',
    textColor: 'text-green-600',
    bgLight: 'bg-green-50',
    icon: CheckCircle,
    label: { uk: 'Resolved', en: 'Resolved', bg: 'Resolved' },
  },
};

// Event type labels
const EVENT_LABELS = {
  'lead.hot_not_contacted': { uk: 'HOT lead without contact', en: 'HOT lead not contacted', bg: 'HOT lead without contact' },
  'invoice.overdue': { uk: 'Overdue bill', en: 'Overdue invoice', bg: 'Overdue invoice' },
  'shipment.stalled': { uk: 'Delivery stopped', en: 'Shipment stalled', bg: 'Suspended delivery' },
  'shipment.tracking_missing': { uk: 'No tracking', en: 'No tracking', bg: 'No tracking' },
  'payment.failed': { uk: 'Payment error', en: 'Payment failed', bg: 'Failed payment' },
  'staff.session_suspicious': { uk: 'Suspicious session', en: 'Suspicious session', bg: 'Suspicious session' },
};

export default function EscalationDashboard() {
  const { lang, t } = useLang();
  const [escalations, setEscalations] = useState([]);
  const [stats, setStats] = useState({
    managerPending: 0,
    teamLeadPending: 0,
    ownerPending: 0,
    resolvedToday: 0,
  });
  const [loading, setLoading] = useState(true);
  const [selectedEscalation, setSelectedEscalation] = useState(null);
  const [resolving, setResolving] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };

      const [escRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/escalations`, { headers }),
        fetch(`${API_URL}/api/escalations/stats`, { headers }),
      ]);

      const escData = await escRes.json();
      const statsData = await statsRes.json();

      setEscalations(Array.isArray(escData) ? escData : escData.escalations || []);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to fetch escalations:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleResolve = async (escalation) => {
    setResolving(true);
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/escalations/${escalation._id}/resolve`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          eventType: escalation.eventType,
          entityId: escalation.entityId,
          reason: 'resolved_from_dashboard',
        }),
      });
      await fetchData();
      setSelectedEscalation(null);
    } catch (error) {
      console.error('Failed to resolve:', error);
    } finally {
      setResolving(false);
    }
  };

  const triggerManualProcess = async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/api/escalations/process`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchData();
    } catch (error) {
      console.error('Failed to trigger processing:', error);
    }
  };

  const getTimeRemaining = (deadline) => {
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const diff = deadlineDate - now;
    
    if (diff <= 0) return { text: t('adm2_a764e0f0d7'), isOverdue: true };
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return { text: `${hours}${t('r9_h')} ${minutes % 60}${t('r9_min')}`, isOverdue: false };
    }
    return { text: `${minutes}${t('r9_min')}`, isOverdue: false };
  };

  const getEventLabel = (eventType) => {
    return EVENT_LABELS[eventType]?.[lang] || eventType;
  };

  const totalActive = stats.managerPending + stats.teamLeadPending + stats.ownerPending;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-5" data-testid="escalation-dashboard">
      <AdminPageHeader
        icon={Zap}
        title={lang === 'uk' ? t('adm2_e8eddbb096') : 'Escalations'}
        subtitle={lang === 'uk' ? t('adm2_7e27d05d7e') : 'Team reaction control'}
        testId="escalation-header"
        actions={(
          <RefreshButton
            onClick={triggerManualProcess}
            ariaLabel={lang === 'uk' ? t('adm2_b6bf91f845') : 'Refresh'}
            testId="escalation-refresh-btn"
          />
        )}
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-3">
        <StatsCard
          title={lang === 'uk' ? t('adm2_d2ae4c4732') : 'Manager'}
          count={stats.managerPending}
          color="amber"
          icon={User}
        />
        <StatsCard
          title={t('roleTeamLead')}
          count={stats.teamLeadPending}
          color="orange"
          icon={Users}
        />
        <StatsCard
          title={t('ownerLabel')}
          count={stats.ownerPending}
          color="red"
          icon={Crown}
        />
        <StatsCard
          title={lang === 'uk' ? t('adm2_679ef5e260') : 'Resolved Today'}
          count={stats.resolvedToday}
          color="green"
          icon={CheckCircle}
        />
      </div>

      {/* Active Escalations List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            {lang === 'uk' ? t('adm2_fd3f2f0a6b') : 'Active Escalations'}
            {totalActive > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs font-bold bg-red-100 text-red-600 rounded-full">
                {totalActive}
              </span>
            )}
          </h2>
        </div>

        {escalations.length === 0 ? (
          <div className="p-8 text-center">
            <Shield className="w-12 h-12 text-green-400 mx-auto mb-3" />
            <p className="text-gray-600">
              {lang === 'uk' ? t('adm2_b9bfdf5dc7') : 'No active escalations'}
            </p>
            <p className="text-sm text-gray-400 mt-1">
              {lang === 'uk' ? t('adm2_ea5a84e7e4') : 'Team is responding on time'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {escalations.map((esc) => {
              const levelConfig = LEVEL_CONFIG[esc.status] || LEVEL_CONFIG.manager_pending;
              const LevelIcon = levelConfig.icon;
              const deadline = esc.status === 'manager_pending' 
                ? esc.managerDeadlineAt 
                : esc.teamLeadDeadlineAt;
              const timeInfo = getTimeRemaining(deadline);

              return (
                <div
                  key={esc._id}
                  className={`p-4 hover:bg-gray-50 cursor-pointer transition ${
                    selectedEscalation?._id === esc._id ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => setSelectedEscalation(esc)}
                  data-testid={`escalation-item-${esc._id}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      {/* Level indicator */}
                      <div className={`p-2 rounded-lg ${levelConfig.bgLight}`}>
                        <LevelIcon className={`w-5 h-5 ${levelConfig.textColor}`} />
                      </div>

                      {/* Event info */}
                      <div>
                        <div className="font-medium text-gray-900">
                          {getEventLabel(esc.eventType)}
                        </div>
                        <div className="text-sm text-gray-500 flex items-center gap-2">
                          <span>{esc.entityType}: {esc.entityId?.slice(0, 8)}...</span>
                          <span className={`px-2 py-0.5 rounded-full text-xs ${levelConfig.bgLight} ${levelConfig.textColor}`}>
                            {levelConfig.label[lang] || levelConfig.label.en}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Time remaining */}
                    <div className="flex items-center gap-4">
                      <div className={`flex items-center gap-1 ${timeInfo.isOverdue ? 'text-red-600 font-bold' : 'text-gray-600'}`}>
                        <Clock className="w-4 h-4" />
                        <span className="text-sm">{timeInfo.text}</span>
                      </div>
                      <ChevronRight className="w-5 h-5 text-gray-400" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedEscalation && (
        <EscalationModal
          escalation={selectedEscalation}
          lang={lang}
          onClose={() => setSelectedEscalation(null)}
          onResolve={() => handleResolve(selectedEscalation)}
          resolving={resolving}
          getEventLabel={getEventLabel}
          getTimeRemaining={getTimeRemaining}
        />
      )}
    </div>
  );
}

function StatsCard({ title, count, color, icon: Icon }) {
  const colorClasses = {
    amber: { bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-200' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-200' },
    red: { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-200' },
    green: { bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-200' },
  };

  const c = colorClasses[color];

  return (
    <div className={`p-4 rounded-xl border ${c.border} ${c.bg}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className={`text-3xl font-bold ${c.text}`}>{count}</p>
        </div>
        <div className={`p-3 rounded-lg bg-white/50`}>
          <Icon className={`w-6 h-6 ${c.text}`} />
        </div>
      </div>
    </div>
  );
}

function EscalationModal({ escalation, lang, onClose, onResolve, resolving, getEventLabel, getTimeRemaining }) {
  const { t } = useLang();
  const levelConfig = LEVEL_CONFIG[escalation.status] || LEVEL_CONFIG.manager_pending;
  const deadline = escalation.status === 'manager_pending' 
    ? escalation.managerDeadlineAt 
    : escalation.teamLeadDeadlineAt;
  const timeInfo = getTimeRemaining(deadline);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`p-4 ${levelConfig.bgLight} border-b`}>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <AlertTriangle className={`w-5 h-5 ${levelConfig.textColor}`} />
              {getEventLabel(escalation.eventType)}
            </h3>
            <button onClick={onClose} className="p-1 hover:bg-white/50 rounded">
              <XCircle className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">
                {lang === 'uk' ? t('adm2_e56fb37394') : 'Level'}
              </p>
              <p className={`font-medium ${levelConfig.textColor}`}>
                {levelConfig.label[lang] || levelConfig.label.en}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">
                {lang === 'uk' ? t('adm2_9aca4fb736') : 'Time'}
              </p>
              <p className={`font-medium ${timeInfo.isOverdue ? 'text-red-600' : 'text-gray-900'}`}>
                {timeInfo.text}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">
                {lang === 'uk' ? t('adm2_da449adf59') : 'Entity Type'}
              </p>
              <p className="font-medium text-gray-900">{escalation.entityType}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">ID</p>
              <p className="font-medium text-gray-900 font-mono text-sm">
                {escalation.entityId}
              </p>
            </div>
          </div>

          {/* Timeline */}
          <div className="border-t pt-4">
            <p className="text-sm text-gray-500 mb-2">
              {lang === 'uk' ? t('adm2_a494b56ec9') : 'Timeline'}
            </p>
            <div className="space-y-2">
              <TimelineItem
                label={lang === 'uk' ? t('adm2_6268a9fafc') : 'Created'}
                time={new Date(escalation.createdAt).toLocaleString()}
                done
              />
              <TimelineItem
                label={lang === 'uk' ? t('adm2_f9c9a5d595') : 'Manager deadline'}
                time={new Date(escalation.managerDeadlineAt).toLocaleString()}
                done={escalation.escalationLevel >= 1}
              />
              {escalation.teamLeadDeadlineAt && (
                <TimelineItem
                  label={lang === 'uk' ? t('adm2_team_lead_bef00fddc8') : 'Team Lead deadline'}
                  time={new Date(escalation.teamLeadDeadlineAt).toLocaleString()}
                  done={escalation.escalationLevel >= 2}
                />
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="p-4 bg-gray-50 border-t flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            {lang === 'uk' ? t('adm2_41a707dea9') : 'Close'}
          </button>
          <button
            onClick={onResolve}
            disabled={resolving}
            className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {resolving ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <CheckCircle className="w-4 h-4" />
            )}
            {lang === 'uk' ? t('adm2_c946efa988') : 'Resolve'}
          </button>
        </div>
      </div>
    </div>
  );
}

function TimelineItem({ label, time, done }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-2 h-2 rounded-full ${done ? 'bg-green-500' : 'bg-gray-300'}`} />
      <div className="flex-1 flex justify-between">
        <span className="text-sm text-gray-600">{label}</span>
        <span className="text-sm text-gray-400">{time}</span>
      </div>
    </div>
  );
}
