/**
 * contentApi.js — Admin Content Center API client (Phase D1).
 *
 * All endpoints require a master-admin JWT (`Authorization: Bearer <token>`)
 * except the public read helpers under /api/content and /api/media.
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

const apiForm = async (path, formData) => {
  const token = readToken();
  const r = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    body: formData,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data;
};

export const contentApi = {
  // Metadata / introspection
  getBlockTypes: () => apiJson('/api/admin/content/block-types'),

  // Pages
  listPages: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v && q.append(k, v));
    const qs = q.toString();
    return apiJson(`/api/admin/content/pages${qs ? `?${qs}` : ''}`);
  },
  getPage: (pageId) => apiJson(`/api/admin/content/pages/${encodeURIComponent(pageId)}`),
  createPage: (body) => apiJson('/api/admin/content/pages', { method: 'POST', body: JSON.stringify(body) }),
  updatePage: (pageId, body) => apiJson(`/api/admin/content/pages/${encodeURIComponent(pageId)}`, { method: 'PUT', body: JSON.stringify(body) }),
  deletePage: (pageId) => apiJson(`/api/admin/content/pages/${encodeURIComponent(pageId)}`, { method: 'DELETE' }),
  transitionPage: (pageId, status) => apiJson(`/api/admin/content/pages/${encodeURIComponent(pageId)}/transition`, {
    method: 'POST', body: JSON.stringify({ status }),
  }),
  listVersions: (pageId) => apiJson(`/api/admin/content/pages/${encodeURIComponent(pageId)}/versions`),
  restoreVersion: (pageId, version) => apiJson(`/api/admin/content/pages/${encodeURIComponent(pageId)}/restore`, {
    method: 'POST', body: JSON.stringify({ version }),
  }),

  // Media
  listMedia: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v && q.append(k, v));
    const qs = q.toString();
    return apiJson(`/api/admin/media${qs ? `?${qs}` : ''}`);
  },
  uploadMedia: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return apiForm('/api/admin/media/upload', fd);
  },
  updateMedia: (assetId, body) => apiJson(`/api/admin/media/${encodeURIComponent(assetId)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteMedia: (assetId) => apiJson(`/api/admin/media/${encodeURIComponent(assetId)}`, { method: 'DELETE' }),

  // FAQ
  listFaq: (params = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v && q.append(k, v));
    const qs = q.toString();
    return apiJson(`/api/admin/faq${qs ? `?${qs}` : ''}`);
  },
  createFaq: (body) => apiJson('/api/admin/faq', { method: 'POST', body: JSON.stringify(body) }),
  updateFaq: (faqId, body) => apiJson(`/api/admin/faq/${encodeURIComponent(faqId)}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteFaq: (faqId) => apiJson(`/api/admin/faq/${encodeURIComponent(faqId)}`, { method: 'DELETE' }),
};

export { BACKEND_URL };
