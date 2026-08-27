import React from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Warning, CheckCircle, X } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const DealBlockersList = ({ dealId, blockers = [], onChange }) => {
  const open    = blockers.filter((b) => !b.resolved);
  const closed  = blockers.filter((b) => b.resolved);

  const resolve = async (id) => {
    const note = window.prompt('Resolution note (optional):') || '';
    try {
      const url = note ? `${API_URL}/api/deals/${dealId}/blockers/${id}?note=${encodeURIComponent(note)}` : `${API_URL}/api/deals/${dealId}/blockers/${id}`;
      await axios.delete(url);
      toast.success('Blocker resolved');
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    }
  };

  if (!open.length && !closed.length) return null;

  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal-blockers-list">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Blockers</div>
        <div className="text-[11px] text-[#71717A]">{open.length} open · {closed.length} resolved</div>
      </div>

      <ul className="space-y-2">
        {open.map((b) => (
          <li key={b.id} className="flex items-start justify-between gap-2 bg-red-50 border border-red-200 rounded-xl p-3" data-testid={`blocker-row-${b.id}`}>
            <div className="flex items-start gap-2 min-w-0">
              <Warning size={16} weight="bold" className="text-red-600 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <div className="font-semibold text-[#7F1D1D] truncate">{b.label}</div>
                {b.note ? <div className="text-[12px] text-[#7F1D1D]/80 mt-0.5">{b.note}</div> : null}
                <div className="text-[11px] text-[#7F1D1D]/60 mt-1">{b.created_by || '—'} · {b.created_at ? new Date(b.created_at).toLocaleString() : ''}</div>
              </div>
            </div>
            <button
              onClick={() => resolve(b.id)}
              className="shrink-0 inline-flex items-center gap-1 bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 text-[12px] font-semibold rounded-lg px-2 py-1"
              data-testid={`blocker-resolve-${b.id}`}
            >
              <CheckCircle size={12} weight="bold" /> Resolve
            </button>
          </li>
        ))}

        {closed.map((b) => (
          <li key={b.id} className="flex items-start gap-2 bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl p-3 text-[#52525B]" data-testid={`blocker-resolved-${b.id}`}>
            <CheckCircle size={16} weight="bold" className="text-emerald-600 mt-0.5 shrink-0" />
            <div className="min-w-0">
              <div className="font-semibold text-[#3F3F46] truncate line-through opacity-80">{b.label}</div>
              {b.resolution ? <div className="text-[12px] mt-0.5">{b.resolution}</div> : null}
              <div className="text-[11px] text-[#71717A] mt-1">Resolved {b.resolved_at ? new Date(b.resolved_at).toLocaleString() : ''} by {b.resolved_by || '—'}</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default DealBlockersList;
