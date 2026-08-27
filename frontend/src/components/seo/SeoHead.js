/**
 * SeoHead — centralized per-route <head> manager (ECO.NOVA).
 * ==========================================================
 *
 * Mounted once inside <BrowserRouter>. On every route/language change it
 * asks the backend SEO engine (`/api/seo/meta`) for the fully-resolved
 * metadata for the current path and injects/updates:
 *
 *   • document.title + <html lang>
 *   • <meta name=description|keywords|robots>
 *   • <link rel=canonical>
 *   • Open Graph + Twitter card tags
 *   • hreflang alternates (uk / en / x-default)
 *   • a single JSON-LD @graph <script>
 *
 * Because Googlebot renders JavaScript, these client-injected tags are
 * indexed. Non-production hosts (preview/localhost/stage) are forced to
 * `noindex` so they never dilute the real production domain.
 *
 * All tags created here carry data-seo="1" so they can be refreshed
 * cleanly on navigation without touching unrelated head entries.
 */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useLang } from '@/i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const NON_PROD_MARKERS = [
  'preview.emergentagent.com',
  'localhost',
  '127.0.0.1',
  '.local',
  'ngrok',
  'vercel.app',
];

const isNonProdHost = () => {
  try {
    const h = (window.location.hostname || '').toLowerCase();
    return NON_PROD_MARKERS.some((m) => h.includes(m));
  } catch {
    return false;
  }
};

// ─── head helpers ─────────────────────────────────────────────────────────
const upsertMeta = (attr, key, content) => {
  if (content == null || content === '') return;
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    el.setAttribute('data-seo', '1');
    document.head.appendChild(el);
  }
  el.setAttribute('content', String(content));
};

const upsertLink = (rel, href, extra = {}) => {
  if (!href) return;
  const selectorParts = [`link[rel="${rel}"]`];
  if (extra.hreflang) selectorParts.push(`[hreflang="${extra.hreflang}"]`);
  let el = document.head.querySelector(selectorParts.join(''));
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', rel);
    el.setAttribute('data-seo', '1');
    if (extra.hreflang) el.setAttribute('hreflang', extra.hreflang);
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
};

const clearOwned = (selector) => {
  document.head.querySelectorAll(selector).forEach((n) => n.remove());
};

// module-level de-dupe so StrictMode double-invoke doesn't double-fetch
let _lastKey = null;

export default function SeoHead() {
  const { pathname, search } = useLocation();
  const { lang } = useLang();

  useEffect(() => {
    // language can also be forced via ?lang= (crawlable alt URLs)
    const params = new URLSearchParams(search);
    const urlLang = params.get('lang');
    const effLang = (urlLang || lang || 'uk').toLowerCase().startsWith('en') ? 'en' : 'uk';

    // Keep the document language attribute in sync (a11y + SEO).
    try { document.documentElement.setAttribute('lang', effLang); } catch {}

    // Do NOT emit SEO tags for private areas (they're disallowed anyway).
    const isPrivate =
      pathname.startsWith('/app') ||
      pathname.startsWith('/admin') ||
      pathname.startsWith('/client') ||
      pathname.startsWith('/cabinet') ||
      pathname.startsWith('/login') ||
      pathname.startsWith('/contract');

    const key = `${pathname}::${effLang}`;
    if (key === _lastKey && !isPrivate) return;
    _lastKey = key;

    let cancelled = false;

    const apply = (m) => {
      if (cancelled || !m) return;

      // title
      if (m.title) document.title = m.title;

      // robots — force noindex on non-production hosts
      const robots = isNonProdHost()
        ? 'noindex, nofollow'
        : (m.robots || 'index, follow');
      upsertMeta('name', 'robots', robots);
      upsertMeta('name', 'description', m.description);
      if (m.keywords) upsertMeta('name', 'keywords', m.keywords);

      // canonical
      upsertLink('canonical', m.canonical);

      // Open Graph
      if (m.og) {
        upsertMeta('property', 'og:type', m.og.type);
        upsertMeta('property', 'og:site_name', m.og.site_name);
        upsertMeta('property', 'og:title', m.og.title);
        upsertMeta('property', 'og:description', m.og.description);
        upsertMeta('property', 'og:url', m.og.url);
        upsertMeta('property', 'og:image', m.og.image);
        upsertMeta('property', 'og:locale', m.og.locale);
        upsertMeta('property', 'og:locale:alternate', m.og.locale_alternate);
      }

      // Twitter
      if (m.twitter) {
        upsertMeta('name', 'twitter:card', m.twitter.card);
        upsertMeta('name', 'twitter:title', m.twitter.title);
        upsertMeta('name', 'twitter:description', m.twitter.description);
        upsertMeta('name', 'twitter:image', m.twitter.image);
      }

      // hreflang — refresh the full set
      clearOwned('link[rel="alternate"][hreflang]');
      (m.hreflang || []).forEach((alt) =>
        upsertLink('alternate', alt.href, { hreflang: alt.hreflang })
      );

      // JSON-LD @graph (single owned script)
      try {
        clearOwned('script[data-seo-jsonld="1"]');
        if (m.jsonld) {
          const s = document.createElement('script');
          s.type = 'application/ld+json';
          s.setAttribute('data-seo-jsonld', '1');
          s.text = JSON.stringify(m.jsonld);
          document.head.appendChild(s);
        }
      } catch {
        /* never break navigation over structured data */
      }
    };

    if (isPrivate) {
      // Private route: strip public JSON-LD and force noindex.
      clearOwned('script[data-seo-jsonld="1"]');
      upsertMeta('name', 'robots', 'noindex, nofollow');
      return () => { cancelled = true; };
    }

    fetch(
      `${BACKEND_URL}/api/seo/meta?path=${encodeURIComponent(pathname)}&lang=${effLang}`,
      { credentials: 'omit' }
    )
      .then((r) => (r.ok ? r.json() : null))
      .then(apply)
      .catch(() => { /* baseline index.html tags remain as fallback */ });

    return () => { cancelled = true; };
  }, [pathname, search, lang]);

  return null;
}
