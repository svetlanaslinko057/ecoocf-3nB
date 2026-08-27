/**
 * InsightsHelpTooltip.jsx
 *
 * Reused everywhere across /admin/insights — hover-only tooltip wrapper.
 *
 * Tooltip is shown by hovering the wrapped child element directly — there is
 * NO visible "?" help icon. The component is now a thin wrapper around the
 * shadcn/Radix `Tooltip` so it inherits keyboard / accessibility behaviour
 * without adding any extra UI affordance.
 *
 *   <InsightsHelpTooltip text={...}>           // wrap children — hover them
 *     <span>Revenue MTD</span>
 *   </InsightsHelpTooltip>
 *
 *   <InsightsHelpTooltip text={...} />         // no children → renders nothing
 */
import React from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../ui/tooltip';

/** Shared tooltip-panel className — same look across all Insights surfaces. */
const PANEL_CLASS =
  'max-w-xs sm:max-w-sm bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg';

const InsightsHelpTooltip = ({
  text,
  side = 'top',
  align = 'start',
  delay = 150,
  className = '',
  children,
}) => {
  // No tooltip text → just render children (or nothing).
  if (!text) return children || null;
  // No children to anchor the tooltip → render nothing (no standalone "?" icon).
  if (!children) return null;

  return (
    <TooltipProvider delayDuration={delay}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className={`inline-flex cursor-help items-center ${className}`}>
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent side={side} align={align} className={PANEL_CLASS}>
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default InsightsHelpTooltip;
