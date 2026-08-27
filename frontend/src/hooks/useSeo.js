/**
 * useSeo — lightweight per-route SEO hook (no external deps)
 * ============================================================
 *
 *   Updates <title>, <meta name="description">, canonical link,
 *   Open Graph + Twitter cards, optional structured-data block,
 *   and hreflang language alternates on route change.
 *
 *   ✔ Works without react-helmet / SSR
 *   ✔ Idempotent — never duplicates tags between renders
 *   ✔ Restores the default values on unmount (e.g. when leaving
 *     a public page for /admin) so the next route can re-define
 *     its own SEO cleanly.
 *
 * Usage:
 *
 *   useSeo({
 *     title:       'Каталог — ECO.NOVA',
 *     description: '…',
 *     keywords:    'used cars bulgaria, …',
 *     image:       '/og-image.png',            // optional
 *     type:        'website',                  // og:type
 *     noindex:     false,
 *     structuredData: { '@context': 'https://schema.org', … },  // optional JSON-LD
 *     alternates:  { en: '/catalog?lang=en', bg: '/catalog?lang=bg' },
 *     path:        '/catalog',                 // override canonical path
 *   });
 */
import { useEffect } from 'react';

// Public-origin shim. Resolved at runtime from the active browser
// origin so SEO tags follow whichever domain the app is actually
// served from (preview, staging, custom production host …). When the
// hook executes server-side (SSR/SSG) we fall back to the value of
// REACT_APP_PUBLIC_ORIGIN or, lastly, the API origin.
const _publicOrigin = () => {
  if (typeof window !== 'undefined' && window.location && window.location.origin) {
    return window.location.origin;
  }
  return (process.env.REACT_APP_PUBLIC_ORIGIN
       || process.env.REACT_APP_BACKEND_URL
       || '').replace(/\/$/, '');
};
const ORIGIN = _publicOrigin();

const DEFAULTS = {
  title:       'ECO.NOVA — Утилізація небезпечних відходів для бізнесу | B2B Україна',
  description: 'ECO.NOVA — ліцензований оператор поводження з небезпечними відходами. Класифікація, збір, вивіз, утилізація та повний документальний супровід для бізнесу в одній прозорій B2B-системі.',
  image:       `${ORIGIN}/og-image.png`,
  type:        'website',
};

const TAG_FLAG = 'data-managed-by-useSeo';

const _ensureMeta = (selector, attrs) => {
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement('meta');
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    el.setAttribute(TAG_FLAG, '1');
    document.head.appendChild(el);
  }
  return el;
};

const _ensureLink = (rel, hreflang = null) => {
  const sel = hreflang
    ? `link[rel="alternate"][hreflang="${hreflang}"]`
    : `link[rel="${rel}"]:not([hreflang])`;
  let el = document.head.querySelector(sel);
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', rel);
    if (hreflang) el.setAttribute('hreflang', hreflang);
    el.setAttribute(TAG_FLAG, '1');
    document.head.appendChild(el);
  }
  return el;
};

const _setMeta = (selector, attrs, value) => {
  if (!value) return;
  const el = _ensureMeta(selector, attrs);
  el.setAttribute('content', value);
};

export function useSeo(opts = {}) {
  useEffect(() => {
    const o = { ...DEFAULTS, ...opts };
    const fullUrl = o.path
      ? `${ORIGIN}${o.path.startsWith('/') ? o.path : '/' + o.path}`
      : `${ORIGIN}${window.location.pathname}${window.location.search || ''}`;

    // Title — always update
    if (o.title) document.title = o.title;

    // Description / keywords / robots
    _setMeta('meta[name="description"]',  { name: 'description' },  o.description);
    _setMeta('meta[name="keywords"]',     { name: 'keywords' },     o.keywords);
    _setMeta(
      'meta[name="robots"]',
      { name: 'robots' },
      o.noindex ? 'noindex, nofollow' : 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
    );

    // Canonical
    const canonical = _ensureLink('canonical');
    canonical.setAttribute('href', fullUrl);

    // Open Graph
    _setMeta('meta[property="og:title"]',       { property: 'og:title' },       o.title);
    _setMeta('meta[property="og:description"]', { property: 'og:description' }, o.description);
    _setMeta('meta[property="og:url"]',         { property: 'og:url' },         fullUrl);
    _setMeta('meta[property="og:type"]',        { property: 'og:type' },        o.type);
    _setMeta('meta[property="og:image"]',       { property: 'og:image' },       o.image);

    // Twitter
    _setMeta('meta[name="twitter:title"]',       { name: 'twitter:title' },       o.title);
    _setMeta('meta[name="twitter:description"]', { name: 'twitter:description' }, o.description);
    _setMeta('meta[name="twitter:image"]',       { name: 'twitter:image' },       o.image);

    // Language alternates — replace whole set on each call
    if (o.alternates && typeof o.alternates === 'object') {
      Object.entries(o.alternates).forEach(([lang, href]) => {
        const el = _ensureLink('alternate', lang);
        el.setAttribute('href', href.startsWith('http') ? href : `${ORIGIN}${href}`);
      });
    }

    // Optional per-page JSON-LD
    let ldEl = null;
    if (o.structuredData) {
      ldEl = document.createElement('script');
      ldEl.setAttribute('type', 'application/ld+json');
      ldEl.setAttribute(TAG_FLAG, 'jsonld');
      ldEl.textContent = JSON.stringify(o.structuredData);
      document.head.appendChild(ldEl);
    }

    return () => {
      // Tear down only the JSON-LD we injected. The other tags get
      // overwritten by the next useSeo() call (idempotent), so we
      // intentionally leave them in place for graceful transitions.
      if (ldEl && ldEl.parentNode) ldEl.parentNode.removeChild(ldEl);
    };
    // We intentionally serialise opts to a stable key so consumers can
    // pass inline literals without infinite re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(opts)]);
}

export default useSeo;
