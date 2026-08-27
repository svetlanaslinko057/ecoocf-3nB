/**
 * DealDrillSheet.jsx — opens a right-side Sheet with deep deal pipeline detail.
 *
 * Triggered from PipelineVertical → Deals sub-tab (clicking a bottleneck or
 * cycle-time row drills into specific deals stuck at that stage).
 *
 * Modular: zero coupling to PipelineVertical internals — receives a `deal`
 * (or a stage descriptor) prop and self-fetches enrichment data.
 *
 * Data sources (parallel, best-effort):
 *   GET /api/deals/{id}                 → core deal profile
 *   GET /api/journey/timeline?dealId=…  → full stage-by-stage timeline
 *   GET /api/deals/{id}/activity        → contacts / calls / emails timeline
 */
import React, { useEffect, useState } from 'react';
import { CurrencyDollar, Clock, Target, ArrowRight, UsersThree, Receipt, ChartLineUp, MapPin } from '@phosphor-icons/react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../ui/sheet';
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';
import { safeGet, fmtMoney, fmtCompact, fmtDuration, fmtPct } from './insightsApi';
import { InsightsLoading, InsightsEmpty, MetricChip } from './InsightsCard';

const KpiTile = ({ icon: Icon, label, value, tone = 'neutral' }) => {
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

/** Stage chips with current-stage highlight. */
const StageRibbon = ({ timeline = [], currentStage }) => (
  <div className="flex flex-wrap items-center gap-1.5" data-testid="deal-drill-stage-ribbon">
    {timeline.map((s, i) => {
      const active = s.stage === currentStage || s.name === currentStage;
      const past = s.completedAt || s.exitedAt;
      const cls = active ? 'bg-zinc-900 text-white border-zinc-900' :
                  past ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                  'bg-zinc-50 text-zinc-500 border-zinc-200';
      return (
        <span key={i} className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium ${cls}`}>
          {s.stage || s.name || `Stage ${i+1}`}
          {s.avgDays != null && <span className="opacity-70">· {fmtDuration(s.avgDays)}</span>}
        </span>
      );
    })}
  </div>
);

const DealDrillSheet = ({ open, onOpenChange, deal, stage }) => {
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [activity, setActivity] = useState([]);

  const id = deal?._id || deal?.id || deal?.dealId;

  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      setLoading(true);
      const [prof, tl, act] = await Promise.all([
        id ? safeGet(`/api/deals/${encodeURIComponent(id)}`) : Promise.resolve({ data: null }),
        safeGet(`/api/journey/timeline`, id ? { dealId: id } : (stage ? { stage } : undefined)),
        id ? safeGet(`/api/deals/${encodeURIComponent(id)}/activity`) : Promise.resolve({ data: null }),
      ]);
      if (!alive) return;
      setProfile(prof.data || deal || null);
      const stages = tl.data?.stages || tl.data?.timeline || (Array.isArray(tl.data) ? tl.data : []);
      setTimeline(Array.isArray(stages) ? stages : []);
      const acts = act.data?.events || act.data?.activity || (Array.isArray(act.data) ? act.data : []);
      setActivity(Array.isArray(acts) ? acts : []);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [open, id, stage, deal]);

  // Derive a tiny activity-volume series from events (last 14 days)
  const activitySeries = (() => {
    if (!activity.length) return [];
    const byDay = {};
    activity.forEach(e => {
      const day = (e.ts || e.timestamp || e.createdAt || '').slice(5, 10);
      if (!day) return;
      byDay[day] = (byDay[day] || 0) + 1;
    });
    return Object.entries(byDay).slice(-14).map(([date, count]) => ({ date, count }));
  })();

  const amount = profile?.amount ?? profile?.totalAmount ?? profile?.dealAmount ?? deal?.amount;
  const currentStage = profile?.stage || profile?.currentStage || deal?.stage || stage;
  const ageDays = profile?.ageDays ?? deal?.ageDays;
  const cycleDays = profile?.cycleDays ?? profile?.totalDays;
  const status = profile?.status || deal?.status || (currentStage === 'closed_won' ? 'won' : currentStage === 'closed_lost' ? 'lost' : 'open');

  const title = profile?.title || profile?.dealTitle || deal?.title || (stage ? `Deals stuck at "${stage}"` : `Deal ${id || ''}`);
  const subtitle = profile?.customerName || profile?.customer?.name || deal?.customerName || (currentStage ? `Stage: ${currentStage}` : '');

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle data-testid="deal-drill-title">{title}</SheetTitle>
          <SheetDescription>{subtitle}</SheetDescription>
        </SheetHeader>

        {loading ? <div className="mt-6"><InsightsLoading rows={4} /></div> : (
          <div className="mt-5 space-y-5">
            {/* Status + amount header */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Status</div>
                  <div className="mt-1 flex items-center gap-2">
                    <MetricChip value={status} tone={status==='won'||status==='closed_won'?'positive':status==='lost'||status==='closed_lost'?'negative':'info'} />
                    {currentStage && <span className="text-sm text-zinc-700">at <span className="font-medium">{currentStage}</span></span>}
                  </div>
                </div>
                {amount != null && (
                  <div className="text-right">
                    <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Amount</div>
                    <div className="text-2xl font-semibold tabular-nums text-zinc-900">{fmtMoney(amount)}</div>
                  </div>
                )}
              </div>
            </div>

            {/* KPI tiles */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="deal-drill-kpis">
              <KpiTile icon={Clock}        label="Age"          value={ageDays ? `${ageDays}d` : '—'} tone={ageDays > 30 ? 'warning' : 'neutral'} />
              <KpiTile icon={ChartLineUp}  label="Cycle"        value={cycleDays ? `${cycleDays}d` : '—'} />
              <KpiTile icon={Target}       label="Probability"  value={profile?.probability != null ? fmtPct(profile.probability) : '—'} tone={profile?.probability >= 60 ? 'positive' : profile?.probability >= 30 ? 'warning' : 'neutral'} />
              <KpiTile icon={UsersThree}   label="Touches"      value={fmtCompact(activity.length)} />
            </div>

            {/* Stage ribbon / timeline */}
            {timeline.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="deal-drill-timeline">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Journey timeline</span>
                  {profile?.bottleneck && <MetricChip value="Bottleneck" tone="warning" />}
                </div>
                <StageRibbon timeline={timeline} currentStage={currentStage} />
                <div className="mt-3 space-y-1 text-[11px] text-zinc-600">
                  {timeline.slice(0, 8).map((s, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md bg-zinc-50 px-2 py-1.5">
                      <span className="flex items-center gap-1"><ArrowRight size={11} className="opacity-50" />{s.stage || s.name}</span>
                      <span className="tabular-nums">{s.avgDays != null ? `avg ${fmtDuration(s.avgDays)}` : ''}{s.count != null ? ` · ${s.count} deals` : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Activity time-series */}
            {activitySeries.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="deal-drill-activity-chart">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Activity volume · last days</div>
                <div className="h-28">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={activitySeries} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#71717a' }} />
                      <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={28} allowDecimals={false} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                      <Line type="monotone" dataKey="count" stroke="#18181b" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Activity feed */}
            {activity.length > 0 ? (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="deal-drill-activity-list">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Recent activity ({activity.length})</span>
                </div>
                <ul className="divide-y divide-zinc-100">
                  {activity.slice(0, 12).map((e, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-zinc-900">{e.title || e.type || e.eventType || 'event'}</p>
                        <p className="text-[11px] text-zinc-500">{e.actor || e.userEmail || ''}</p>
                      </div>
                      <span className="shrink-0 text-[11px] tabular-nums text-zinc-500">{(e.ts || e.timestamp || e.createdAt || '').slice(0, 16)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              !timeline.length && !profile && <InsightsEmpty title="No deep deal data" hint="No timeline / activity records returned for this deal or stage." />
            )}

            {/* Owner / location */}
            {(profile?.ownerEmail || profile?.owner || profile?.location || profile?.destination) && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Owner & route</div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-700">
                  {(profile.ownerEmail || profile.owner) && <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><UsersThree size={12} weight="duotone" />{profile.ownerEmail || profile.owner}</span>}
                  {profile.location && <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><MapPin size={12} weight="duotone" />{profile.location}</span>}
                  {profile.destination && <span className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-2 py-1"><MapPin size={12} weight="duotone" />→ {profile.destination}</span>}
                </div>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default DealDrillSheet;
