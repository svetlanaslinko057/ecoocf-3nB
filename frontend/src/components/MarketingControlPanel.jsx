/**
 * Маркетинг-контроль
 * 
 * Full admin UI for marketing automation:
 * - Авто-режим
 * - Дії кампаній (Scale/Kill/Watch)
 * - Статус синхронізації
 * - Журнал рішень
 * - Історія дій
 * - ROI Tracking
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { toast } from 'sonner';
import { useLang } from '../i18n';
import WhiteSelect from '../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ==========================================
// REUSABLE COMPONENTS
// ==========================================

const StatusBadge = ({ status }) => {
  const colors = {
    scale: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    keep: 'bg-blue-100 text-blue-700 border-blue-200',
    watch: 'bg-amber-100 text-amber-700 border-amber-200',
    kill: 'bg-red-100 text-red-700 border-red-200',
    executed: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    failed: 'bg-red-100 text-red-700 border-red-200',
    pending: 'bg-amber-100 text-amber-700 border-amber-200',
  };

  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${colors[status] || colors.watch}`}>
      {status?.toUpperCase()}
    </span>
  );
};

const ActionButton = ({ onClick, variant, children, disabled, loading }) => {
  const { t } = useLang();
  const variants = {
    scale: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    kill: 'bg-red-500 hover:bg-red-600 text-white',
    watch: 'bg-amber-500 hover:bg-amber-600 text-white',
    default: 'bg-gray-500 hover:bg-gray-600 text-white',
    outline: 'border border-gray-300 hover:bg-gray-50 text-gray-700',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${variants[variant] || variants.default} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {loading ? (
        <span className="flex items-center gap-1">
          <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {t('i18n_processing_40e8d3')}
        </span>
      ) : children}
    </button>
  );
};

const Card = ({ title, children, action }) => (
  <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
    {title && (
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        {action}
      </div>
    )}
    <div className="p-6">{children}</div>
  </div>
);

const StatCard = ({ label, value, subValue, color = 'blue', icon }) => {
  const colors = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-emerald-50 text-emerald-600',
    yellow: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  };

  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 font-medium">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subValue && <p className="text-xs text-gray-400 mt-1">{subValue}</p>}
        </div>
        {icon && <div className={`p-3 rounded-lg ${colors[color]}`}>{icon}</div>}
      </div>
    </div>
  );
};

// ==========================================
// AUTO MODE CONTROL PANEL
// ==========================================

const AutoModePanel = ({ config, onUpdate, loading }) => {
  const { t } = useLang();
  const [localConfig, setLocalConfig] = useState(config);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(localConfig);
      toast.success(t('i18n_configuration_saved_ea26a4'));
    } catch (err) {
      toast.error(t('i18n_error_saving_d1b0c1'));
    }
    setSaving(false);
  };

  const handleToggle = async () => {
    const newEnabled = !localConfig.enabled;
    setLocalConfig({ ...localConfig, enabled: newEnabled });
    try {
      await onUpdate({ enabled: newEnabled });
      toast.success(newEnabled ? t('i18n_auto_mode_enabled_89ee57') : t('i18n_auto_mode_disabled_293d05'));
    } catch (err) {
      toast.error(t('i18n_error_fd7728'));
      setLocalConfig({ ...localConfig, enabled: !newEnabled });
    }
  };

  if (loading) {
    return (
      <Card title={t('i18n_auto_mode_a35d55')}>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
        </div>
      </Card>
    );
  }

  return (
    <Card title={t('i18n_auto_mode_a35d55')}>
      <div className="space-y-6">
        {/* Main Toggle */}
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
          <div>
            <p className="font-semibold text-gray-900">{t('i18n_auto_mode_a35d55')}</p>
            <p className="text-sm text-gray-500">{t('i18n_automatic_campaign_management_795ec4')}</p>
          </div>
          <button
            onClick={handleToggle}
            className={`relative w-14 h-7 rounded-full transition-colors ${localConfig.enabled ? 'bg-emerald-500' : 'bg-gray-300'}`}
          >
            <span
              className={`absolute top-1 w-5 h-5 bg-white rounded-full shadow transition-transform ${localConfig.enabled ? 'translate-x-8' : 'translate-x-1'}`}
            />
          </button>
        </div>

        {/* Status */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <p className="text-2xl font-bold text-blue-600">{config.todayActions || 0}</p>
            <p className="text-xs text-blue-600">{t('i18n_act_today_54a77b')}</p>
          </div>
          <div className="text-center p-3 bg-emerald-50 rounded-lg">
            <p className="text-2xl font-bold text-emerald-600">{config.actionsRemaining ?? config.maxActionsPerDay}</p>
            <p className="text-xs text-emerald-600">{t('i18n_remaining_efc14c')}</p>
          </div>
          <div className="text-center p-3 bg-amber-50 rounded-lg">
            <p className="text-2xl font-bold text-amber-600">{config.maxActionsPerDay}</p>
            <p className="text-xs text-amber-600">{t('i18n_daily_limit_e96a14')}</p>
          </div>
        </div>

        {/* Settings */}
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700">{t('i18n_maximum_actions_per_day_fe3470')}</label>
            <input
              type="number"
              value={localConfig.maxActionsPerDay}
              onChange={(e) => setLocalConfig({ ...localConfig, maxActionsPerDay: parseInt(e.target.value) || 5 })}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">{t('i18n_max_budget_change_7e5e7c')}</label>
            <input
              type="number"
              value={localConfig.maxBudgetChangePercent}
              onChange={(e) => setLocalConfig({ ...localConfig, maxBudgetChangePercent: parseInt(e.target.value) || 20 })}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">{t('i18n_min_cost_for_decision_477120')}</label>
            <input
              type="number"
              value={localConfig.minSpendForDecision}
              onChange={(e) => setLocalConfig({ ...localConfig, minSpendForDecision: parseInt(e.target.value) || 50 })}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
        >
          {saving ? t('i18n_saving_034bf1') : t('i18n_save_configuration_42b7a3')}
        </button>
      </div>
    </Card>
  );
};

