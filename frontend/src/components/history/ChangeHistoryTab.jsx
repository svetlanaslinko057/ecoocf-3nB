/* eslint-disable */
/**
 * BIBI Cars — Block 7.1 — Change History tab
 * ==============================================
 *
 * Generic table that fetches /api/<entity_type>s/{id}/change-history and
 * renders ``who | field | old | new | when`` rows.
 *
 * Usage:
 *   <ChangeHistoryTab entityType="customer" entityId={id} />
 *   <ChangeHistoryTab entityType="lead"     entityId={id} />
 *   <ChangeHistoryTab entityType="deal"     entityId={id} />
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Clock, User, ArrowRight, ClockCounterClockwise } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const PLURAL = { customer: 'customers', lead: 'leads', deal: 'deals' };

const formatVal = (v) => {
  if (v === null || v === undefined || v === '') return <span className="text-[#A1A1AA] italic">—</span>;
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'object') {
    try { return <code className="text-[11px] bg-[#F4F4F5] px-1 rounded">{JSON.stringify(v)}</code>; }
    catch { return String(v); }
  }
  return String(v);
};

const formatField = (f) => {
  if (!f) return '';
  // CamelCase / snake_case → Title Case
  return f
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (c) => c.toUpperCase())
    .trim();
};

const ChangeHistoryTab = ({ entityType, entityId }) => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!entityType || !entityId) return;
    const plural = PLURAL[entityType] || entityType + 's';
    setLoading(true);
    setError(null);
    axios.get(`${API_URL}/api/${plural}/${entityId}/change-history?limit=200`)
      .then((res) => {
        const data = res?.data?.data || [];
        setRows(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        const msg = err?.response?.data?.detail || err?.message || 'Failed to load';
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [entityType, entityId]);

  return (
    <div className="bg-white rounded-2xl border border-[#E4E4E7] overflow-hidden" data-testid="change-history-tab">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#F4F4F5]">
        <ClockCounterClockwise size={20} weight="duotone" className="text-[#4F46E5]" />
        <h3 className="text-base font-semibold text-[#18181B]">Change history</h3>
        <span className="text-xs text-[#71717A] ml-auto">{rows.length} entries</span>
      </div>

      {loading && (
        <div className="px-4 py-12 text-center text-[#71717A] text-sm">
          <div className="inline-flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
            Loading…
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="px-4 py-6 text-center text-sm text-[#B91C1C]">{error}</div>
      )}

      {!loading && !error && rows.length === 0 && (
        <div className="px-4 py-12 text-center text-[#71717A] text-sm">No changes recorded yet.</div>
      )}

      {!loading && !error && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="bg-[#FAFAFA] text-[#52525B] text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-2 font-medium">When</th>
                <th className="text-left px-4 py-2 font-medium">Who</th>
                <th className="text-left px-4 py-2 font-medium">Field</th>
                <th className="text-left px-4 py-2 font-medium">Old → New</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F4F4F5]">
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-[#FAFAFA]">
                  <td className="px-4 py-2.5 whitespace-nowrap text-[#52525B] text-xs">
                    <div className="flex items-center gap-1">
                      <Clock size={12} className="text-[#A1A1AA]" />
                      {r.changed_at ? new Date(r.changed_at).toLocaleString() : '—'}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1.5 text-[#18181B]">
                      <User size={12} className="text-[#A1A1AA]" />
                      <span className="font-medium">{r.changed_by_name || r.changed_by || 'system'}</span>
                      {r.changed_by_role ? (
                        <span className="text-[10px] text-[#71717A] uppercase">({r.changed_by_role})</span>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 font-medium text-[#18181B]">{formatField(r.field)}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2 text-[#3F3F46]">
                      <span className="px-1.5 py-0.5 rounded bg-[#FEE2E2] text-[#991B1B] text-xs">
                        {formatVal(r.old_value)}
                      </span>
                      <ArrowRight size={12} className="text-[#A1A1AA]" />
                      <span className="px-1.5 py-0.5 rounded bg-[#DCFCE7] text-[#166534] text-xs">
                        {formatVal(r.new_value)}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ChangeHistoryTab;
