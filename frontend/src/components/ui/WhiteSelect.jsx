/**
 * WhiteSelect — кастомный белый dropdown (v3 — portal + auto-flip).
 *
 * Особенности v3:
 *  • Popover рендерится через React Portal в document.body — больше не обрезается
 *    overflow:hidden родительских контейнеров и не перекрывается соседними
 *    карточками. Z-index 9999.
 *  • Auto-flip: если снизу триггера не хватает места, popover открывается вверх.
 *  • Min-width: popover не уже триггера и не уже max-content, чтобы длинные
 *    labels были читаемы даже если триггер маленький (inline в таблицах).
 *  • Закрытие при скролле страницы, ресайзе окна, клике вне и Escape.
 *
 * API не изменился — совместим с prop-API (options) и drop-in (children <option>).
 */
import React, { useState, useRef, useEffect, useCallback, useLayoutEffect, Children, isValidElement } from 'react';
import { createPortal } from 'react-dom';
import { CaretDown, Check } from '@phosphor-icons/react';

function extractOptionsFromChildren(children) {
  const flat = [];
  const walk = (node) => {
    if (node == null || typeof node === 'boolean') return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (!isValidElement(node)) return;
    const t = node.type;
    if (t === 'option' || t === 'OPTION') {
      const value = node.props.value !== undefined
        ? String(node.props.value)
        : '';
      const labelChildren = node.props.children;
      let label;
      if (typeof labelChildren === 'string' || typeof labelChildren === 'number') {
        label = String(labelChildren);
      } else if (Array.isArray(labelChildren)) {
        label = labelChildren
          .filter(c => typeof c === 'string' || typeof c === 'number')
          .join('');
        if (!label) label = String(value);
      } else {
        label = String(value);
      }
      flat.push({ value, label, disabled: !!node.props.disabled });
    } else if (t === 'optgroup' || t === 'OPTGROUP') {
      flat.push({ value: `__group_${node.props.label}`, label: node.props.label, isGroup: true });
      walk(node.props.children);
    } else if (node.props && node.props.children) {
      walk(node.props.children);
    }
  };
  walk(children);
  return flat;
}

