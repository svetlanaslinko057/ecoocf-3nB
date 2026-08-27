/**
 * PipelineVertical.jsx — Leads + Deals (two sub-tabs)
 *  Leads sub-tab: funnel + stale + conversion per manager
 *  Deals sub-tab: journey funnel + bottlenecks + cycle time + win/loss
 */
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, FunnelChart, Funnel, LabelList, LineChart, Line, Legend } from 'recharts';
import { TrendUp, UsersThree, Clock, Target } from '@phosphor-icons/react';
import { InsightsCard, InsightsSection, InsightsLoading, InsightsEmpty, MetricChip } from '../shared/InsightsCard';
import { safeGet, fmtCompact, fmtDuration, fmtPct } from '../shared/insightsApi';
import DealDrillSheet from '../shared/DealDrillSheet';
import { useLang } from '../../../i18n';

function LeadsTab({ scope, period }) {
  const { t } = useLang();
  const [loading, setLoading] = useState(true);
  const [kpi, setKpi] = useState({});
  const [stale, setStale] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [k, s, lb] = await Promise.all([
        safeGet('/api/admin/kpi/dashboard'),
        safeGet('/api/team/leads/stale').then(r => r.data ? r : safeGet('/api/admin/leads/stale')),
        safeGet('/api/admin/kpi/leaderboard'),
      ]);
      if (!alive) return;
      setKpi(k.data || {});
      setStale(Array.isArray(s.data) ? s.data : s.data?.items || []);
      setLeaderboard(lb.data?.managers || []);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [scope, period]);

  if (loading) return <InsightsLoading rows={6} />;

  const total = kpi.leadsCreated || 0;
  const contactRate = kpi.contactRate || 0;
  const convRate = kpi.conversionRate || 0;
  const contacted = Math.round((total * contactRate) / 100);
  const converted = Math.round((total * convRate) / 100);
  const funnel = [
    { name: 'New', value: total, fill: '#27272a' },
    { name: 'Contacted', value: contacted, fill: '#52525b' },
    { name: 'Qualified', value: Math.round(contacted * 0.7), fill: '#a1a1aa' },
    { name: 'Converted', value: converted, fill: '#f59e0b' },
  ];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <InsightsCard className="lg:col-span-7" title={t('ins_sec_leads_funnel')} tip={t('ins_tip_leads_funnel')} testId="insights-leads-funnel-card">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <FunnelChart>
                <Tooltip />
                <Funnel dataKey="value" data={funnel} isAnimationActive>
                  <LabelList position="right" dataKey="name" style={{ fontSize: 12, fill: '#18181b' }} />
                  <LabelList position="center" dataKey="value" style={{ fontSize: 12, fill: '#fff' }} />
                </Funnel>
              </FunnelChart>
            </ResponsiveContainer>
          </div>
        </InsightsCard>
        <InsightsCard className="lg:col-span-5" title={t('ins_card_funnel_health')}>
          <ul className="space-y-3">
            <li className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2"><span className="text-sm text-zinc-700">{t('ins_metric_contact_rate')}</span><MetricChip value={fmtPct(contactRate)} tone={contactRate>=60?'positive':contactRate>=30?'warning':'negative'} /></li>
            <li className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2"><span className="text-sm text-zinc-700">{t('ins_metric_conversion_rate')}</span><MetricChip value={fmtPct(convRate)} tone={convRate>=20?'positive':convRate>=10?'warning':'negative'} /></li>
            <li className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2"><span className="text-sm text-zinc-700">{t('ins_metric_avg_first_response')}</span><MetricChip value={kpi.avgResponseTime ? `${kpi.avgResponseTime}m` : '—'} tone={kpi.avgResponseTime<=10?'positive':kpi.avgResponseTime<=60?'warning':'negative'} /></li>
            <li className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2"><span className="text-sm text-zinc-700">{t('ins_metric_leads_trend')}</span><MetricChip value={kpi.trends?.leads != null ? `${kpi.trends.leads>0?'+':''}${kpi.trends.leads}%` : '—'} tone={kpi.trends?.leads>0?'positive':kpi.trends?.leads<0?'negative':'neutral'} /></li>
          </ul>
        </InsightsCard>
      </div>

      <InsightsCard title={t('ins_sec_stale_leads')} tip={t('ins_tip_stale_leads')} testId="insights-stale-leads-table" padded={false}>
        {stale.length === 0 ? <div className="p-5"><InsightsEmpty title="No stale leads — great work." /></div> : (
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                <th className="px-4 py-2 text-left font-medium">Lead</th>
                <th className="px-4 py-2 text-left font-medium">Owner</th>
                <th className="px-4 py-2 text-left font-medium">Source</th>
                <th className="px-4 py-2 text-right font-medium">Age</th>
                <th className="px-4 py-2 text-left font-medium">Last touch</th>
              </tr></thead>
              <tbody>
                {stale.slice(0, 50).map((l, i) => (
                  <tr key={l._id || l.id || i} className="border-b border-zinc-50 hover:bg-zinc-50">
                    <td className="px-4 py-2 font-medium text-zinc-900">{l.name || l.email || l.phone || `Lead ${l._id || l.id}`}</td>
                    <td className="px-4 py-2 text-zinc-700">{l.ownerEmail || l.owner || l.managerEmail || '—'}</td>
                    <td className="px-4 py-2 text-zinc-600">{l.source || '—'}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{l.ageDays ? `${l.ageDays}d` : '—'}</td>
                    <td className="px-4 py-2 text-zinc-500">{l.lastTouchAt || l.updatedAt || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </InsightsCard>

      <InsightsCard title={t('ins_sec_conversion_per_manager')} tip={t('ins_tip_conversion_per_manager')} testId="insights-conversion-per-manager-card">
        {leaderboard.length === 0 ? <InsightsEmpty title="No managers data" /> : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={leaderboard} margin={{ top: 4, right: 8, left: -16, bottom: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#71717a' }} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={32} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Bar dataKey="score" fill="#18181b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </InsightsCard>
    </div>
  );
}

function DealsTab({ scope, period }) {
  const [loading, setLoading] = useState(true);
  const [funnel, setFunnel] = useState([]);
  const [bottle, setBottle] = useState([]);
  const [durations, setDurations] = useState([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [f, b, d] = await Promise.all([
        safeGet('/api/journey/funnel', { days: period }),
        safeGet('/api/journey/bottlenecks', { days: period }),
        safeGet('/api/journey/durations', { days: period }),
      ]);
      if (!alive) return;
      const fr = f.data?.funnel || f.data?.stages || f.data || [];
      setFunnel(Array.isArray(fr) ? fr.map((s, i) => ({ name: s.stage || s.name, value: s.count ?? s.value ?? 0, fill: i === fr.length - 1 ? '#f59e0b' : '#52525b' })) : []);
      setBottle(Array.isArray(b.data?.bottlenecks) ? b.data.bottlenecks : Array.isArray(b.data) ? b.data : []);
      setDurations(Array.isArray(d.data?.durations) ? d.data.durations : Array.isArray(d.data) ? d.data : []);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [scope, period]);

  if (loading) return <InsightsLoading rows={6} />;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <InsightsCard className="lg:col-span-8" title={t('ins_sec_deals_funnel')} tip={t('ins_tip_deals_funnel')} testId="insights-deals-journey-funnel-card">
          {funnel.length === 0 ? <InsightsEmpty title="No journey data" /> : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <FunnelChart>
                  <Tooltip />
                  <Funnel dataKey="value" data={funnel} isAnimationActive>
                    <LabelList position="right" dataKey="name" style={{ fontSize: 12, fill: '#18181b' }} />
                    <LabelList position="center" dataKey="value" style={{ fontSize: 12, fill: '#fff' }} />
                  </Funnel>
                </FunnelChart>
              </ResponsiveContainer>
            </div>
          )}
        </InsightsCard>
        <InsightsCard className="lg:col-span-4" title={t('ins_card_bottlenecks')} tip={t('ins_tip_bottlenecks')}>
          {bottle.length === 0 ? <InsightsEmpty title="No bottlenecks" /> : (
            <ul className="space-y-2">
              {bottle.slice(0, 6).map((b, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => setDrillStage({ stage: b.stage || b.name, avgDays: b.avgDays || b.avg, stuck: b.stuck || b.count, bottleneck: true })}
                    data-testid={`insights-bottleneck-row-${i}`}
                    className="flex w-full items-center justify-between rounded-lg border border-zinc-100 px-3 py-2 text-left hover:border-zinc-300 hover:bg-zinc-50"
                  >
                    <div><p className="text-sm font-medium text-zinc-900">{b.stage || b.name}</p><p className="text-[11px] text-zinc-500">avg {fmtDuration(b.avgDays || b.avg || 0)}</p></div>
                    <MetricChip value={fmtCompact(b.stuck || b.count || 0)} tone="warning" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </InsightsCard>
      </div>

      <InsightsCard title={t('ins_sec_cycle_time')} tip={t('ins_tip_cycle_time')} testId="insights-cycle-time-card" padded={false}>
        {durations.length === 0 ? <div className="p-5"><InsightsEmpty title="No duration data" /></div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                <th className="px-4 py-2 text-left font-medium">Stage</th>
                <th className="px-4 py-2 text-right font-medium">Avg days</th>
                <th className="px-4 py-2 text-right font-medium">P75 days</th>
                <th className="px-4 py-2 text-right font-medium">Count</th>
              </tr></thead>
              <tbody>
                {durations.map((d, i) => (
                  <tr key={i} className="cursor-pointer border-b border-zinc-50 hover:bg-zinc-50" onClick={() => setDrillStage({ stage: d.stage || d.name, avgDays: d.avgDays || d.avg, p75Days: d.p75Days || d.p75 })} data-testid={`insights-cycle-row-${i}`}>
                    <td className="px-4 py-2 font-medium text-zinc-900">{d.stage || d.name}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{fmtDuration(d.avgDays || d.avg)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{fmtDuration(d.p75Days || d.p75)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{fmtCompact(d.count || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </InsightsCard>

      {/* Deal drill-down sheet — opens on bottleneck / cycle-row click */}
      <DealDrillSheet open={!!drillStage} onOpenChange={(o) => !o && setDrillStage(null)} deal={drillStage} stage={drillStage?.stage} />
    </div>
  );
}

const PipelineVertical = ({ scope, period = 30 }) => {
  const { t } = useLang();
  const [sub, setSub] = useState('leads');
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="space-y-4">
      <div className="inline-flex rounded-lg bg-zinc-100 p-0.5" data-testid="insights-pipeline-subtabs">
        <button onClick={() => setSub('leads')} data-testid="insights-pipeline-tab-leads" className={`px-4 py-1.5 text-sm font-medium ${sub==='leads'?'rounded-md bg-white text-zinc-900 shadow-sm':'text-zinc-600'}`}>
          <UsersThree size={14} className="mr-1 inline" weight="duotone" /> {t('ins_pipeline_subtab_leads')}
        </button>
        <button onClick={() => setSub('deals')} data-testid="insights-pipeline-tab-deals" className={`px-4 py-1.5 text-sm font-medium ${sub==='deals'?'rounded-md bg-white text-zinc-900 shadow-sm':'text-zinc-600'}`}>
          <Target size={14} className="mr-1 inline" weight="duotone" /> {t('ins_pipeline_subtab_deals')}
        </button>
      </div>
      {sub === 'leads' ? <LeadsTab scope={scope} period={period} /> : <DealsTab scope={scope} period={period} />}
    </motion.div>
  );
};

export default PipelineVertical;
