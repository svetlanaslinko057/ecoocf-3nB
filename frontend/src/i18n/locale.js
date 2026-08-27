/**
 * Locale helpers — pick the right BCP-47 locale tag for date/number formatting
 * based on the current bibi_lang stored in localStorage.
 *
 *   en → 'en-US'
 *   uk → 'uk-UA'
 *
 * This guarantees that toLocaleDateString / toLocaleString / Intl.NumberFormat
 * all format consistently with the user's selected language.
 */

const LOCALE_MAP = {
  en: 'en-US',
  uk: 'uk-UA',
  ua: 'uk-UA', // legacy alias
};

const DEFAULT_LOCALE = 'uk-UA';

/**
 * Returns the BCP-47 locale tag for the currently active language.
 * Reads from localStorage["bibi_lang"], falls back to 'en-US'.
 * Safe to call at module top-level (returns a string, no side effects).
 */
export const getLocale = () => {
  if (typeof window === 'undefined' || !window.localStorage) return DEFAULT_LOCALE;
  try {
    const lang = (window.localStorage.getItem('bibi_lang') || '').toLowerCase();
    return LOCALE_MAP[lang] || DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
};

/**
 * Map a 2-letter language code to a BCP-47 locale.
 * Useful inside components when you already have `lang` from useLang().
 */
export const localeFor = (lang) => LOCALE_MAP[(lang || '').toLowerCase()] || DEFAULT_LOCALE;

/**
 * Convenience: format a date with the current locale.
 *   fmtDate('2024-12-31') → '12/31/2024' (EN), '31.12.2024' (UK)
 *   fmtDate(date, { day:'2-digit', month:'short' }) → '31 Dec' / '31 дек.' / '31 груд.'
 */
export const fmtDate = (date, opts) => {
  try {
    const d = date instanceof Date ? date : new Date(date);
    if (isNaN(d.getTime())) return String(date ?? '');
    return d.toLocaleDateString(getLocale(), opts);
  } catch {
    return String(date ?? '');
  }
};

/**
 * Convenience: format date + time with the current locale.
 */
export const fmtDateTime = (date, opts) => {
  try {
    const d = date instanceof Date ? date : new Date(date);
    if (isNaN(d.getTime())) return String(date ?? '');
    return d.toLocaleString(getLocale(), opts);
  } catch {
    return String(date ?? '');
  }
};

/**
 * Convenience: format time with the current locale.
 */
export const fmtTime = (date, opts) => {
  try {
    const d = date instanceof Date ? date : new Date(date);
    if (isNaN(d.getTime())) return String(date ?? '');
    return d.toLocaleTimeString(getLocale(), opts);
  } catch {
    return String(date ?? '');
  }
};

export default { getLocale, localeFor, fmtDate, fmtDateTime, fmtTime };
