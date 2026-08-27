import React from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

export const LEAD_HEALTH_CFG = {
  healthy: { emoji: '🟢', label: 'Healthy',  cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', ring: '#10B981' },
  warning: { emoji: '🟡', label: 'Warning',  cls: 'bg-amber-50 text-amber-700 border-amber-200',       ring: '#F59E0B' },
  overdue: { emoji: '🔴', label: 'Overdue',  cls: 'bg-red-50 text-red-700 border-red-200',              ring: '#DC2626' },
  stale:   { emoji: '⚪', label: 'Stale',     cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',           ring: '#71717A' },
  dead:    { emoji: '⚫', label: 'Dead',      cls: 'bg-zinc-900/10 text-zinc-700 border-zinc-300',       ring: '#3F3F46' },
  converted: { emoji: '🏆', label: 'Converted', cls: 'bg-emerald-100 text-emerald-800 border-emerald-300', ring: '#15803D' },
};

const SIZE = {
  xs: { px: 'px-1.5 py-0.5',  text: 'text-[10px]' },
  sm: { px: 'px-2 py-0.5',    text: 'text-[11px]' },
  md: { px: 'px-2.5 py-1',    text: 'text-xs' },
  lg: { px: 'px-3 py-1.5',    text: 'text-sm' },
};

const Inner = ({ health, size = 'md', showScore = true, testId }) => {
  if (!health) return null;
  const cfg = LEAD_HEALTH_CFG[health.status] || LEAD_HEALTH_CFG.warning;
  const s = SIZE[size] || SIZE.md;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-semibold ${cfg.cls} ${s.px} ${s.text}`}
      data-testid={testId || `lead-health-${health.status}`}
    >
      <span>{cfg.emoji}</span>
      <span>{cfg.label}</span>
      {showScore && typeof health.score === 'number' ? (
        <span className="opacity-70 tabular-nums">· {health.score}</span>
      ) : null}
    </span>
  );
};

const LeadHealthBadge = ({ health, size, showScore = true, testId }) => {
  if (!health) return null;
  const reasons = (health.reasons || []).slice(0, 4);
  if (!reasons.length) return <Inner health={health} size={size} showScore={showScore} testId={testId} />;
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span><Inner health={health} size={size} showScore={showScore} testId={testId} /></span>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="start" className="max-w-xs bg-white border border-[#E4E4E7] rounded-lg shadow-lg p-2.5">
          <div className="text-[11px] font-semibold text-[#52525B] mb-1">Why this score</div>
          <ul className="text-[12px] text-[#18181B] space-y-0.5">
            {reasons.map((r, i) => (<li key={i}>• {r}</li>))}
          </ul>
          {typeof health.days_since_contact === 'number' ? (
            <div className="mt-2 text-[10px] text-[#71717A]">
              Last contact: {health.days_since_contact}d ago
            </div>
          ) : null}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default LeadHealthBadge;
