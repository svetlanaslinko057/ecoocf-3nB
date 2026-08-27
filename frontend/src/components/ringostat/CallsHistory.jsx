/**
 * CallsHistory Component
 * Отображает историю звонков для лида
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed, Play, Clock, User } from 'lucide-react';
import { useLang, getLocale } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const CallsHistory = ({ leadId }) => {
  const { t } = useLang();
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (leadId) {
      loadCalls();
    }
  }, [leadId]);

  const loadCalls = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/leads/${leadId}/calls`);
      if (response.data.success) {
        setCalls(response.data.calls);
      }
    } catch (error) {
      console.error('Failed to load calls:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds || seconds === 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString(getLocale(), {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status) => {
    switch (status?.toUpperCase()) {
      case 'ANSWERED':
        return 'text-green-600 bg-green-50';
      case 'MISSED':
        return 'text-red-600 bg-red-50';
      case 'VOICEMAIL':
        return 'text-yellow-600 bg-yellow-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const getDirectionIcon = (direction, status) => {
    if (status?.toUpperCase() === 'MISSED') {
      return <PhoneMissed className="w-4 h-4" />;
    }
    return direction === 'inbound' ? 
      <PhoneIncoming className="w-4 h-4" /> : 
      <PhoneOutgoing className="w-4 h-4" />;
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Phone className="w-5 h-5 text-gray-400" />
          <h3 className="font-semibold text-gray-900">{t('cmp_calls')}</h3>
        </div>
        <div className="text-sm text-gray-500">{t('cmp_loading_3')}</div>
      </div>
    );
  }

  if (calls.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Phone className="w-5 h-5 text-gray-400" />
          <h3 className="font-semibold text-gray-900">{t('cmp_calls')}</h3>
        </div>
        <div className="text-sm text-gray-500">{t('cmp_no_calls')}</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center gap-2 mb-4">
        <Phone className="w-5 h-5 text-gray-600" />
        <h3 className="font-semibold text-gray-900">{t('cmp_calls')}</h3>
        <span className="ml-auto text-sm text-gray-500">{calls.length}</span>
      </div>

      <div className="space-y-3">
        {calls.map((call) => (
          <div
            key={call._id}
            className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div className={`p-2 rounded-lg ${getStatusColor(call.status)}`}>
              {getDirectionIcon(call.direction, call.status)}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-gray-900">
                  {call.direction === 'inbound' ? t('adm3_7ab4e464a6') : t('adm3_ea4d2f8efc')}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(call.status)}`}>
                  {call.status === 'ANSWERED' ? t('adm3_0b9dcbb736') : 
                   call.status === 'MISSED' ? t('adm3_4d35c798a2') : 
                   call.status}
                </span>
              </div>

              <div className="flex items-center gap-3 text-xs text-gray-600">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatTime(call.started_at)}
                </span>
                {call.duration > 0 && (
                  <span className="flex items-center gap-1">
                    <Phone className="w-3 h-3" />
                    {formatDuration(call.duration)}
                  </span>
                )}
                {call.utm_source && (
                  <span className="text-blue-600">
                    {call.utm_source}
                  </span>
                )}
              </div>

              {call.outcome_note && (
                <div className="mt-2 text-xs text-gray-600 bg-white p-2 rounded">
                  {call.outcome_note}
                </div>
              )}
            </div>

            {call.recording_url && (
              <button
                onClick={() => window.open(call.recording_url, '_blank')}
                className="p-2 rounded-lg hover:bg-white text-blue-600 hover:text-blue-700 transition-colors"
                title={t('cmp_listen_to_recording')}
              >
                <Play className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default CallsHistory;
