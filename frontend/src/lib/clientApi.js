import axios from "axios";

// Isolated axios instance + token storage for the CLIENT (B2B customer) area.
// Kept separate from lib/api.js (which uses `eco_token` for STAFF/CRM) so the
// two sessions never collide.
const BASE = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
const TOKEN_KEY = "eco_client_token";

export const getClientToken = () => localStorage.getItem(TOKEN_KEY);
export const setClientToken = (t) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

export const clientApi = axios.create({ baseURL: `${BASE}/api` });

clientApi.interceptors.request.use((config) => {
  const t = getClientToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export const ClientAPI = {
  // auth — Google (fast)
  googleClientId: () => clientApi.get("/auth/google-client-id").then((r) => r.data),
  googleVerify: (credential) =>
    clientApi.post("/customer-auth/google/verify", { credential }).then((r) => r.data),
  devLogin: (email, extra = {}) =>
    clientApi.post("/client/dev-login", { email, ...extra }).then((r) => r.data),
  // auth — classic email/password
  loginEmail: (email, password) =>
    clientApi.post("/customer-auth/login", { email, password }).then((r) => r.data),
  registerEmail: (body) =>
    clientApi.post("/customer-auth/register", body).then((r) => r.data),
  verifyEmail: (email, code) =>
    clientApi.post("/customer-auth/verify-email", { email, code }).then((r) => r.data),
  resendCode: (email) =>
    clientApi.post("/customer-auth/resend-email-code", { email }).then((r) => r.data),
  forgotPassword: (email) =>
    clientApi.post("/customer-auth/forgot-password", { email }).then((r) => r.data),
  resetPassword: (token, password) =>
    clientApi.post("/customer-auth/reset-password", { token, password }).then((r) => r.data),
  validateResetToken: (token) =>
    clientApi.get("/customer-auth/validate-reset-token", { params: { token } }).then((r) => r.data),
  // profile
  me: () => clientApi.get("/client/me").then((r) => r.data),
  updateMe: (body) => clientApi.put("/client/me", body).then((r) => r.data),
  // data
  summary: () => clientApi.get("/client/summary").then((r) => r.data),
  requests: (params) => clientApi.get("/client/requests", { params }).then((r) => r.data),
  request: (id) => clientApi.get(`/client/requests/${id}`).then((r) => r.data),
  createRequest: (body) => clientApi.post("/client/requests", body).then((r) => r.data),
  reorder: (id) => clientApi.post(`/client/requests/${id}/reorder`).then((r) => r.data),
  documents: () => clientApi.get("/client/documents").then((r) => r.data),
  // invoices — IBAN bank-transfer flow
  invoices: () => clientApi.get("/client/invoices").then((r) => r.data),
  invoice: (id) => clientApi.get(`/client/invoices/${id}`).then((r) => r.data),
  confirmInvoicePayment: (id, body) =>
    clientApi.post(`/client/invoices/${id}/confirm-payment`, body).then((r) => r.data),
  uploadInvoiceProof: (id, formData) =>
    clientApi.post(`/client/invoices/${id}/upload-proof`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data),
  // notifications / messages (received from staff)
  notifications: (params) => clientApi.get("/client/notifications", { params }).then((r) => r.data),
  notificationsUnread: () => clientApi.get("/client/notifications/unread-count").then((r) => r.data),
  markNotificationRead: (id) => clientApi.post(`/client/notifications/${id}/read`).then((r) => r.data),
  markAllNotificationsRead: () => clientApi.post("/client/notifications/read-all").then((r) => r.data),
  // public waste search (licensed only) — used by the in-cabinet new-request form
  searchCodes: (q, limit = 10) =>
    clientApi.get("/waste/search", { params: { q, limit, accepted: true } }).then((r) => r.data),
  // Contract Execution Engine (read-only mirror)
  ceContracts: () => clientApi.get("/client/contract-engine").then((r) => r.data),
  ceContract: (id) => clientApi.get(`/client/contract-engine/${id}`).then((r) => r.data),
  ceReportPdf: (contractId, reportId) =>
    clientApi.get(`/client/contract-engine/${contractId}/reports/${reportId}/pdf`, { responseType: "blob" }).then((r) => r.data),
  // ── Universal Contract Flow (acceptance + IBAN payment) ──
  cfLegalProfile: () => clientApi.get("/client/cflow/legal-profile").then((r) => r.data),
  cfSaveLegalProfile: (b) => clientApi.put("/client/cflow/legal-profile", b).then((r) => r.data),
  cfContracts: () => clientApi.get("/client/cflow/contracts").then((r) => r.data),
  cfContract: (id) => clientApi.get(`/client/cflow/contracts/${id}`).then((r) => r.data),
  cfOpen: (id) => clientApi.post(`/client/cflow/contracts/${id}/open`, {}).then((r) => r.data),
  cfAccept: (id, b = {}) => clientApi.post(`/client/cflow/contracts/${id}/accept`, b).then((r) => r.data),
  cfUploadProof: (id, formData) =>
    clientApi.post(`/client/cflow/contracts/${id}/proof`, formData, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  cfPdfUrl: (id) => `${BASE}/api/client/cflow/contracts/${id}/pdf`,
  cfFileUrl: (id) => `${BASE}/api/client/cflow/files/${id}`,
};

export const PublicAPI = {
  inquiry: (body) => clientApi.post("/public/inquiry", body).then((r) => r.data),
  companySuggest: (q, limit = 8) =>
    clientApi.get("/public/company-suggest", { params: { q, limit } }).then((r) => r.data),
  contacts: () => clientApi.get("/public/contacts").then((r) => r.data),
  siteInfo: () => clientApi.get("/site-info").then((r) => r.data),
  policy: (key, lang = "uk") =>
    clientApi.get(`/site-info/policy/${key}`, { params: { lang } }).then((r) => r.data),
};