const WhiteSelect = React.forwardRef(function WhiteSelect({
  value = '',
  onChange,
  options,
  children,
  placeholder,
  className = '',
  disabled = false,
  ariaLabel,
  searchable,
  placement = 'auto', // 'auto' | 'bottom' | 'top'
  ...rest
}, ref) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0, openUp: false });
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const testId = rest['data-testid'];

  const resolvedOptions = (Array.isArray(options) && options.length > 0)
    ? options
    : extractOptionsFromChildren(children);

  const recalcPosition = useCallback(() => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const POPOVER_MAX_H = 340;
    const MARGIN = 8;
    const GAP = 6;

    const spaceBelow = vh - rect.bottom;
    const spaceAbove = rect.top;

    // Decide direction based on `placement` prop
    let openUp;
    if (placement === 'top') {
      openUp = true;
    } else if (placement === 'bottom') {
      openUp = false;
    } else {
      // auto: open up only when there isn't enough room below and there's more above
      openUp = spaceBelow < Math.min(240, POPOVER_MAX_H + GAP) && spaceAbove > spaceBelow;
    }

    const minWidth = rect.width;
    const maxWidth = Math.max(minWidth, Math.min(360, vw - MARGIN * 2));

    let left = rect.left;
    if (left + maxWidth > vw - MARGIN) {
      left = Math.max(MARGIN, vw - MARGIN - maxWidth);
    }
    if (left < MARGIN) left = MARGIN;

    const top = openUp
      ? Math.max(MARGIN, rect.top - GAP)
      : rect.bottom + GAP;

    setPos({ top, left, width: maxWidth, minWidth, openUp });
  }, [placement]);

  // Recalc when opens, on scroll, on resize
  useLayoutEffect(() => {
    if (!isOpen) return;
    recalcPosition();
  }, [isOpen, recalcPosition]);

  useEffect(() => {
    if (!isOpen) return;
    const onScroll = () => recalcPosition();
    const onResize = () => recalcPosition();
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
  }, [isOpen, recalcPosition]);

  // Close on outside click / escape
  useEffect(() => {
    if (!isOpen) return;
    const onDocClick = (e) => {
      const inTrigger = wrapRef.current && wrapRef.current.contains(e.target);
      const inMenu = menuRef.current && menuRef.current.contains(e.target);
      if (!inTrigger && !inMenu) {
        setIsOpen(false);
        setQuery('');
      }
    };
    const onEsc = (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEsc);
    };
  }, [isOpen]);

  const selected = resolvedOptions.find(
    (o) => !o.isGroup && String(o.value) === String(value ?? ''),
  );
  const triggerLabel = selected?.label || placeholder || '— select —';

  const handleSelect = useCallback(
    (val, opt) => {
      if (opt?.disabled || opt?.isGroup) return;
      if (typeof onChange === 'function') {
        const syntheticEvent = {
          target: { value: val, name: rest.name },
          currentTarget: { value: val, name: rest.name },
          preventDefault: () => {},
          stopPropagation: () => {},
          persist: () => {},
        };
        try {
          onChange(syntheticEvent);
        } catch {
          onChange(val);
        }
      }
      setIsOpen(false);
      setQuery('');
    },
    [onChange, rest.name],
  );

  const searchEnabled = searchable !== undefined
    ? !!searchable
    : resolvedOptions.length > 8;
  const filtered = searchEnabled && query
    ? resolvedOptions.filter((o) =>
        o.isGroup || (o.label || '').toLowerCase().includes(query.toLowerCase()),
      )
    : resolvedOptions;

  // Portal popover content
  const popoverEl = isOpen && typeof document !== 'undefined' ? createPortal(
    <div
      ref={menuRef}
      role="listbox"
      data-testid={testId ? `${testId}-menu` : undefined}
      style={{
        position: 'fixed',
        top: pos.openUp ? undefined : pos.top,
        bottom: pos.openUp ? (window.innerHeight - pos.top) : undefined,
        left: pos.left,
        width: pos.width,
        minWidth: pos.minWidth,
        zIndex: 9999,
        maxHeight: 340,
        transformOrigin: pos.openUp ? 'bottom center' : 'top center',
        animation: 'ws-popover-in 140ms cubic-bezier(0.16, 1, 0.3, 1)',
      }}
      className="bg-white border border-[#E4E4E7] rounded-xl shadow-xl overflow-hidden flex flex-col"
    >
      {searchEnabled && (
        <div className="p-2 border-b border-[#F4F4F5] bg-white sticky top-0 z-10 flex-shrink-0">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            placeholder="Search…"
            className="w-full text-sm px-3 py-2 rounded-lg bg-[#F9FAFB] border border-transparent focus:outline-none focus:bg-white focus:border-[#E4E4E7]"
            data-testid={testId ? `${testId}-search` : undefined}
          />
        </div>
      )}
      <div className="overflow-y-auto py-1 flex-1">
        {filtered.length === 0 ? (
          <div className="px-4 py-3 text-sm text-[#A1A1AA] text-center">
            No matches
          </div>
        ) : (
          filtered.map((opt, idx) => {
            if (opt.isGroup) {
              return (
                <div
                  key={`group-${idx}-${opt.label}`}
                  className="px-4 pt-3 pb-1 text-[10px] uppercase tracking-wider text-[#A1A1AA] font-semibold"
                >
                  {opt.label}
                </div>
              );
            }
            const isSel = String(opt.value) === String(value ?? '');
            return (
              <button
                key={`${opt.value}__${idx}`}
                type="button"
                role="option"
                aria-selected={isSel}
                disabled={opt.disabled}
                onClick={() => handleSelect(opt.value, opt)}
                data-testid={testId ? `${testId}-option-${opt.value || 'empty'}` : undefined}
                className={`w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left transition-colors
                  ${opt.disabled ? 'opacity-50 cursor-not-allowed' : ''}
                  ${isSel
                    ? 'bg-[#F4F4F5] text-[#18181B] font-medium'
                    : 'text-[#3F3F46] hover:bg-[#F4F4F5]'}
                `}
              >
                <span className="flex-1 truncate">{opt.label}</span>
                {isSel && (
                  <Check size={16} weight="bold" className="flex-shrink-0 text-[#18181B]" />
                )}
              </button>
            );
          })
        )}
      </div>
    </div>,
    document.body,
  ) : null;

  return (
    <div className={`relative w-full min-w-0 ${className}`} ref={wrapRef}>
      <button
        ref={(node) => { buttonRef.current = node; if (typeof ref === 'function') ref(node); else if (ref) ref.current = node; }}
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={ariaLabel}
        data-testid={testId}
        className={`flex items-center justify-between gap-2 w-full min-w-0 bg-white border rounded-xl px-3.5 py-2.5 min-h-[2.75rem] text-sm text-left transition-all
          focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10
          ${isOpen ? 'border-[#18181B] ring-2 ring-[#18181B]/10' : 'border-[#E4E4E7] hover:border-[#A1A1AA]'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <span
          className={`flex-1 min-w-0 truncate leading-snug ${selected ? 'text-[#18181B]' : 'text-[#A1A1AA]'}`}
          title={typeof triggerLabel === 'string' ? triggerLabel : undefined}
        >
          {triggerLabel}
        </span>
        <CaretDown
          size={16}
          className={`flex-shrink-0 text-[#71717A] transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>
      {popoverEl}
    </div>
  );
});

export default WhiteSelect;
