/**
 * Manager Calls Page
 * Страница для менеджера с историей звонков
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed, Play, Clock, User, Filter } from 'lucide-react';

import { useLang, getLocale } from '../../i18n';
const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const ManagerCallsPage = () => {
  const { t } = useLang();
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [missedCount, setMissedCount] = useState(0);

  useEffect(() => {
    loadCalls();
  }, [activeTab]);

  const loadCalls = async () => {
    setLoading(true);
    try {
      let url = `${API_URL}/api/manager/calls/my?limit=50`;
      
      if (activeTab === 'missed') {
        url = `${API_URL}/api/manager/calls/missed`;
      } else if (activeTab === 'today') {
        url = `${API_URL}/api/manager/calls/my?limit=50`;
        // Filter today on frontend for now
      }

      const response = await axios.get(url);
      if (response.data.success) {
        let callsData = response.data.calls;
        
        // Filter today if needed
        if (activeTab === 'today') {
          const today = new Date().toDateString();
          callsData = callsData.filter(call => {
            const callDate = new Date(call.started_at).toDateString();
            return callDate === today;
          });
        }
        
        setCalls(callsData);
        
        // Count missed calls
        const missed = callsData.filter(c => c.status === 'MISSED').length;
        setMissedCount(missed);
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

  const getStatusBadge = (status) => {
    switch (status?.toUpperCase()) {
      case 'ANSWERED':
        return <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">{t('answered')}</span>;
      case 'MISSED':
        return <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700">{t('missed')}</span>;
      case 'VOICEMAIL':
        return <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-700">{t('voicemail')}</span>;
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">{status}</span>;
    }
  };

  const getDirectionIcon = (direction, status) => {
    if (status?.toUpperCase() === 'MISSED') {
      return <PhoneMissed className="w-4 h-4 text-red-600" />;
    }
    return direction === 'inbound' ? 
      <PhoneIncoming className="w-4 h-4 text-green-600" /> : 
      <PhoneOutgoing className="w-4 h-4 text-blue-600" />;
  };

  const tabs = [
    { key: 'all', label: t('callsTabAll') },
    { key: 'missed', label: `${t('callsTabMissed')}${missedCount > 0 ? ` (${missedCount})` : ''}` },
    { key: 'today', label: t('today') },
  ];

  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('callsTab')}</h1>
        <p className="text-gray-600">{t('callsHistoryDesc')}</p>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg border border-gray-200 mb-6">
        <div className="flex border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-6 py-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Calls Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">
            {t('callsLoading')}
          </div>
        ) : calls.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            {t('callsEmpty')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('time')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('phoneNumber')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('callsHeaderName')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('callsHeaderType')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('duration')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('statusGeneric')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('dealOne')}</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">{t('action')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {calls.map((call) => (
                  <tr key={call._id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {formatTime(call.started_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {call.from}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {call.lead?.name || 'Unknown'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {getDirectionIcon(call.direction, call.status)}
                        <span className="text-sm text-gray-600">
                          {call.direction === 'inbound' ? t('callsDirInbound') : t('callsDirOutbound')}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {formatDuration(call.duration)}
                    </td>
                    <td className="px-4 py-3">
                      {getStatusBadge(call.status)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {call.deal?.title || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {call.lead && (
                          <a
                            href={`/admin/leads/${call.lead_id}`}
                            className="text-sm text-blue-600 hover:text-blue-800"
                          >
                            {t('callsActionOpen')}
                          </a>
                        )}
                        {call.recording_url && (
                          <button
                            onClick={() => window.open(call.recording_url, '_blank')}
                            className="p-1 rounded hover:bg-gray-100 text-blue-600"
                            title={t('listen')}
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ManagerCallsPage;
