import React from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

/**
 * Wave 11 — Deal Health Badge
 *
 *  healthy           — green
 *  waiting_customer  — amber
 *  blocked           — red
 *  overdue           — red
 *  risk              — red-dark
 *  cancelled         — zinc
 */
export const DEAL_HEALTH_CFG = {
  healthy:          { label: 'Healthy',          cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',   dot: '#10B981' },
  waiting_customer: { label: 'Waiting customer', cls: 'bg-amber-50 text-amber-800 border-amber-200',         dot: '#F59E0B' },
  blocked:          { label: 'Blocked',          cls: 'bg-red-50 text-red-700 border-red-200',               dot: '#DC2626' },
  overdue:          { label: 'Overdue',          cls: 'bg-orange-50 text-orange-800 border-orange-200',      dot: '#EA580C' },
  risk:             { label: 'Risk',             cls: 'bg-red-100 text-red-800 border-red-300',              dot: '#991B1B' },
  cancelled:        { label: 'Cancelled',        cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',           dot: '#71717A' },
};

const SIZE = {
  sm: { px: 'px-1.5 py-0.5', text: 'text-[10px]' },
  md: { px: 'px-2 py-0.5',   text: 'text-[11px]' },
  lg: { px: 'px-2.5 py-1',   text: 'text-xs' },
};

const DealHealthBadge = ({ health, size = 'md', testId }) => {
  if (!health?.state) return null;
  const cfg = DEAL_HEALTH_CFG[health.state] || DEAL_HEALTH_CFG.healthy;
  const s   = SIZE[size] || SIZE.md;
  const reason = health.reason;

  const inner = (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold uppercase tracking-wider ${cfg.cls} ${s.px} ${s.text}`}
      data-testid={testId || `deal-health-${health.state}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {cfg.label}
    </span>
  );

  if (!reason) return inner;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild><span>{inner}</span></TooltipTrigger>
        <TooltipContent side="bottom" align="start" className="max-w-xs bg-white border border-[#E4E4E7] rounded-lg shadow-lg p-2.5">
          <div className="text-[11px] font-semibold text-[#52525B] mb-0.5">Why this state</div>
          <div className="text-[12px] text-[#18181B]">{reason}</div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default DealHealthBadge;
