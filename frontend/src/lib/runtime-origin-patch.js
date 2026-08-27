/**
 * runtime-origin-patch.js — portable backend URL rewriting.
 *
 * THE PROBLEM
 * ───────────
 * When the app is attached to a CUSTOM domain (e.g. `bibi.cars`) AFTER the
 * React bundle was built, the bundle still has the build-time
 * `REACT_APP_BACKEND_URL` baked in. The browser opens the custom domain,
 * axios fires the request to the old (build-time) host, the browser's CORS
 * policy blocks the cross-origin call, and the UI shows a generic
 * "Network Error".
 *
 * THE FIX
 * ───────
 * We DO NOT rebuild the bundle and DO NOT touch the source files that use
 * `${process.env.REACT_APP_BACKEND_URL}/...`. Instead we install a single
 * axios request interceptor (and a `window.fetch` wrapper) that runs BEFORE
 * every outbound HTTP call and:
 *
 *   1. Looks at the original URL.
 *   2. If it absolutely points to the BUILD-TIME backend host AND the page
 *      is currently served from a DIFFERENT origin → rewrite the host to the
 *      current `window.location.origin` (keeping the path intact).
 *   3. Otherwise the URL is left untouched (localhost dev, same-origin
 *      requests, and third-party CDNs all keep working).
 *
 * This makes the deployment fully portable across domains without a rebuild.
 * The patch is idempotent and silent in production.
 */
import axios from "axios";

// Host that the bundle was built against (from REACT_APP_BACKEND_URL).
function buildTimeBackendHost() {
  try {
    const raw = process.env.REACT_APP_BACKEND_URL;
    if (!raw) return null;
    return new URL(raw).hostname.toLowerCase();
  } catch {
    return null;
  }
}

const BUILD_HOST = buildTimeBackendHost();

function isBuildTimeHost(host) {
  if (!host || !BUILD_HOST) return false;
  return host.toLowerCase() === BUILD_HOST;
}

/**
 * Returns the origin the frontend SHOULD use as backend base. In the browser
 * this is `window.location.origin`. In SSR / Node (e.g. CRA tests) we return
 * null and the original URL is kept.
 */
function currentOrigin() {
  if (typeof window === "undefined" || !window.location) return null;
  return window.location.origin;
}

/**
 * Rewrites a target URL when its host matches the build-time backend host AND
 * we are running in the browser AND the current origin differs. Same-origin
 * URLs and relative paths pass through untouched.
 */
export function rewriteIfStale(rawUrl) {
  if (!rawUrl || typeof rawUrl !== "string") return rawUrl;
  // Relative path (starts with `/`, `./`, `../`) — keep as-is.
  if (!/^https?:\/\//i.test(rawUrl)) return rawUrl;
  const origin = currentOrigin();
  if (!origin) return rawUrl;
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return rawUrl;
  }
  // Same origin — leave untouched.
  if (parsed.origin === origin) return rawUrl;
  // Not the build-time backend host — leave untouched (3rd-party CDN, image
  // proxy, vesselfinder.com, etc.).
  if (!isBuildTimeHost(parsed.hostname)) return rawUrl;
  // Otherwise: rewrite host + protocol to current origin.
  const next = new URL(parsed.pathname + parsed.search + parsed.hash, origin);
  return next.toString();
}

let installed = false;

export function installRuntimeOriginPatch() {
  if (installed) return;
  installed = true;

  // ── axios — global interceptor on the default + module instance ──
  const tagInterceptor = (instance) => {
    if (!instance || !instance.interceptors || !instance.interceptors.request) return;
    instance.interceptors.request.use((config) => {
      if (config.url) config.url = rewriteIfStale(config.url);
      if (config.baseURL) config.baseURL = rewriteIfStale(config.baseURL);
      return config;
    });
  };
  tagInterceptor(axios);
  // Also patch the default baseURL in case something reads it directly.
  if (axios.defaults && axios.defaults.baseURL) {
    axios.defaults.baseURL = rewriteIfStale(axios.defaults.baseURL);
  }

  // ── window.fetch — wrap once, preserving all other arguments ────
  if (typeof window !== "undefined" && typeof window.fetch === "function") {
    const original = window.fetch.bind(window);
    window.fetch = (input, init) => {
      if (typeof input === "string") {
        return original(rewriteIfStale(input), init);
      }
      // Request object (rare in this codebase) — re-create with new URL
      if (input && typeof input === "object" && "url" in input) {
        const rewritten = rewriteIfStale(input.url);
        if (rewritten !== input.url) {
          const cloned = new Request(rewritten, input);
          return original(cloned, init);
        }
      }
      return original(input, init);
    };
  }
}

// Auto-install on import so consumers only need `import "./runtime-origin-patch"`.
installRuntimeOriginPatch();

export default installRuntimeOriginPatch;
