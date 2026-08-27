import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, Check } from 'lucide-react';

/**
 * BibiSelect — fully custom dropdown styled in BIBI palette.
 *
 * Props:
 *   value       : string                 — currently selected option value
 *   onChange    : (value) => void        — called when user picks an option
 *   options     : [{ value, label, hint }]
 *   placeholder : string
 *   label       : string (optional, rendered above the control)
 *   size        : 'md' | 'lg'            (default 'md')
 *   disabled    : boolean
 *   testId      : string
 *
 * Notes:
 *   - Uses a button + absolutely-positioned listbox (NO native select).
 *   - Closes on outside click / Esc.
 *   - Keyboard accessible (Up/Down/Home/End/Enter/Space).
 *   - Matches the dark card (#1D1D1B) + amber accent (#FEAE00) language.
 */
export default function BibiSelect({
  value,
  onChange,
  options = [],
  placeholder = 'Select…',
  label,
  size = 'md',
  disabled = false,
  testId,
  className = '',
}) {
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const rootRef = useRef(null);
  const listRef = useRef(null);

  const selected = options.find((o) => o.value === value);

  // Close on outside click
  useEffect(() => {
    if (!open) return undefined;
    const onDocClick = (e) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  // Close on Esc + focus option on open
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setOpen(false);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(options.length - 1, (i < 0 ? -1 : i) + 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(0, (i < 0 ? options.length : i) - 1));
      } else if (e.key === 'Home') {
        e.preventDefault();
        setActiveIdx(0);
      } else if (e.key === 'End') {
        e.preventDefault();
        setActiveIdx(options.length - 1);
      } else if (e.key === 'Enter' || e.key === ' ') {
        if (activeIdx >= 0 && activeIdx < options.length) {
          e.preventDefault();
          const opt = options[activeIdx];
          onChange?.(opt.value);
          setOpen(false);
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, activeIdx, options, onChange]);

  // When opening, scroll active into view
  useEffect(() => {
    if (!open || activeIdx < 0) return;
    const el = listRef.current?.querySelector(`[data-idx="${activeIdx}"]`);
    if (el?.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }, [open, activeIdx]);

  const toggle = useCallback(() => {
    if (disabled) return;
    setOpen((v) => {
      const next = !v;
      if (next) {
        const idx = options.findIndex((o) => o.value === value);
        setActiveIdx(idx >= 0 ? idx : 0);
      }
      return next;
    });
  }, [disabled, options, value]);

  const pick = (opt) => {
    onChange?.(opt.value);
    setOpen(false);
  };

  const heightCls = size === 'lg' ? 'h-[52px]' : 'h-12';
  const textCls = size === 'lg' ? 'text-[15px]' : 'text-[14px]';

  return (
    <div
      ref={rootRef}
      className={`relative ${className}`}
      data-testid={testId}
    >
      {label ? (
        <label className="block text-[12px] uppercase tracking-wider text-[#8A8A8A] mb-2">
          {label}
        </label>
      ) : null}

      {/* Trigger */}
      <button
        type="button"
        onClick={toggle}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`relative w-full ${heightCls} ${textCls} flex items-center justify-between gap-3 px-4 rounded-md border transition-colors text-left
          ${open ? 'border-[#FEAE00]' : 'border-[#555452] hover:border-[#7a7a78]'}
          bg-transparent text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:border-[#FEAE00]`}
        data-testid={testId ? `${testId}-trigger` : undefined}
      >
        <span className={`truncate ${selected ? 'text-white' : 'text-[#6A6A6A]'}`}>
          {selected?.label || placeholder}
        </span>
        <ChevronDown
          size={16}
          className={`flex-shrink-0 text-[#FEAE00] transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Popover */}
      {open ? (
        <div
          ref={listRef}
          role="listbox"
          aria-label={label}
          className="absolute z-50 mt-2 left-0 right-0 max-h-[280px] overflow-auto rounded-md border border-[#3a3a38] bg-[#161614] shadow-[0_12px_40px_rgba(0,0,0,0.6)] py-1"
          data-testid={testId ? `${testId}-list` : undefined}
        >
          {options.length === 0 ? (
            <div className="px-4 py-3 text-[13px] text-[#6A6A6A] italic">No options</div>
          ) : (
            options.map((opt, idx) => {
              const active = idx === activeIdx;
              const isSelected = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  data-idx={idx}
                  onMouseEnter={() => setActiveIdx(idx)}
                  onClick={() => pick(opt)}
                  className={`w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left text-[13.5px] transition-colors
                    ${active ? 'bg-[#FEAE00]/10 text-white' : 'text-[#D0D0D0] hover:bg-white/5'}
                    ${isSelected ? 'text-[#FEAE00] font-semibold' : ''}`}
                  data-testid={testId ? `${testId}-option-${opt.value}` : undefined}
                >
                  <span className="flex flex-col min-w-0">
                    <span className="truncate">{opt.label}</span>
                    {opt.hint ? (
                      <span className="text-[11px] uppercase tracking-wider text-[#6A6A6A] mt-0.5">
                        {opt.hint}
                      </span>
                    ) : null}
                  </span>
                  {isSelected ? (
                    <Check size={14} className="text-[#FEAE00] flex-shrink-0" />
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}
