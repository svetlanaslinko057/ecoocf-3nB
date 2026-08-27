/**
 * AlertDrillSheet.jsx — deep alert detail Sheet with linked-entity timeline.
 *
 * Triggered from RiskAlertsVertical → Critical Alerts Live Feed row click.
 *
 * Modular: receives `alert` and pulls extras:
 *   GET /api/alerts/{id}/timeline           — chronology of related events
 *   GET /api/alerts/{id}/related            — linked entity (deal/customer/manager)
 * Falls back gracefully if those endpoints are not yet wired — still shows the
 * raw alert with structured chips.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Lightning, Warning, Clock, Link, ArrowRight, ShieldCheck } from '@phosphor-icons/react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../ui/sheet';
import { safeGet, fmtMoney } from './insightsApi';
import { InsightsLoading, InsightsEmpty, MetricChip, SeverityDot } from './InsightsCard';

const severityTone = (s) => s === 'critical' ? 'negative' : s === 'high' ? 'warning' : s === 'medium' ? 'info' : 'neutral';

const AlertDrillSheet = ({ open, onOpenChange, alert, onResolve }) => {
  const [loading, setLoading] = useState(false);
  const [timeline, setTimeline] = useState([]);
  const [related, setRelated] = useState(null);

  const id = alert?._id || alert?.id;

  useEffect(() => {
    if (!open || !id) return;
    let alive = true;
    (async () => {
      setLoading(true);
      const [tl, rel] = await Promise.all([
        safeGet(`/api/alerts/${encodeURIComponent(id)}/timeline`),
        safeGet(`/api/alerts/${encodeURIComponent(id)}/related`),
      ]);
      if (!alive) return;
      const tlList = tl.data?.events || tl.data?.timeline || (Array.isArray(tl.data) ? tl.data : []);
      setTimeline(Array.isArray(tlList) ? tlList : []);
      setRelated(rel.data || null);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [open, id]);

  const severity = alert?.severity || alert?.level || 'medium';
  const tone = severityTone(severity);
  const ageDays = alert?.ageDays ?? alert?.age;
  const createdAt = alert?.createdAt || alert?.created_at || alert?.ts;

  const chips = useMemo(() => {
    const out = [];
    if (alert?.entity || alert?.entityType) out.push({ label: 'Entity', value: alert.entityType || alert.entity });
    if (alert?.entityId) out.push({ label: 'Entity ID', value: alert.entityId });
    if (alert?.owner || alert?.ownerEmail) out.push({ label: 'Owner', value: alert.ownerEmail || alert.owner });
    if (alert?.source) out.push({ label: 'Source', value: alert.source });
    if (alert?.slaBreached) out.push({ label: 'SLA', value: 'BREACHED', tone: 'negative' });
    return out;
  }, [alert]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle data-testid="alert-drill-title">{alert?.title || alert?.message || alert?.type || 'Alert'}</SheetTitle>
          <SheetDescription>{alert?.entity || alert?.entityType || alert?.source || '—'}</SheetDescription>
        </SheetHeader>

        {loading ? <div className="mt-6"><InsightsLoading rows={3} /></div> : (
          <div className="mt-5 space-y-5">
            {/* Severity banner */}
            <div className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white p-4" data-testid="alert-drill-severity-banner">
              <div className="flex items-center gap-3">
                <SeverityDot severity={severity} />
                <div>
                  <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Severity</div>
                  <div className="mt-0.5"><MetricChip value={severity} tone={tone} /></div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Age</div>
                <div className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-900">{ageDays != null ? `${ageDays}d` : '—'}</div>
              </div>
            </div>

            {/* Message */}
            {(alert?.message || alert?.description) && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4 text-sm text-zinc-700">
                {alert.message || alert.description}
              </div>
            )}

            {/* Metadata chips */}
            {chips.length > 0 && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4">
                <div className="mb-2 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">Metadata</div>
                <div className="flex flex-wrap gap-2">
                  {chips.map((c, i) => (
                    <div key={i} className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-xs">
                      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{c.label}</div>
                      <div className="font-medium text-zinc-900">{c.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Linked entity */}
            {related && (
              <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="alert-drill-related">
                <div className="mb-2 flex items-center gap-1 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">
                  <Link size={11} /> Linked entity
                </div>
                <div className="text-sm font-medium text-zinc-900">{related.title || related.name || related.email || related._id}</div>
                {related.amount != null && <div className="mt-1 text-xs text-zinc-600">Amount: {fmtMoney(related.amount)}</div>}
                {related.status && <MetricChip className="mt-2" value={related.status} tone={related.status === 'paid' ? 'positive' : 'neutral'} />}
              </div>
            )}

            {/* Timeline */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-4" data-testid="alert-drill-timeline">
              <div className="mb-2 flex items-center gap-1 text-[10.5px] font-medium uppercase tracking-wider text-zinc-500">
                <Clock size={11} /> Timeline
              </div>
              {timeline.length === 0 ? (
                <InsightsEmpty title="No timeline events" hint={createdAt ? `Created at ${String(createdAt).slice(0, 16)}` : undefined} />
              ) : (
                <ol className="relative space-y-3 border-l-2 border-zinc-100 pl-4">
                  {timeline.slice(0, 20).map((e, i) => (
                    <li key={i} className="relative">
                      <span className="absolute -left-[22px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-zinc-400" />
                      <div className="text-sm font-medium text-zinc-900">{e.title || e.type || e.event || 'event'}</div>
                      <div className="text-[11px] text-zinc-500">{e.actor || ''} · {(e.ts || e.timestamp || e.createdAt || '').slice(0, 16)}</div>
                      {e.message && <div className="mt-1 text-xs text-zinc-600">{e.message}</div>}
                    </li>
                  ))}
                </ol>
              )}
            </div>

            {/* Actions */}
            {onResolve && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => { onResolve(alert); onOpenChange?.(false); }}
                  className="inline-flex items-center gap-1 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
                  data-testid="alert-drill-resolve-button"
                >
                  <ShieldCheck size={12} weight="bold" /> Mark as resolved
                </button>
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
};

export default AlertDrillSheet;