// ==========================================
// CAMPAIGN TABLE WITH ACTIONS
// ==========================================

const CampaignActionsTable = ({ campaigns, onAction, loading }) => {
  const { t } = useLang();
  const [actionLoading, setActionLoading] = useState({});

  const handleAction = async (campaign, status) => {
    setActionLoading({ ...actionLoading, [campaign.campaign]: true });
    try {
      await onAction({
        campaign: campaign.campaign,
        status,
        roi: campaign.roi,
        profit: campaign.profit,
        spend: campaign.spend,
      });
      toast.success(`${t('i18n_action_1547c9')} ${status} ${t('i18n_applied_to_15adc3')} ${campaign.campaign}`);
    } catch (err) {
      toast.error(t('i18n_error_performing_action_1a89d9'));
    }
    setActionLoading({ ...actionLoading, [campaign.campaign]: false });
  };

  if (!campaigns || campaigns.length === 0) {
    return (
      <Card title={t('i18n_campaign_actions_8e4343')}>
        <p className="text-gray-500 text-center py-8">{t('i18n_no_campaign_data_dccdf9')}</p>
      </Card>
    );
  }

  return (
    <Card 
      title={t('i18n_campaign_actions_8e4343')} 
      action={<span className="text-sm text-gray-500">{campaigns.length} {t('i18n_campaigns_714c09')}</span>}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_campaign_15b3d1')}</th>
              <th className="text-right py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_expenses_1ceb39')}</th>
              <th className="text-right py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_profit_123a87')}</th>
              <th className="text-right py-3 px-2 text-sm font-semibold text-gray-600">ROI</th>
              <th className="text-center py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_status_7203f7')}</th>
              <th className="text-center py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_actions_cec375')}</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c, idx) => (
              <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-2">
                  <div className="font-medium text-gray-900">{c.campaign || 'Direct'}</div>
                  <div className="text-xs text-gray-500">{c.source}</div>
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  ${(c.spend || 0).toLocaleString()}
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  ${(c.profit || 0).toLocaleString()}
                </td>
                <td className={`py-3 px-2 text-right font-bold ${
                  c.roi > 30 ? 'text-emerald-600' :
                  c.roi > 0 ? 'text-blue-600' :
                  c.roi !== null ? 'text-red-600' : 'text-gray-400'
                }`}>
                  {c.roi !== null && c.roi !== undefined ? `${c.roi}%` : t('i18n_n_a_5f0039')}
                </td>
                <td className="py-3 px-2 text-center">
                  <StatusBadge status={c.status} />
                </td>
                <td className="py-3 px-2">
                  <div className="flex items-center justify-center gap-2">
                    <ActionButton
                      variant="scale"
                      onClick={() => handleAction(c, 'scale')}
                      loading={actionLoading[c.campaign]}
                      disabled={c.status === 'kill'}
                    >
                      {t('i18n_zoom_cbd937')}
                    </ActionButton>
                    <ActionButton
                      variant="kill"
                      onClick={() => handleAction(c, 'kill')}
                      loading={actionLoading[c.campaign]}
                      disabled={c.status === 'scale'}
                    >
                      {t('i18n_stop_38d654')}
                    </ActionButton>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

// ==========================================
// SPEND SYNC STATUS
// ==========================================

const SpendSyncStatus = ({ metaAds, onSync, loading }) => {
  const { t } = useLang();
  const [syncing, setSyncing] = useState(false);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await onSync();
      toast.success(t('i18n_cost_data_synced_7e760e'));
    } catch (err) {
      toast.error(t('i18n_synchronization_error_b58c1b'));
    }
    setSyncing(false);
  };

  return (
    <Card title={t('i18n_meta_ads_sync_f010de')}>
      <div className="space-y-4">
        <div className={`p-4 rounded-lg ${metaAds?.configured ? 'bg-emerald-50' : 'bg-amber-50'}`}>
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${metaAds?.configured ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <div>
              <p className="font-medium">
                {metaAds?.configured ? t('i18n_meta_ads_connected_7d6cb0') : t('i18n_meta_ads_not_configured_9625d5')}
              </p>
              <p className="text-sm text-gray-600">
                {metaAds?.configured 
                  ? t('i18n_cost_data_syncs_automatically_fb1333')
                  : t('i18n_configure_in_settings_integrat_50caa6')
                }
              </p>
            </div>
          </div>
        </div>

        {metaAds?.configured && (
          <button
            onClick={handleSync}
            disabled={syncing}
            className="w-full py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
          >
            {syncing ? t('i18n_syncing_405590') : t('i18n_sync_now_a05702')}
          </button>
        )}

        {!metaAds?.configured && (
          <div className="p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600">
              {t('i18n_go_to_settings_integrations_to_cfec9d')}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
};

// ==========================================
// DECISION LOG
// ==========================================

const DecisionLog = ({ decisions, loading }) => {
  const { t } = useLang();
  if (loading) {
    return (
      <Card title={t('i18n_decision_log_faa83d')}>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
        </div>
      </Card>
    );
  }

  if (!decisions || decisions.length === 0) {
    return (
      <Card title={t('i18n_decision_log_faa83d')}>
        <p className="text-gray-500 text-center py-8">{t('i18n_no_decision_records_yet_a0ec49')}</p>
      </Card>
    );
  }

  return (
    <Card 
      title={t('i18n_decision_log_faa83d')} 
      action={<span className="text-sm text-gray-500">{t('i18n_why_the_system_made_each_decis_a4e64e')}</span>}
    >
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {decisions.map((d, idx) => (
          <div key={idx} className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">{d.campaign}</span>
              <StatusBadge status={d.decision} />
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm mb-2">
              <span>ROI: <strong>{d.roi !== null ? `${d.roi}%` : t('i18n_n_a_5f0039')}</strong></span>
              <span>{t('i18n_costs_60669c')} <strong>${d.spend}</strong></span>
              <span>{t('i18n_profit_653621')} <strong>${d.profit}</strong></span>
            </div>
            {d.reasons && d.reasons.length > 0 && (
              <div className="text-xs text-gray-600">
                <strong>{t('i18n_reasons_b12aea')}</strong> {d.reasons.join(', ')}
              </div>
            )}
            <div className="text-xs text-gray-400 mt-1">
              {new Date(d.timestamp).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

// ==========================================
// ACTION HISTORY
// ==========================================

const ActionHistory = ({ history, loading }) => {
  const { t } = useLang();
  if (loading) {
    return (
      <Card title={t('i18n_action_history_e275d8')}>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
        </div>
      </Card>
    );
  }

  if (!history || history.length === 0) {
    return (
      <Card title={t('i18n_action_history_e275d8')}>
        <p className="text-gray-500 text-center py-8">{t('i18n_no_actions_performed_yet_ca6f23')}</p>
      </Card>
    );
  }

  return (
    <Card 
      title={t('i18n_action_history_e275d8')} 
      action={<span className="text-sm text-gray-500">{history.length} {t('i18n_actions_050857')}</span>}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_campaign_15b3d1')}</th>
              <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_action_773c46')}</th>
              <th className="text-center py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_status_7203f7')}</th>
              <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_details_27eae6')}</th>
              <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">{t('i18n_time_9aca4f')}</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h, idx) => (
              <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-2 font-medium">{h.campaign}</td>
                <td className="py-3 px-2">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    h.actionType === 'scale_up' ? 'bg-emerald-100 text-emerald-700' :
                    h.actionType === 'pause' ? 'bg-red-100 text-red-700' :
                    'bg-amber-100 text-amber-700'
                  }`}>
                    {h.actionType?.replace('_', ' ').toUpperCase()}
                  </span>
                </td>
                <td className="py-3 px-2 text-center">
                  <StatusBadge status={h.status} />
                </td>
                <td className="py-3 px-2 text-sm text-gray-600 max-w-xs truncate">
                  {h.error || h.reason || '-'}
                </td>
                <td className="py-3 px-2 text-sm text-gray-500">
                  {new Date(h.createdAt).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

// ==========================================
// ROI SUMMARY
// ==========================================

const ROISummary = ({ data }) => {
  const { t } = useLang();
  if (!data) return null;

  const { summary } = data;
  const pieData = [
    { name: t('i18n_scale_0883ab'), value: summary?.scaleCount || 0, color: '#10b981' },
    { name: t('i18n_hold_3d4a3f'), value: summary?.keepCount || 0, color: '#3b82f6' },
    { name: t('i18n_watchers_5c91a0'), value: summary?.watchCount || 0, color: '#f59e0b' },
    { name: t('i18n_stop_5d9160'), value: summary?.killCount || 0, color: '#ef4444' },
  ].filter(d => d.value > 0);

  return (
    <Card title={t('i18n_roi_summary_c490d8')}>
      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-4">
          <div className="p-4 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl text-white">
            <p className="text-sm opacity-80">{t('i18n_total_expenses_b5033b')}</p>
            <p className="text-3xl font-bold">${(summary?.totalSpend || 0).toLocaleString()}</p>
          </div>
          <div className="p-4 bg-gradient-to-r from-emerald-500 to-emerald-600 rounded-xl text-white">
            <p className="text-sm opacity-80">{t('i18n_total_profit_58105d')}</p>
            <p className="text-3xl font-bold">${(summary?.totalProfit || 0).toLocaleString()}</p>
          </div>
          <div className={`p-4 rounded-xl text-white ${summary?.overallRoi >= 0 ? 'bg-gradient-to-r from-emerald-500 to-emerald-600' : 'bg-gradient-to-r from-red-500 to-red-600'}`}>
            <p className="text-sm opacity-80">{t('i18n_total_roi_1c7384')}</p>
            <p className="text-3xl font-bold">{summary?.overallRoi?.toFixed(1) || 0}%</p>
          </div>
        </div>
        <div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={80}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-4 mt-2">
            {pieData.map((d, i) => (
              <div key={i} className="flex items-center gap-1 text-xs">
                <div className="w-3 h-3 rounded" style={{ backgroundColor: d.color }} />
                {d.name}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
};

// ==========================================
// MAIN COMPONENT
// ==========================================

const MarketingControlPanel = () => {
  const { t } = useLang();
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState({});
  const [campaigns, setCampaigns] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [history, setHistory] = useState([]);
  const [roiData, setRoiData] = useState(null);
  const [days, setDays] = useState(30);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, configRes, roiRes, decisionsRes, historyRes] = await Promise.all([
        fetch(`${API_URL}/api/marketing/status`).then(r => r.json()),
        fetch(`${API_URL}/api/marketing/auto/config`).then(r => r.json()),
        fetch(`${API_URL}/api/marketing/roi?days=${days}`).then(r => r.json()),
        fetch(`${API_URL}/api/marketing/auto/decisions?limit=50`).then(r => r.json()),
        fetch(`${API_URL}/api/marketing/auto/history?days=${days}`).then(r => r.json()),
      ]);

      if (statusRes.ok) setStatus(statusRes);
      if (configRes.success) setConfig(configRes.data);
      if (roiRes.success) {
        setRoiData(roiRes.data);
        setCampaigns(roiRes.data.decisions || []);
      }
      if (decisionsRes.success) setDecisions(decisionsRes.data || []);
      if (historyRes.success) setHistory(historyRes.data || []);
    } catch (err) {
      console.error(t('i18n_error_loading_marketing_data_2c7086'), err);
      toast.error(t('i18n_error_loading_data_de6e6d'));
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleUpdateConfig = async (newConfig) => {
    const res = await fetch(`${API_URL}/api/marketing/auto/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newConfig),
    });
    const data = await res.json();
    if (data.success) {
      setConfig(data.data);
    }
    return data;
  };

  const handleAction = async (actionData) => {
    const res = await fetch(`${API_URL}/api/marketing/auto/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(actionData),
    });
    const data = await res.json();
    if (data.success) {
      fetchData(); // Refresh data
    }
    return data;
  };

  const handleSync = async () => {
    const res = await fetch(`${API_URL}/api/marketing/spend/sync`, {
      method: 'POST',
    });
    const data = await res.json();
    if (data.success) {
      fetchData();
    }
    return data;
  };

  const tabs = [
    { id: 'overview', label: t('i18n_overview_b32ea1') },
    { id: 'campaigns', label: t('i18n_campaigns_6fd7f7') },
    { id: 'automation', label: t('i18n_automation_f525b6') },
    { id: 'history', label: t('i18n_history_a68139') },
  ];

  return (
    <div className="min-h-screen bg-gray-50" data-testid="marketing-control-panel">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('i18n_marketing_control_13918e')}</h1>
            <p className="text-sm text-gray-500">
              {status?.features?.length || 0} {t('i18n_active_features_5e5697')}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <WhiteSelect value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>{t('i18n_last_7_days_79531d')}</option>
              <option value={14}>{t('i18n_last_14_days_a937d9')}</option>
              <option value={30}>{t('i18n_last_30_days_f5c99e')}</option>
              <option value={60}>{t('i18n_last_60_days_226c39')}</option>
            </WhiteSelect>
            <button
              onClick={fetchData}
              disabled={loading}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
            >
              {loading ? t('i18n_loading_1fcad6') : t('i18n_refresh_b6bf91')}
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-4 mt-4 border-b border-gray-200 -mb-px">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label={t('i18n_total_expenses_b5033b')}
                value={`$${(roiData?.summary?.totalSpend || 0).toLocaleString()}`}
                color="blue"
              />
              <StatCard
                label={t('i18n_total_profit_58105d')}
                value={`$${(roiData?.summary?.totalProfit || 0).toLocaleString()}`}
                color="green"
              />
              <StatCard
                label={t('i18n_total_roi_1c7384')}
                value={`${roiData?.summary?.overallRoi?.toFixed(1) || 0}%`}
                color={roiData?.summary?.overallRoi >= 0 ? 'green' : 'red'}
              />
              <StatCard
                label={t('i18n_campaigns_6fd7f7')}
                value={campaigns.length}
                subValue={`${roiData?.summary?.scaleCount || 0} ${t('i18n_to_scale_b122fc')}`}
                color="purple"
              />
            </div>

            {/* ROI Summary */}
            <ROISummary data={roiData} />

            {/* Quick Actions */}
            <div className="grid lg:grid-cols-2 gap-6">
              <SpendSyncStatus metaAds={status?.metaAds} onSync={handleSync} loading={loading} />
              <AutoModePanel config={config} onUpdate={handleUpdateConfig} loading={loading} />
            </div>
          </div>
        )}

        {activeTab === 'campaigns' && (
          <CampaignActionsTable campaigns={campaigns} onAction={handleAction} loading={loading} />
        )}

        {activeTab === 'automation' && (
          <div className="grid lg:grid-cols-2 gap-6">
            <AutoModePanel config={config} onUpdate={handleUpdateConfig} loading={loading} />
            <DecisionLog decisions={decisions} loading={loading} />
          </div>
        )}

        {activeTab === 'history' && (
          <ActionHistory history={history} loading={loading} />
        )}
      </div>
    </div>
  );
};

export default MarketingControlPanel;
