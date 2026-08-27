/**
 * Missed Call Aggressive Alerts
 * 
 * Показывает агрессивные toast уведомления для пропущенных звонков > 5 минут
 * Toast каждые 30 секунд пока звонок не обработан
 */

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { PhoneMissed, Phone } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

export const useMissedCallAlerts = () => {
  const [missedCalls, setMissedCalls] = useState([]);
  const [lastAlertTime, setLastAlertTime] = useState({});

  useEffect(() => {
    const checkMissedCalls = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const res = await fetch(`${BACKEND_URL}/api/manager/calls/missed`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        const data = await res.json();
        if (data.calls) {
          const urgentCalls = data.calls.filter(call => {
            const minutesSince = getMinutesSinceMissed(call.started_at || call.created_at);
            return minutesSince > 5;
          });

          setMissedCalls(urgentCalls);

          // Show toast for each urgent call (if not shown recently)
          urgentCalls.forEach(call => {
            const now = Date.now();
            const lastAlert = lastAlertTime[call._id] || 0;
            
            // Show toast every 30 seconds
            if (now - lastAlert > 30000) {
              showMissedCallToast(call);
              setLastAlertTime(prev => ({ ...prev, [call._id]: now }));
            }
          });
        }
      } catch (error) {
        console.error('Failed to check missed calls:', error);
      }
    };

    // Check immediately and then every 30 seconds
    checkMissedCalls();
    const interval = setInterval(checkMissedCalls, 30000);

    return () => clearInterval(interval);
  }, [lastAlertTime]);

  const getMinutesSinceMissed = (timestamp) => {
    const now = new Date();
    const callTime = new Date(timestamp);
    return Math.floor((now - callTime) / 1000 / 60);
  };

  const showMissedCallToast = (call) => {
    const minutes = getMinutesSinceMissed(call.started_at || call.created_at);
    
    toast.error(
      <div className="flex items-center gap-3 cursor-pointer" onClick={() => handleCallBack(call)}>
        <PhoneMissed className="h-6 w-6 text-red-600 animate-pulse" />
        <div>
          <div className="font-bold text-base">🔴 Пропущений дзвінок ({minutes} хв)</div>
          <div className="text-sm">{call.lead_name || call.from}</div>
          <div className="text-xs text-red-700 font-semibold mt-1">Передзвоніть негайно!</div>
        </div>
      </div>,
      {
        duration: 10000,
        position: 'top-right',
        className: 'border-2 border-red-600 bg-red-50',
        important: true
      }
    );
  };

  const handleCallBack = (call) => {
    // Open missed calls board
    window.location.href = '/manager/calls/missed';
  };

  return { missedCallCount: missedCalls.length };
};
