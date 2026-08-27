/**
 * BIBI Cars — Wave 7 — ReassignDialog
 * ======================================
 *
 * Reusable modal for reassigning lead / customer / deal (single or bulk)
 * to another manager. Powered by:
 *   GET  /api/admin/reassign/managers   → workload payload (sorted by loadScore)
 *   POST /api/admin/reassign            → executes the reassignment
 *
 * Props:
 *   open         : boolean
 *   onClose      : () => void
 *   entity       : "lead" | "customer" | "deal"
 *   ids          : string[]   — entity ids to reassign (single or bulk)
 *   currentManagerId? : string  — used to show "current owner" badge
 *   onSuccess    : (result) => void  — fired after a successful POST
 *
 * Role gating is enforced server-side (admin/team_lead only). This
 * component is rendered conditionally based on caller's role check.
 */
import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './dialog';
import { ArrowsClockwise, User, CheckCircle, Warning, MagnifyingGlass } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const ENTITY_LABEL = {
  lead:     { en: 'leads',     uk: 'лідів',    bg: 'лийдове'  },
  customer: { en: 'customers', uk: 'клієнтів', bg: 'клиенти'  },
  deal:     { en: 'deals',     uk: 'угод',     bg: 'сделки'   },
};

function plural(entity, n) {
  // very tiny localised plural — UI text only
  const map = ENTITY_LABEL[entity] || { en: entity, uk: entity, bg: entity };
  return n === 1
    ? entity
    : map.en;
}

