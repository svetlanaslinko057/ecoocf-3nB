/**
 * Call Board Page
 * 
 * /admin/call-board
 * 
 * - Call session management
 * - Status pipeline (new → no_answer → callback → interested → deal)
 * - Next action scheduling
 * - Call board view
 * - Due actions reminders
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { useLang } from '../../i18n';
import { 
  Phone, 
  PhoneIncoming,
  PhoneOutgoing,
  PhoneX,
  Clock,
  User,
  Calendar,
  ArrowRight,
  Fire,
  CheckCircle,
  Warning,
  Handshake,
  ChatCircle,
  Timer,
  Target
} from '@phosphor-icons/react';
import { toast } from 'sonner';
import WhiteSelect from '../../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Status config
const CALL_STATUSES = {
  new: { label: 'New', color: 'zinc', icon: PhoneOutgoing },
  no_answer: { label: 'No answer', color: 'amber', icon: PhoneX },
  callback: { label: 'Call Back', color: 'blue', icon: PhoneIncoming },
  interested: { label: 'Interested', color: 'emerald', icon: ChatCircle },
  thinking: { label: 'Thinking', color: 'violet', icon: Timer },
  negotiation: { label: 'Negotiations', color: 'orange', icon: Target },
  deal: { label: 'adm_deal_4', color: 'green', icon: Handshake },
  rejected: { label: 'Refusal', color: 'red', icon: PhoneX },
};

// Call Session Card
const CallCard = ({ session, onUpdateStatus, onScheduleCallback, loading }) => {
  const { t } = useLang();
  const status = CALL_STATUSES[session.status] || CALL_STATUSES.new;
  const StatusIcon = status.icon;
  const isOverdue = session.nextActionAt && new Date(session.nextActionAt) < new Date();
  const isHot = session.leadIntent === 'hot';

  return (
    <div className={`bg-white rounded-xl border p-4 hover:shadow-md transition-all
      ${isOverdue ? 'border-red-200 bg-red-50/30' : 
        isHot ? 'border-amber-200' : 'border-zinc-200'}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-${status.color}-100`}>
            <StatusIcon size={20} className={`text-${status.color}-600`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              {session.customerId ? (
                <Link
                  to={`/admin/customers/${session.customerId}/360`}
                  className="font-semibold text-zinc-900 hover:text-[#4F46E5] hover:underline"
                  data-testid={`callboard-customer-link-${session.id}`}
                >
                  {session.customerName || t('adm3_313ec9c7c2')}
                </Link>
              ) : (
                <h3 className="font-semibold text-zinc-900">{session.customerName || t('adm3_313ec9c7c2')}</h3>
              )}
              {isHot && (
                <Fire size={16} className="text-red-500" weight="fill" />
              )}
            </div>
            <p className="text-sm text-zinc-500">{session.phone || session.leadId}</p>
          </div>
        </div>

        <span className={`px-2 py-1 rounded-full text-xs font-medium bg-${status.color}-100 text-${status.color}-700`}>
          {status.label}
        </span>
      </div>

      {/* VIN & Vehicle */}
      {session.vin && (
        <div className="mb-3 p-2 rounded-lg bg-zinc-50 font-mono text-sm text-zinc-600">
          VIN: {session.vin}
        </div>
      )}

      {/* Call Stats */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center p-2 rounded-lg bg-zinc-50">
          <p className="text-lg font-bold text-zinc-900">{session.callAttempts || 0}</p>
          <p className="text-xs text-zinc-500">{t('adm_attempts')}</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-zinc-50">
          <p className="text-lg font-bold text-zinc-900">
            {session.totalCallDuration ? Math.floor(session.totalCallDuration / 60) : 0}
          </p>
          <p className="text-xs text-zinc-500">{t('adm_minutes')}</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-zinc-50">
          <p className="text-lg font-bold text-zinc-900">{session.notesCount || 0}</p>
          <p className="text-xs text-zinc-500">{t('adm_notes_2')}</p>
        </div>
      </div>

      {/* Next Action */}
      {session.nextActionAt && (
        <div className={`mb-3 p-2 rounded-lg flex items-center gap-2 text-sm
          ${isOverdue ? 'bg-red-100 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
          <Clock size={16} />
          <span>
            {isOverdue ? t('adm3_19c2985089') : t('adm3_34df85665b')}
            {new Date(session.nextActionAt).toLocaleString('uk')}
          </span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-zinc-100">
        {session.status !== 'deal' && session.status !== 'rejected' && (
          <>
            <WhiteSelect onChange={(e) => onUpdateStatus(session.id, e.target.value)} value="" disabled={loading} className="flex-1" data-testid={`status-select-${session.id}`}>
              <option value="" disabled>{t('adm_change_status')}</option>
              {Object.entries(CALL_STATUSES).map(([key, val]) => (
                <option key={key} value={key}>{val.label}</option>
              ))}
            </WhiteSelect>

            <button
              onClick={() => onScheduleCallback(session.id)}
              disabled={loading}
              className="p-2 rounded-lg border border-zinc-200 text-zinc-600 
                         hover:bg-blue-50 hover:border-blue-200 hover:text-blue-600 
                         transition-colors disabled:opacity-50"
              title={t('adm_schedule_a_callback')}
              data-testid={`schedule-callback-${session.id}`}
            >
              <Calendar size={20} />
            </button>

            <button
              disabled={loading}
              className="p-2 rounded-lg bg-emerald-600 text-white 
                         hover:bg-emerald-700 transition-colors disabled:opacity-50"
              title={t('adm_call_2')}
              data-testid={`call-${session.id}`}
            >
              <Phone size={20} />
            </button>
          </>
        )}

        {session.status === 'deal' && (
          <div className="flex-1 text-center text-emerald-600 font-medium">
            <CheckCircle size={20} className="inline mr-2" weight="fill" />
            {t('adm_deal_closed')}
          </div>
        )}
      </div>

      {/* Last Note */}
      {session.lastNote && (
        <div className="mt-3 pt-3 border-t border-zinc-100 text-sm text-zinc-500">
          <p className="italic">"{session.lastNote}"</p>
        </div>
      )}
    </div>
  );
};

// Stats Card
const StatCard = ({ icon: Icon, title, value, color = 'zinc' }) => (
  <div className="bg-white rounded-xl border border-zinc-200 p-4 flex items-center gap-3">
    <div className={`p-2 rounded-lg bg-${color}-100`}>
      <Icon size={20} className={`text-${color}-600`} />
    </div>
    <div>
      <p className="text-2xl font-bold text-zinc-900">{value}</p>
      <p className="text-sm text-zinc-500">{title}</p>
    </div>
  </div>
);

export default function CallBoardPage() {
  const { t } = useLang();
  const [sessions, setSessions] = useState([]);
  const [dueActions, setDueActions] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [filter, setFilter] = useState('all'); // all, due, hot

  useEffect(() => {
    loadData();
    // Auto-refresh every 60 seconds
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [boardRes, dueRes, statsRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/call-flow/board`),
        axios.get(`${API_URL}/api/admin/call-flow/due`),
        axios.get(`${API_URL}/api/admin/call-flow/stats`),
      ]);

      // Ensure we always set arrays, even if API returns error objects
      setSessions(Array.isArray(boardRes.data) ? boardRes.data : []);
      setDueActions(Array.isArray(dueRes.data) ? dueRes.data : []);
      setStats(statsRes.data || {});
    } catch (err) {
      console.error('Failed to load call board:', err);
      // Reset to empty arrays on error
      setSessions([]);
      setDueActions([]);
      setStats({});
      if (!sessions.length) {
        toast.error(t('loadError'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (sessionId, newStatus) => {
    setActionLoading(true);
    try {
      await axios.put(`${API_URL}/api/admin/call-flow/session/${sessionId}`, {
        status: newStatus,
      });
      toast.success(`${t('r9_status_changed_to')}"${CALL_STATUSES[newStatus]?.label}"`);
      loadData();
    } catch (err) {
      toast.error(t('adm_status_change_error'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleScheduleCallback = async (sessionId) => {
    const dateStr = prompt(t('adm3_82752e3944'));
    if (!dateStr) return;

    setActionLoading(true);
    try {
      await axios.put(`${API_URL}/api/admin/call-flow/session/${sessionId}`, {
        nextActionAt: new Date(dateStr),
        nextActionType: 'callback',
      });
      toast.success(t('adm_call_back_scheduled'));
      loadData();
    } catch (err) {
      toast.error(t('adm_scheduling_error'));
    } finally {
      setActionLoading(false);
    }
  };

  // Filter sessions
  const filteredSessions = sessions.filter(s => {
    if (filter === 'due') return dueActions.some(d => d.id === s.id);
    if (filter === 'hot') return s.leadIntent === 'hot';
    return true;
  });

  // Group by status
  const groupedByStatus = filteredSessions.reduce((acc, session) => {
    const status = session.status || 'new';
    if (!acc[status]) acc[status] = [];
    acc[status].push(session);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-zinc-900 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="call-board-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">{t('callBoard')}</h1>
          <p className="text-zinc-500">{t('callbackControl')}</p>
        </div>
        <div className="flex items-center gap-2">
          {dueActions.length > 0 && (
            <span className="px-3 py-1.5 rounded-lg bg-red-100 text-red-700 text-sm font-medium animate-pulse">
              <Warning size={16} className="inline mr-1" />
              {dueActions.length} {t('r9_overdue')}
            </span>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard icon={Phone} title={t('activeSessions')} value={stats.activeSessions || 0} color="blue" />
          <StatCard icon={Clock} title={t('adm_awaiting_call')} value={stats.pendingCalls || 0} color="amber" />
          <StatCard icon={Fire} title={t('adm_hot_leads')} value={stats.hotLeads || 0} color="red" />
          <StatCard icon={Handshake} title={t('adm_deals_today')} value={stats.dealsToday || 0} color="emerald" />
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2">
        {[
          { key: 'all', label: t('adm_all_2'), count: sessions.length },
          { key: 'due', label: t('adm_overdue_2'), count: dueActions.length },
          { key: 'hot', label: 'HOT', count: sessions.filter(s => s.leadIntent === 'hot').length },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
              ${filter === key 
                ? 'bg-zinc-900 text-white' 
                : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'}`}
          >
            {label}
            <span className="ml-2 px-1.5 py-0.5 rounded bg-white/20 text-xs">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Board - Kanban style */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Object.entries(CALL_STATUSES).map(([statusKey, statusConfig]) => {
          const statusSessions = groupedByStatus[statusKey] || [];
          if (statusSessions.length === 0 && !['new', 'callback', 'interested'].includes(statusKey)) {
            return null;
          }

          return (
            <div key={statusKey} className="space-y-3">
              {/* Column Header */}
              <div className={`flex items-center justify-between p-3 rounded-xl bg-${statusConfig.color}-100`}>
                <div className="flex items-center gap-2">
                  <statusConfig.icon size={18} className={`text-${statusConfig.color}-600`} />
                  <span className={`font-medium text-${statusConfig.color}-700`}>{statusConfig.label}</span>
                </div>
                <span className={`px-2 py-0.5 rounded-full bg-white text-xs font-medium text-${statusConfig.color}-600`}>
                  {statusSessions.length}
                </span>
              </div>

              {/* Cards */}
              <div className="space-y-3">
                {statusSessions.map(session => (
                  <CallCard
                    key={session.id}
                    session={session}
                    onUpdateStatus={handleUpdateStatus}
                    onScheduleCallback={handleScheduleCallback}
                    loading={actionLoading}
                  />
                ))}
                {statusSessions.length === 0 && (
                  <div className="p-4 rounded-xl border-2 border-dashed border-zinc-200 text-center text-zinc-400 text-sm">
                    {t('adm_no_calls')}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
