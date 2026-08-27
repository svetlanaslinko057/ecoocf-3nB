/**
 * TrafficVertical.jsx — Traffic & Engagement
 * Merges old: Analytics (traffic/conversion/campaigns) + UserEngagement + IntentDashboard
 *
 * Sections:
 *  1. Visits Funnel  (site→view→fav→compare→lead)
 *  2. Traffic Sources & ROI table
 *  3. User Engagement small multiples (favs/compares/shares)
 *  4. Top Users + Top Vehicles + Hot Leads (AI intent)
 */
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ResponsiveContainer, FunnelChart, Funnel, LabelList, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line, Legend } from 'recharts';
import { Heart, Eye, ShareNetwork, Scales, Flame, ArrowsLeftRight } from '@phosphor-icons/react';
import { InsightsCard, InsightsSection, InsightsLoading, InsightsEmpty, MetricChip } from '../shared/InsightsCard';
import { safeGet, fmtCompact, fmtPct, fmtMoney } from '../shared/insightsApi';
import CustomerDrillSheet from '../shared/CustomerDrillSheet';
import { useLang } from '../../../i18n';

const TrafficVertical = ({ scope, period = 30 }) => {
  const { t } = useLang();
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState(null);
  const [marketing, setMarketing] = useState(null);
  const [engagement, setEngagement] = useState(null);
  const [topUsers, setTopUsers] = useState([]);
  const [topVehicles, setTopVehicles] = useState([]);
  const [hotLeads, setHotLeads] = useState([]);
  const [drillCustomer, setDrillCustomer] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [a, m, eng, tu, tv, hl] = await Promise.all([
        safeGet('/api/analytics/dashboard', { days: period }),
        safeGet('/api/analytics/marketing-campaigns', { days: period }),
        safeGet('/api/admin/engagement/analytics'),
        safeGet('/api/admin/engagement/top-users', { limit: 20 }),
        safeGet('/api/admin/engagement/top-vehicles', { limit: 20 }),
        safeGet('/api/admin/intent/hot-leads'),
      ]);
      if (!alive) return;
      setAnalytics(a.data || {});
      setMarketing(m.data || {});
      setEngagement(eng.data || {});
      setTopUsers(Array.isArray(tu.data) ? tu.data : tu.data?.items || []);
      setTopVehicles(Array.isArray(tv.data) ? tv.data : tv.data?.items || []);
      setHotLeads(Array.isArray(hl.data) ? hl.data : hl.data?.items || []);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [period, scope]);

  if (loading) return <InsightsLoading rows={8} />;

  const funnel = (() => {
    const f = analytics?.funnel || analytics?.conversionFunnel || [];
    if (Array.isArray(f) && f.length) return f.map(x => ({ name: x.name || x.stage || x.label, value: x.value ?? x.count ?? 0, fill: '#18181b' }));
    const visits = analytics?.visits ?? 0;
    const views = analytics?.vehicleViews ?? 0;
    const favs = (engagement?.totalFavorites) ?? 0;
    const compares = engagement?.totalCompares ?? 0;
    const leads = analytics?.leadsSubmitted ?? analytics?.leads ?? 0;
    return [
      { name: 'Visits', value: visits, fill: '#27272a' },
      { name: 'Vehicle Views', value: views, fill: '#3f3f46' },
      { name: 'Favorites', value: favs, fill: '#52525b' },
      { name: 'Compares', value: compares, fill: '#71717a' },
      { name: 'Leads', value: leads, fill: '#f59e0b' },
    ];
  })();

  const sources = analytics?.trafficSources || analytics?.sources || [];
  const campaigns = marketing?.campaigns || marketing?.items || [];
  const engagementSeries = engagement?.timeseries || engagement?.series || [];

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="space-y-6">
      <InsightsSection id="traffic-funnel" title={t('ins_sec_visits_funnel')} subtitle={t('ins_sec_visits_funnel_sub')} tip={t('ins_tip_visits_funnel')}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <InsightsCard className="lg:col-span-7" title={t('ins_sec_visits_funnel')} testId="insights-traffic-funnel-card">
            <div className="h-72" data-testid="insights-traffic-funnel-chart">
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
          <InsightsCard className="lg:col-span-5" title={t('ins_sec_traffic_sources')} tip={t('ins_tip_traffic_sources')} testId="insights-traffic-sources-table">
            {sources.length === 0 ? <InsightsEmpty title="No traffic-source data for this period." /> : (
              <div className="max-h-72 overflow-auto">
                <table className="w-full text-sm">
                  <thead><tr className="text-[11px] uppercase tracking-wider text-zinc-500">
                    <th className="py-2 text-left font-medium">Source</th>
                    <th className="py-2 text-right font-medium">Visits</th>
                    <th className="py-2 text-right font-medium">Conv.</th>
                    <th className="py-2 text-right font-medium">ROI</th>
                  </tr></thead>
                  <tbody>
                    {sources.slice(0, 25).map((s, i) => (
                      <tr key={i} className="border-t border-zinc-50 hover:bg-zinc-50">
                        <td className="py-2 font-medium text-zinc-900">{s.source || s.name || s.utm || '(direct)'}</td>
                        <td className="py-2 text-right tabular-nums">{fmtCompact(s.visits ?? s.sessions ?? 0)}</td>
                        <td className="py-2 text-right tabular-nums">{fmtPct(s.conversionRate ?? s.conv ?? 0)}</td>
                        <td className="py-2 text-right tabular-nums">{s.roi != null ? `${Number(s.roi).toFixed(1)}x` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </InsightsCard>
        </div>
      </InsightsSection>

      <InsightsSection id="campaign-roi" title={t('ins_sec_campaign_roi')} subtitle={t('ins_sec_campaign_roi_sub')} tip={t('ins_tip_campaign_roi')}>
        <InsightsCard testId="insights-campaign-roi-card" padded={false}>
          {campaigns.length === 0 ? <div className="p-5"><InsightsEmpty title="No active campaigns" /></div> : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-white"><tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-2 text-left font-medium">Campaign</th>
                  <th className="px-4 py-2 text-right font-medium">Spend</th>
                  <th className="px-4 py-2 text-right font-medium">Leads</th>
                  <th className="px-4 py-2 text-right font-medium">CPL</th>
                  <th className="px-4 py-2 text-right font-medium">Revenue</th>
                  <th className="px-4 py-2 text-right font-medium">ROI</th>
                </tr></thead>
                <tbody>
                  {campaigns.slice(0, 30).map((c, i) => (
                    <tr key={c.id || i} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="px-4 py-2 font-medium text-zinc-900">{c.name || c.campaign}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{fmtMoney(c.spend ?? c.cost ?? 0)}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{fmtCompact(c.leads ?? 0)}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{fmtMoney(c.cpl ?? (c.spend && c.leads ? c.spend / c.leads : 0))}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{fmtMoney(c.revenue ?? 0)}</td>
                      <td className="px-4 py-2 text-right">
                        {c.roi != null ? <MetricChip value={`${Number(c.roi).toFixed(1)}x`} tone={c.roi >= 2 ? 'positive' : c.roi >= 1 ? 'warning' : 'negative'} /> : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      <InsightsSection id="engagement" title="User Engagement" subtitle="Favorites · Compares · Shares trend">
        <InsightsCard testId="insights-engagement-card">
          {engagementSeries.length === 0 ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-zinc-100 p-3"><div className="text-[11px] uppercase tracking-wider text-zinc-500">Favorites</div><div className="text-2xl font-semibold tabular-nums">{fmtCompact(engagement?.totalFavorites ?? 0)}</div></div>
              <div className="rounded-lg border border-zinc-100 p-3"><div className="text-[11px] uppercase tracking-wider text-zinc-500">Compares</div><div className="text-2xl font-semibold tabular-nums">{fmtCompact(engagement?.totalCompares ?? 0)}</div></div>
              <div className="rounded-lg border border-zinc-100 p-3"><div className="text-[11px] uppercase tracking-wider text-zinc-500">Shares</div><div className="text-2xl font-semibold tabular-nums">{fmtCompact(engagement?.totalShares ?? 0)}</div></div>
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={engagementSeries} margin={{ top: 6, right: 8, left: -16, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#71717a' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={32} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="favorites" stroke="#dc2626" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="compares" stroke="#2563eb" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="shares" stroke="#059669" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </InsightsCard>
      </InsightsSection>

      <InsightsSection id="top-entities" title={t('ins_sec_top_entities')} subtitle={t('ins_sec_top_entities_sub')}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Heart size={14} weight="duotone" /> {t('ins_card_top_users')}</span>} tip={t('ins_tip_top_users')} testId="insights-top-users-table">
            {topUsers.length === 0 ? <InsightsEmpty title="No customer activity yet" /> : (
              <ul className="divide-y divide-zinc-50">
                {topUsers.slice(0, 10).map((u, i) => (
                  <li key={u._id || u.id || i}>
                    <button type="button" onClick={() => setDrillCustomer(u)} className="flex w-full items-center justify-between gap-2 rounded-md px-1 py-2 text-left hover:bg-zinc-50" data-testid={`insights-top-user-row-${i}`}>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{u.email || u.name || u.customerId}</p>
                        <p className="text-[11px] text-zinc-500">{u.lastActivity || u.lastSeen || ''}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 text-[11px] tabular-nums">
                        <span className="text-red-600">❤ {u.favoritesCount ?? 0}</span>
                        <span className="text-blue-600">⚖ {u.comparesCount ?? 0}</span>
                        <span className="text-emerald-600">↗ {u.sharesCount ?? 0}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </InsightsCard>
          <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Eye size={14} weight="duotone" /> {t('ins_card_top_vehicles')}</span>} tip={t('ins_tip_top_vehicles')} testId="insights-top-vehicles-table">
            {topVehicles.length === 0 ? <InsightsEmpty title="No vehicle interest yet" /> : (
              <ul className="divide-y divide-zinc-50">
                {topVehicles.slice(0, 10).map((v, i) => (
                  <li key={v.vin || i} className="flex items-center justify-between gap-2 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-zinc-900">{v.title || `${v.year || ''} ${v.make || ''} ${v.model || ''}`.trim() || v.vin}</p>
                      <p className="text-[11px] text-zinc-500">VIN: {v.vin}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-[11px] tabular-nums">
                      <span className="text-red-600">❤ {v.favoritesCount ?? 0}</span>
                      <span className="text-blue-600">⚖ {v.comparesCount ?? 0}</span>
                      <span className="text-emerald-600">↗ {v.sharesCount ?? 0}</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </InsightsCard>
          <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Flame size={14} weight="duotone" /> {t('ins_card_hot_leads')}</span>} tip={t('ins_tip_hot_leads')} testId="insights-hot-leads-table">
            {hotLeads.length === 0 ? <InsightsEmpty title="No hot leads right now" /> : (
              <ul className="divide-y divide-zinc-50">
                {hotLeads.slice(0, 10).map((l, i) => (
                  <li key={l._id || l.id || i}>
                    <button type="button" onClick={() => setDrillCustomer(l)} className="flex w-full items-center justify-between gap-2 rounded-md px-1 py-2 text-left hover:bg-zinc-50" data-testid={`insights-hot-lead-row-${i}`}>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{l.name || l.email || l.customerName || `Lead ${l._id || l.id}`}</p>
                        <p className="text-[11px] text-zinc-500">{l.intent || l.lastActivity || l.source || ''}</p>
                      </div>
                      <MetricChip value={l.score != null ? `${Math.round(l.score)}` : '—'} tone={Number(l.score)>=70?'negative':Number(l.score)>=40?'warning':'positive'} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </InsightsCard>
        </div>
      </InsightsSection>

      {/* Customer drill-down sheet — opens on row click in Top Users / Hot Leads */}
      <CustomerDrillSheet open={!!drillCustomer} onOpenChange={(o) => !o && setDrillCustomer(null)} customer={drillCustomer} />
    </motion.div>
  );
};

export default TrafficVertical;
