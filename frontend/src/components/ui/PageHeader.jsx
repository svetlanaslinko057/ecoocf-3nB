/**
 * Unified admin shell header — single source of truth across all admin pages.
 *
 * Final layout invariant (BIBI master-admin standard, June 2026):
 *
 *   ALL viewports — single row, icon top-left / actions top-right:
 *     ┌─────────────────────────────────────────────────────────────────────┐
 *     │ ┌─┐ Title (wraps on word-boundary, never letter-wrap) [act][act][↻] │
 *     │ │I│ Subtitle                                                        │
 *     │ └─┘                                                                 │
 *     └─────────────────────────────────────────────────────────────────────┘
 *
 *   PageTabs — ALWAYS horizontal scroll, never wrap.
 *
 * How letter-wrap is prevented:
 *   • Title block uses `flex-1 min-w-0` so it can shrink, but its parent
 *     reserves only SHRINK-0 width for actions. Crucially, labeled action
 *     buttons (Sync, New, "Action Center", "Run SLA Scan") collapse to
 *     icon-only at the `< sm` breakpoint using `responsiveIconOnly` on
 *     HeaderActionButton. That guarantees the actions cluster on mobile is
 *     at most ~3×36 px ≈ 108 px wide, leaving the title plenty of room to
 *     wrap on word boundaries instead of letter-by-letter.
 *
 * Tokens:
 *   icon block  : w-10 h-10 rounded-2xl bg-[#18181B] text-white (Phosphor 20/bold)
 *   title       : text-xl sm:text-2xl font-bold text-[#18181B]
 *   subtitle    : text-[12px] text-[#71717A]
 *   tabs shell  : bg-white border border-[#E4E4E7] rounded-2xl p-1
 *   tab active  : bg-[#18181B] text-white
 *   tab idle    : text-[#52525B] hover:bg-[#FAFAFA]
 *
 * Public API
 *   <PageHeader icon={Phosphor.IconComponent} title="…" subtitle="…" actions={<>…</>} />
 *   <PageTabs tabs={[{key,label,icon}]} active={tab} onChange={setTab} testId="…" />
 *   <HeaderActionButton icon={…} label="…" onClick={…} responsiveIconOnly />
 *
 * For the refresh action, use the canonical <RefreshButton> (icon-only black square).
 */

import React from 'react';
import { HelpTooltip } from './HelpTooltip';

/* ───────────────────────── PageHeader ───────────────────────── */

export const PageHeader = ({
  icon: Icon,
  title,
  subtitle,
  actions,
  className = '',
  testId,
}) => (
  <div
    className={`flex flex-row items-start justify-between gap-2 sm:gap-3 mb-6 ${className}`}
    data-testid={testId}
  >
    {/* Title block — flex-1 min-w-0 so long titles wrap on word boundary,
        never letter-wrap. Actions block stays shrink-0 right. */}
    <div className="flex items-start gap-3 flex-1 min-w-0">
      {Icon ? (
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <Icon size={20} weight="bold" />
        </div>
      ) : null}
      <div className="flex-1 min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-[#18181B] leading-tight break-words">
          {title}
        </h1>
        {subtitle ? (
          <p className="text-[12px] text-[#71717A] mt-0.5 leading-relaxed break-words">
            {subtitle}
          </p>
        ) : null}
      </div>
    </div>
    {actions ? (
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {actions}
      </div>
    ) : null}
  </div>
);

/* ───────────────────────── PageTabs ───────────────────────── */
/*
 * Horizontal-scroll rail. Tabs NEVER wrap to multiple rows — instead the
 * whole rail scrolls horizontally inside the rounded card.
 */
export const PageTabs = ({
  tabs = [],
  active,
  onChange,
  className = '',
  testId = 'page-tabs',
}) => (
  <div
    className={`bg-white border border-[#E4E4E7] rounded-2xl p-1 mb-6 max-w-full overflow-x-auto ${className}`}
    style={{ scrollbarWidth: 'thin' }}
    data-testid={testId}
  >
    <div className="flex gap-1 flex-nowrap whitespace-nowrap w-max">
      {tabs.map(({ key, label, icon: TabIcon, badge, tooltip }) => {
        const isActive = active === key;
        const btn = (
          <button
            key={key}
            onClick={() => onChange && onChange(key)}
            data-testid={`tab-${key}`}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-semibold transition-colors shrink-0 ${
              isActive
                ? 'bg-[#18181B] text-white'
                : 'text-[#52525B] hover:bg-[#FAFAFA]'
            }`}
          >
            {TabIcon ? <TabIcon size={14} weight="bold" /> : null}
            <span>{label}</span>
            {badge != null && badge !== '' ? (
              <span
                className={`ml-1 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold ${
                  isActive ? 'bg-white/20 text-white' : 'bg-[#F4F4F5] text-[#52525B]'
                }`}
              >
                {badge}
              </span>
            ) : null}
          </button>
        );
        return tooltip ? (
          <HelpTooltip key={key} text={tooltip} side="bottom">
            {btn}
          </HelpTooltip>
        ) : (
          React.cloneElement(btn, { key })
        );
      })}
    </div>
  </div>
);

/* ───────────────────────── HeaderActionButton ───────────────────────── */
/*
 * Convenience helper for header action buttons (Sync, New, etc.).
 *
 * Props:
 *   iconOnly           : permanently icon-only (no label, ever)
 *   responsiveIconOnly : icon-only on mobile (< sm), full label on sm+.
 *                        Used for labeled buttons in headers so the title
 *                        block always has room to render properly on mobile.
 *
 * For the refresh action, prefer the icon-only `<RefreshButton>` import.
 */
export const HeaderActionButton = ({
  icon: Icon,
  label,
  onClick,
  variant = 'secondary',
  disabled = false,
  testId,
  iconOnly = false,
  responsiveIconOnly = false,
}) => {
  const cls =
    variant === 'primary'
      ? 'bg-[#18181B] text-white hover:bg-black'
      : 'bg-white text-[#18181B] border border-[#E4E4E7] hover:bg-[#FAFAFA]';

  // Sizing strategy:
  //   iconOnly           : fixed 36×36 square
  //   responsiveIconOnly : 36×36 on mobile, padded text-button on sm+
  //   default            : padded text-button on all viewports
  const sizeClass = iconOnly
    ? 'w-9 h-9 justify-center px-0 py-0'
    : responsiveIconOnly
      ? 'w-9 h-9 px-0 py-0 justify-center sm:w-auto sm:h-auto sm:px-3 sm:py-2'
      : 'px-3 py-2';

  const labelClass = iconOnly
    ? 'hidden'
    : responsiveIconOnly
      ? 'hidden sm:inline'
      : '';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={iconOnly || responsiveIconOnly ? label : undefined}
      aria-label={iconOnly || responsiveIconOnly ? label : undefined}
      data-testid={testId}
      className={`inline-flex items-center gap-2 ${sizeClass} rounded-xl text-[12px] font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0 ${cls}`}
    >
      {Icon ? <Icon size={iconOnly ? 16 : 14} weight="bold" /> : null}
      {labelClass !== 'hidden' && <span className={labelClass}>{label}</span>}
    </button>
  );
};

export default PageHeader;
