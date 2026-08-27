/**
 * Customer360 — TimelineTab (Sprint 4)
 * --------------------------------------
 * Unified history of EVERYTHING that happened around a customer:
 * invoices, payments, orders, documents, files, comments, tasks,
 * roadmap stages — in one chronological feed.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  ClockCounterClockwise,
  Receipt,
  CurrencyDollar,
  Package,
  FilePdf,
  UploadSimple,
  ChatCircle,
  CheckSquare,
  Compass,
  UserPlus,
  Phone,
  PushPin,
} from '@phosphor-icons/react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const authHeaders = () => {
  const tok = localStorage.getItem('token') || localStorage.getItem('access_token');
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

const KIND_META = {
  invoice_created:    { icon: Receipt,        color: 'text-indigo-500',  label: 'Invoice created' },
  invoice_paid:       { icon: Receipt,        color: 'text-emerald-500', label: 'Invoice paid' },
  payment_received:   { icon: CurrencyDollar, color: 'text-emerald-500', label: 'Payment received' },
  order_created:      { icon: Package,        color: 'text-amber-500',   label: 'Order created' },
  document_generated: { icon: FilePdf,        color: 'text-rose-500',    label: 'Document generated' },
  file_uploaded:      { icon: UploadSimple,   color: 'text-blue-500',    label: 'File uploaded' },
  file_deleted:       { icon: UploadSimple,   color: 'text-zinc-400',    label: 'File deleted' },
  comment_added:      { icon: ChatCircle,     color: 'text-violet-500',  label: 'Comment added' },
  comment_pinned:     { icon: PushPin,        color: 'text-amber-500',   label: 'Comment pinned' },
  task_created:       { icon: CheckSquare,    color: 'text-sky-500',     label: 'Task created' },
  task_completed:     { icon: CheckSquare,    color: 'text-emerald-500', label: 'Task completed' },
  task_overdue:       { icon: CheckSquare,    color: 'text-red-500',     label: 'Task overdue' },
  roadmap_created:    { icon: Compass,        color: 'text-indigo-500',  label: 'Roadmap started' },
  roadmap_updated:    { icon: Compass,        color: 'text-amber-500',   label: 'Roadmap updated' },
  roadmap_completed:  { icon: Compass,        color: 'text-emerald-500', label: 'Roadmap completed' },
  customer_created:   { icon: UserPlus,       color: 'text-indigo-500',  label: 'Customer created' },
  customer_assigned:  { icon: UserPlus,       color: 'text-amber-500',   label: 'Customer assigned' },
  lead_converted:     { icon: UserPlus,       color: 'text-emerald-500', label: 'Lead converted' },
  call_logged:        { icon: Phone,          color: 'text-sky-500',     label: 'Call logged' },
  deposit_received:   { icon: CurrencyDollar, color: 'text-emerald-500', label: 'Deposit received' },
  contract_signed:    { icon: FilePdf,        color: 'text-emerald-500', label: 'Contract signed' },
};

const fmtDateTime = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch { return ''; }
};

const groupByDay = (items) => {
  const map = new Map();
  items.forEach((e) => {
    if (!e.created_at) return;
    const d = new Date(e.created_at);
    const key = d.toLocaleDateString();
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(e);
  });
  return Array.from(map.entries());
};

const TimelineTab = ({ customerId }) => {
  const [items, setItems] = useState([]);
  const [breakdown, setBreakdown] = useState({});
  const [available, setAvailable] = useState([]);
  const [active, setActive] = useState(new Set());
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/customers/${customerId}/timeline?limit=200`, { headers: authHeaders() });
      setItems(res.data?.items || []);
      setBreakdown(res.data?.breakdown || {});
      setAvailable(res.data?.available_kinds || []);
    } catch (e) {
      try {
        const fallback = await axios.get(`${API_URL}/api/customers/${customerId}/timeline-legacy?limit=200`);
        const events = (fallback.data?.events || []).map((e) => ({
          id: e.ref || `${e.type}_${e.at}`,
          kind: e.type,
          title: e.title,
          created_at: e.at,
          ref: { id: e.ref },
        }));
        setItems(events);
      } catch {
        setItems([]);
      }
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customers/${customerId}/timeline?limit=200`, { headers: authHeaders() });
        if (cancelled) return;
        setItems(res.data?.items || []);
        setBreakdown(res.data?.breakdown || {});
        setAvailable(res.data?.available_kinds || []);
      } catch {
        try {
          const fallback = await axios.get(`${API_URL}/api/customers/${customerId}/timeline-legacy?limit=200`);
          if (cancelled) return;
          const events = (fallback.data?.events || []).map((e) => ({
            id: e.ref || `${e.type}_${e.at}`,
            kind: e.type,
            title: e.title,
            created_at: e.at,
            ref: { id: e.ref },
          }));
          setItems(events);
        } catch {
          if (!cancelled) setItems([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [customerId]);

  const filtered = useMemo(() => {
    if (active.size === 0) return items;
    return items.filter((e) => active.has(e.kind));
  }, [items, active]);

  const grouped = useMemo(() => groupByDay(filtered), [filtered]);

  const toggle = (k) => {
    setActive((s) => {
      const n = new Set(s);
      if (n.has(k)) n.delete(k); else n.add(k);
      return n;
    });
  };

  if (loading) return <div className="flex items-center justify-center h-32"><div className="animate-spin w-7 h-7 border-2 border-[#4F46E5] border-t-transparent rounded-full" /></div>;

  return (
    <div className="space-y-5" data-testid="customer360-timeline-tab">
      {/* Filter pills */}
      {available.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(breakdown)
            .sort(([, a], [, b]) => b - a)
            .map(([k, count]) => {
              const meta = KIND_META[k] || { color: 'text-zinc-500', label: k.replace(/_/g, ' '), icon: ClockCounterClockwise };
              const Icon = meta.icon;
              const on = active.has(k);
              return (
                <button
                  key={k}
                  onClick={() => toggle(k)}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border transition-all ${on ? 'bg-[#18181B] text-white border-[#18181B]' : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50'}`}
                  data-testid={`timeline-filter-${k}`}
                >
                  <Icon size={12} weight="fill" /> {meta.label} <span className="font-mono tabular-nums opacity-70">{count}</span>
                </button>
              );
            })}
          {active.size > 0 && (
            <button onClick={() => setActive(new Set())} className="text-xs text-zinc-500 hover:text-zinc-900 underline">Скинути</button>
          )}
        </div>
      )}

      {filtered.length === 0 && (
        <div className="section-card text-center py-12" data-testid="timeline-empty">
          <ClockCounterClockwise size={32} className="mx-auto text-[#A1A1AA] mb-2" />
          <p className="text-[#71717A]">Немає подій за фільтром.</p>
        </div>
      )}

      <div className="space-y-6">
        {grouped.map(([day, evs]) => (
          <div key={day} data-testid={`timeline-day-${day}`}>
            <h4 className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-3">{day}</h4>
            <div className="relative pl-6 border-l-2 border-zinc-100 space-y-3">
              {evs.map((e, idx) => {
                const meta = KIND_META[e.kind] || { icon: ClockCounterClockwise, color: 'text-zinc-500', label: (e.kind || '').replace(/_/g, ' ') };
                const Icon = meta.icon;
                return (
                  <div key={e.id || idx} className="relative" data-testid={`timeline-event-${e.kind}`}>
                    <div className={`absolute -left-[1.7rem] top-0.5 w-7 h-7 rounded-full bg-white border-2 border-zinc-200 flex items-center justify-center ${meta.color}`}>
                      <Icon size={14} weight="duotone" />
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-zinc-900">{e.title || meta.label}</p>
                        {e.body && <p className="text-xs text-zinc-500 mt-0.5 line-clamp-2">{e.body}</p>}
                        {e.actor && (e.actor.name || e.actor.email) && (
                          <p className="text-[11px] text-zinc-400 mt-1">— {e.actor.name || e.actor.email}</p>
                        )}
                      </div>
                      <span className="text-[11px] text-zinc-400 tabular-nums shrink-0">{fmtDateTime(e.created_at)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TimelineTab;