const ReassignDialog = ({
  open,
  onClose,
  entity = 'lead',
  ids = [],
  currentManagerId = null,
  onSuccess = () => {},
}) => {
  const [managers, setManagers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedManagerId, setSelectedManagerId] = useState(null);
  const [reason, setReason] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!open) return;
    setSelectedManagerId(null);
    setReason('');
    setSearch('');
    fetchManagers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const fetchManagers = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/admin/reassign/managers`);
      const data = Array.isArray(res.data) ? res.data : (res.data?.data || []);
      setManagers(data);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to load managers';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const filteredManagers = useMemo(() => {
    if (!search.trim()) return managers;
    const q = search.trim().toLowerCase();
    return managers.filter(m =>
      (m.name || '').toLowerCase().includes(q) ||
      (m.email || '').toLowerCase().includes(q)
    );
  }, [managers, search]);

  const handleSubmit = async () => {
    if (!selectedManagerId) {
      toast.error('Please select a manager');
      return;
    }
    if (!ids.length) {
      toast.error('Nothing to reassign');
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API_URL}/api/admin/reassign`, {
        entity,
        ids,
        toManagerId: selectedManagerId,
        reason: reason.trim() || null,
      });
      const r = res.data || {};
      const processed = r.processed || 0;
      const noChange = r.no_change || 0;
      const failed = r.failed || 0;

      if (failed > 0 && processed === 0) {
        const firstErr = r.results?.find(x => !x.ok)?.error || 'Reassignment failed';
        toast.error(`Failed: ${firstErr}`);
      } else if (failed > 0) {
        toast.warning(`Reassigned ${processed} / ${ids.length} (${failed} failed)`);
      } else if (processed === 0 && noChange > 0) {
        toast.info(`No change — already owned by this manager`);
      } else {
        toast.success(
          ids.length === 1
            ? `Reassigned successfully`
            : `Reassigned ${processed} ${plural(entity, processed)}`
        );
      }
      onSuccess(r);
      onClose();
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Reassignment failed';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // loadScore color thresholds
  const loadColor = (score) => {
    if (score == null) return 'text-[#71717A]';
    if (score < 10) return 'text-[#059669]'; // green
    if (score < 25) return 'text-[#D97706]'; // amber
    return 'text-[#DC2626]';                  // red
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent
        className="max-w-[calc(100%-2rem)] sm:max-w-lg bg-white rounded-2xl border border-[#E4E4E7] max-h-[90vh] overflow-hidden flex flex-col"
        data-testid="reassign-dialog"
      >
        <DialogHeader>
          <DialogTitle className="text-lg sm:text-xl font-bold text-[#18181B] flex items-center gap-2"
            style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
            <ArrowsClockwise size={20} weight="duotone" className="text-[#4F46E5]" />
            Reassign {ids.length > 1 ? `${ids.length} ${plural(entity, ids.length)}` : entity}
          </DialogTitle>
        </DialogHeader>

        {/* Search */}
        <div className="px-1 pb-2">
          <div className="relative">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A1A1AA]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search manager by name or email…"
              className="w-full h-10 pl-9 pr-3 rounded-xl border border-[#E4E4E7] bg-white text-sm focus:outline-none focus:border-[#4F46E5]"
              data-testid="reassign-search"
            />
          </div>
        </div>

        {/* Manager list */}
        <div className="flex-1 overflow-y-auto px-1 pb-2 -mx-1 space-y-2">
          {loading ? (
            <div className="text-center py-8 text-[#71717A]">
              <div className="inline-flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-[#18181B] border-t-transparent rounded-full animate-spin" />
                Loading managers…
              </div>
            </div>
          ) : filteredManagers.length === 0 ? (
            <div className="text-center py-8 text-[#71717A] text-sm">
              <Warning size={20} className="mx-auto mb-2 text-[#D97706]" weight="duotone" />
              No managers found
            </div>
          ) : (
            filteredManagers.map((m) => {
              const isSelected = selectedManagerId === m.id;
              const isCurrent = currentManagerId === m.id;
              const disabled = !m.isAvailable;
              return (
                <button
                  key={m.id}
                  type="button"
                  disabled={disabled}
                  onClick={() => setSelectedManagerId(m.id)}
                  data-testid={`reassign-manager-${m.id}`}
                  className={`w-full p-3 rounded-xl border transition-all text-left flex items-center gap-3
                    ${isSelected ? 'border-[#4F46E5] bg-[#EEF2FF] ring-1 ring-[#4F46E5]' : 'border-[#E4E4E7] hover:border-[#A5B4FC] bg-white'}
                    ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white flex items-center justify-center font-semibold flex-shrink-0">
                    {(m.name || m.email || '?').slice(0, 1).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="font-medium text-[#18181B] truncate">{m.name || m.email}</div>
                      {isCurrent && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#FEF3C7] text-[#92400E] rounded-md font-medium">CURRENT</span>
                      )}
                      {m.role === 'team_lead' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-[#E0E7FF] text-[#3730A3] rounded-md font-medium">TL</span>
                      )}
                    </div>
                    <div className="text-xs text-[#71717A] truncate">{m.email}</div>
                    <div className="flex items-center gap-3 mt-1 text-[11px] text-[#52525B]">
                      <span>L:<b className="ml-0.5 text-[#18181B]">{m.activeLeads ?? 0}</b></span>
                      <span>C:<b className="ml-0.5 text-[#18181B]">{m.activeCustomers ?? 0}</b></span>
                      <span>D:<b className="ml-0.5 text-[#18181B]">{m.activeDeals ?? 0}</b></span>
                      <span>T:<b className="ml-0.5 text-[#18181B]">{m.activeTasks ?? 0}</b></span>
                      <span className={`ml-auto font-bold ${loadColor(m.loadScore)}`}>load {m.loadScore}</span>
                    </div>
                  </div>
                  {isSelected && (
                    <CheckCircle size={20} weight="fill" className="text-[#4F46E5] flex-shrink-0" />
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* Reason */}
        <div className="pt-2 border-t border-[#F4F4F5]">
          <label className="text-xs font-medium text-[#52525B] uppercase tracking-wider">Reason (optional)</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Manager overloaded, vacation, redistribution…"
            rows={2}
            className="mt-1.5 w-full px-3 py-2 rounded-xl border border-[#E4E4E7] text-sm focus:outline-none focus:border-[#4F46E5] resize-none"
            data-testid="reassign-reason"
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 pt-3 border-t border-[#F4F4F5]">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 rounded-xl text-sm font-medium text-[#52525B] hover:bg-[#F4F4F5] transition-colors"
            data-testid="reassign-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !selectedManagerId}
            className="px-4 py-2 rounded-xl text-sm font-semibold text-white bg-[#4F46E5] hover:bg-[#4338CA] disabled:bg-[#A5B4FC] disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            data-testid="reassign-submit"
          >
            {submitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Reassigning…
              </>
            ) : (
              <>
                <ArrowsClockwise size={16} weight="bold" />
                Reassign {ids.length > 1 ? `(${ids.length})` : ''}
              </>
            )}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ReassignDialog;
