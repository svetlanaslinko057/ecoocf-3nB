/**
 * SectionTabs — single canonical tab component for the whole platform.
 *
 * Why this exists:
 *   Different pages used different tab visuals (underline, solid black pill,
 *   white outline card, yellow halo, etc.). This caused the UI to feel like
 *   four different products glued together. SectionTabs is the ONE source of
 *   truth — every page-level tab strip should use it.
 *
 * Design contract (the unified PageTabs pill standard):
 *   • Track:   bg white + 1px #E4E4E7 border, rounded-2xl, p-1.
 *   • Active:  bg #18181B (solid black) + white text, semibold.
 *   • Idle:    transparent, neutral text, hover -> bg #FAFAFA + black text.
 *   • Icons:   13–15px, bold weight on both states.
 *
 * Usage:
 *   <SectionTabs
 *     tabs={[{ id:'overview', label:'Overview', icon:Eye }, ...]}
 *     activeId={tab}
 *     onChange={setTab}
 *   />
 */
import React from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './tooltip';

function classNames(...xs) {
  return xs.filter(Boolean).join(' ');
}

export default function SectionTabs({
  tabs,
  activeId,
  onChange,
  className = '',
  size = 'md',          // 'sm' | 'md' | 'lg'
  testIdPrefix = 'tab',
  ariaLabel = 'Sections',
  fullWidth = false,    // stretch each tab to equal width inside the track
}) {
  const sizeClass =
    size === 'sm' ? 'px-3 py-1.5 text-[12px]' :
    size === 'lg' ? 'px-4 py-2 text-[14px]'   :
                    'px-3.5 py-1.5 text-[12.5px] sm:text-[13px]';

  const iconSize = size === 'lg' ? 15 : size === 'sm' ? 12 : 14;

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={classNames(
        'inline-flex p-1 bg-white border border-[#E4E4E7] rounded-2xl gap-1 max-w-full overflow-x-auto no-scrollbar',
        fullWidth && 'w-full',
        className,
      )}
      style={{ scrollbarWidth: 'none' }}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = activeId === tab.id;
        const btn = (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            data-testid={`${testIdPrefix}-${tab.id}`}
            disabled={tab.disabled}
            className={classNames(
              'inline-flex items-center justify-center gap-1.5 sm:gap-2 rounded-xl whitespace-nowrap shrink-0 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10 disabled:opacity-40 disabled:cursor-not-allowed',
              sizeClass,
              fullWidth && 'flex-1',
              active
                ? 'bg-[#18181B] text-white font-semibold hover:bg-black'
                : 'bg-transparent text-[#52525B] hover:bg-[#FAFAFA] hover:text-[#18181B] font-medium',
            )}
            style={{ fontFamily: 'inherit' }}
          >
            {Icon && (
              <Icon size={iconSize} weight="bold" />
            )}
            <span className="truncate">{tab.label}</span>
            {tab.badge != null && (
              <span
                className={classNames(
                  'ml-0.5 inline-flex items-center justify-center min-w-[16px] h-[16px] px-1 rounded-full text-[10px] font-semibold',
                  active
                    ? 'bg-white/20 text-white'
                    : 'bg-[#F4F4F5] text-[#52525B]',
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );

        // If a tab provides a `tip`, wrap it with a hover Tooltip (no icon).
        if (tab.tip) {
          return (
            <TooltipProvider key={tab.id} delayDuration={120}>
              <Tooltip>
                <TooltipTrigger asChild>{btn}</TooltipTrigger>
                <TooltipContent
                  side="bottom"
                  className="max-w-xs bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2 rounded-lg shadow-lg"
                >
                  {tab.tip}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          );
        }
        return btn;
      })}
    </div>
  );
}

/**
 * Segmented helper for option-pills (e.g. "Deposit / Final / Purchase" in
 * Create Contract). Uses the same black-outline language as SectionTabs but
 * is laid out as a responsive grid that wraps cleanly on small screens.
 */
export function OptionPillGroup({
  options,
  value,
  onChange,
  className = '',
  testIdPrefix = 'opt',
  ariaLabel = 'Options',
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={classNames(
        'grid grid-cols-2 sm:grid-cols-3 gap-2',
        className,
      )}
    >
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            data-testid={`${testIdPrefix}-${opt.value}`}
            className={classNames(
              'px-3 py-2 rounded-xl text-[12.5px] sm:text-[13px] font-semibold uppercase tracking-wide transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10',
              active
                ? 'bg-[#18181B] text-white hover:bg-black'
                : 'bg-white text-[#71717A] border border-[#E4E4E7] hover:text-[#18181B] hover:border-[#A1A1AA]',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
