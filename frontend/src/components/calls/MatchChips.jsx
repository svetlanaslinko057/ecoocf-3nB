/**
 * BIBI Cars — W2A — MatchChips
 * ================================
 * Compact visual indicator of WHY a call matched a customer.
 * Used in CallsTab table rows and CallDrawer.
 *
 * Each chip = one match key from the backend's `matchedBy[]` list.
 * Hovering shows the full reason (value, side).
 */
import React from 'react';
import { useLang } from '../../i18n';

const KEY_STYLES = {
  customer_id:    { abbr: 'CID', cls: 'bg-indigo-100 text-indigo-700 border-indigo-200', label: 'Customer ID' },
  lead_id:        { abbr: 'LD',  cls: 'bg-violet-100 text-violet-700 border-violet-200', label: 'Lead ID' },
  deal_id:        { abbr: 'DL',  cls: 'bg-amber-100 text-amber-700 border-amber-200',    label: 'Deal ID' },
  phone_primary:  { abbr: 'P1',  cls: 'bg-emerald-100 text-emerald-700 border-emerald-200', label: 'Primary phone' },
  phone_secondary:{ abbr: 'P2',  cls: 'bg-teal-100 text-teal-700 border-teal-200',         label: 'Secondary phone' },
  phone_lead:     { abbr: 'PL',  cls: 'bg-sky-100 text-sky-700 border-sky-200',            label: 'Lead phone' },
};

const makeTitle = (r, t) => {
  const parts = [t(`w2a_match_${r.key}`) || KEY_STYLES[r.key]?.label || r.key];
  if (r.value) parts.push(`= ${r.value}`);
  if (r.side)  parts.push(`(${r.side})`);
  if (r.leadId) parts.push(`→ lead ${r.leadId}`);
  return parts.join(' ');
};

const MatchChips = ({ matchedBy = [], reasons = [], size = 'sm' }) => {
  const { t } = useLang();
  // Dedup by key while preserving order — prefer the reason object if we have it.
  const keys = Array.from(new Set(matchedBy));
  if (keys.length === 0) return <span className="text-zinc-300 text-xs">—</span>;
  return (
    <div className="flex flex-wrap gap-1" data-testid="match-chips">
      {keys.map((k) => {
        const style = KEY_STYLES[k] || { abbr: k.slice(0,2).toUpperCase(),
                                         cls: 'bg-zinc-100 text-zinc-600 border-zinc-200',
                                         label: k };
        const reason = reasons.find((r) => r.key === k);
        const title = reason ? makeTitle(reason, t) : (t(`w2a_match_${k}`) || style.label);
        const px = size === 'xs' ? 'px-1.5 py-0' : 'px-2 py-0.5';
        return (
          <span
            key={k}
            title={title}
            className={`inline-flex items-center text-[10px] font-mono font-semibold rounded-md border ${style.cls} ${px} leading-tight`}
            data-testid={`match-chip-${k}`}
          >
            {style.abbr}
          </span>
        );
      })}
    </div>
  );
};

export default MatchChips;
