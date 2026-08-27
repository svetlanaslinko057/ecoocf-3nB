/**
 * RefreshButton — single canonical "reload data" button used across the
 * entire admin app.
 *
 * Visual contract (the user-requested standard):
 *   • Solid black square (#18181B), 9–10mm tall, rounded-xl.
 *   • White ArrowsClockwise icon, NO text label, NO surrounding card.
 *   • Hover: lifts to #27272A. Active: brief 180° spin animation.
 *   • Accessible: `aria-label` always provided (defaults to "Refresh").
 *
 * Why this exists:
 *   Every admin page used to render its own variant — "↻ Refresh" with white
 *   outline, blue text, black outline, gray pill, etc. The mismatch made the
 *   UI feel inconsistent. Now there is ONE component, used everywhere.
 *
 * Usage:
 *   <RefreshButton onClick={fetchData} loading={isFetching} />
 */
import React from 'react';
import { ArrowsClockwise } from '@phosphor-icons/react';

export default function RefreshButton({
  onClick,
  loading = false,
  disabled = false,
  ariaLabel = 'Refresh',
  size = 'md', // 'sm' (32px) | 'md' (36px) | 'lg' (40px)
  className = '',
  testId = 'refresh-btn',
  title,
}) {
  const sizePx =
    size === 'sm' ? 'w-8 h-8'   :
    size === 'lg' ? 'w-10 h-10' :
                    'w-9 h-9';
  const iconPx = size === 'sm' ? 14 : size === 'lg' ? 18 : 16;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      title={title || ariaLabel}
      aria-label={ariaLabel}
      data-testid={testId}
      className={[
        'inline-flex items-center justify-center',
        sizePx,
        'rounded-xl bg-[#18181B] text-white',
        'hover:bg-[#27272A] active:bg-[#000000]',
        'transition-colors',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15',
        'shrink-0',
        className,
      ].filter(Boolean).join(' ')}
    >
      <ArrowsClockwise
        size={iconPx}
        weight="bold"
        className={loading ? 'animate-spin' : ''}
      />
    </button>
  );
}
