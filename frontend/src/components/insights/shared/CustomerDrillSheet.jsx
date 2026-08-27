/**
 * CustomerDrillSheet.jsx — opens a right-side Sheet with deep customer detail.
 * Triggered from TrafficVertical (Top Users, Hot Leads) and reused elsewhere.
 *
 * Data sources:
 *   GET /api/admin/engagement/customer/{customerId}  → favorites/compares/shares history
 *   GET /api/admin/intent/scores?customerId=...      → intent score + breakdown
 *   GET /api/customers/{id}                          → core profile (best-effort)
 */
import React, { useEffect, useState } from 'react';
import { Heart, Scales, ShareNetwork, Eye, Flame, Phone, EnvelopeSimple, MapPin, Calendar, Star } from '@phosphor-icons/react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../ui/sheet';
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';
import { safeGet, fmtCompact, riskBandClass } from './insightsApi';
import { InsightsLoading, InsightsEmpty, MetricChip, SeverityDot } from './InsightsCard';

const StatTile = ({ icon: Icon, label, value, tone = 'neutral' }) => {
  const toneClass = tone === 'positive' ? 'border-emerald-200 bg-emerald-50' :
                    tone === 'warning' ? 'border-amber-200 bg-amber-50' :
                    tone === 'negative' ? 'border-red-200 bg-red-50' :
                    'border-zinc-200 bg-white';
  return (
    <div className={`rounded-xl border ${toneClass} px-3 py-2.5`}>
      <div className="flex items-center justify-between text-zinc-500">
        <span className="text-[10.5px] font-medium uppercase tracking-wider">{label}</span>
        {Icon && <Icon size={13} weight="duotone" />}
      </div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-zinc-900">{value}</div>
    </div>
  );
};

const CustomerDrillSheet = ({ open, onOpenChange, customer }) => {
  const [loading, setLoading] = useState(false);
  const [engagement, setEngagement] = useState(null);
  const [intent, setIntent] = useState(null);
  const [profile, setProfile] = useState(null);

  const id = customer?.customerId || customer?._id || customer?.id || customer?.email;

  useEffect(() => {
    if (!open || !id) return;
    let alive = true;
    (async () => {
      setLoading(true);
      const [eng, intentRes, prof] = await Promise.all([
        safeGet(`/api/admin/engagement/customer/${encodeURIComponent(id)}`),
        safeGet(`/api/admin/intent/scores`, { customerId: id }),
        safeGet(`/api/customers/${encodeURIComponent(id)}`),
      ]);
      if (!alive) return;
      setEngagement(eng.data || null);
      const scores = intentRes.data?.scores || intentRes.data?.items || (Array.isArray(intentRes.data) ? intentRes.data : []);
      const own = scores.find?.(s => (s.customerId === id || s.email === customer?.email)) || scores[0] || intentRes.data || null;
      setIntent(own);
      setProfile(prof.data || null);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [open, id, customer?.email]);

  const intentScore = intent?.score ?? customer?.score;
  const band = riskBandClass(intentScore);

  // Build a synthetic activity series from engagement events if available
  const activitySeries = (() => {
    const events = engagement?.events || engagement?.history || [];
    if (!Array.isArray(events) || !events.length) return [];
    const byDay = {};
    events.forEach(e => {
      const day = (e.ts || e.timestamp || e.createdAt || '').slice(5, 10);
      if (!day) return;
      byDay[day] = (byDay[day] || 0) + 1;
    });
    return Object.entries(byDay).slice(-14).map(([date, count]) => ({ date, count }));
  })();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle data-testid="customer-drill-title">{profile?.name || customer?.name || customer?.email || 'Customer'}</SheetTitle>
          <SheetDescription>{profile?.email || customer?.email || ''}</SheetDescription>
        </SheetHeader>

        {loading ? <div className="mt-6"><InsightsLoading rows={4} /></div> : (
          <div className="mt-5 space-y-5">
            {/* Profile chips */}
            <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-600">
              {(profile?.phone || customer?.phone) && (
                <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><Phone size={12} weight="duotone" />{profile?.phone || customer?.phone}</span>
              )}
              {(profile?.email || customer?.email) && (
                <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><EnvelopeSimple size={12} weight="duotone" />{profile?.email || customer?.email}</span>
              )}
              {profile?.city && (
                <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><MapPin size={12} weight="duotone" />{profile.city}</span>
              )}
              {(profile?.createdAt || profile?.registeredAt) && (
                <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><Calendar size={12} weight="duotone" />Joined {(profile?.createdAt || profile?.registeredAt).slice(0,10)}</span>
              )}
              {profile?.tier && <MetricChip value={profile.tier} tone="info" />}
            </div>

            {/* Intent score */}
            <div className={`rounded-2xl border ${band.border} ${band.bg} p-4`} data-testid="customer-drill-intent-score">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Intent score</div>
                  <div className={`text-3xl font-semibold tabular-nums ${band.text}`}>{intentScore != null ? Math.round(intentScore) : '—'}</div>
                  <div className="text-[11px] text-zinc-600">{intent?.label || (intentScore >= 70 ? 'Hot — call today' : intentScore >= 40 ? 'Warm — nurture' : 'Cold — long-tail')}</div>
                </div>
                <Flame size={36} weight="duotone" className={band.text} />
              </div>
              {Array.isArray(intent?.signals) && intent.signals.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {intent.signals.slice(0, 5).map((s, i) => (
                    <li key={i} className="flex items-center justify-between rounded-md bg-white/60 px-2 py-1 text-[11px] text-zinc-700">
                      <span>{s.label || s.name || s.signal}</span>
                      <MetricChip value={`+${s.weight || s.value || 1}`} tone="info" />
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Engagement tiles */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="customer-drill-engagement-tiles">
              <StatTile icon={Heart}        label="Favorites" value={fmtCompact(engagement?.favoritesCount ?? customer?.favoritesCount ?? 0)} tone="negative" />
              <StatTile icon={Scales}       label="Compares"  value={fmtCompact(engagement?.comparesCount ?? customer?.comparesCount ?? 0)} tone="warning" />
              <StatTile icon={ShareNetwork} label="Shares"    value={fmtCompact(engagement?.sharesCount ?? customer?.sharesCount ?? 0)} tone="positive" />
              <StatTile icon={Eye}          label="Views"     value={fmtCompact(engagement?.viewsCount ?? engagement?.totalViews ?? 0)} />
            </div>

            {/* Activity timeseries */}
            {activitySeries.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="customer-drill-activity-chart">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Recent activity</div>
                <div className="h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={activitySeries} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#71717a' }} />
                      <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={28} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                      <Line type="monotone" dataKey="count" stroke="#18181b" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Favorited / compared vehicles */}
            {Array.isArray(engagement?.favoriteVehicles) && engagement.favoriteVehicles.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="customer-drill-favorites-list">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Favorited vehicles ({engagement.favoriteVehicles.length})</div>
                <ul className="divide-y divide-zinc-100">
                  {engagement.favoriteVehicles.slice(0, 8).map((v, i) => (
                    <li key={v.vin || i} className="flex items-center justify-between py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-900">{v.title || `${v.year || ''} ${v.make || ''} ${v.model || ''}`.trim() || v.vin}</p>
                        <p className="text-[11px] text-zinc-500">VIN {v.vin || '—'}</p>
                      </div>
                      <Star size={14} weight="fill" className="text-amber-400" />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!engagement && !intent && !profile && (
              <InsightsEmpty title="No drill-down data" hint="No engagement / intent records were returned for this customer." />
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default CustomerDrillSheet;
