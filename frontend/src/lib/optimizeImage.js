/**
 * optimizeImage(url, options) — universal image optimizer used across the
 * mobile + desktop UI. Wraps external (non-asset) URLs through the
 * `images.weserv.nl` proxy that re-encodes JPEG/PNG payloads into WebP
 * (or AVIF when supported by the browser) on the fly. This preserves
 * the original photo content (no replacement, no logic change) while
 * cutting bytes-on-the-wire by ~5–10× for large multi-MB JPGs.
 *
 * Why weserv:
 *   • Public, free CDN (no auth, no API key needed).
 *   • Supports `?url=` for arbitrary remote images.
 *   • Supports `&output=webp`, width/height resize, and `&q=` quality.
 *   • Caches results globally → first request slow, subsequent ones fast.
 *
 * Rules:
 *   • Local assets (`/figma/*`, `/mobile/*`, relative `/api/*`, data:/blob:)
 *     → return untouched. They're already small and served by our own
 *     infra.
 *   • Already-optimized URLs (already containing `images.weserv.nl`)
 *     → return untouched (idempotent).
 *   • Remote `http(s)` URLs → wrap through weserv with width / quality.
 */

const WESERV = 'https://images.weserv.nl/';

export function optimizeImage(url, options = {}) {
  if (!url || typeof url !== 'string') return url || '';

  const trimmed = url.trim();

  // data:, blob:, mailto:, javascript: — never touch
  if (/^(data:|blob:|mailto:|javascript:)/i.test(trimmed)) return trimmed;

  // Already proxied → idempotent
  if (trimmed.includes('images.weserv.nl/')) return trimmed;

  // Local public assets / API paths → don't touch
  if (trimmed.startsWith('/')) return trimmed;
  if (!/^https?:\/\//i.test(trimmed)) return trimmed;

  const { w, h, q = 82, format = 'webp', fit = 'cover' } = options;

  // weserv `url=` expects the protocol stripped (their docs)
  const target = trimmed.replace(/^https?:\/\//i, '');
  const params = new URLSearchParams();
  params.set('url', target);
  if (w) params.set('w', String(w));
  if (h) params.set('h', String(h));
  if (q) params.set('q', String(q));
  if (format) params.set('output', format);
  if (fit) params.set('fit', fit);
  // Skip cache busting — let weserv cache aggressively
  params.set('we', '1');

  return `${WESERV}?${params.toString()}`;
}

/**
 * Convenience presets for the most common UI usages so callers don't have
 * to memorize widths. Keeps the design tokens centralized.
 */
export const ImageSize = {
  // Vehicle card on mobile welcome carousel (~336px wide, 2× for retina)
  cardMobile: { w: 720, q: 82 },
  // Vehicle card on desktop catalog (~410px wide, 2× for retina)
  cardDesktop: { w: 820, q: 84 },
  // Thumbnail strip / small previews
  thumb: { w: 320, q: 78 },
  // Hero / banner images (full-bleed)
  hero: { w: 1280, q: 85 },
  // Avatars (40-80px, 2× → 160)
  avatar: { w: 160, q: 80 },
  // Before/After photos (~150px each, 2× → 300)
  beforeAfter: { w: 360, q: 82 },
};

export default optimizeImage;
