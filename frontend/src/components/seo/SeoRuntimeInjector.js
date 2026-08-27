/**
 * SeoRuntimeInjector
 * ===================
 *
 * Mounts at the React root (App.js) and on bootstrap fetches the public
 * SEO runtime config (`/api/seo/runtime-config`). Based on that config it
 * injects:
 *
 *   • Google Analytics 4 (gtag.js + `gtag('config', G-XXXX')`)
 *   • Google Ads conversion linker (AW-XXXX)
 *   • Facebook Pixel (fbq base + PageView)
 *   • Search-engine verification <meta> tags (gsc/bing/yandex)
 *
 * Replaces the static `<script async ...gtag>` blocks that used to live in
 * index.html — now they are admin-configurable through
 * /admin/seo-settings without redeploys.
 *
 * Safe to mount everywhere — public site, admin, cabinet. The hook itself
 * decides whether to inject (skips admin/cabinet routes by default so we
 * don't bloat internal navigation with tracking pixels they don't need).
 */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─── Memoised fetch — survives StrictMode double-invocation in dev and
//    avoids hammering the backend across route transitions in prod.
let _cachedPromise = null;
const fetchRuntimeConfig = () => {
  if (!_cachedPromise) {
    _cachedPromise = fetch(`${BACKEND_URL}/api/seo/runtime-config`, {
      credentials: 'omit',
    })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({}));
  }
  return _cachedPromise;
};

const _hasScript = (id) => !!document.getElementById(id);

const injectGtagBase = (gtagId) => {
  if (_hasScript('gtag-base')) return;
  const s = document.createElement('script');
  s.id   = 'gtag-base';
  s.async = true;
  s.src  = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(gtagId)}`;
  document.head.appendChild(s);

  const init = document.createElement('script');
  init.id = 'gtag-init';
  init.text = `
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    window.gtag = gtag;
    gtag('js', new Date());
  `;
  document.head.appendChild(init);
};

const injectGa4 = (measurementId) => {
  if (!measurementId || _hasScript(`gtag-config-${measurementId}`)) return;
  injectGtagBase(measurementId);
  const cfg = document.createElement('script');
  cfg.id = `gtag-config-${measurementId}`;
  cfg.text = `
    gtag('config', '${measurementId}', {
      anonymize_ip: true,
      cookie_flags: 'SameSite=None;Secure'
    });
  `;
  document.head.appendChild(cfg);
};

const injectGoogleAds = (conversionId, sendPageView) => {
  if (!conversionId || _hasScript(`gtag-config-${conversionId}`)) return;
  injectGtagBase(conversionId);
  const cfg = document.createElement('script');
  cfg.id = `gtag-config-${conversionId}`;
  cfg.text = `
    gtag('config', '${conversionId}', {
      send_page_view: ${sendPageView ? 'true' : 'false'}
    });
  `;
  document.head.appendChild(cfg);
};

const injectFacebookPixel = (pixelId) => {
  if (!pixelId || _hasScript('fbq-base')) return;
  const s = document.createElement('script');
  s.id = 'fbq-base';
  s.text = `
    !function(f,b,e,v,n,t,s){
      if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};
      if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];
      t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)
    }(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', '${pixelId}');
    fbq('track', 'PageView');
  `;
  document.head.appendChild(s);
};

const setVerificationMeta = (name, value) => {
  if (!value) return;
  let el = document.head.querySelector(`meta[name="${name}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('name', name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', value);
};

export default function SeoRuntimeInjector() {
  const { pathname } = useLocation();

  useEffect(() => {
    // Skip authenticated areas — no tracking on admin / cabinet pages.
    if (
      pathname.startsWith('/admin') ||
      pathname.startsWith('/cabinet') ||
      pathname.startsWith('/login')
    ) {
      return;
    }
    let cancelled = false;
    fetchRuntimeConfig().then((cfg) => {
      if (cancelled || !cfg) return;
      setVerificationMeta('google-site-verification', cfg.google_site_verification);
      setVerificationMeta('msvalidate.01',           cfg.bing_site_verification);
      setVerificationMeta('yandex-verification',     cfg.yandex_site_verification);
      injectGa4(cfg.ga4_measurement_id);
      injectGoogleAds(cfg.google_ads_conversion_id, cfg.google_ads_send_page_view !== false);
      injectFacebookPixel(cfg.facebook_pixel_id);
    });
    return () => { cancelled = true; };
  }, [pathname]);

  return null;
}

// ─── Lightweight helper for conversion fires from anywhere in the app ─────
// Usage:
//   import { fireConversion } from '@/components/seo/SeoRuntimeInjector';
//   fireConversion('lead_submit', { value: 100, currency: 'EUR' });
export const fireConversion = async (eventKey, eventData = {}) => {
  try {
    const cfg = await fetchRuntimeConfig();
    const id  = cfg?.google_ads_conversion_id;
    const lbl = cfg?.google_ads_conversion_labels?.[eventKey];
    if (!id || !lbl || typeof window.gtag !== 'function') return;
    window.gtag('event', 'conversion', {
      send_to: `${id}/${lbl}`,
      ...eventData,
    });
  } catch {
    /* silently no-op — analytics must never break the user flow */
  }
};
