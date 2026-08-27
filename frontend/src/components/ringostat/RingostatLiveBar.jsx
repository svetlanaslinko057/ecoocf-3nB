/**
 * Ringostat Live Bar
 * 
 * Global status bar для отображения в header:
 * - Статус подключения Ringostat
 * - Активные звонки
 * - Пропущенные звонки сегодня
 * - Callbacks в очереди
 */

import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Phone, 
  PhoneMissed, 
  Calendar,
  AlertCircle
} from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useNavigate } from 'react-router-dom';
import { useLang } from '../../i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

export const RingostatLiveBar = () => {
  const { t } = useLang();
  const navigate = useNavigate();
  const { isConnected, subscribe } = useWebSocket();
  const [stats, setStats] = useState({
    status: 'offline',
    active_calls: 0,
    missed_today: 0,
    callbacks_pending: 0
  });

  // Load initial stats
  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Subscribe to real-time events
  useEffect(() => {
    const unsubIncoming = subscribe('ringostat:incoming_call', () => {
      setStats(prev => ({ ...prev, active_calls: prev.active_calls + 1 }));
      loadStats(); // Reload for accuracy
    });

    const unsubMissed = subscribe('ringostat:missed_call', () => {
      setStats(prev => ({ ...prev, missed_today: prev.missed_today + 1 }));
      loadStats();
    });

    return () => {
      unsubIncoming();
      unsubMissed();
    };
  }, [subscribe]);

  const loadStats = async () => {
    try {
      const token = localStorage.getItem('token');
      if (!token) return;

      const res = await fetch(`${BACKEND_URL}/api/admin/ringostat/health`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (res.ok) {
        const data = await res.json();
        setStats({
          status: data.connection?.status === 'connected' ? 'online' : 'offline',
          active_calls: 0, // Can be calculated from active calls in DB
          missed_today: data.unassigned?.calls_today || 0,
          callbacks_pending: 0 // Can be calculated from tasks
        });
      }
    } catch (error) {
      console.error('Failed to load Ringostat stats:', error);
    }
  };

  const getStatusColor = () => {
    if (stats.status === 'online') return 'bg-green-500';
    return 'bg-gray-400';
  };

  const hasAlerts = stats.missed_today > 0 || stats.callbacks_pending > 0;

  return (
    <div 
      className="flex items-center gap-2 sm:gap-3 px-2 sm:px-3 py-1.5 rounded-lg border bg-white hover:bg-gray-50 transition-colors cursor-pointer flex-shrink-0 whitespace-nowrap"
      onClick={() => navigate('/manager/calls')}
      data-testid="ringostat-live-bar"
      title={`Ringostat — ${stats.status}`}
    >
      {/* Status Indicator */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} data-testid="status-indicator" />
        <span className="hidden sm:inline text-sm font-medium text-gray-700">{t('cmp_ringostat')}</span>
      </div>

      {/* Stats — only show counters; hide "All clear" label on mobile */}
      <div className="flex items-center gap-2 sm:gap-3 text-sm">
        {/* Active Calls */}
        {stats.active_calls > 0 && (
          <div className="flex items-center gap-1" data-testid="active-calls">
            <Phone className="h-4 w-4 text-blue-600" />
            <span className="font-semibold text-blue-600">{stats.active_calls}</span>
          </div>
        )}

        {/* Missed Calls */}
        {stats.missed_today > 0 && (
          <div className="flex items-center gap-1" data-testid="missed-calls">
            <PhoneMissed className="h-4 w-4 text-red-600" />
            <span className="font-semibold text-red-600">{stats.missed_today}</span>
          </div>
        )}

        {/* Callbacks */}
        {stats.callbacks_pending > 0 && (
          <div className="flex items-center gap-1" data-testid="callbacks-pending">
            <Calendar className="h-4 w-4 text-amber-600" />
            <span className="font-semibold text-amber-600">{stats.callbacks_pending}</span>
          </div>
        )}

        {/* All Clear — desktop only, mobile shows just status dot */}
        {!hasAlerts && stats.active_calls === 0 && (
          <span className="hidden sm:inline text-xs text-gray-500 whitespace-nowrap">{t('cmp_all_clear')}</span>
        )}
      </div>

      {/* Alert Badge */}
      {hasAlerts && (
        <Badge className="bg-red-600 text-white" data-testid="alert-badge">
          {stats.missed_today + stats.callbacks_pending}
        </Badge>
      )}
    </div>
  );
};

export default RingostatLiveBar;
