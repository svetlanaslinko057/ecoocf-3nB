/**
 * InsightsCard.jsx
 * Visual primitives reused across all 5 verticals:
 *   - InsightsCard: solid white/dark card with optional header/actions
 *   - InsightsSection: page-section wrapper with anchor + title
 *   - InsightsEmpty / InsightsLoading / InsightsError
 *
 * All surfaces are SOLID (no transparency) and theme-safe.
 */
import React from 'react';
import { ArrowClockwise, Warning } from '@phosphor-icons/react';
import InsightsHelpTooltip from './InsightsHelpTooltip';

export const InsightsCard = ({ title, tip, actions, children, className = '', testId, padded = true }) => {
  return (
    <div
      className={`rounded-2xl border border-zinc-200 bg-white shadow-sm transition-[box-shadow,border-color] duration-150 hover:border-zinc-300 hover:shadow-md ${className}`}
      data-testid={testId}
    >
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3 sm:px-5">
          <div className="min-w-0">
            {tip ? (
              <InsightsHelpTooltip text={tip}>
                {typeof title === 'string' ? (
                  <h3 className="truncate text-sm font-medium text-zinc-900">{title}</h3>
                ) : title}
              </InsightsHelpTooltip>
            ) : (
              typeof title === 'string' ? (
                <h3 className="truncate text-sm font-medium text-zinc-900">{title}</h3>
              ) : title
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={padded ? 'p-4 sm:p-5' : ''}>{children}</div>
    </div>
  );
};

export const InsightsSection = ({ id, title, subtitle, tip, actions, children, className = '' }) => (
  <section id={id} className={`scroll-mt-32 ${className}`} data-testid={`insights-section-${id}`}>
    <div className="mb-3 flex items-end justify-between gap-3">
      <div className="min-w-0">
        {tip ? (
          <InsightsHelpTooltip text={tip}>
            <h2 className="truncate text-base font-semibold text-zinc-900 sm:text-lg">{title}</h2>
          </InsightsHelpTooltip>
        ) : (
          <h2 className="truncate text-base font-semibold text-zinc-900 sm:text-lg">{title}</h2>
        )}
        {subtitle && <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
    {children}
  </section>
);

export const InsightsLoading = ({ rows = 3, testId }) => (
  <div className="space-y-2" data-testid={testId || 'insights-card-loading'}>
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="h-10 animate-pulse rounded-md bg-zinc-100" />
    ))}
  </div>
);

export const InsightsEmpty = ({ title = 'No data', hint, testId }) => (
  <div className="flex flex-col items-center justify-center gap-1 py-10 text-center" data-testid={testId || 'insights-empty-state'}>
    <p className="text-sm font-medium text-zinc-700">{title}</p>
    {hint && <p className="max-w-md text-xs text-zinc-500">{hint}</p>}
  </div>
);

export const InsightsError = ({ message = 'Failed to load', onRetry, testId }) => (
  <div className="flex flex-col items-center justify-center gap-2 py-6 text-center" data-testid={testId || 'insights-error-state'}>
    <div className="flex items-center gap-2 text-sm text-red-700">
      <Warning size={16} weight="bold" />
      <span>{message}</span>
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
        data-testid="insights-error-retry-button"
      >
        <ArrowClockwise size={12} weight="bold" /> Retry
      </button>
    )}
  </div>
);

/** Inline metric chip used inside cards / tables. */
export const MetricChip = ({ label, value, tone = 'neutral', className = '' }) => {
  const toneClasses = {
    neutral: 'bg-zinc-100 text-zinc-700 border-zinc-200',
    positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    negative: 'bg-red-50 text-red-700 border-red-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    info: 'bg-sky-50 text-sky-700 border-sky-200',
  }[tone] || 'bg-zinc-100 text-zinc-700 border-zinc-200';
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium tabular-nums ${toneClasses} ${className}`}>
      {label && <span className="opacity-70">{label}</span>}
      <span>{value}</span>
    </span>
  );
};

/** Tiny dot used in row markers. */
export const SeverityDot = ({ severity = 'low' }) => {
  const cls = {
    critical: 'bg-red-500',
    high: 'bg-amber-500',
    medium: 'bg-sky-500',
    low: 'bg-zinc-400',
  }[severity] || 'bg-zinc-400';
  return <span className={`inline-block h-2 w-2 shrink-0 rounded-full ${cls}`} />;
};
