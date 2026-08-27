/**
 * CabinetLangPicker — visual twin of the public-header language dropdown
 * ====================================================================
 *
 * Phase B3.1 (hardening). Replaces the small UA / EN pill switcher in the
 * cabinet sidebar with the same Mazzard H "ENG ▾" dropdown used on the
 * main site header, so the picker is consistent across the product.
 *
 * Behaviour:
 *   • Sources languages from CUSTOMER_LANGUAGES (UA + EN only — Bulgarian
 *     has been fully removed from the product).
 *   • Auto-sync: when the parent <LanguageProvider> hydrates, the cabinet
 *     inherits whichever language the user last picked on the public site
 *     (same `useLang()` context).
 *   • Dropdown is rendered into a Portal so the parent's `overflow` does
 *     not clip it.
 *   • Solid backgrounds in every state (per design rules — no transparency).
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLang, CUSTOMER_LANGUAGES } from '../../i18n';

const DEFAULT_FALLBACK = { code: 'uk', label: 'UA', name: 'Українська' };

const CabinetLangPicker = ({ className = '' }) => {
  const { lang, changeLang } = useLang();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef(null);
  const ddRef = useRef(null);
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 });

  // Customer cabinet supports UA + EN. Fall back to the static label
  // map if the context didn't expose CUSTOMER_LANGUAGES (super defensive).
  const languages = useMemo(() => {
    const arr = Array.isArray(CUSTOMER_LANGUAGES) ? CUSTOMER_LANGUAGES : [];
    if (arr.length) return arr;
    return [DEFAULT_FALLBACK, { code: 'en', label: 'EN', name: 'English' }];
  }, []);

  const activeLabel = useMemo(() => {
    const l = languages.find((x) => x.code === lang);
    return l ? l.label : DEFAULT_FALLBACK.label;
  }, [lang, languages]);

  // Position the portalled dropdown right under the trigger.
  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setMenuPos({
      top: rect.bottom + window.scrollY + 6,
      right: window.innerWidth - rect.right - window.scrollX,
    });
  }, [open]);

  // Click-outside / Esc to close.
  useEffect(() => {
    if (!open) return undefined;
    const onDocClick = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        ddRef.current && !ddRef.current.contains(e.target)
      ) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={triggerRef} className={className} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        data-testid="cabinet-lang-toggle"
        aria-haspopup="listbox"
        aria-expanded={open}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 10px',
          background: '#1d1d1b',
          border: '1px solid #2a2a28',
          borderRadius: 8,
          color: '#E7E7E7',
          fontFamily: "'Mazzard H', var(--font-mazzard, system-ui, sans-serif)",
          fontSize: 13,
          fontWeight: 400,
          letterSpacing: 0,
          textTransform: 'uppercase',
          cursor: 'pointer',
          lineHeight: 1,
          userSelect: 'none',
        }}
      >
        <span>{activeLabel}</span>
        <svg
          width="12" height="12" viewBox="0 0 16 16"
          aria-hidden="true"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }}
        >
          <path d="M3 6l5 5 5-5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && typeof document !== 'undefined' && createPortal(
        <ul
          ref={ddRef}
          role="listbox"
          data-testid="cabinet-lang-menu"
          style={{
            position: 'absolute',
            top: menuPos.top,
            right: menuPos.right,
            minWidth: 96,
            background: '#1d1d1b',
            border: '1px solid #2a2a28',
            borderRadius: 8,
            padding: 4,
            margin: 0,
            listStyle: 'none',
            zIndex: 9999,
            boxShadow: '0 12px 28px rgba(0,0,0,0.45)',
            fontFamily: "var(--font-mazzard, system-ui, sans-serif)",
          }}
        >
          {languages.map((l) => {
            const active = l.code === lang;
            return (
              <li key={l.code}>
                <button
                  type="button"
                  onClick={() => { changeLang(l.code); setOpen(false); }}
                  data-testid={`cabinet-lang-option-${l.code}`}
                  title={l.name}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 12px',
                    background: active ? '#FEAE00' : 'transparent',
                    color: active ? '#000' : '#E7E7E7',
                    border: 0,
                    borderRadius: 4,
                    cursor: 'pointer',
                    fontFamily: "'Mazzard H', var(--font-mazzard, system-ui, sans-serif)",
                    fontSize: 13,
                    fontWeight: 400,
                    lineHeight: '17px',
                    letterSpacing: 0,
                    textTransform: 'uppercase',
                  }}
                >
                  {l.label}
                </button>
              </li>
            );
          })}
        </ul>,
        document.body,
      )}
    </div>
  );
};

export default CabinetLangPicker;
