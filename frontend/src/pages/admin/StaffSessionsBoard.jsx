/**
 * Staff Sessions Board
 * 
 * /admin/staff-sessions
 * 
 * - Хто зараз онлайн
 * - Хто коли зайшов
 * - З якого IP/device
 * - Тривалість сесії
 * - Підозрілі входи
 * - Force logout
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useLang } from '../../i18n';
import RefreshButton from '../../components/ui/RefreshButton';
import { 
  User, 
  SignOut, 
  ShieldWarning, 
  Globe,
  DeviceMobile,
  Clock,
  CheckCircle,
  XCircle,
  Warning,
  ArrowClockwise,
  ArrowLeft,
  Eye,
  LockKey
} from '@phosphor-icons/react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Session Card
const SessionCard = ({ session, onForceLogout, loading }) => {
  const { t } = useLang();
  const isActive = session.status === 'active';
  const startTime = new Date(session.startedAt);
  const lastSeen = session.lastSeenAt ? new Date(session.lastSeenAt) : startTime;
  const duration = Math.round((lastSeen - startTime) / 1000 / 60);

  return (
    <div className={`bg-white rounded-xl border p-4 transition-all hover:shadow-md
      ${session.isSuspicious ? 'border-red-200 bg-red-50/30' : 
        session.isNewDevice ? 'border-amber-200' : 'border-zinc-200'}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold
            ${session.role === 'team_lead' ? 'bg-blue-600' : 'bg-zinc-600'}`}>
            {session.email?.charAt(0).toUpperCase() || 'U'}
          </div>

          <div>
            {/* User Info */}
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-zinc-900">{session.email}</h3>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase
                ${session.role === 'team_lead' ? 'bg-blue-100 text-blue-700' : 
                  'bg-zinc-100 text-zinc-600'}`}>
                {session.role}
              </span>
            </div>

            {/* Status */}
            <div className="flex items-center gap-3 mt-1 text-sm text-zinc-500">
              <span className="flex items-center gap-1">
                {isActive ? (
                  <CheckCircle size={14} className="text-emerald-500" weight="fill" />
                ) : (
                  <XCircle size={14} className="text-zinc-400" weight="fill" />
                )}
                {isActive ? t('adm2_e10cee7357') : session.status}
              </span>
              <span className="flex items-center gap-1">
                <Clock size={14} />
                {duration} {t('r9_min_short')}
              </span>
            </div>

            {/* Device & IP */}
            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-zinc-400">
              {session.ipAddress && (
                <span className="flex items-center gap-1">
                  <Globe size={12} />
                  {session.ipAddress}
                </span>
              )}
              {session.deviceId && (
                <span className="flex items-center gap-1">
                  <DeviceMobile size={12} />
                  {session.deviceId.slice(0, 8)}...
                </span>
              )}
            </div>

            {/* Flags */}
            <div className="flex items-center gap-2 mt-2">
              {session.twoFactorVerified && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 text-xs">
                  <LockKey size={12} />
                  {t('adm_2fa')}
                </span>
              )}
              {session.isNewDevice && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-100 text-amber-700 text-xs">
                  <DeviceMobile size={12} />
                  {t('adm_new_device')}
                </span>
              )}
              {session.isUnusualLocation && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-orange-100 text-orange-700 text-xs">
                  <Globe size={12} />
                  {t('adm_unusual_ip')}
                </span>
              )}
              {session.isSuspicious && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs">
                  <ShieldWarning size={12} />
                  {t('adm_suspicious_2')}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        {isActive && (
          <button
            onClick={() => onForceLogout(session.id, session.email)}
            disabled={loading}
            className="p-2 rounded-lg border border-zinc-200 text-zinc-600 hover:bg-red-50 
                       hover:border-red-200 hover:text-red-600 transition-colors disabled:opacity-50"
            data-testid={`force-logout-${session.id}`}
            title={t('forceLogout')}
          >
            <SignOut size={20} />
          </button>
        )}
      </div>

      {/* Suspicious Reason */}
      {session.suspiciousReason && (
        <div className="mt-3 p-2 rounded bg-red-50 border border-red-100 text-sm text-red-700">
          <Warning size={14} className="inline mr-1" />
          {session.suspiciousReason}
        </div>
      )}

      {/* Session Times */}
      <div className="mt-3 pt-3 border-t border-zinc-100 flex items-center justify-between text-xs text-zinc-400">
        <span>{t('adm3_e0bf555325')} {startTime.toLocaleString('uk')}</span>
        <span>{t('adm3_834bfce4ba')} {lastSeen.toLocaleString('uk')}</span>
      </div>
    </div>
  );
};

// Analytics Card
const AnalyticsCard = ({ title, value, subtitle, icon: Icon, color = 'zinc' }) => (
  <div className="bg-white rounded-xl border border-zinc-200 p-4">
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg bg-${color}-100`}>
        <Icon size={20} className={`text-${color}-600`} />
      </div>
      <div>
        <p className="text-2xl font-bold text-zinc-900">{value}</p>
        <p className="text-sm text-zinc-500">{title}</p>
        {subtitle && <p className="text-xs text-zinc-400">{subtitle}</p>}
      </div>
    </div>
  </div>
);

