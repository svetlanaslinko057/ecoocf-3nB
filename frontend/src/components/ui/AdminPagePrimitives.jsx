/**
 * AdminPageHeader & AdminCard — canonical primitives for every admin page.
 *
 * Why this exists:
 *   Different admin pages used different header/card patterns (blue gradient
 *   bars, gray icons, double-bordered "card-in-card" wrappers, mismatched
 *   paddings & fonts). This file is the single source of truth.
 *
 * Use them like:
 *   <AdminPageHeader
 *     icon={Funnel}
 *     title="Customer Journey & Funnel"
 *     subtitle="Conversion analytics across the lifecycle."
 *     actions={(
 *       <>
 *         <WhiteSelect ... />
 *         <button>Refresh</button>
 *       </>
 *     )}
 *   />
 *
 *   <AdminCard padding="md">…body…</AdminCard>
 *
 * Both inherit Mazzard and the platform's #18181B / #FAFAFA palette.
 */
import React from 'react';

function cn(...xs) {
  return xs.filter(Boolean).join(' ');
}

/**
 * Page header — title block (icon + title + subtitle) on the LEFT,
 * primary actions docked to the top-RIGHT.
 *
 * Mobile rule:
 *   When `actions` is wider than ~80 px (i.e. ANY actions are provided), the
 *   header switches to a two-row layout so the title block is never squeezed
 *   into a per-character-wrap column. Title row gets full width, actions row
 *   sits below. On `sm:` and up we go back to one row with actions on the
 *   right — there is always enough room then.
 */
export function AdminPageHeader({
  icon: Icon,
  title,
  subtitle,
  actions,
  className = '',
  testId = 'admin-page-header',
}) {
  return (
    <header
      className={cn(
        'bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5',
        className,
      )}
      data-testid={testId}
    >
      {/*
        Layout invariant (BIBI master-admin standard, June 2026 — FINAL):
          • ALWAYS single-row: title block on the LEFT, actions on the RIGHT.
            This guarantees the canonical "icon top-left / refresh top-right"
            shape on EVERY viewport. Pages that need many wide actions
            (filter selects, CSV buttons, etc.) MUST NOT pass them through
            this primitive — they should render their own inline header
            (see AdminPaymentsPage / AdminInfoPage for examples).
          • Title block uses `min-w-0 flex-1` so it can shrink without
            pushing actions off-screen. Long titles wrap on word boundaries
            via `break-words` — they NEVER letter-wrap because there is
            always at least ~36 px (one icon) reserved on the right.
          • Actions wrapper uses `shrink-0` so a small icon button (the
            standard RefreshButton) always stays compact in the top-right
            corner — exactly where the design system pins it.
      */}
      <div className="flex flex-row items-start justify-between gap-2 sm:gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {Icon && (
            <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
              <Icon size={20} weight="bold" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h1
              className="text-xl sm:text-2xl font-bold tracking-tight text-[#18181B] leading-tight break-words"
              style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
            >
              {title}
            </h1>
            {subtitle && (
              <p className="mt-0.5 text-[12px] text-[#71717A] leading-relaxed break-words">
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {actions && (
          <div
            className="flex items-center gap-1.5 sm:gap-2 shrink-0"
            data-testid={`${testId}-actions`}
          >
            {actions}
          </div>
        )}
      </div>
    </header>
  );
}

/**
 * Card — the only acceptable wrapper for content sections on admin pages.
 *
 * Rules:
 *   • A child of <AdminCard> must NEVER be another <AdminCard>. Use
 *     `<AdminSection>` (no border, just spacing) for sub-sections inside.
 *   • Padding is calibrated for mobile (`p-4`) and tablet+ (`sm:p-5`).
 *   • Hover/clickable variants share the same outer geometry to avoid
 *     subtle border/shadow drift between pages.
 */
export function AdminCard({
  children,
  className = '',
  padding = 'md',          // 'none' | 'sm' | 'md' | 'lg'
  as: Tag = 'div',
  testId,
  ...rest
}) {
  const padClass =
    padding === 'none' ? '' :
    padding === 'sm'   ? 'p-3 sm:p-4' :
    padding === 'lg'   ? 'p-5 sm:p-6' :
                         'p-4 sm:p-5';
  return (
    <Tag
      className={cn(
        'bg-white border border-[#E4E4E7] rounded-2xl',
        padClass,
        className,
      )}
      data-testid={testId}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/**
 * Section — borderless wrapper used inside a card to group sub-content
 * with consistent vertical rhythm.  This is what you reach for when you
 * would otherwise have nested <AdminCard>'s — i.e. "card-in-card".
 */
export function AdminSection({
  children,
  title,
  description,
  className = '',
  titleClassName = '',
  actions,
}) {
  return (
    <section className={cn('space-y-3', className)}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h3
                className={cn(
                  'text-[10.5px] font-semibold uppercase tracking-[0.14em] text-[#71717A]',
                  titleClassName,
                )}
              >
                {title}
              </h3>
            )}
            {description && (
              <p className="mt-1 text-[12px] text-[#71717A]">{description}</p>
            )}
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * Metric/KPI tile — used on dashboards to show a single number with label.
 * Uses subtle gray inside-card variant to avoid double-bordering when sitting
 * INSIDE an <AdminCard>, but switches to bordered variant when standalone.
 */
export function AdminStat({
  label,
  value,
  delta,
  icon: Icon,
  tone = 'default', // 'default' | 'positive' | 'negative' | 'warning'
  inside = false,
  className = '',
}) {
  const valueColor =
    tone === 'positive' ? 'text-emerald-600' :
    tone === 'negative' ? 'text-rose-600' :
    tone === 'warning'  ? 'text-amber-600' :
                          'text-[#18181B]';
  const base = inside
    ? 'bg-[#FAFAFA] rounded-xl p-3 sm:p-4'
    : 'bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5';
  return (
    <div className={cn(base, className)}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[10.5px] sm:text-[11px] font-semibold uppercase tracking-[0.12em] text-[#71717A]">
          {label}
        </span>
        {Icon && <Icon size={14} className="text-[#A1A1AA]" />}
      </div>
      <div className={cn('text-[22px] sm:text-[26px] font-semibold tabular-nums leading-tight', valueColor)}>
        {value}
      </div>
      {delta && (
        <div className="mt-1 text-[11.5px] text-[#71717A]">{delta}</div>
      )}
    </div>
  );
}

export default AdminPageHeader;
