/**
 * ReassignPopover.jsx — small composable popover for inline "Reassign" action.
 *
 * Designed to be embedded in any table row (Escalation Queue today, can be
 * reused later for stale leads / overdue invoices reassignment).
 *
 * Behaviour
 *   - Opens an anchored popover with a text input (owner email) + Confirm.
 *   - Pre-populates a `<datalist>` of available staff (best-effort: tries
 *     GET /api/team/managers, falls back to free typing if not available).
 *   - Calls `onSubmit(owner)` on confirm.
 *
 * Modular: zero knowledge of escalation specifics — purely a UI primitive.
 */
import React, { useEffect, useRef, useState } from 'react';
import { ArrowsClockwise, X, CheckCircle } from '@phosphor-icons/react';
import { safeGet } from './insightsApi';
import { useLang } from '../../../i18n';

const ReassignPopover = ({ trigger, currentOwner, onSubmit, testId = 'reassign-popover' }) => {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [managers, setManagers] = useState([]);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    // Fetch potential assignees lazily; ignore failures silently.
    safeGet('/api/team/managers').then(({ data }) => {
      const items = Array.isArray(data) ? data : data?.items || [];
      setManagers(items);
    });
    // Click-outside close
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const handleConfirm = async (e) => {
    e?.preventDefault?.();
    e?.stopPropagation?.();
    const value = owner.trim();
    if (!value) return;
    setSubmitting(true);
    try {
      await onSubmit?.(value);
      setOpen(false);
      setOwner('');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <span ref={wrapRef} className="relative inline-flex" data-testid={testId}>
      {React.isValidElement(trigger) ? React.cloneElement(trigger, {
        onClick: (e) => {
          e.preventDefault?.();
          e.stopPropagation?.();
          setOpen(v => !v);
        },
        'data-testid': `${testId}-trigger`,
      }) : (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setOpen(v => !v); }}
          className="rounded-md border border-zinc-200 px-2 py-1 text-[11px] font-medium text-zinc-700 hover:bg-zinc-50"
          data-testid={`${testId}-trigger`}
        >
          <ArrowsClockwise size={11} className="mr-0.5 inline" />{t('ins_reassign')}
        </button>
      )}

      {open && (
        <div
          className="absolute right-0 top-full z-50 mt-1 w-64 rounded-xl border border-zinc-200 bg-white p-3 shadow-lg"
          onClick={(e) => e.stopPropagation()}
          data-testid={`${testId}-panel`}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-900">{t('ins_reassign_to')}</span>
            <button type="button" onClick={() => setOpen(false)} className="text-zinc-400 hover:text-zinc-700"><X size={12} weight="bold" /></button>
          </div>
          {currentOwner && (
            <div className="mb-2 text-[11px] text-zinc-500">{t('ins_current_owner')} <span className="font-medium text-zinc-700">{currentOwner}</span></div>
          )}
          <form onSubmit={handleConfirm} className="space-y-2">
            <input
              list={`${testId}-list`}
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="manager@bibi.cars"
              className="w-full rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-900 focus:border-zinc-400 focus:outline-none"
              autoFocus
              data-testid={`${testId}-input`}
            />
            <datalist id={`${testId}-list`}>
              {managers.map(m => <option key={m.id || m.email} value={m.email || m.name} />)}
            </datalist>
            <div className="flex justify-end gap-1">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-md px-2 py-1 text-[11px] font-medium text-zinc-600 hover:bg-zinc-100"
              >Cancel</button>
              <button
                type="submit"
                disabled={submitting || !owner.trim()}
                className="inline-flex items-center gap-1 rounded-md bg-zinc-900 px-2 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                data-testid={`${testId}-confirm`}
              >
                <CheckCircle size={11} weight="bold" />
                {submitting ? 'Saving…' : 'Confirm'}
              </button>
            </div>
          </form>
        </div>
      )}
    </span>
  );
};

export default ReassignPopover;
