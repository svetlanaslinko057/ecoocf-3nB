// Custom, fully-designed country selector for react-phone-number-input.
// Replaces the unstyled native <select> with an on-brand dropdown that is
// identical in UA and international (EN) modes: searchable list, flag, country
// name and +dial code, ECO green theme, keyboard + click-outside support.
//
// The dropdown panel is rendered through a PORTAL with FIXED positioning so it
// can never be clipped or shifted by a scrollable/overflow-hidden parent
// (e.g. the InquiryModal card). Position is viewport-aware: it flips upward
// when there is not enough room below and is clamped horizontally on small
// screens.
import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getCountryCallingCode } from "react-phone-number-input";

const PANEL_MAX_W = 340;
const PANEL_MIN_W = 260;
const GAP = 8;
const VIEWPORT_PAD = 8;
const SEARCH_H = 58; // approx height of the sticky search row
// Must sit ABOVE the inquiry modal overlay (.inq-overlay z-index:500) since the
// panel is portalled to <body>. Otherwise the modal backdrop covers it and the
// dropdown looks dimmed / broken / detached.
const PANEL_Z = 2147483000;

// Clean single-glyph globe for the "International" (no country) state. Rendering
// it ourselves guarantees ONE crisp icon (the library's default international
// glyph reads as a phone-over-globe = two icons).
function GlobeGlyph() {
  return (
    <svg className="ccsel__globe" viewBox="0 0 24 24" width="20" height="20" role="img" aria-label="International">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18M4.5 7.5c4.7 2.2 10.3 2.2 15 0M4.5 16.5c4.7-2.2 10.3-2.2 15 0"
        fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"
      />
    </svg>
  );
}

