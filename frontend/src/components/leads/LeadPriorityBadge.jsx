import React from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

/**
 * Wave 10A — Priority bucket badge (A/B/C/D)
 *  A — Hot   (red)
 *  B — Active (orange)
 *  C — Watch (blue)
 *  D — Cold  (grey)
 *
 * Accepts either:
 *   <LeadPriorityBadge priority={{ bucket, label, score, reasons }} />
 *  OR
 *   <LeadPriorityBadge bucket="A" score={87} reasons={['...']} />
 */
export const PRIORITY_CFG = {
  A: { label: 'Hot',    cls: 'bg-red-50 text-red-700 border-red-200',         dot: '#DC2626' },
  B: { label: 'Active', cls: 'bg-amber-50 text-amber-700 border-amber-200',   dot: '#F59E0B' },
  C: { label: 'Watch',  cls: 'bg-sky-50 text-sky-700 border-sky-200',         dot: '#0EA5E9' },
  D: { label: 'Cold',   cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',     dot: '#71717A' },
};

const SIZE = {
  xs: { px: 'px-1 py-0',    text: 'text-[9px]',  gap: 'gap-0.5' },
  sm: { px: 'px-1.5 py-0.5', text: 'text-[10px]', gap: 'gap-1' },
  md: { px: 'px-2 py-0.5',   text: 'text-[11px]', gap: 'gap-1' },
  lg: { px: 'px-2.5 py-1',   text: 'text-xs',     gap: 'gap-1.5' },
};

const Inner = ({ bucket, label, score, size = 'sm', showLabel = true, testId }) => {
  const cfg = PRIORITY_CFG[bucket] || PRIORITY_CFG.D;
  const s   = SIZE[size] || SIZE.sm;
  return (
    <span
      className={`inline-flex items-center ${s.gap} rounded-full border font-bold uppercase tracking-wider ${cfg.cls} ${s.px} ${s.text}`}
      data-testid={testId || `lead-priority-${bucket}`}
    >
      <span className="font-extrabold tabular-nums">{bucket}</span>
      {showLabel ? <span>{label || cfg.label}</span> : null}
      {typeof score === 'number' && size !== 'xs' ? (
        <span className="opacity-70 tabular-nums">· {score}</span>
      ) : null}
    </span>
  );
};

const LeadPriorityBadge = ({ priority, bucket, score, reasons, label, size, showLabel = true, testId }) => {
  const p = priority || { bucket, score, reasons, label };
  if (!p?.bucket) return null;
  const rs = (p.reasons || []).slice(0, 4);
  if (!rs.length) {
    return <Inner bucket={p.bucket} label={p.label} score={p.score} size={size} showLabel={showLabel} testId={testId} />;
  }
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span><Inner bucket={p.bucket} label={p.label} score={p.score} size={size} showLabel={showLabel} testId={testId} /></span>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="start" className="max-w-xs bg-white border border-[#E4E4E7] rounded-lg shadow-lg p-2.5">
          <div className="text-[11px] font-semibold text-[#52525B] mb-1">Why this priority</div>
          <ul className="text-[12px] text-[#18181B] space-y-0.5">
            {rs.map((r, i) => (<li key={i}>· {r}</li>))}
          </ul>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default LeadPriorityBadge;
