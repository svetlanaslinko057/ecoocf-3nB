/**
 * MeetingsTab — Customer360 tab. Wired to /api/customers/{cid}/meetings.
 * Implemented in Phase Final / Block 3 (Meetings + Calendar).
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { CalendarCheck, Plus } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STATUS_BADGE = {
  scheduled: { bg: 'bg-amber-100',   text: 'text-amber-700',   label: 'Scheduled' },
  completed: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Completed' },
  cancelled: { bg: 'bg-rose-100',    text: 'text-rose-700',    label: 'Cancelled' },
  no_show:   { bg: 'bg-zinc-100',    text: 'text-zinc-700',    label: 'No-show' },
};

export default function MeetingsTab({ customerId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!customerId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/customers/${customerId}/meetings`);
      setItems(r.data?.items || []);
    } catch (e) {
      // Meetings router lands in Block 3; absorb 404 gracefully.
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4" data-testid="customer360-meetings-tab">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <CalendarCheck className="w-5 h-5 text-zinc-500" />
          <h3 className="text-base font-semibold text-zinc-900">Meetings ({items.length})</h3>
        </div>
        <a
          href={`/admin/meetings?customerId=${customerId}`}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold"
          data-testid="meetings-tab-add-link"
        >
          <Plus className="w-4 h-4" /> New Meeting
        </a>
      </div>

      {loading ? (
        <div className="text-center py-8 text-zinc-400 text-sm">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-center py-10 text-zinc-400 text-sm bg-zinc-50 rounded-2xl">
          No meetings scheduled for this customer.
        </div>
      ) : (
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-zinc-600 text-[11.5px] uppercase">
                <tr>
                  <th className="text-left px-4 py-2.5 font-semibold">When</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Title</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Result</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Next Step</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {items.map((m) => {
                  const badge = STATUS_BADGE[m.status] || STATUS_BADGE.scheduled;
                  const when = m.startAt ? new Date(m.startAt).toLocaleString() : '—';
                  return (
                    <tr key={m.id} data-testid={`c360-meeting-row-${m.id}`}>
                      <td className="px-4 py-3 text-zinc-900 font-medium">{when}</td>
                      <td className="px-4 py-3 text-zinc-700">{m.title || '—'}</td>
                      <td className="px-4 py-3 text-zinc-600 text-[12px]">{m.result || '—'}</td>
                      <td className="px-4 py-3 text-zinc-600 text-[12px]">{m.nextStep || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold ${badge.bg} ${badge.text}`}>
                          {badge.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
