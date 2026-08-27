/**
 * RiskAlertsVertical.jsx — the DEEPEST vertical (user's pain point: 'risk was just a few cards').
 *
 * Sections (in scroll order):
 *  1. Risk Overview — composite score gauge + time-series + risk drivers list
 *  2. Risk by Manager/Team/Deal — sub-tabs with risk ranking table
 *  3. Critical Alerts Live Feed — severity-coded cells, inline filters
 *  4. Escalation Queue — full-width table with row-state colouring
 *  5. Unified Stuck Items — segmented (Leads · Invoices · Shipments)
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { ResponsiveContainer, RadialBarChart, RadialBar, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, BarChart, Bar } from 'recharts';
import { Lightning, Shield, Warning, Clock, ArrowRight, CheckCircle, Snowflake, ArrowsClockwise } from '@phosphor-icons/react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../../ui/sheet';
import { API_URL } from '../../../App';
import { InsightsCard, InsightsSection, InsightsLoading, InsightsEmpty, MetricChip, SeverityDot } from '../shared/InsightsCard';
import { safeGet, fmtCompact, fmtMoney, riskBandClass } from '../shared/insightsApi';
import ReassignPopover from '../shared/ReassignPopover';
import ManagerDrillSheet from '../shared/ManagerDrillSheet';
import AlertDrillSheet from '../shared/AlertDrillSheet';
import { useLang } from '../../../i18n';

const SEVERITIES = ['critical', 'high', 'medium', 'low'];

function RiskOverviewSection({ data }) {
  const { t } = useLang();
  const score = data?.score ?? 0;
  const band = riskBandClass(score);
  const radialData = [{ name: 'Risk', value: score, fill: score >= 70 ? '#dc2626' : score >= 40 ? '#d97706' : '#10b981' }];
  const drivers = data?.drivers || [];
  const series = data?.timeseries || [];
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <InsightsCard className="lg:col-span-7" title={<span className="flex items-center gap-2 text-sm font-medium"><Shield size={14} weight="duotone" /> {t('ins_card_composite_score')}</span>} tip={t('ins_tip_risk_overview')} testId="insights-risk-overview-card">
        <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-2">
          <div className="relative h-48">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart innerRadius="68%" outerRadius="100%" data={radialData} startAngle={210} endAngle={-30}>
                <RadialBar background={{ fill: '#f4f4f5' }} dataKey="value" cornerRadius={6} />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className={`text-3xl font-semibold tabular-nums ${band.text}`} data-testid="insights-risk-composite-score">{score}</span>
              <span className="text-[11px] uppercase tracking-wider text-zinc-500">{score < 40 ? t('ins_band_healthy') : score < 70 ? t('ins_band_watch') : t('ins_band_critical')}</span>
            </div>
          </div>
          <div className="h-48" data-testid="insights-risk-timeseries-chart">
            <p className="mb-1 text-[11px] uppercase tracking-wider text-zinc-500">{t('ins_chart_risk_14d')}</p>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 4, right: 8, left: -16, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#71717a' }} />
                <YAxis tick={{ fontSize: 10, fill: '#71717a' }} width={28} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Line type="monotone" dataKey="score" stroke="#18181b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </InsightsCard>

      <InsightsCard className="lg:col-span-5" title={<span className="flex items-center gap-2 text-sm font-medium"><Warning size={14} weight="duotone" /> Top Risk Drivers</span>} testId="insights-risk-drivers-list">
        {drivers.length === 0 ? (
          <InsightsEmpty title="No active risk drivers" hint="You are in the clear. Keep an eye on Alerts feed below." />
        ) : (
          <ul className="space-y-2">
            {drivers.map((d, i) => (
              <li key={i} className="flex items-center justify-between gap-3 rounded-lg border border-zinc-100 px-3 py-2 hover:bg-zinc-50">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-900">{d.label}</p>
                  <p className="text-[11px] text-zinc-500">{d.hint || d.detail}</p>
                </div>
                <MetricChip value={fmtCompact(d.count)} tone={d.severity === 'critical' ? 'negative' : d.severity === 'high' ? 'warning' : 'neutral'} />
              </li>
            ))}
          </ul>
        )}
      </InsightsCard>
    </div>
  );
}

function RiskByEntitySection({ entities, onOpenManager }) {
  const { t } = useLang();
  const [tab, setTab] = useState('manager');
  const rows = entities[tab] || [];
  const entityLabels = { manager: t('ins_risk_entity_manager'), team: t('ins_risk_entity_team'), deal: t('ins_risk_entity_deal') };
  return (
    <InsightsCard title={<div className="flex items-center gap-3"><span className="text-sm font-medium">{t('ins_sec_risk_by_entity')}</span><div className="flex rounded-lg bg-zinc-100 p-0.5">{['manager','team','deal'].map(k => (
      <button key={k} type="button" onClick={() => setTab(k)} data-testid={`insights-risk-entity-tab-${k}`}
        className={`px-3 py-1 text-xs font-medium ${tab===k?'rounded-md bg-white text-zinc-900 shadow-sm':'text-zinc-600'}`}>{entityLabels[k]}</button>
    ))}</div></div>} testId="insights-risk-by-entity-card">
      {rows.length === 0 ? (
        <InsightsEmpty title={`No ${tab} risk data`} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="insights-risk-entity-table">
            <thead>
              <tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
                <th className="py-2 pr-3 text-left font-medium">Name</th>
                <th className="py-2 pr-3 text-right font-medium">Risk</th>
                <th className="py-2 pr-3 text-right font-medium">Open Alerts</th>
                <th className="py-2 pr-3 text-right font-medium">Stale / Overdue</th>
                <th className="py-2 pr-3 text-right font-medium">Top driver</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const band = riskBandClass(r.score);
                return (
                  <tr key={r.id || i} className="cursor-pointer border-b border-zinc-50 hover:bg-zinc-50" onClick={() => onOpenManager?.(r)} data-testid={`insights-risk-entity-row-${i}`}>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <span className={`inline-block h-6 w-1 rounded ${band.bg.replace('bg-','bg-')}`} />
                        <span className="truncate font-medium text-zinc-900">{r.name}</span>
                      </div>
                    </td>
                    <td className={`py-2 pr-3 text-right font-semibold tabular-nums ${band.text}`}>{r.score ?? '—'}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-zinc-700">{r.openAlerts ?? '—'}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-zinc-700">{(r.staleLeads ?? 0) + (r.overdue ?? 0)}</td>
                    <td className="py-2 pr-3 text-right text-xs text-zinc-500">{r.topDriver || '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </InsightsCard>
  );
}

function CriticalAlertsFeed({ alerts, onOpen, severity, setSeverity, onRefresh }) {
  const filtered = severity === 'all' ? alerts : alerts.filter(a => (a.severity || 'medium') === severity);
  return (
    <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Lightning size={14} weight="duotone" /> Critical Alerts · Live Feed</span>}
      actions={
        <div className="flex items-center gap-1" data-testid="insights-alerts-filters">
          {['all', ...SEVERITIES].map(s => (
            <button key={s} onClick={() => setSeverity(s)} className={`rounded-md px-2 py-1 text-[11px] font-medium uppercase tracking-wider ${severity===s ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'}`}>{s}</button>
          ))}
          <button onClick={onRefresh} className="ml-2 inline-flex h-7 w-7 items-center justify-center rounded-md border border-zinc-200 text-zinc-600 hover:bg-zinc-50" data-testid="insights-alerts-refresh-button" title="Refresh"><ArrowsClockwise size={14} /></button>
        </div>
      }
      testId="insights-critical-alerts-card"
      padded={false}
    >
      <div data-testid="insights-alerts-feed" className="divide-y divide-zinc-100">
        {filtered.length === 0 ? (
          <InsightsEmpty title="No alerts match current filters" />
        ) : filtered.slice(0, 50).map((a, i) => {
          const sev = a.severity || 'medium';
          const rail = sev === 'critical' ? 'bg-red-500' : sev === 'high' ? 'bg-amber-500' : sev === 'medium' ? 'bg-sky-500' : 'bg-zinc-400';
          return (
            <button key={a._id || a.id || i} type="button" onClick={() => onOpen?.(a)}
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-zinc-50">
              <span className={`mt-0.5 inline-block h-9 w-1 shrink-0 rounded-sm ${rail}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <SeverityDot severity={sev} />
                  <p className="truncate text-sm font-medium text-zinc-900">{a.title || a.message || 'Alert'}</p>
                </div>
                <p className="mt-0.5 truncate text-xs text-zinc-500">{a.entity || a.entityType || a.source || ''} · {a.owner || a.ownerEmail || 'unassigned'} · {a.createdAt || a.created_at || a.ts || ''}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <MetricChip value={a.age || a.ageDays ? `${a.ageDays}d` : ''} tone={sev === 'critical' ? 'negative' : sev === 'high' ? 'warning' : 'neutral'} />
                {a.slaBreached ? <MetricChip value="SLA" tone="negative" /> : null}
              </div>
            </button>
          );
        })}
      </div>
    </InsightsCard>
  );
}

function EscalationQueue({ escalations, onOpen, onAction, onBulkAction }) {
  const { t } = useLang();
  const [selected, setSelected] = useState(new Set());
  const [bulkReassignOpen, setBulkReassignOpen] = useState(false);
  const [bulkReassignOwner, setBulkReassignOwner] = useState('');

  const toggleOne = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const allIds = escalations.map(e => e._id || e.id).filter(Boolean);
  const allSelected = allIds.length > 0 && allIds.every(id => selected.has(id));
  const toggleAll = () => {
    setSelected(prev => {
      if (allSelected) return new Set();
      return new Set(allIds);
    });
  };
  const selectedItems = escalations.filter(e => selected.has(e._id || e.id));
  const hasSelection = selectedItems.length > 0;

  const handleBulk = async (action, extra) => {
    await onBulkAction?.(action, selectedItems, extra);
    setSelected(new Set());
  };

  return (
    <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Warning size={14} weight="duotone" /> {t('ins_sec_escalation_queue')}</span>} padded={false} testId="insights-escalation-queue-card"
      actions={hasSelection ? (
        <div className="flex items-center gap-1.5" data-testid="insights-escalation-bulk-actions">
          <span className="text-[11px] font-medium text-zinc-700">{selectedItems.length} {t('ins_selected')}</span>
          <button onClick={() => handleBulk('resolve')} className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-emerald-700" data-testid="insights-escalation-bulk-resolve">
            <CheckCircle size={11} weight="bold" /> {t('ins_bulk_resolve')}
          </button>
          <button onClick={() => handleBulk('snooze')} className="inline-flex items-center gap-1 rounded-md bg-sky-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-sky-700" data-testid="insights-escalation-bulk-snooze">
            <Snowflake size={11} weight="bold" /> {t('ins_bulk_snooze')}
          </button>
          <span className="relative">
            <button onClick={() => setBulkReassignOpen(v => !v)} className="inline-flex items-center gap-1 rounded-md bg-zinc-900 px-2 py-1 text-[11px] font-medium text-white hover:bg-zinc-800" data-testid="insights-escalation-bulk-reassign-trigger">
              <ArrowsClockwise size={11} weight="bold" /> {t('ins_bulk_reassign')}
            </button>
            {bulkReassignOpen && (
              <span className="absolute right-0 top-full z-50 mt-1 inline-flex w-64 flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-3 shadow-lg" data-testid="insights-escalation-bulk-reassign-panel">
                <span className="text-xs font-medium text-zinc-900">{t('ins_reassign_to')} {selectedItems.length}</span>
                <input
                  value={bulkReassignOwner}
                  onChange={(e) => setBulkReassignOwner(e.target.value)}
                  placeholder="manager@bibi.cars"
                  className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-900 focus:border-zinc-400 focus:outline-none"
                  data-testid="insights-escalation-bulk-reassign-input"
                  autoFocus
                />
                <span className="flex justify-end gap-1">
                  <button type="button" onClick={() => { setBulkReassignOpen(false); setBulkReassignOwner(''); }} className="rounded-md px-2 py-1 text-[11px] font-medium text-zinc-600 hover:bg-zinc-100">{t('ins_cancel')}</button>
                  <button
                    type="button"
                    disabled={!bulkReassignOwner.trim()}
                    onClick={async () => { await handleBulk('reassign', { owner: bulkReassignOwner.trim() }); setBulkReassignOpen(false); setBulkReassignOwner(''); }}
                    className="inline-flex items-center gap-1 rounded-md bg-zinc-900 px-2 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                    data-testid="insights-escalation-bulk-reassign-confirm"
                  ><CheckCircle size={11} weight="bold" /> {t('ins_confirm')}</button>
                </span>
              </span>
            )}
          </span>
          <button onClick={() => setSelected(new Set())} className="rounded-md border border-zinc-200 px-2 py-1 text-[11px] text-zinc-600 hover:bg-zinc-50">{t('ins_clear')}</button>
        </div>
      ) : null}
    >
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-sm" data-testid="insights-escalation-queue-table">
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
              <th className="w-8 px-2 py-2 text-left font-medium">
                <input type="checkbox" checked={allSelected} onChange={toggleAll} className="h-3.5 w-3.5 cursor-pointer accent-zinc-900" data-testid="insights-escalation-select-all" aria-label="Select all" />
              </th>
              <th className="px-4 py-2 text-left font-medium">Priority</th>
              <th className="px-4 py-2 text-left font-medium">Item</th>
              <th className="px-4 py-2 text-left font-medium">Owner</th>
              <th className="px-4 py-2 text-left font-medium">Queue</th>
              <th className="px-4 py-2 text-right font-medium">Age</th>
              <th className="px-4 py-2 text-right font-medium">SLA</th>
              <th className="px-4 py-2 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {escalations.length === 0 ? (
              <tr><td colSpan={8}><InsightsEmpty title="Escalation queue is empty" hint="Nothing requires escalation. Maintain SLAs and this stays clear." /></td></tr>
            ) : escalations.map((e, i) => {
              const id = e._id || e.id;
              const breached = e.slaBreached || e.breached;
              const dueSoon = e.dueSoon;
              const isSel = selected.has(id);
              const rowBg = isSel ? 'bg-zinc-50' : breached ? 'border-l-4 border-l-red-500 bg-red-50/50' : dueSoon ? 'border-l-4 border-l-amber-500 bg-amber-50/50' : '';
              return (
                <tr key={id || i} className={`border-b border-zinc-50 hover:bg-zinc-50 ${rowBg}`}>
                  <td className="w-8 px-2 py-2"><input type="checkbox" checked={isSel} onChange={() => toggleOne(id)} onClick={(ev) => ev.stopPropagation()} className="h-3.5 w-3.5 cursor-pointer accent-zinc-900" data-testid={`insights-escalation-select-${i}`} aria-label="Select row" /></td>
                  <td className="px-4 py-2"><SeverityDot severity={e.severity || (breached?'critical':'medium')} /></td>
                  <td className="px-4 py-2"><button type="button" onClick={() => onOpen?.(e)} className="text-left font-medium text-zinc-900 hover:underline">{e.title || e.subject || e.itemTitle || e.message || e.type || '—'}</button></td>
                  <td className="px-4 py-2 text-zinc-700">{e.owner || e.ownerEmail || e.assignedTo || '—'}</td>
                  <td className="px-4 py-2 text-zinc-600">{e.queue || e.type || '—'}</td>
                  <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{e.ageDays ?? e.age ?? '—'}</td>
                  <td className="px-4 py-2 text-right">{breached ? <MetricChip value="BREACHED" tone="negative" /> : dueSoon ? <MetricChip value="Due soon" tone="warning" /> : <MetricChip value="On track" tone="positive" />}</td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-flex items-center gap-1">
                      <button onClick={() => onAction?.('resolve', e)} className="rounded-md border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50" data-testid={`insights-escalation-resolve-${i}`}><CheckCircle size={11} className="mr-0.5 inline" />Resolve</button>
                      <button onClick={() => onAction?.('snooze', e)} className="rounded-md border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50" data-testid={`insights-escalation-snooze-${i}`}><Snowflake size={11} className="mr-0.5 inline" />Snooze</button>
                      <ReassignPopover
                        testId={`insights-escalation-reassign-${i}`}
                        currentOwner={e.owner || e.ownerEmail || e.assignedTo}
                        onSubmit={(newOwner) => onAction?.('reassign', e, { owner: newOwner })}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </InsightsCard>
  );
}

function StuckItems({ items }) {
  const { t } = useLang();
  const [seg, setSeg] = useState('all');
  const list = useMemo(() => {
    if (seg === 'all') return items;
    return items.filter(i => i.kind === seg);
  }, [items, seg]);
  return (
    <InsightsCard title={<span className="flex items-center gap-2 text-sm font-medium"><Clock size={14} weight="duotone" /> {t('ins_sec_stuck_items')}</span>}
      actions={
        <div className="flex rounded-lg bg-zinc-100 p-0.5" data-testid="insights-stuck-items-segmented">
          {[{k:'all',l:'All'},{k:'lead',l:'Stale Leads'},{k:'invoice',l:'Overdue Invoices'},{k:'shipment',l:'Stalled Shipments'}].map(s => (
            <button key={s.k} onClick={() => setSeg(s.k)} className={`px-3 py-1 text-xs font-medium ${seg===s.k?'rounded-md bg-white text-zinc-900 shadow-sm':'text-zinc-600'}`}>{s.l} {items.filter(i=>s.k==='all'||i.kind===s.k).length}</button>
          ))}
        </div>
      }
      padded={false}
      testId="insights-stuck-items-card"
    >
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full text-sm" data-testid="insights-stuck-items-table">
          <thead className="sticky top-0 z-10 bg-white">
            <tr className="border-b border-zinc-100 text-[11px] uppercase tracking-wider text-zinc-500">
              <th className="px-4 py-2 text-left font-medium">Type</th>
              <th className="px-4 py-2 text-left font-medium">Item</th>
              <th className="px-4 py-2 text-left font-medium">Owner</th>
              <th className="px-4 py-2 text-right font-medium">Amount</th>
              <th className="px-4 py-2 text-right font-medium">Age</th>
              <th className="px-4 py-2 text-left font-medium">Last update</th>
            </tr>
          </thead>
          <tbody>
            {list.length === 0 ? (
              <tr><td colSpan={6}><InsightsEmpty title="Nothing stuck — keep it up." /></td></tr>
            ) : list.map((it, i) => (
              <tr key={i} className="border-b border-zinc-50 hover:bg-zinc-50">
                <td className="px-4 py-2"><MetricChip value={it.kindLabel || it.kind} tone={it.kind==='invoice'?'warning':it.kind==='shipment'?'info':'neutral'} /></td>
                <td className="px-4 py-2 font-medium text-zinc-900">{it.title || '—'}</td>
                <td className="px-4 py-2 text-zinc-700">{it.owner || '—'}</td>
                <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{it.amount ? fmtMoney(it.amount) : '—'}</td>
                <td className="px-4 py-2 text-right tabular-nums text-zinc-700">{it.ageDays ? `${it.ageDays}d` : '—'}</td>
                <td className="px-4 py-2 text-zinc-500">{it.lastUpdate || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </InsightsCard>
  );
}

const RiskAlertsVertical = ({ scope }) => {
  const { t } = useLang();
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState({ score: 0, drivers: [], timeseries: [] });
  const [entities, setEntities] = useState({ manager: [], team: [], deal: [] });
  const [alerts, setAlerts] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [stuck, setStuck] = useState([]);
  const [severity, setSeverity] = useState('all');
  const [openItem, setOpenItem] = useState(null);
  const [drillManager, setDrillManager] = useState(null);
  const [drillAlert, setDrillAlert] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [cr, esc, escStats, kpiLb, kpiAlerts, ownerDash, teamStale, teamOverdue, teamShipping] = await Promise.all([
        safeGet('/api/alerts/critical', { limit: 100 }),
        safeGet('/api/escalations'),
        safeGet('/api/escalations/stats'),
        safeGet('/api/admin/kpi/leaderboard'),
        safeGet('/api/admin/kpi/alerts'),
        safeGet('/api/owner-dashboard'),
        safeGet('/api/team/leads/stale'),
        safeGet('/api/team/payments/overdue'),
        safeGet('/api/team/shipping/stalled'),
      ]);
      if (!alive) return;

      // Alerts feed: combine alerts/critical + ops_audit critical
      const crAlerts = Array.isArray(cr.data?.alerts) ? cr.data.alerts : Array.isArray(cr.data) ? cr.data : [];
      const opsAlerts = Array.isArray(kpiAlerts.data?.alerts) ? kpiAlerts.data.alerts : [];
      const allAlerts = [...crAlerts, ...opsAlerts].map(a => ({
        ...a,
        severity: a.severity || a.level || 'medium',
        title: a.title || a.message || a.type || 'Alert',
        entity: a.entity || a.entityType || a.kind,
      }));

      const escList = Array.isArray(esc.data) ? esc.data : Array.isArray(esc.data?.items) ? esc.data.items : [];
      const escMapped = escList.map(e => ({
        ...e,
        severity: e.severity || (e.priority === 'high' ? 'high' : 'medium'),
        ageDays: e.ageDays ?? (e.createdAt ? Math.max(0, Math.round((Date.now() - new Date(e.createdAt).getTime())/86400000)) : null),
        slaBreached: e.slaBreached || e.breached || (e.ageDays > (e.slaDays || 3)),
      }));

      // Build entity risk rankings from KPI leaderboard
      const lb = (kpiLb.data?.managers || []);
      const managerRisk = lb.map(m => {
        const conv = Number(m.score || 0);
        const baseRisk = Math.max(0, Math.min(100, 100 - conv));
        return {
          id: m.id,
          email: m.email,                 // forward to ManagerDrillSheet for scoped queries
          ownerEmail: m.email,
          role: m.role,
          name: m.name || m.email || 'Manager',
          score: Math.round(baseRisk),
          openAlerts: allAlerts.filter(a => (a.owner || a.ownerEmail) === m.email).length,
          staleLeads: 0,
          overdue: 0,
          topDriver: conv < 20 ? 'Low conversion' : conv < 50 ? 'Below average' : 'OK',
        };
      }).sort((a,b) => b.score - a.score);

      // Drivers
      const drivers = [];
      const staleArr = Array.isArray(teamStale.data) ? teamStale.data : teamStale.data?.items || [];
      if (staleArr.length) drivers.push({ label: 'Stale leads', detail: 'No touch in 7+ days', count: staleArr.length, severity: staleArr.length > 10 ? 'critical' : 'high' });
      const overdueArr = Array.isArray(teamOverdue.data) ? teamOverdue.data : teamOverdue.data?.items || [];
      if (overdueArr.length) drivers.push({ label: 'Overdue invoices', detail: 'Past due date', count: overdueArr.length, severity: 'critical' });
      const shippingArr = Array.isArray(teamShipping.data) ? teamShipping.data : teamShipping.data?.items || [];
      if (shippingArr.length) drivers.push({ label: 'Stalled shipments', detail: 'No update in 5+ days', count: shippingArr.length, severity: 'high' });
      const escOpen = escMapped.filter(e => !e.resolved).length;
      if (escOpen) drivers.push({ label: 'Open escalations', detail: 'Awaiting action', count: escOpen, severity: 'critical' });
      if (allAlerts.length) drivers.push({ label: 'Active alerts', detail: 'Critical + ops audit', count: allAlerts.length, severity: 'high' });

      // Build a 14-day risk-score time-series from escalation creation dates if possible
      const today = new Date();
      const ts = Array.from({ length: 14 }, (_, i) => {
        const d = new Date(today); d.setDate(d.getDate() - (13 - i));
        const key = d.toISOString().slice(5, 10);
        const sameDay = escMapped.filter(e => (e.createdAt || '').slice(0,10) === d.toISOString().slice(0,10)).length;
        return { date: key, score: Math.min(100, sameDay * 8 + Math.max(0, drivers.reduce((a,b)=>a+b.count,0) * 0.4)) };
      });

      // Composite score
      const compositeScore = Math.min(100, Math.round(
        (allAlerts.length * 3) +
        (escOpen * 4) +
        (staleArr.length * 1) +
        (overdueArr.length * 2) +
        (shippingArr.length * 1.5)
      ));

      // Stuck items unified
      const stuckList = [
        ...staleArr.map(l => ({ kind: 'lead', kindLabel: 'Stale Lead', title: l.title || l.name || l.email || l.phone || `Lead ${l._id || l.id}`, owner: l.owner || l.managerEmail || l.ownerEmail, ageDays: l.ageDays, lastUpdate: l.lastUpdate || l.updatedAt })),
        ...overdueArr.map(p => ({ kind: 'invoice', kindLabel: 'Overdue Invoice', title: p.title || p.invoiceNumber || p.dealTitle || `Invoice ${p._id || p.id}`, owner: p.owner || p.managerEmail || p.ownerEmail, amount: p.amount, ageDays: p.ageDays || p.daysOverdue, lastUpdate: p.lastUpdate || p.updatedAt })),
        ...shippingArr.map(s => ({ kind: 'shipment', kindLabel: 'Stalled Shipment', title: s.title || s.vesselName || s.shipmentId || `Shipment ${s._id || s.id}`, owner: s.owner || s.managerEmail, ageDays: s.ageDays || s.daysStalled, lastUpdate: s.lastUpdate || s.updatedAt })),
      ];

      setOverview({ score: compositeScore, drivers, timeseries: ts });
      setEntities({ manager: managerRisk, team: [], deal: [] });
      setAlerts(allAlerts);
      setEscalations(escMapped);
      setStuck(stuckList);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [refreshTick, scope]);

  const handleAction = async (action, item, extra = {}) => {
    try {
      const id = item._id || item.id;
      if (!id) return;
      if (action === 'resolve') {
        await axios.post(`${API_URL}/api/escalations/${id}/resolve`, { actor: 'admin' });
        setEscalations(prev => prev.filter(e => (e._id || e.id) !== id));
      } else if (action === 'snooze') {
        await axios.post(`${API_URL}/api/escalations/${id}/snooze`, { hours: 4, actor: 'admin' });
        // Optimistic: remove from queue — worker will surface it again when due
        setEscalations(prev => prev.filter(e => (e._id || e.id) !== id));
      } else if (action === 'reassign') {
        const newOwner = extra?.owner;
        if (!newOwner) return;
        await axios.post(`${API_URL}/api/escalations/${id}/reassign`, { owner: newOwner, actor: 'admin' });
        setEscalations(prev => prev.map(e => (e._id || e.id) === id
          ? { ...e, owner: newOwner, ownerEmail: newOwner, assignedTo: newOwner }
          : e
        ));
      }
    } catch (err) {
      // surface a soft inline error — full toast system is out of scope here
      console.error('[insights] escalation action failed', action, err);
    }
  };

  // Bulk action handler — sequentially calls the per-item endpoint.
  // Sequential rather than Promise.all to avoid hammering the API and to
  // keep optimistic UI updates predictable.
  const handleBulkAction = async (action, items, extra = {}) => {
    if (!items?.length) return;
    const ids = items.map(it => it._id || it.id).filter(Boolean);
    for (const id of ids) {
      try {
        if (action === 'resolve') {
          await axios.post(`${API_URL}/api/escalations/${id}/resolve`, { actor: 'admin' });
        } else if (action === 'snooze') {
          await axios.post(`${API_URL}/api/escalations/${id}/snooze`, { hours: extra.hours || 4, actor: 'admin' });
        } else if (action === 'reassign' && extra.owner) {
          await axios.post(`${API_URL}/api/escalations/${id}/reassign`, { owner: extra.owner, actor: 'admin' });
        }
      } catch (err) {
        console.error('[insights] bulk action failed for', id, err);
      }
    }
    // Optimistic UI refresh
    if (action === 'resolve' || action === 'snooze') {
      setEscalations(prev => prev.filter(e => !ids.includes(e._id || e.id)));
    } else if (action === 'reassign') {
      setEscalations(prev => prev.map(e => ids.includes(e._id || e.id)
        ? { ...e, owner: extra.owner, ownerEmail: extra.owner, assignedTo: extra.owner }
        : e
      ));
    }
  };

  if (loading) return <InsightsLoading rows={8} />;

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="space-y-6">
      <InsightsSection id="risk-overview" title={t('ins_sec_risk_overview')} subtitle={t('ins_sec_risk_overview_sub')} tip={t('ins_tip_risk_overview')}>
        <RiskOverviewSection data={overview} />
      </InsightsSection>
      <InsightsSection id="risk-by-entity" title={t('ins_sec_risk_by_entity')} subtitle={t('ins_sec_risk_by_entity_sub')} tip={t('ins_tip_risk_by_entity')}>
        <RiskByEntitySection entities={entities} onOpenManager={setDrillManager} />
      </InsightsSection>
      <InsightsSection id="critical-alerts-feed" title={t('ins_sec_alerts_feed')} subtitle={t('ins_sec_alerts_feed_sub')} tip={t('ins_tip_alerts_feed')}>
        <CriticalAlertsFeed alerts={alerts} onOpen={setDrillAlert} severity={severity} setSeverity={setSeverity} onRefresh={() => setRefreshTick(t => t+1)} />
      </InsightsSection>
      <InsightsSection id="escalation-queue" title={t('ins_sec_escalation_queue')} subtitle={t('ins_sec_escalation_queue_sub')} tip={t('ins_tip_escalation_queue')}>
        <EscalationQueue escalations={escalations} onOpen={setOpenItem} onAction={handleAction} onBulkAction={handleBulkAction} />
      </InsightsSection>
      <InsightsSection id="stuck-items" title={t('ins_sec_stuck_items')} subtitle={t('ins_sec_stuck_items_sub')} tip={t('ins_tip_stuck_items')}>
        <StuckItems items={stuck} />
      </InsightsSection>

      {/* Deep manager drill-down — opens on click in "Risk by Manager" rows */}
      <ManagerDrillSheet open={!!drillManager} onOpenChange={(o) => !o && setDrillManager(null)} manager={drillManager} />

      {/* Deep alert drill-down — replaces legacy JSON sheet for Alerts feed */}
      <AlertDrillSheet
        open={!!drillAlert}
        onOpenChange={(o) => !o && setDrillAlert(null)}
        alert={drillAlert}
        onResolve={(a) => handleAction('resolve', a)}
      />

      {/* Lightweight raw-detail sheet — still used for Alerts feed + Escalation rows
          (those don't have a dedicated drill-down primitive yet). */}
      <Sheet open={!!openItem} onOpenChange={(o) => !o && setOpenItem(null)}>
        <SheetContent side="right" className="w-full sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>{openItem?.title || openItem?.name || 'Detail'}</SheetTitle>
            <SheetDescription>{openItem?.entity || openItem?.queue || openItem?.kindLabel}</SheetDescription>
          </SheetHeader>
          <div className="mt-4 space-y-3 text-sm text-zinc-700">
            <div className="rounded-lg bg-zinc-50 p-3">
              <pre className="whitespace-pre-wrap break-all text-xs text-zinc-600">{JSON.stringify(openItem, null, 2)}</pre>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </motion.div>
  );
};

export default RiskAlertsVertical;