export default function CountrySelect({
  value,
  onChange,
  options = [],
  iconComponent: Icon,
  disabled,
  readOnly,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const [coords, setCoords] = useState(null);
  const rootRef = useRef(null);
  const panelRef = useRef(null);
  const listRef = useRef(null);
  const searchRef = useRef(null);
  const labelId = useId();

  const current = useMemo(
    () => options.find((o) => o.value === value) || options.find((o) => !o.value),
    [options, value]
  );

  const dial = (code) => {
    if (!code) return "";
    try { return "+" + getCountryCallingCode(code); } catch { return ""; }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => {
      const name = (o.label || "").toLowerCase();
      const d = o.value ? dial(o.value).toLowerCase() : "";
      const code = (o.value || "").toLowerCase();
      return name.includes(q) || d.includes(q) || code.includes(q) || q.replace("+", "") === d.replace("+", "");
    });
  }, [options, query]);

  // ── viewport-aware positioning (fixed, anchored to the trigger) ───────────
  const computeCoords = useCallback(() => {
    const el = rootRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const width = Math.max(PANEL_MIN_W, Math.min(PANEL_MAX_W, vw - VIEWPORT_PAD * 2));
    // horizontal: align to trigger, clamp inside viewport
    let left = r.left;
    if (left + width > vw - VIEWPORT_PAD) left = vw - VIEWPORT_PAD - width;
    if (left < VIEWPORT_PAD) left = VIEWPORT_PAD;
    // vertical: prefer below; flip above when not enough room
    const spaceBelow = vh - r.bottom - GAP - VIEWPORT_PAD;
    const spaceAbove = r.top - GAP - VIEWPORT_PAD;
    const below = spaceBelow >= 220 || spaceBelow >= spaceAbove;
    const avail = below ? spaceBelow : spaceAbove;
    const maxH = Math.max(180, Math.min(380, avail));
    setCoords(below
      ? { top: Math.round(r.bottom + GAP), left: Math.round(left), width: Math.round(width), maxH: Math.round(maxH) }
      : { bottom: Math.round(vh - r.top + GAP), left: Math.round(left), width: Math.round(width), maxH: Math.round(maxH) });
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    computeCoords();
  }, [open, computeCoords]);

  // Reposition on scroll / resize while open
  useEffect(() => {
    if (!open) return;
    const onMove = () => computeCoords();
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    return () => {
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
    };
  }, [open, computeCoords]);

  // Close on outside click (account for the portalled panel)
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      const inTrigger = rootRef.current && rootRef.current.contains(e.target);
      const inPanel = panelRef.current && panelRef.current.contains(e.target);
      if (!inTrigger && !inPanel) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  // Focus search + sync active index when opening
  useEffect(() => {
    if (open) {
      setQuery("");
      const idx = Math.max(0, options.findIndex((o) => o.value === value));
      setActiveIdx(idx);
      const t = setTimeout(() => searchRef.current?.focus(), 10);
      return () => clearTimeout(t);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep active option scrolled into view
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-idx="${activeIdx}"]`);
    if (el) el.scrollIntoView({ block: "nearest" });
  }, [activeIdx, open]);

  const choose = (opt) => {
    onChange(opt.value);
    setOpen(false);
  };

  const onKeyDown = (e) => {
    if (!open) {
      if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === "Escape") { setOpen(false); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = filtered[activeIdx];
      if (opt) choose(opt);
    }
  };

  const isDisabled = disabled || readOnly;

  const panelStyle = coords
    ? {
        position: "fixed",
        zIndex: PANEL_Z,
        left: coords.left,
        width: coords.width,
        ...(coords.top != null ? { top: coords.top } : { bottom: coords.bottom }),
      }
    : { position: "fixed", zIndex: PANEL_Z, left: -9999, top: -9999 };

  const panel = open ? createPortal(
    <div
      className="ccsel__panel"
      role="dialog"
      ref={panelRef}
      style={panelStyle}
      data-testid="country-select-panel"
    >
      <div className="ccsel__search">
        <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          ref={searchRef}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setActiveIdx(0); }}
          onKeyDown={onKeyDown}
          placeholder="Search country…"
          aria-label="Search country"
          data-testid="country-select-search"
        />
      </div>
      <ul
        className="ccsel__list"
        role="listbox"
        ref={listRef}
        style={{ maxHeight: coords ? Math.max(120, coords.maxH - SEARCH_H) : 280 }}
      >
        {filtered.length === 0 && <li className="ccsel__empty">No matches</li>}
        {filtered.map((opt, i) => {
          const selected = opt.value === value;
          const active = i === activeIdx;
          return (
            <li
              key={(opt.value || "intl") + i}
              data-idx={i}
              role="option"
              aria-selected={selected}
              className={`ccsel__opt ${selected ? "is-selected" : ""} ${active ? "is-active" : ""}`}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => choose(opt)}
            >
              <span className="ccsel__optflag">
                {opt.value
                  ? (Icon ? <Icon country={opt.value} label={opt.label} /> : null)
                  : <GlobeGlyph />}
              </span>
              <span className="ccsel__name">{opt.label}</span>
              <span className="ccsel__dial">{dial(opt.value)}</span>
            </li>
          );
        })}
      </ul>
    </div>,
    document.body
  ) : null;

  return (
    <div className="ccsel" ref={rootRef}>
      <button
        type="button"
        className={`ccsel__trigger ${open ? "is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={labelId}
        disabled={isDisabled}
        onClick={() => !isDisabled && setOpen((o) => !o)}
        onKeyDown={onKeyDown}
        data-testid="country-select-trigger"
      >
        <span className={`ccsel__flag ${current?.value ? "has-flag" : "is-intl"}`}>
          {current?.value
            ? (Icon ? <Icon country={current.value} label={current.label} /> : null)
            : <GlobeGlyph />}
        </span>
        <svg className="ccsel__chev" width="10" height="6" viewBox="0 0 10 6" aria-hidden="true">
          <path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {panel}
      <span id={labelId} hidden>Country</span>
    </div>
  );
}
