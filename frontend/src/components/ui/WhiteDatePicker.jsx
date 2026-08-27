/**
 * WhiteDatePicker — кастомный date picker, drop-in замена нативного <input type="date">.
 *
 * Особенности (как и WhiteSelect v3):
 *  • Portal в document.body — popover не обрезается родительским overflow и
 *    не вылазит за края viewport
 *  • Auto-flip вверх/вниз по доступному месту
 *  • Min-width: гарантируется читаемый календарь (минимум 280px)
 *  • Закрытие по клику вне / Escape / выбор даты
 *
 * API совместим с нативным input[type="date"]:
 *   <WhiteDatePicker
 *     value="2026-05-22"          // ISO yyyy-mm-dd
 *     onChange={(e) => set(e.target.value)}
 *     min="2026-01-01"            // optional
 *     max="2027-12-31"            // optional
 *     data-testid="…"
 *     className="…"               // for trigger button
 *     disabled
 *     placeholder="дд.мм.гггг"
 *   />
 *
 * onChange вызывается с синтетическим event {target:{value: "yyyy-mm-dd"}}.
 */
import React, { useState, useRef, useEffect, useCallback, useLayoutEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Calendar as CalendarIcon, CaretLeft, CaretRight, X } from '@phosphor-icons/react';

// Format yyyy-mm-dd → dd.mm.yyyy for display
function formatDisplay(iso) {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

// yyyy-mm-dd → Date | null
function parseIso(iso) {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(d.getTime()) ? null : d;
}

// Date → yyyy-mm-dd (local time, no timezone shift)
function toIso(date) {
  if (!date) return '';
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function sameDay(a, b) {
  return a && b && a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function getMonthMatrix(year, month) {
  // month: 0-11. Returns array of 6 weeks × 7 days, Mon-first.
  const first = new Date(year, month, 1);
  const firstDow = (first.getDay() + 6) % 7; // 0 = Monday
  const start = new Date(year, month, 1 - firstDow);
  const weeks = [];
  for (let w = 0; w < 6; w += 1) {
    const row = [];
    for (let d = 0; d < 7; d += 1) {
      const dt = new Date(start);
      dt.setDate(start.getDate() + w * 7 + d);
      row.push(dt);
    }
    weeks.push(row);
  }
  return weeks;
}

const WEEKDAYS_UK = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'];
const WEEKDAYS_EN = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTH_NAMES_UK = [
  'січень', 'лютий', 'березень', 'квітень', 'травень', 'червень',
  'липень', 'серпень', 'вересень', 'жовтень', 'листопад', 'грудень',
];
const MONTH_NAMES_EN = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const CLEAR_LABELS = { uk: 'Очистити', en: 'Clear' };
const TODAY_LABELS = { uk: 'Сьогодні', en: 'Today' };

const WhiteDatePicker = React.forwardRef(function WhiteDatePicker({
  value = '',
  onChange,
  min,
  max,
  placeholder = 'дд.мм.гггг',
  className = '',
  disabled = false,
  ariaLabel,
  placement = 'auto',
  locale,
  ...rest
}, ref) {
  const [isOpen, setIsOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, openUp: false });
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const testId = rest['data-testid'];

  // Detect locale: supports uk / en. Russian/Bulgarian are NOT supported.
  const localeCode = useMemo(() => {
    const probe = (v) => {
      if (!v) return null;
      const s = String(v).toLowerCase();
      if (s.startsWith('uk')) return 'uk';
      if (s.startsWith('en')) return 'en';
      return null;
    };
    return (
      probe(locale)
      || (typeof document !== 'undefined'
        ? probe(document.documentElement.lang) || probe(document.body.getAttribute('data-app-lang'))
        : null)
      || 'uk' // default to Ukrainian (canonical Cyrillic for this CRM)
    );
  }, [locale]);
  const WEEKDAYS = localeCode === 'en' ? WEEKDAYS_EN : WEEKDAYS_UK;
  const MONTH_NAMES = localeCode === 'en' ? MONTH_NAMES_EN : MONTH_NAMES_UK;

  // Current viewed month
  const initialDate = parseIso(value) || new Date();
  const [viewYear, setViewYear] = useState(initialDate.getFullYear());
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth());

  // When value or open state changes, reset view to value (or today)
  useEffect(() => {
    if (isOpen) {
      const d = parseIso(value) || new Date();
      setViewYear(d.getFullYear());
      setViewMonth(d.getMonth());
    }
  }, [isOpen, value]);

  const recalcPosition = useCallback(() => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const vh = window.innerHeight;
    const vw = window.innerWidth;
    const POPOVER_H = 360;
    const POPOVER_W = 320;
    const MARGIN = 8;
    const GAP = 6;

    const spaceBelow = vh - rect.bottom;
    const spaceAbove = rect.top;
    let openUp;
    if (placement === 'top') openUp = true;
    else if (placement === 'bottom') openUp = false;
    else openUp = spaceBelow < POPOVER_H + GAP && spaceAbove > spaceBelow;

    // Align left edge of popover to left edge of trigger; clamp inside viewport
    let left = rect.left;
    if (left + POPOVER_W > vw - MARGIN) left = vw - MARGIN - POPOVER_W;
    if (left < MARGIN) left = MARGIN;

    const top = openUp
      ? Math.max(MARGIN, rect.top - GAP)
      : rect.bottom + GAP;

    setPos({ top, left, openUp });
  }, [placement]);

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

  useEffect(() => {
    if (!isOpen) return;
    const onDocClick = (e) => {
      const inTrigger = wrapRef.current && wrapRef.current.contains(e.target);
      const inMenu = menuRef.current && menuRef.current.contains(e.target);
      if (!inTrigger && !inMenu) setIsOpen(false);
    };
    const onEsc = (e) => { if (e.key === 'Escape') setIsOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEsc);
    };
  }, [isOpen]);

  // CRITICAL — prevent Radix Dialog / Popover host modals from interpreting
  // clicks INSIDE the portaled calendar as "outside interaction" and auto-
  // closing themselves. The calendar popover lives in document.body, so
  // every native pointerdown that bubbles past the popover up to document
  // is interpreted by Radix's outside-detector as a "click outside".
  //
  // Fix: attach NATIVE bubble-phase listeners on the popover root that call
  // stopPropagation. The events still reach descendants in capture+target
  // phase (so the day button's onClick fires normally), but the bubble
  // phase is stopped at the popover root → document never sees the event
  // → Radix never closes its Dialog.
  //
  // We DO NOT use {capture:true} — that would block the event from
  // descending to the day button at all.
  useEffect(() => {
    if (!isOpen) return;
    const node = menuRef.current;
    if (!node) return;
    const swallow = (e) => { e.stopPropagation(); };
    node.addEventListener('pointerdown', swallow);
    node.addEventListener('mousedown',   swallow);
    node.addEventListener('touchstart',  swallow, { passive: true });
    return () => {
      node.removeEventListener('pointerdown', swallow);
      node.removeEventListener('mousedown',   swallow);
      node.removeEventListener('touchstart',  swallow);
    };
  }, [isOpen]);

  const selectedDate = parseIso(value);
  const today = new Date();
  const minDate = parseIso(min);
  const maxDate = parseIso(max);

  const isDisabledDay = (d) => {
    if (minDate && d < new Date(minDate.getFullYear(), minDate.getMonth(), minDate.getDate())) return true;
    if (maxDate && d > new Date(maxDate.getFullYear(), maxDate.getMonth(), maxDate.getDate())) return true;
    return false;
  };

  const emitChange = (iso) => {
    if (typeof onChange === 'function') {
      const syntheticEvent = {
        target: { value: iso, name: rest.name },
        currentTarget: { value: iso, name: rest.name },
        preventDefault: () => {},
        stopPropagation: () => {},
        persist: () => {},
      };
      try { onChange(syntheticEvent); } catch { onChange(iso); }
    }
  };

  // Schedule a close on the NEXT animation frame so that the popover DOM
  // stays in place while the current native event finishes bubbling. This
  // is what lets the project-wide Dialog wrapper detect that the click
  // originated inside a `[data-whitedatepicker-popover]` portal and veto
  // Radix's auto-dismiss — `.closest()` only works on connected nodes.
  const closeNextFrame = () => {
    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(() => setIsOpen(false));
    } else {
      setTimeout(() => setIsOpen(false), 0);
    }
  };

  const handlePickDay = (d) => {
    if (isDisabledDay(d)) return;
    emitChange(toIso(d));
    closeNextFrame();
  };

  const handleClear = () => { emitChange(''); closeNextFrame(); };
  const handleToday = () => {
    if (isDisabledDay(today)) return;
    emitChange(toIso(today));
    closeNextFrame();
  };

  const goPrevMonth = () => {
    const d = new Date(viewYear, viewMonth - 1, 1);
    setViewYear(d.getFullYear()); setViewMonth(d.getMonth());
  };
  const goNextMonth = () => {
    const d = new Date(viewYear, viewMonth + 1, 1);
    setViewYear(d.getFullYear()); setViewMonth(d.getMonth());
  };

  const weeks = useMemo(() => getMonthMatrix(viewYear, viewMonth), [viewYear, viewMonth]);

  const popoverEl = isOpen && typeof document !== 'undefined' ? createPortal(
    <div
      ref={menuRef}
      role="dialog"
      data-testid={testId ? `${testId}-popover` : undefined}
      // Mark the popover so any modal host (Radix Dialog / Popover / Sheet)
      // can recognise the calendar as a "trusted portal" and NOT treat clicks
      // inside it as outside-interaction. The pointer/mouse-down handlers
      // below also stopPropagation so Radix's document-level outside detector
      // never sees these events at all.
      data-whitedatepicker-popover
      onPointerDown={(e) => e.stopPropagation()}
      onPointerDownCapture={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      onMouseDownCapture={(e) => e.stopPropagation()}
      onTouchStart={(e) => e.stopPropagation()}
      onTouchStartCapture={(e) => e.stopPropagation()}
      // Some Radix versions probe via focus events; keep focus contained too.
      onFocusCapture={(e) => e.stopPropagation()}
      style={{
        position: 'fixed',
        top: pos.openUp ? undefined : pos.top,
        bottom: pos.openUp ? (window.innerHeight - pos.top) : undefined,
        // Mobile-safe: never overflow the viewport. We clamp the
        // calendar width to (viewport - 24px gutters) and clip its left
        // edge so it never extends off-screen. The trigger anchor is
        // still respected on tablet+ where there is room.
        left: Math.max(8, Math.min(pos.left, (typeof window !== 'undefined' ? window.innerWidth : 1024) - Math.min(320, (typeof window !== 'undefined' ? window.innerWidth - 16 : 320)) - 8)),
        width: Math.min(320, (typeof window !== 'undefined' ? window.innerWidth - 16 : 320)),
        maxWidth: 'calc(100vw - 16px)',
        zIndex: 9999,
        // CRITICAL — Radix Dialog disables pointer-events on body when open
        // (so the user can't click "through" the modal). Because we portal
        // the calendar into body, the calendar inherits/picks up that
        // pointer-events:none, which causes browser hit-testing to skip the
        // calendar and route every click straight to Radix's overlay → which
        // then dismisses the dialog. Forcing pointer-events:auto here makes
        // the calendar clickable again.
        pointerEvents: 'auto',
        transformOrigin: pos.openUp ? 'bottom center' : 'top center',
        animation: 'ws-popover-in 140ms cubic-bezier(0.16, 1, 0.3, 1)',
      }}
      className="bg-white border border-[#E4E4E7] rounded-2xl shadow-xl overflow-hidden flex flex-col"
    >
      {/* Header — month + year + nav */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2">
        <div className="font-semibold text-[#18181B] text-sm">
          {MONTH_NAMES[viewMonth].charAt(0).toUpperCase() + MONTH_NAMES[viewMonth].slice(1)} {viewYear}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={goPrevMonth}
            className="p-1.5 rounded-lg hover:bg-[#F4F4F5] text-[#71717A]"
            aria-label="Previous month"
            data-testid={testId ? `${testId}-prev` : undefined}
          >
            <CaretLeft size={16} weight="bold" />
          </button>
          <button
            type="button"
            onClick={goNextMonth}
            className="p-1.5 rounded-lg hover:bg-[#F4F4F5] text-[#71717A]"
            aria-label="Next month"
            data-testid={testId ? `${testId}-next` : undefined}
          >
            <CaretRight size={16} weight="bold" />
          </button>
        </div>
      </div>

      {/* Weekday labels */}
      <div className="grid grid-cols-7 gap-1 px-3 pb-1">
        {WEEKDAYS.map((d) => (
          <div key={d} className="text-center text-[11px] font-medium text-[#A1A1AA] py-1">{d}</div>
        ))}
      </div>

      {/* Days grid */}
      <div className="grid grid-cols-7 gap-1 px-3 pb-3">
        {weeks.flat().map((d, i) => {
          const outside = d.getMonth() !== viewMonth;
          const isSel = sameDay(d, selectedDate);
          const isToday = sameDay(d, today);
          const dis = isDisabledDay(d);
          return (
            <button
              type="button"
              key={i}
              onClick={() => handlePickDay(d)}
              disabled={dis}
              data-testid={testId ? `${testId}-day-${toIso(d)}` : undefined}
              className={`h-9 w-full rounded-lg text-sm transition-colors
                ${dis ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}
                ${isSel
                  ? 'bg-[#4F46E5] text-white font-semibold'
                  : outside
                    ? 'text-[#D4D4D8] hover:bg-[#FAFAFA]'
                    : isToday
                      ? 'text-[#4F46E5] font-semibold ring-1 ring-[#4F46E5]/30 hover:bg-[#EEF2FF]'
                      : 'text-[#18181B] hover:bg-[#F4F4F5]'}
              `}
            >
              {d.getDate()}
            </button>
          );
        })}
      </div>

      {/* Footer — Clear + Today */}
      <div className="flex items-center justify-between border-t border-[#F4F4F5] px-3 py-2">
        <button
          type="button"
          onClick={handleClear}
          className="text-xs font-medium text-[#71717A] hover:text-[#DC2626] transition-colors px-2 py-1 rounded-lg hover:bg-[#FEE2E2]"
          data-testid={testId ? `${testId}-clear` : undefined}
        >
          {CLEAR_LABELS[localeCode] || CLEAR_LABELS.uk}
        </button>
        <button
          type="button"
          onClick={handleToday}
          className="text-xs font-medium text-[#4F46E5] hover:bg-[#EEF2FF] px-2 py-1 rounded-lg transition-colors"
          data-testid={testId ? `${testId}-today` : undefined}
        >
          {TODAY_LABELS[localeCode] || TODAY_LABELS.uk}
        </button>
      </div>
    </div>,
    document.body,
  ) : null;

  return (
    <div className={`relative w-full ${className}`} ref={wrapRef}>
      <button
        ref={(node) => { buttonRef.current = node; if (typeof ref === 'function') ref(node); else if (ref) ref.current = node; }}
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-label={ariaLabel}
        data-testid={testId}
        className={`flex items-center justify-between gap-2 w-full bg-white border rounded-xl px-4 py-3 text-sm text-left transition-all
          ${isOpen ? 'border-[#18181B] ring-2 ring-[#18181B]/10' : 'border-[#E4E4E7] hover:border-[#A1A1AA]'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <span className={`truncate ${value ? 'text-[#18181B]' : 'text-[#A1A1AA]'}`}>
          {value ? formatDisplay(value) : placeholder}
        </span>
        <span className="flex items-center gap-1 flex-shrink-0">
          {value && !disabled && (
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => { e.stopPropagation(); handleClear(); }}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); handleClear(); } }}
              className="text-[#A1A1AA] hover:text-[#DC2626] transition-colors p-0.5 rounded cursor-pointer"
              aria-label="Clear date"
              data-testid={testId ? `${testId}-trigger-clear` : undefined}
            >
              <X size={14} weight="bold" />
            </span>
          )}
          <CalendarIcon size={16} className="text-[#71717A]" />
        </span>
      </button>
      {popoverEl}
    </div>
  );
});

export default WhiteDatePicker;