export default function StaffSessionsBoard() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [suspiciousSessions, setSuspiciousSessions] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [filter, setFilter] = useState('active'); // active, suspicious, all

  useEffect(() => {
    loadData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [sessionsRes, suspiciousRes, analyticsRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/staff-sessions/active`),
        axios.get(`${API_URL}/api/admin/staff-sessions/suspicious`),
        axios.get(`${API_URL}/api/admin/staff-sessions/analytics`),
      ]);

      setSessions(Array.isArray(sessionsRes.data) ? sessionsRes.data : []);
      setSuspiciousSessions(Array.isArray(suspiciousRes.data) ? suspiciousRes.data : []);
      setAnalytics(analyticsRes.data || {});
    } catch (err) {
      console.error('Failed to load sessions:', err);
      // Don't show error on auto-refresh failures
      if (!sessions.length) {
        toast.error(t('adm_session_loading_error'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleForceLogout = async (sessionId, email) => {
    if (!confirm(`${t('r9_force_end_session_for')} ${email}?`)) return;
    
    setActionLoading(true);
    try {
      await axios.post(`${API_URL}/api/admin/staff-sessions/force-logout/${sessionId}`, {
        reason: t('adm2_50887229d0')
      });
      toast.success(`${t('r9_session')} ${email} ${t('r9_ended')}`);
      loadData();
    } catch (err) {
      toast.error(t('adm_session_termination_error'));
    } finally {
      setActionLoading(false);
    }
  };

  const filteredSessions = filter === 'suspicious' 
    ? (Array.isArray(suspiciousSessions) ? suspiciousSessions : [])
    : filter === 'active' 
      ? (Array.isArray(sessions) ? sessions.filter(s => s && s.status === 'active') : [])
      : (Array.isArray(sessions) ? sessions : []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-zinc-900 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="staff-sessions-board">
      {/* Header — back button TOP-LEFT, refresh TOP-RIGHT (admin convention) */}
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={() => {
            // Prefer returning to the previous page (team dashboard) when present.
            // Fallback: navigate to /admin (master) or /team (team-lead) home.
            if (window.history.length > 1) {
              navigate(-1);
            } else {
              const fallback = window.location.pathname.startsWith('/team') ? '/team' : '/admin';
              navigate(fallback);
            }
          }}
          aria-label={t('back') || 'Back'}
          data-testid="staff-sessions-back-btn"
          className="inline-flex items-center justify-center w-9 h-9 rounded-xl border border-[#E4E4E7] bg-white hover:bg-[#FAFAFA] text-[#18181B] shrink-0 focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10 transition-colors"
        >
          <ArrowLeft size={16} weight="bold" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 break-words leading-tight">{t('staffSessions')}</h1>
          <p className="text-[12.5px] sm:text-sm text-zinc-500 break-words mt-1">{t('teamLoadControl')}</p>
        </div>
        <RefreshButton
          onClick={loadData}
          loading={loading}
          ariaLabel={t('refresh')}
          testId="staff-sessions-refresh-btn"
        />
      </div>

      {/* Analytics */}
      {analytics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <AnalyticsCard
            icon={User}
            title={t('activeSessions')}
            value={analytics.activeSessions}
            color="emerald"
          />
          <AnalyticsCard
            icon={ShieldWarning}
            title={t('adm_suspicious')}
            value={analytics.suspiciousSessions}
            color="red"
          />
          <AnalyticsCard
            icon={SignOut}
            title={t('adm_forced_exits')}
            value={analytics.forcedLogouts}
            subtitle={`${t('r9_for_period')} ${analytics.periodDays} ${t('r9_days_plural')}`}
            color="amber"
          />
          <AnalyticsCard
            icon={Clock}
            title={t('adm_average_duration')}
            value={`${analytics.avgDurationMinutes} ${t('r9_min_short')}`}
            color="blue"
          />
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2">
        {[
          { key: 'active', label: t('adm_active_5'), count: sessions.filter(s => s.status === 'active').length },
          { key: 'suspicious', label: t('adm_suspicious_3'), count: suspiciousSessions.length },
          { key: 'all', label: t('adm_all_2'), count: sessions.length },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
              ${filter === key 
                ? 'bg-zinc-900 text-white' 
                : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'}`}
            data-testid={`filter-${key}`}
          >
            {label}
            <span className="ml-2 px-1.5 py-0.5 rounded bg-white/20 text-xs">
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Sessions List */}
      {filteredSessions.length === 0 ? (
        <div className="bg-white rounded-2xl border border-zinc-200 p-12 text-center">
          <Eye size={48} className="mx-auto mb-4 text-zinc-300" />
          <p className="text-zinc-500">{t('adm_no_sessions_to_display')}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredSessions.map(session => (
            <SessionCard
              key={session.id}
              session={session}
              onForceLogout={handleForceLogout}
              loading={actionLoading}
            />
          ))}
        </div>
      )}
    </div>
  );
}
