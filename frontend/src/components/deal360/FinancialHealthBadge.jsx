import React from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

/**
 * Wave 12B — Financial Health Badge
 *
 *  healthy    — green   — score >= 80
 *  warning    — amber   — score >= 60
 *  at_risk    — orange  — score >= 40
 *  critical   — red     — score <  40
 *  cancelled  — zinc    — deal cancelled
 *
 *  Distinct from `DealHealthBadge` (operational/process health). The two
 *  badges can disagree — that's exactly the case TL/owner want to spot.
 */
export const FIN_HEALTH_CFG = {
  healthy:   { label: 'Financial · Healthy',   cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: '#10B981' },
  warning:   { label: 'Financial · Warning',   cls: 'bg-amber-50 text-amber-800 border-amber-200',       dot: '#F59E0B' },
  at_risk:   { label: 'Financial · At Risk',   cls: 'bg-orange-50 text-orange-800 border-orange-200',    dot: '#EA580C' },
  critical:  { label: 'Financial · Critical',  cls: 'bg-red-50 text-red-700 border-red-200',             dot: '#DC2626' },
  cancelled: { label: 'Financial · Cancelled', cls: 'bg-zinc-100 text-zinc-700 border-zinc-200',         dot: '#71717A' },
};

const SIZE = {
  sm: { px: 'px-1.5 py-0.5', text: 'text-[10px]' },
  md: { px: 'px-2 py-0.5',   text: 'text-[11px]' },
  lg: { px: 'px-2.5 py-1',   text: 'text-xs' },
};

const fmtMoney = (n, ccy = 'EUR') => {
  const num = Number(n || 0);
  try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: ccy, maximumFractionDigits: 0 }).format(num); }
  catch { return `${ccy} ${num.toFixed(0)}`; }
};

const FinancialHealthBadge = ({ health, size = 'md', testId }) => {
  if (!health || !health.segment) return null;
  const cfg = FIN_HEALTH_CFG[health.segment] || FIN_HEALTH_CFG.healthy;
  const s   = SIZE[size] || SIZE.md;
  const score = typeof health.score === 'number' ? health.score : null;
  const reasons = Array.isArray(health.reasons) ? health.reasons : [];
  const metrics = health.metrics || {};

  const inner = (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold uppercase tracking-wider ${cfg.cls} ${s.px} ${s.text}`}
      data-testid={testId || `fin-health-${health.segment}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: cfg.dot }} />
      {cfg.label}
      {score != null ? <span className="tabular-nums opacity-70">{score}</span> : null}
    </span>
  );

  if (reasons.length === 0 && !metrics.outstanding) return inner;

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild><span>{inner}</span></TooltipTrigger>
        <TooltipContent
          side="bottom"
          align="start"
          className="max-w-xs bg-white border border-[#E4E4E7] rounded-lg shadow-lg p-3"
        >
          <div className="text-[11px] font-bold uppercase tracking-wider text-[#52525B] mb-1.5">
            Financial Health · {score != null ? `${score} / 100` : cfg.label}
          </div>

          {metrics.expected ? (
            <div className="text-[11px] text-[#71717A] mb-2 grid grid-cols-3 gap-2">
              <div>
                <div className="text-[10px] uppercase">Expected</div>
                <div className="text-[12px] font-semibold text-[#18181B] tabular-nums">{fmtMoney(metrics.expected)}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase">Received</div>
                <div className="text-[12px] font-semibold text-emerald-700 tabular-nums">{fmtMoney(metrics.received)}</div>
              </div>
              <div>
                <div className="text-[10px] uppercase">Outstanding</div>
                <div className="text-[12px] font-semibold text-red-700 tabular-nums">{fmtMoney(metrics.outstanding)}</div>
              </div>
            </div>
          ) : null}

          {reasons.length > 0 ? (
            <ul className="space-y-0.5">
              {reasons.map((r, i) => (
                <li key={i} className="text-[12px] text-[#18181B] flex items-start gap-1.5">
                  <span className="text-[#A1A1AA] mt-0.5">•</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default FinancialHealthBadge;
