/**
 * Language Context — ECO.NOVA Platform (Ukraine)
 *
 * Languages: Ukrainian (UK) + English (EN) ONLY. Bulgarian has been fully removed.
 *
 * Default language is GEO-based:
 *   • Visitors on Ukrainian territory (Ukrainian timezone / locale) → UK
 *   • Everyone else → EN
 *
 * A manual choice is always respected and persisted in localStorage["bibi_lang"].
 * The UK/EN toggle is available everywhere (public site, client cabinet, back-office).
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import translations from './translations';

const LanguageContext = createContext(null);

// All available languages — UK first (primary for a Ukrainian platform), EN second.
export const LANGUAGES = [
  { code: 'uk', label: 'UA', flag: '🇺🇦', name: 'Українська' },
  { code: 'en', label: 'EN', flag: '🇬🇧', name: 'English' },
];

// Public site + customer cabinet support the same set (UK + EN).
export const PUBLIC_LANGUAGES = LANGUAGES;
export const CUSTOMER_LANGUAGES = LANGUAGES;

const SUPPORTED = LANGUAGES.map((l) => l.code);
const FALLBACK_LANG = 'en';

// Ukrainian IANA timezones — used as the primary "territory" signal.
const UA_TIMEZONES = new Set([
  'Europe/Kyiv',
  'Europe/Kiev',
  'Europe/Uzhgorod',
  'Europe/Zaporozhye',
  'Europe/Simferopol',
]);

const normalizeLang = (raw) => {
  if (!raw) return null;
  const v = String(raw).toLowerCase();
  if (v === 'ua') return 'uk';
  const code = v.slice(0, 2);
  return SUPPORTED.includes(code) ? code : null;
};

/**
 * Geo-based default: Ukrainian territory → 'uk', everywhere else → 'en'.
 * Uses the browser timezone as the strongest territory signal, with the
 * navigator locale as a secondary hint.
 */
const detectDefaultLang = () => {
  if (typeof window === 'undefined') return FALLBACK_LANG;
  // 1) Timezone signal (most reliable proxy for physical territory).
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    if (UA_TIMEZONES.has(tz)) return 'uk';
    // Any other resolved timezone that is clearly non-UA → English by default.
    if (tz && !tz.startsWith('Europe/')) return 'en';
  } catch {}
  // 2) Browser locale hint (uk / uk-UA / ua).
  try {
    const langs = (navigator.languages && navigator.languages.length)
      ? navigator.languages
      : [navigator.language || ''];
    for (const raw of langs) {
      const code = (raw || '').toLowerCase().slice(0, 2);
      if (code === 'uk' || code === 'ua') return 'uk';
    }
  } catch {}
  return FALLBACK_LANG;
};

export const LanguageProvider = ({ children }) => {
  const [lang, setLangState] = useState(() => {
    if (typeof window === 'undefined') return FALLBACK_LANG;
    let stored = null;
    try { stored = localStorage.getItem('bibi_lang'); } catch {}
    const initial = normalizeLang(stored) || detectDefaultLang();
    try { localStorage.setItem('bibi_lang', initial); } catch {}
    return initial;
  });

  // The public marketing site runs a heavy GSAP / ScrollTrigger cinematic
  // timeline whose pinned sections are measured once. Switching language while
  // it is mounted swaps all the text (and therefore every element's height),
  // which leaves the pins with stale measurements → broken cards, wrong
  // spacing and blank blocks until a manual refresh. The most reliable fix is
  // to do a FULL page reload on language change for public pages, so the new
  // language is rendered from a clean state with correct measurements.
  // The back-office (/app) and client cabinet (/client) do NOT use that
  // timeline and may hold unsaved form state, so there we switch in-place.
  const isPublicRoute = () => {
    if (typeof window === 'undefined') return false;
    const p = window.location.pathname || '/';
    return !/^\/(admin|app|client|cabinet|login|contract)(\/|$)/.test(p);
  };

  // setLang wrapper that can also flag a *manual* user choice so the IP-based
  // auto-detect never overrides what the visitor explicitly picked.
  const setLang = (next, manual = false) => {
    if (typeof window !== 'undefined') {
      // Persist synchronously BEFORE any reload so the provider re-initialises
      // in the newly chosen language after the refresh.
      try { localStorage.setItem('bibi_lang', next); } catch {}
      if (manual) {
        try { localStorage.setItem('bibi_lang_manual', '1'); } catch {}
      }
    }
    if (manual && typeof window !== 'undefined' && isPublicRoute()) {
      // Ensure we land at the top so the cinematic pins build cleanly.
      try { window.scrollTo(0, 0); } catch {}
      window.location.reload();
      return;
    }
    setLangState(next);
  };

  // ── IP-based default language (territory, not browser locale) ───────────
  // Runs once on first load. Skipped entirely once the visitor has made a
  // manual UK/EN choice. The local timezone guess above is used immediately
  // (no flash); the IP result refines it: country "UA" → uk, else → en.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let manual = false;
    try { manual = localStorage.getItem('bibi_lang_manual') === '1'; } catch {}
    if (manual) return;

    const base = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${base}/api/public/geo`, { headers: { Accept: 'application/json' } });
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled || !data || !data.country) return; // unknown → keep guess
        const geoLang = data.country === 'UA' ? 'uk' : 'en';
        // Only update if it differs and the user still hasn't chosen manually.
        let stillAuto = true;
        try { stillAuto = localStorage.getItem('bibi_lang_manual') !== '1'; } catch {}
        if (stillAuto) setLangState(geoLang);
      } catch {
        /* offline / blocked → silently keep the local guess */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Persist preference + reflect on <html lang> / <body data-app-lang>.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try { localStorage.setItem('bibi_lang', lang); } catch {}
    try { document.documentElement.setAttribute('lang', lang); } catch {}
    try { document.body && document.body.setAttribute('data-app-lang', lang); } catch {}
  }, [lang]);

  // Translation lookup: current lang → UK → EN → raw key.
  const t = (key) => (
    translations[lang]?.[key]
    ?? translations.uk?.[key]
    ?? translations.en?.[key]
    ?? key
  );

  // Toggle UK ↔ EN (explicit, manual). Uses the reload-aware setter so the
  // public site refreshes cleanly on change.
  const toggleLang = () => {
    const next = lang === 'uk' ? 'en' : 'uk';
    setLang(next, true);
  };

  // Set a specific language (aliases 'ua' → 'uk', ignores unknown codes).
  // Treated as an explicit, manual choice.
  const changeLang = (newLang) => {
    const normalized = normalizeLang(newLang);
    if (normalized) setLang(normalized, true);
  };

  return (
    <LanguageContext.Provider
      value={{
        lang,
        setLang: changeLang,
        t,
        toggleLang,
        changeLang,
        languages: LANGUAGES,
        publicLanguages: PUBLIC_LANGUAGES,
        customerLanguages: CUSTOMER_LANGUAGES,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
};

export const useLang = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    return {
      lang: FALLBACK_LANG,
      setLang: () => {},
      t: (key) => translations[FALLBACK_LANG]?.[key] || key,
      toggleLang: () => {},
      changeLang: () => {},
      languages: LANGUAGES,
      publicLanguages: PUBLIC_LANGUAGES,
      customerLanguages: CUSTOMER_LANGUAGES,
    };
  }
  return context;
};

export default LanguageContext;
