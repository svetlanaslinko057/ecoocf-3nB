/**
 * Breadcrumb — навигационный путь "Section › Subsection › Current page".
 *
 * Usage:
 *   <Breadcrumb
 *     items={[
 *       { label: 'Team Dashboard', to: '/team' },
 *       { label: 'Managers', to: '/team/managers' },
 *       { label: 'John Doe' },           // last item — current page (not a link)
 *     ]}
 *   />
 *
 * Каждый item:
 *   - label: string                    — отображаемый текст
 *   - to?: string                      — если указан, render как Link
 *   - icon?: React.ComponentType       — опциональная иконка слева
 *
 * Последний item рендерится без ссылки (текущая страница). На мобиле длинные
 * крошки сжимаются: показываются только первый и последний, средние под "…".
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { CaretRight, DotsThree } from '@phosphor-icons/react';

const Breadcrumb = ({ items = [], className = '', testId = 'breadcrumb' }) => {
  const [expanded, setExpanded] = useState(false);

  if (!Array.isArray(items) || items.length === 0) return null;

  // Mobile collapsing: when >3 items, show first + "…" + last on mobile
  const shouldCollapse = items.length > 3;
  // We'll handle this with CSS — on mobile hide middle items
  // For simplicity, fall back to: if user clicks "…" we expand

  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex items-center gap-1 text-sm flex-wrap ${className}`}
      data-testid={testId}
    >
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        const isFirst = idx === 0;
        const isMiddle = !isFirst && !isLast;

        // On mobile, hide middle items unless expanded
        const hideOnMobile = shouldCollapse && isMiddle && !expanded;

        const Icon = item.icon;
        const labelEl = (
          <span className={`inline-flex items-center gap-1 ${isLast ? 'text-[#18181B] font-semibold' : 'text-[#71717A]'} truncate max-w-[160px] sm:max-w-[240px]`}>
            {Icon && <Icon size={14} weight="duotone" />}
            <span className="truncate">{item.label}</span>
          </span>
        );

        return (
          <React.Fragment key={`bc-${idx}`}>
            {/* Separator before this item (except first) */}
            {!isFirst && (
              <span
                className={`text-[#A1A1AA] flex-shrink-0 ${hideOnMobile ? 'hidden sm:inline-flex' : 'inline-flex'}`}
                aria-hidden="true"
              >
                <CaretRight size={14} weight="bold" />
              </span>
            )}

            {/* Show "..." collapsed middle indicator on mobile only when collapsed */}
            {shouldCollapse && !expanded && idx === 1 && (
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className="inline-flex sm:hidden items-center px-1 py-0.5 rounded hover:bg-[#F4F4F5] text-[#71717A] flex-shrink-0"
                aria-label="Show full path"
                data-testid={`${testId}-expand`}
              >
                <DotsThree size={16} weight="bold" />
              </button>
            )}
            {shouldCollapse && !expanded && idx === 1 && (
              <span className="text-[#A1A1AA] inline-flex sm:hidden flex-shrink-0" aria-hidden="true">
                <CaretRight size={14} weight="bold" />
              </span>
            )}

            {/* Item itself */}
            <span className={hideOnMobile ? 'hidden sm:inline-flex' : 'inline-flex'}>
              {!isLast && item.to ? (
                <Link
                  to={item.to}
                  data-testid={`${testId}-link-${idx}`}
                  className="inline-flex items-center px-1.5 py-1 -my-1 rounded-md hover:bg-[#F4F4F5] hover:text-[#18181B] transition-colors"
                >
                  {labelEl}
                </Link>
              ) : (
                <span
                  data-testid={`${testId}-current`}
                  aria-current={isLast ? 'page' : undefined}
                  className="inline-flex items-center px-1.5 py-1 -my-1"
                >
                  {labelEl}
                </span>
              )}
            </span>
          </React.Fragment>
        );
      })}
    </nav>
  );
};

export default Breadcrumb;
