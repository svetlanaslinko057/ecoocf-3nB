import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Fire, ThermometerSimple, Snowflake, Target, Phone, Eye } from '@phosphor-icons/react';
import { toast } from 'sonner';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const BUCKETS = {
  hot: { labelKey: 'hotLeadsCount', icon: Fire, color: 'red', bg: 'bg-red-500' },
  warm: { labelKey: 'warmLeadsCount', icon: ThermometerSimple, color: 'amber', bg: 'bg-amber-500' },
  cold: { labelKey: 'coldLeadsCount', icon: Snowflake, color: 'blue', bg: 'bg-blue-500' },
};

const ScoreBar = ({ label, value, max = 100, color = 'blue' }) => {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-500">{label}</span>
        <span className="font-medium text-zinc-900">{value}</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-100 overflow-hidden">
        <div className={`h-full rounded-full bg-${color}-500`} style={{ width: `${pct}%` }}/>
      </div>
    </div>
  );
};

const LeadCard = ({ lead, onAction  }) => {
  const { t } = useLang();
  const bucket = BUCKETS[lead.bucket] || BUCKETS.cold;
  const BucketIcon = bucket.icon;
  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-4 hover:shadow-lg transition-all" data-testid={`lead-card-${lead.id}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${bucket.bg}`}>
            <BucketIcon size={24} className="text-white" weight="fill" />
          </div>
          <div>
            <h3 className="font-semibold text-zinc-900">{lead.customerName || 'Lead'}</h3>
            <p className="text-sm text-zinc-500">{lead.phone || lead.email}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-zinc-900">{lead.totalScore || 0}</p>
          <p className="text-xs text-zinc-500">{t('score')}</p>
        </div>
      </div>
      {lead.vin && (
        <div className="mb-4 p-3 rounded-lg bg-zinc-50">
          <p className="text-sm font-medium text-zinc-900">{lead.vehicleTitle || t('vehicle')}</p>
          <p className="text-xs text-zinc-500 font-mono">{lead.vin}</p>
        </div>
      )}
      <div className="space-y-2 mb-4">
        <ScoreBar label={t('behavior')} value={lead.behaviorScore || 0} color="violet" />
        <ScoreBar label={t('sales')} value={lead.salesScore || 0} color="blue" />
        <ScoreBar label={t('deal')} value={lead.dealScore || 0} color="emerald" />
      </div>
      {lead.nextAction && (
        <div className="mb-4 p-3 rounded-lg bg-blue-50 border border-blue-100">
          <p className="text-xs text-blue-600 font-medium mb-1">{t('recommended')}:</p>
          <p className="text-sm text-blue-800">{lead.nextAction}</p>
        </div>
      )}
      <div className="flex items-center gap-2 pt-3 border-t border-zinc-100">
        <button onClick={() => onAction(lead.id, 'call')} className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 text-sm font-medium" data-testid={`call-lead-${lead.id}`}>
          <Phone size={16} /> {t('call')}
        </button>
        <button onClick={() => onAction(lead.id, 'view')} className="p-2 rounded-lg border border-zinc-200 text-zinc-600 hover:bg-zinc-50" data-testid={`view-lead-${lead.id}`}>
          <Eye size={18} />
        </button>
      </div>
    </div>
  );
};

const StatCard = ({ icon: Icon, title, value, color = 'zinc' }) => (
  <div className="bg-white rounded-xl border border-zinc-200 p-4 flex items-center gap-3">
    <div className={`p-2 rounded-lg bg-${color}-100`}>
      <Icon size={20} className={`text-${color}-600`} weight="fill" />
    </div>
    <div>
      <p className="text-2xl font-bold text-zinc-900">{value}</p>
      <p className="text-sm text-zinc-500">{title}</p>
    </div>
  </div>
);

export default function PredictiveLeadsPage() {
  const { t } = useLang();
  const [hotLeads, setHotLeads] = useState([]);
  const [warmLeads, setWarmLeads] = useState([]);
  const [coldLeads, setColdLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const [hotRes, warmRes, coldRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/predictive-leads/bucket/hot`),
        axios.get(`${API_URL}/api/admin/predictive-leads/bucket/warm`),
        axios.get(`${API_URL}/api/admin/predictive-leads/bucket/cold`),
      ]);
      // Ensure we always set arrays, even if API returns error objects
      setHotLeads(Array.isArray(hotRes.data) ? hotRes.data : []);
      setWarmLeads(Array.isArray(warmRes.data) ? warmRes.data : []);
      setColdLeads(Array.isArray(coldRes.data) ? coldRes.data : []);
    } catch (err) {
      console.error('Failed to load leads:', err);
      // Reset to empty arrays on error
      setHotLeads([]);
      setWarmLeads([]);
      setColdLeads([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = (leadId, action) => {
    if (action === 'view') window.open(`/admin/leads?id=${leadId}`, '_blank');
    if (action === 'call') toast.info(t('openingTelephony'));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-zinc-900 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="predictive-leads-page">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900">{t('predictiveLeads')}</h1>
        <p className="text-zinc-500">{t('aiScoringPrioritization')}</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Fire} title={t('hotLeadsCount')} value={hotLeads.length} color="red" />
        <StatCard icon={ThermometerSimple} title={t('warmLeadsCount')} value={warmLeads.length} color="amber" />
        <StatCard icon={Snowflake} title={t('coldLeadsCount')} value={coldLeads.length} color="blue" />
        <StatCard icon={Target} title={t('total')} value={hotLeads.length + warmLeads.length + coldLeads.length} color="violet" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {Object.entries(BUCKETS).map(([key, config]) => {
          const leads = key === 'hot' ? hotLeads : key === 'warm' ? warmLeads : coldLeads.slice(0, 5);
          const BIcon = config.icon;
          return (
            <div key={key} className="space-y-4">
              <div className={`flex items-center justify-between p-4 rounded-xl bg-${config.color}-100`}>
                <div className="flex items-center gap-2">
                  <BIcon size={24} className={`text-${config.color}-600`} weight="fill" />
                  <span className={`text-lg font-bold text-${config.color}-700`}>{t(config.labelKey)}</span>
                </div>
                <span className={`px-3 py-1 rounded-full bg-white text-${config.color}-600 font-bold`}>{leads.length}</span>
              </div>
              <div className="space-y-4">
                {leads.length === 0 ? (
                  <div className="p-6 rounded-xl border-2 border-dashed border-zinc-200 text-center text-zinc-400">{t('noLeadsInBucket')}</div>
                ) : (
                  leads.map(lead => <LeadCard key={lead.id} lead={lead} onAction={handleAction} t={t} />)
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
