import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowRight, Prohibit, Warning, Plus } from '@phosphor-icons/react';
import { API_URL } from '../../App';

const STAGE_LABELS = {
  inquiry:          'Inquiry',
  negotiating:      'Negotiating',
  awaiting_deposit: 'Awaiting Deposit',
  deposit_paid:     'Deposit Paid',
  bidding:          'Bidding',
  won:              'Won',
  contract_signed:  'Contract Signed',
  shipping:         'Shipping',
  delivered:        'Delivered',
  cancelled:        'Cancelled',
};

const Modal = ({ open, onClose, title, children }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()} data-testid="deal-modal">
        <div className="text-sm font-bold text-[#18181B] mb-3">{title}</div>
        {children}
      </div>
    </div>
  );
};

const DealPipelineActions = ({ deal, availableTransitions = [], onChange }) => {
  const [moveOpen, setMoveOpen] = useState(false);
  const [blockerOpen, setBlockerOpen] = useState(false);
  const [moveTo, setMoveTo] = useState(availableTransitions.find((s) => s !== 'cancelled') || '');
  const [moveReason, setMoveReason] = useState('');
  const [blockerLabel, setBlockerLabel] = useState('');
  const [blockerNote, setBlockerNote] = useState('');
  const [busy, setBusy] = useState(false);

  const forwardOptions = availableTransitions.filter((s) => s !== 'cancelled');

  const transition = async (target, reason) => {
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/deals/${deal.id}/transition`, { to: target, reason });
      toast.success(`Moved to ${STAGE_LABELS[target] || target}`);
      onChange?.();
      setMoveOpen(false);
      setMoveReason('');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Transition failed');
    } finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!window.confirm('Cancel this deal? This is reversible only by an admin.')) return;
    await transition('cancelled', moveReason || 'Cancelled from Deal360');
  };

  const addBlocker = async () => {
    if (!blockerLabel.trim()) return;
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/deals/${deal.id}/blockers`, {
        label: blockerLabel.trim(),
        note:  blockerNote.trim() || undefined,
      });
      toast.success('Blocker added');
      setBlockerLabel('');
      setBlockerNote('');
      setBlockerOpen(false);
      onChange?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="deal-pipeline-actions">
      <button
        disabled={!forwardOptions.length}
        onClick={() => { setMoveTo(forwardOptions[0]); setMoveOpen(true); }}
        className="inline-flex items-center gap-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-[12px] font-semibold rounded-lg px-2.5 py-1.5"
        data-testid="deal-move-stage-btn"
      >
        <ArrowRight size={12} weight="bold" /> Move stage
      </button>
      <button
        onClick={() => setBlockerOpen(true)}
        className="inline-flex items-center gap-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-[12px] font-semibold rounded-lg px-2.5 py-1.5"
        data-testid="deal-add-blocker-btn"
      >
        <Warning size={12} weight="bold" /> Add blocker
      </button>
      <button
        disabled={!availableTransitions.includes('cancelled')}
        onClick={cancel}
        className="inline-flex items-center gap-1 bg-red-50 hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed text-red-700 border border-red-200 text-[12px] font-semibold rounded-lg px-2.5 py-1.5"
        data-testid="deal-cancel-btn"
      >
        <Prohibit size={12} weight="bold" /> Cancel deal
      </button>

      <Modal open={moveOpen} onClose={() => setMoveOpen(false)} title="Move deal to a new stage">
        <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">New stage</label>
        <select
          value={moveTo} onChange={(e) => setMoveTo(e.target.value)}
          className="mt-1 w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm bg-white"
          data-testid="deal-move-stage-select"
        >
          {availableTransitions.map((s) => (
            <option key={s} value={s}>{STAGE_LABELS[s] || s}</option>
          ))}
        </select>
        <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mt-3 block">Reason (optional)</label>
        <input
          value={moveReason} onChange={(e) => setMoveReason(e.target.value)}
          className="mt-1 w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm"
          placeholder="e.g. customer paid the deposit"
        />
        <div className="flex items-center justify-end gap-2 mt-4">
          <button onClick={() => setMoveOpen(false)} className="text-sm text-[#71717A] hover:underline">Cancel</button>
          <button
            onClick={() => transition(moveTo, moveReason)}
            disabled={busy || !moveTo}
            className="bg-[#18181B] text-white text-sm font-semibold rounded-lg px-3 py-2 disabled:opacity-50"
            data-testid="deal-move-stage-confirm"
          >
            {busy ? 'Moving…' : 'Move'}
          </button>
        </div>
      </Modal>

      <Modal open={blockerOpen} onClose={() => setBlockerOpen(false)} title="Add a blocker">
        <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A]">Label *</label>
        <input
          value={blockerLabel} onChange={(e) => setBlockerLabel(e.target.value)}
          className="mt-1 w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm"
          placeholder="e.g. Missing passport scan" autoFocus
          data-testid="deal-blocker-label-input"
        />
        <label className="text-[11px] uppercase tracking-wider font-bold text-[#71717A] mt-3 block">Note (optional)</label>
        <textarea
          rows={2}
          value={blockerNote} onChange={(e) => setBlockerNote(e.target.value)}
          className="mt-1 w-full px-3 py-2 border border-[#E4E4E7] rounded-lg text-sm resize-none"
          placeholder="What we tried, what we need next…"
        />
        <div className="flex items-center justify-end gap-2 mt-4">
          <button onClick={() => setBlockerOpen(false)} className="text-sm text-[#71717A] hover:underline">Cancel</button>
          <button
            onClick={addBlocker}
            disabled={busy || !blockerLabel.trim()}
            className="inline-flex items-center gap-1 bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold rounded-lg px-3 py-2 disabled:opacity-50"
            data-testid="deal-blocker-add-confirm"
          >
            <Plus size={12} weight="bold" /> Add
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default DealPipelineActions;
