/**
 * seoApi.js — thin fetch wrapper for the Admin SEO Center.
 * Every call includes the JWT from localStorage and returns parsed JSON.
 */
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const TOKEN_KEYS = ['eco_token', 'token'];
const readToken = () => {
  if (typeof window === 'undefined') return '';
  for (const k of TOKEN_KEYS) {
    const v = localStorage.getItem(k);
    if (v) return v;
  }
  return '';
};

const withAuth = (init = {}) => {
  const token = readToken();
  return {
    ...init,
    headers: {
      ...(init.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };
};

const apiJson = async (path, init = {}) => {
  const r = await fetch(`${BACKEND_URL}${path}`, withAuth({
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
  }));
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) {
    const msg = (data && data.detail) || `HTTP ${r.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
};

const apiText = async (path, init = {}) => {
  const r = await fetch(`${BACKEND_URL}${path}`, withAuth(init));
  const text = await r.text();
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${text.slice(0, 200)}`);
  return text;
};

export const seoApi = {
  // Global settings
  getSettings: () => apiJson('/api/admin/seo/settings'),
  patchSettings: (body) => apiJson('/api/admin/seo/settings', { method: 'PATCH', body: JSON.stringify(body) }),
  // Company profile
  getCompany: () => apiJson('/api/admin/seo/company'),
  putCompany: (body) => apiJson('/api/admin/seo/company', { method: 'PUT', body: JSON.stringify(body) }),
  // Analytics
  getAnalytics: () => apiJson('/api/admin/seo/analytics'),
  putAnalytics: (body) => apiJson('/api/admin/seo/analytics', { method: 'PUT', body: JSON.stringify(body) }),
  // Pages
  listPages: (q = '') => apiJson(`/api/admin/seo/pages${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  getPage: (path) => apiJson(`/api/admin/seo/pages${path.startsWith('/') ? path : `/${path}`}`),
  upsertPage: (body) => apiJson('/api/admin/seo/pages', { method: 'POST', body: JSON.stringify(body) }),
  deletePage: (path) => apiJson(`/api/admin/seo/pages${path.startsWith('/') ? path : `/${path}`}`, { method: 'DELETE' }),
  // Robots
  getRobots: () => apiJson('/api/admin/seo/robots'),
  putRobots: (body) => apiJson('/api/admin/seo/robots', { method: 'PUT', body: JSON.stringify(body) }),
  previewRobots: () => apiText('/api/admin/seo/robots/preview'),
  // Sitemap
  getSitemap: () => apiJson('/api/admin/seo/sitemap'),
  previewSitemap: (kind = 'pages') => apiText(`/api/admin/seo/sitemap/preview?kind=${encodeURIComponent(kind)}`),
  regenerateSitemap: () => apiJson('/api/admin/seo/sitemap/regenerate', { method: 'POST' }),
};

export { BACKEND_URL };
