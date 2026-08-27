import axios from "axios";

const BASE = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");

export const api = axios.create({ baseURL: `${BASE}/api` });

const TOKEN_KEY = "eco_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

api.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// ── Call Intelligence (on-demand transcription + AI summary) ────────
export const CallIntelAPI = {
  config: () => api.get("/admin/calls/intelligence/config").then((r) => r.data),
  stats: (params) => api.get("/admin/calls/intelligence/stats", { params }).then((r) => r.data),
  recent: (params) => api.get("/admin/calls/intelligence/recent", { params }).then((r) => r.data),
  atRisk: (params) => api.get("/admin/calls/intelligence/at-risk", { params }).then((r) => r.data),
  // Ringostat calls list (reuse existing admin surface)
  calls: (params) => api.get("/admin/ringostat/calls", { params }).then((r) => r.data),
  get: (callId) => api.get(`/admin/calls/${callId}/intelligence`).then((r) => r.data),
  process: (callId, force = false) =>
    api.post(`/admin/calls/${callId}/intelligence/process`, { force }).then((r) => r.data),
  bulkProcess: (callIds, force = false) =>
    api.post(`/admin/calls/intelligence/bulk-process`, { call_ids: callIds, force }).then((r) => r.data),
  apply: (callId, body) =>
    api.post(`/admin/calls/${callId}/intelligence/apply`, body).then((r) => r.data),
};

// ── Public waste API ──────────────────────────────────────────────
// УВАГА: публічний клієнт ЗАВЖДИ фільтрує за accepted=true — публіка бачить
// лише ліцензований перелік («ми приймаємо»), не більше і не менше.
export const WasteAPI = {
  categories: () => api.get("/waste/categories", { params: { accepted: true } }).then((r) => r.data),
  codes: (params) => api.get("/waste/codes", { params: { ...(params || {}), accepted: true } }).then((r) => r.data),
  codeBySlug: (slug) => api.get(`/waste/codes/${slug}`).then((r) => r.data),
  codeByCode: (code) => api.get("/waste/codes/by-code", { params: { code } }).then((r) => r.data),
  search: (q, limit = 12) => api.get("/waste/search", { params: { q, limit, accepted: true } }).then((r) => r.data),
  licenseCheck: (code) => api.get("/waste/license/check", { params: { code } }).then((r) => r.data),
  price: (payload) => api.post("/waste/price", payload).then((r) => r.data),
  createPublicRequest: (payload) => api.post("/waste/requests/public", payload).then((r) => r.data),
  // National waste list hierarchy
  chapters: () => api.get("/waste/chapters").then((r) => r.data),
  groups: (chapter) => api.get("/waste/groups", { params: chapter ? { chapter } : {} }).then((r) => r.data),
};

// ── Admin: National Waste List management (Wave 5D) ─────────────────
export const WasteAdminAPI = {
  stats: () => api.get("/waste/admin/stats").then((r) => r.data),
  reseedNational: () => api.post("/waste/admin/reseed-national").then((r) => r.data),
  // Codes
  listCodes: (params) => api.get("/waste/codes", { params }).then((r) => r.data),
  createCode: (body) => api.post("/waste/codes", body).then((r) => r.data),
  updateCode: (code, patch) => api.put("/waste/codes/by-code", patch, { params: { code } }).then((r) => r.data),
  deleteCode: (code) => api.delete("/waste/codes/by-code", { params: { code } }).then((r) => r.data),
  // Chapters
  listChapters: () => api.get("/waste/chapters").then((r) => r.data),
  createChapter: (body) => api.post("/waste/chapters", body).then((r) => r.data),
  updateChapter: (code, patch) => api.put("/waste/chapters/by-code", patch, { params: { code } }).then((r) => r.data),
  deleteChapter: (code) => api.delete("/waste/chapters/by-code", { params: { code } }).then((r) => r.data),
  // Groups
  listGroups: (chapter) => api.get("/waste/groups", { params: chapter ? { chapter } : {} }).then((r) => r.data),
  createGroup: (body) => api.post("/waste/groups", body).then((r) => r.data),
  updateGroup: (code, patch) => api.put("/waste/groups/by-code", patch, { params: { code } }).then((r) => r.data),
  deleteGroup: (code) => api.delete("/waste/groups/by-code", { params: { code } }).then((r) => r.data),
  // Public site contacts (header / footer / Contacts page)
  getSiteContacts: () => api.get("/waste/admin/site-contacts").then((r) => r.data),
  saveSiteContacts: (body) => api.put("/waste/admin/site-contacts", body).then((r) => r.data),
};

// ── Staff / portal API ────────────────────────────────────────────
export const PortalAPI = {
  stats: () => api.get("/waste/stats").then((r) => r.data),
  companies: (params) => api.get("/waste/companies", { params }).then((r) => r.data),
  company: (id) => api.get(`/waste/companies/${id}`).then((r) => r.data),
  createCompany: (b) => api.post("/waste/companies", b).then((r) => r.data),
  objects: (params) => api.get("/waste/objects", { params }).then((r) => r.data),
  createObject: (b) => api.post("/waste/objects", b).then((r) => r.data),
  objectDetail: (id) => api.get(`/waste/objects/${id}/detail`).then((r) => r.data),
  requests: (params) => api.get("/waste/requests", { params }).then((r) => r.data),
  createRequest: (b) => api.post("/waste/requests", b).then((r) => r.data),
  request: (id) => api.get(`/waste/requests/${id}`).then((r) => r.data),
  setRequestStage: (id, stage, note) => api.post(`/waste/requests/${id}/stage`, { stage, note }).then((r) => r.data),
  genFromRequest: (id, kind, body = {}) => api.post(`/waste/requests/${id}/${kind}`, body).then((r) => r.data),
  contracts: (params) => api.get("/waste/contracts", { params }).then((r) => r.data),
  contract: (id) => api.get(`/waste/contracts/${id}`).then((r) => r.data),
  updateContract: (id, patch) => api.put(`/waste/contracts/${id}`, patch).then((r) => r.data),
  setContractStatus: (id, status, note) => api.post(`/waste/contracts/${id}/status`, { status, note }).then((r) => r.data),
  // Electronic signature (tokenized) — staff actions
  sendContractEsign: (id) => api.post(`/waste/contracts/${id}/send-esign`, {}).then((r) => r.data),
  revokeContractEsign: (id) => api.post(`/waste/contracts/${id}/revoke-esign`, {}).then((r) => r.data),
  pickups: (params) => api.get("/waste/pickups", { params }).then((r) => r.data),
  pickup: (id) => api.get(`/waste/pickups/${id}`).then((r) => r.data),
  updatePickup: (id, patch) => api.put(`/waste/pickups/${id}`, patch).then((r) => r.data),
  setPickupStatus: (id, status, note) => api.post(`/waste/pickups/${id}/status`, { status, note }).then((r) => r.data),
  acts: (params) => api.get("/waste/acts", { params }).then((r) => r.data),
  act: (id) => api.get(`/waste/acts/${id}`).then((r) => r.data),
  updateAct: (id, patch) => api.put(`/waste/acts/${id}`, patch).then((r) => r.data),
  setActStatus: (id, status, note) => api.post(`/waste/acts/${id}/status`, { status, note }).then((r) => r.data),

  // ── Contract Execution Engine ──────────────────────────────────
  ceSchedule: (id) => api.get(`/waste/contracts/${id}/schedule`).then((r) => r.data),
  ceGenerate: (id, body = {}) => api.post(`/waste/contracts/${id}/schedule/generate`, body).then((r) => r.data),
  ceUpdateEngine: (id, patch) => api.patch(`/waste/contracts/${id}/engine`, patch).then((r) => r.data),
  cePatchLine: (periodId, code, patch) => api.patch(`/waste/periods/${periodId}/lines/${encodeURIComponent(code)}`, patch).then((r) => r.data),
  ceDeleteLine: (periodId, code) => api.delete(`/waste/periods/${periodId}/lines/${encodeURIComponent(code)}`).then((r) => r.data),
  ceAddExtra: (periodId, body) => api.post(`/waste/periods/${periodId}/extra-works`, body).then((r) => r.data),
  ceDelExtra: (periodId, extraId) => api.delete(`/waste/periods/${periodId}/extra-works/${extraId}`).then((r) => r.data),
  cePeriodStatus: (periodId, status) => api.post(`/waste/periods/${periodId}/status`, { status }).then((r) => r.data),
  ceFinancials: (id) => api.get(`/waste/contracts/${id}/financials`).then((r) => r.data),
  ceFreeze: (id, value) => api.post(`/waste/contracts/${id}/freeze-value`, value != null ? { value } : {}).then((r) => r.data),
  ceRecompute: (id) => api.post(`/waste/contracts/${id}/recompute`, {}).then((r) => r.data),
  ceCompletionCheck: (id) => api.get(`/waste/contracts/${id}/completion-check`).then((r) => r.data),
  ceComplete: (id, confirm = true) => api.post(`/waste/contracts/${id}/complete`, { confirm }).then((r) => r.data),
  ceReports: (id) => api.get(`/waste/contracts/${id}/ecologist-reports`).then((r) => r.data),
  ceCreateReport: (id, body) => api.post(`/waste/contracts/${id}/ecologist-reports`, body).then((r) => r.data),
  ceUpdateReport: (reportId, patch) => api.patch(`/waste/ecologist-reports/${reportId}`, patch).then((r) => r.data),
  ceReportPdfUrl: (reportId) => `${BASE}/api/waste/ecologist-reports/${reportId}/pdf`,
  ceSignReport: (reportId) => api.post(`/waste/ecologist-reports/${reportId}/sign-off`, {}).then((r) => r.data),
  ceInvoicePeriod: (id, periodId, body = {}) => api.post(`/waste/contracts/${id}/periods/${periodId}/invoice`, body).then((r) => r.data),
  ceInvoiceAct: (id, actId, body = {}) => api.post(`/waste/contracts/${id}/acts/${actId}/invoice`, body).then((r) => r.data),
  ceInvoiceStatus: (id, invoiceId, body) => api.post(`/waste/contracts/${id}/invoices/${invoiceId}/status`, body).then((r) => r.data),
  ceContractInvoices: (id) => api.get(`/waste/contracts/${id}/invoices`).then((r) => r.data),
  // Object Center
  updateObject: (id, patch) => api.put(`/waste/objects/${id}`, patch).then((r) => r.data),
  deleteObject: (id) => api.delete(`/waste/objects/${id}`).then((r) => r.data),
  // Company360
  timeline: (cid) => api.get(`/waste/companies/${cid}/timeline`).then((r) => r.data),
  tasks: (cid) => api.get(`/waste/companies/${cid}/tasks`).then((r) => r.data),
  createTask: (cid, b) => api.post(`/waste/companies/${cid}/tasks`, b).then((r) => r.data),
  updateTask: (id, patch) => api.put(`/waste/tasks/${id}`, patch).then((r) => r.data),
  deleteTask: (id) => api.delete(`/waste/tasks/${id}`).then((r) => r.data),
  comments: (cid) => api.get(`/waste/companies/${cid}/comments`).then((r) => r.data),
  createComment: (cid, b) => api.post(`/waste/companies/${cid}/comments`, b).then((r) => r.data),
  // Inquiries inbox (public-site callbacks / questions)
  inquiries: (params) => api.get("/waste/inquiries", { params }).then((r) => r.data),
  updateInquiry: (id, b) => api.patch(`/waste/inquiries/${id}`, b).then((r) => r.data),
  // ── Team / linkage: managers, company ownership, cold leads ──
  managers: () => api.get("/waste/managers").then((r) => r.data),
  assignCompanyManager: (id, manager_id) => api.patch(`/waste/companies/${id}/manager`, { manager_id }).then((r) => r.data),
  leads: (params) => api.get("/waste/leads", { params }).then((r) => r.data),
  createLead: (b) => api.post("/waste/leads", b).then((r) => r.data),
  updateLead: (id, b) => api.patch(`/waste/leads/${id}`, b).then((r) => r.data),
  convertLead: (id) => api.post(`/waste/leads/${id}/convert`).then((r) => r.data),
  // Notifications (ECO queue bell)
  notifications: (params) => api.get("/waste/notifications", { params }).then((r) => r.data),
  markNotificationRead: (id) => api.post(`/waste/notifications/${id}/read`).then((r) => r.data),
  markAllNotificationsRead: () => api.post("/waste/notifications/read-all").then((r) => r.data),
  // Message Center (directed messaging: admin→managers+clients, manager→clients)
  messageRecipients: () => api.get("/waste/messages/recipients").then((r) => r.data),
  sendMessage: (body) => api.post("/waste/messages/send", body).then((r) => r.data),
  sentMessages: (params) => api.get("/waste/messages/sent", { params }).then((r) => r.data),
};

// ── Legacy CRM Integration Layer (Wave 5A) ────────────────────────
// Read-only wrappers around the existing CRM endpoints living in server.py
// so the ECO UI can consume Tasks / Calls / Invoices / Documents / Notifications
// without duplicating logic. The legacy backend stores data in collections
// like `db.tasks`, `db.invoices`, `db.ringostat_calls`, `db.documents`.
export const CrmAPI = {
  // Staff (for assignee pickers)
  eligibleAssignees: () => api.get("/tasks/eligible-assignees").then((r) => r.data),
  // Tasks
  tasks: (params) => api.get("/tasks", { params }).then((r) => r.data),
  taskStats: () => api.get("/tasks/stats").then((r) => r.data),
  taskQueue: () => api.get("/tasks/queue").then((r) => r.data),
  taskActive: () => api.get("/tasks/active").then((r) => r.data),
  taskGet: (id) => api.get(`/tasks/${id}`).then((r) => r.data),
  taskCreate: (b) => api.post("/tasks", b).then((r) => r.data),
  taskUpdate: (id, b) => api.patch(`/tasks/${id}`, b).then((r) => r.data),
  taskDelete: (id) => api.delete(`/tasks/${id}`).then((r) => r.data),
  taskStart: (id) => api.post(`/tasks/${id}/start`).then((r) => r.data),
  taskComplete: (id, b) => api.post(`/tasks/${id}/complete`, b || {}).then((r) => r.data),
  // Calls / Ringostat
  myCalls: (params) => api.get("/manager/calls/my", { params }).then((r) => r.data),
  missedCalls: () => api.get("/manager/calls/missed").then((r) => r.data),
  callOutcome: (callId, outcome, comment) => api.post(`/calls/${callId}/outcome`, { outcome, comment }).then((r) => r.data),
  simulateCall: (b) => api.post("/debug/ringostat/simulate", b).then((r) => r.data),
  // Calls Console (ECO unified surface)
  callsSummary: (params) => api.get("/manager/calls/summary", { params }).then((r) => r.data),
  callsFeed: (params) => api.get("/manager/calls/feed", { params }).then((r) => r.data),
  callsAwaiting: (params) => api.get("/manager/calls/awaiting-outcome", { params }).then((r) => r.data),
  callsCallbacks: (params) => api.get("/manager/calls/callbacks", { params }).then((r) => r.data),
  // Save the rich manager outcome (outcome + note + callback date → decision engine)
  saveOutcome: (callId, b) => api.post(`/manager/calls/${callId}/outcome`, b).then((r) => r.data),
  leadCalls: (leadId) => api.get(`/leads/${leadId}/calls`).then((r) => r.data),
  // Ringostat mappings (extension → manager) reused on the console
  ringostatMappings: () => api.get("/admin/ringostat/mappings").then((r) => r.data),
  // Invoices
  invoices: () => api.get("/invoices").then((r) => r.data),
  invoicesManager: () => api.get("/invoices/manager/my").then((r) => r.data),
  invoicesOverdue: () => api.get("/invoices/overdue").then((r) => r.data),
  invoiceAnalytics: () => api.get("/invoices/analytics").then((r) => r.data),
  invoiceCreate: (b) => api.post("/invoices/create", b).then((r) => r.data),
  invoiceGet: (id) => api.get(`/invoices/${id}`).then((r) => r.data),
  // IBAN bank-transfer flow
  invoiceIssueIban: (id) => api.post(`/invoices/${id}/issue-iban`).then((r) => r.data),
  invoicesPendingConfirmation: () => api.get("/manager/invoices/pending-confirmation").then((r) => r.data),
  invoiceConfirmPayment: (id, b = {}) => api.post(`/invoices/${id}/confirm-payment`, b).then((r) => r.data),
  invoiceRejectPayment: (id, b = {}) => api.post(`/invoices/${id}/reject-payment`, b).then((r) => r.data),
  billingRequisites: () => api.get("/billing/requisites").then((r) => r.data),
  // Customers (RBAC-aware list for pickers; manager sees own)
  customersList: (params = {}) => api.get("/customers", { params }).then((r) => r.data),
  // Manager invoices (IBAN-first)
  managerInvoicesMy: (params = {}) => api.get(`/manager/invoices/my`, { params: { limit: 200, ...params } }).then((r) => r.data),
  managerInvoiceCreate: (b) => api.post("/manager/invoices", b).then((r) => r.data),
  // Invoice lifecycle (send / cancel / mark-paid)
  invoiceSend: (id) => api.patch(`/invoices/${id}/send`).then((r) => r.data),
  invoiceCancel: (id) => api.patch(`/invoices/${id}/cancel`).then((r) => r.data),
  invoiceMarkPaid: (id, b = {}) => api.patch(`/invoices/${id}/mark-paid`, b).then((r) => r.data),
  // Contract-first gating (online e-sign / offline upload)
  invoiceContract: (id) => api.get(`/manager/invoices/${id}/contract`).then((r) => r.data),
  invoiceContractOfflineSign: (id, formData) =>
    api.post(`/manager/invoices/${id}/contract/offline-sign`, formData, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  invoiceContractSendOnline: (id) => api.post(`/manager/invoices/${id}/contract/send-online`).then((r) => r.data),
  // Admin requisites configuration
  adminRequisitesGet: () => api.get("/admin/billing/requisites").then((r) => r.data),
  adminRequisitesSave: (b) => api.put("/admin/billing/requisites", b).then((r) => r.data),
  // Documents
  documents: () => api.get("/documents").then((r) => r.data),
  documentsPending: () => api.get("/documents/queue/pending-verification").then((r) => r.data),
  documentCreate: (b) => api.post("/documents", b).then((r) => r.data),
  documentGet: (id) => api.get(`/documents/${id}`).then((r) => r.data),
  // ── Customer 360 (staff) — reuse existing aggregation endpoints ──────
  customerGet: (id) => api.get(`/customers/${id}`).then((r) => r.data),
  customerOverview: (id) => api.get(`/customers/${id}/eco/overview`).then((r) => r.data),
  customerEcoRequests: (id) => api.get(`/customers/${id}/eco/requests`).then((r) => r.data),
  customerEcoContracts: (id) => api.get(`/customers/${id}/eco/contracts`).then((r) => r.data),
  customerEcoActs: (id) => api.get(`/customers/${id}/eco/acts`).then((r) => r.data),
  customerEcoActivity: (id) => api.get(`/customers/${id}/eco/activity`).then((r) => r.data),
  customerInvoices: (id) => api.get(`/customers/${id}/invoices`).then((r) => r.data),
  customerPayments: (id) => api.get(`/customers/${id}/payments`).then((r) => r.data),
  customerFinanceSummary: (id) => api.get(`/customers/${id}/finance-summary`).then((r) => r.data),
  customerDocuments: (id) => api.get(`/customers/${id}/documents`).then((r) => r.data),
  customerComments: (id) => api.get(`/customers/${id}/comments`).then((r) => r.data),
  customerAddComment: (id, b) => api.post(`/customers/${id}/comments`, b).then((r) => r.data),
  companyCustomers: (companyId) => api.get(`/companies/${companyId}/customers`).then((r) => r.data),
};

// ── Action Center (Wave 17) — ECO operations action engine ──────────
// Inbox / My / Team / Analytics + lifecycle (start/resolve/snooze/escalate).
export const ActionsAPI = {
  sources: () => api.get("/actions/sources").then((r) => r.data),
  inbox: () => api.get("/actions/inbox").then((r) => r.data),
  my: () => api.get("/actions/my").then((r) => r.data),
  team: () => api.get("/actions/team").then((r) => r.data),
  analytics: (days = 30) => api.get("/actions/analytics", { params: { days } }).then((r) => r.data),
  list: (params) => api.get("/actions", { params }).then((r) => r.data),
  get: (id) => api.get(`/actions/${id}`).then((r) => r.data),
  create: (b) => api.post("/actions", b).then((r) => r.data),
  sync: () => api.post("/actions/sync", {}).then((r) => r.data),
  lifecycle: (id, action, body = {}) => api.post(`/actions/${id}/${action}`, body).then((r) => r.data),
};

// ── Finance360 + Forecasting (Wave 12) ──────────────────────────────
export const FinanceAPI = {
  overview: () => api.get("/finance/overview").then((r) => r.data),
  transactions: (params) => api.get("/finance/transactions", { params }).then((r) => r.data),
  outstanding: (params) => api.get("/finance/outstanding", { params }).then((r) => r.data),
  risk: () => api.get("/finance/risk").then((r) => r.data),
  collections: () => api.get("/finance/collections").then((r) => r.data),
  managersPnl: () => api.get("/finance/managers/pnl").then((r) => r.data),
  forecast: () => api.get("/forecast/overview").then((r) => r.data),
};

// ── Operations360 (Wave 14) ─────────────────────────────────────────
export const OpsAPI = {
  dashboard: () => api.get("/operations/dashboard").then((r) => r.data),
  bottlenecks: () => api.get("/operations/bottlenecks").then((r) => r.data),
  sla: () => api.get("/operations/sla").then((r) => r.data),
  risk: () => api.get("/operations/risk").then((r) => r.data),
};

// ── Executive Center (Wave 16) — admin only ─────────────────────────
export const ExecAPI = {
  dashboard: () => api.get("/executive/dashboard").then((r) => r.data),
  forecast: () => api.get("/executive/forecast").then((r) => r.data),
  bottlenecks: () => api.get("/executive/bottlenecks").then((r) => r.data),
  risks: () => api.get("/executive/risks").then((r) => r.data),
};

// ── Contract360 (Wave 15) ───────────────────────────────────────────
export const ContractsAPI = {
  overview: () => api.get("/contracts/overview").then((r) => r.data),
  list: (params) => api.get("/contracts", { params }).then((r) => r.data),
  get: (id) => api.get(`/contracts/${id}`).then((r) => r.data),
  templates: () => api.get("/contracts/templates").then((r) => r.data),
  lifecycle: (id, action, body = {}) => api.post(`/contracts/${id}/${action}`, body).then((r) => r.data),
};

// ── Deal Workspace + Deal360 (Wave 6 + 11) — ECO namespace ──────────
export const DealsAPI = {
  full360: (id) => api.get(`/eco/deals/${id}/360`).then((r) => r.data),
  get: (id) => api.get(`/eco/deals/${id}`).then((r) => r.data),
  stageProgress: (id) => api.get(`/eco/deals/${id}/stage-progress`).then((r) => r.data),
  transition: (id, b) => api.post(`/eco/deals/${id}/transition`, b).then((r) => r.data),
};

// ── Ringostat call-tracking admin (full integration control) ─────────
// Powers /app/ringostat — keys, project id, webhook, extension→manager
// mappings, calls history, per-manager stats, automation rules.
export const RingostatAPI = {
  health: () => api.get("/admin/ringostat/health").then((r) => r.data),
  settings: () => api.get("/admin/ringostat/settings").then((r) => r.data),
  updateSettings: (b) => api.patch("/admin/ringostat/settings", b).then((r) => r.data),
  resetSettings: (fields) => api.post("/admin/ringostat/settings/reset", fields ? { fields } : {}).then((r) => r.data),
  testConnection: (b) => api.post("/admin/ringostat/test-connection", b || {}).then((r) => r.data),
  testWebhook: () => api.post("/admin/ringostat/test-webhook").then((r) => r.data),
  webhookInfo: () => api.get("/admin/ringostat/webhook-info").then((r) => r.data),
  mappings: () => api.get("/admin/ringostat/mappings").then((r) => r.data),
  saveMapping: (b) => api.post("/admin/ringostat/mappings", b).then((r) => r.data),
  deleteMapping: (ext) => api.delete(`/admin/ringostat/mappings/${encodeURIComponent(ext)}`).then((r) => r.data),
  calls: (params) => api.get("/admin/ringostat/calls", { params }).then((r) => r.data),
  callDetails: (id) => api.get(`/admin/ringostat/calls/${id}`).then((r) => r.data),
  events: (limit = 50) => api.get("/admin/ringostat/events", { params: { limit } }).then((r) => r.data),
  statsOverview: (days = 7) => api.get("/admin/ringostat/stats/overview", { params: { days } }).then((r) => r.data),
  statsManagers: (days = 7) => api.get("/admin/ringostat/stats/managers", { params: { days } }).then((r) => r.data),
  simulate: (b) => api.post("/debug/ringostat/simulate", b).then((r) => r.data),
};

// ── Files & PDF Engine (Wave 5B-v2) ──────────────────────────────────
export const FilesAPI = {
  upload: (formData) => api.post("/storage/files", formData, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  list: (params) => api.get("/storage/files", { params }).then((r) => r.data),
  versions: (entity_type, entity_id, purpose) =>
    api.get("/storage/files/versions", { params: { entity_type, entity_id, ...(purpose ? { purpose } : {}) } }).then((r) => r.data),
  meta: (id) => api.get(`/storage/files/${id}`).then((r) => r.data),
  view: (id) => api.get(`/storage/files/${id}/view`, { responseType: "blob" }).then((r) => r.data),
  download: (id) => api.get(`/storage/files/${id}/download`, { responseType: "blob" }).then((r) => r.data),
  delete: (id) => api.delete(`/storage/files/${id}`).then((r) => r.data),
  generateContract: (id) => api.post(`/pdf/contract/${id}`).then((r) => r.data),
  generateAct: (id) => api.post(`/pdf/act/${id}`).then((r) => r.data),
  generatePickup: (id) => api.post(`/pdf/pickup/${id}`).then((r) => r.data),
  generateInvoice: (id) => api.post(`/pdf/invoice/${id}`).then((r) => r.data),
  pickupChecklist: (id) => api.get(`/waste/pickups/${id}/photo-checklist`).then((r) => r.data),
};

// Document lifecycle + version history (Wave 5B-v2)
export const DocumentsAPI = {
  lifecycles: () => api.get("/document-lifecycle/lifecycles").then((r) => r.data),
  get: (entityType, entityId) => api.get(`/document-lifecycle/${entityType}/${entityId}`).then((r) => r.data),
  transition: (entityType, entityId, toStatus, note) =>
    api.post(`/document-lifecycle/${entityType}/${entityId}/transition`, { to_status: toStatus, note }).then((r) => r.data),
};

// Helper: open a stored file (requires auth) by streaming through axios.
export async function openStoredFile(idOrUrl, opts = {}) {
  let id = idOrUrl;
  const m = /\/api\/(?:storage\/files|files)\/([^/]+)\/(?:view|download)/.exec(String(idOrUrl || ""));
  if (m) id = m[1];
  if (!id) return;
  try {
    const blob = await FilesAPI[opts.download ? "download" : "view"](id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    if (opts.download) { a.download = opts.filename || "file"; a.click(); }
    else { window.open(url, "_blank", "noopener,noreferrer"); }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (e) {
    // fallback to plain navigation if it's a public URL
    if (/^https?:\/\//.test(String(idOrUrl))) window.open(idOrUrl, "_blank");
  }
}

export const AuthAPI = {
  login: (email, password) => api.post("/auth/login", { email, password }).then((r) => r.data),
  verify2fa: (user_id, code) => api.post("/auth/2fa/verify", { user_id, code }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
};

// ── Universal Contract Flow (staff/admin) ─────────────────────────────
const cf = "/waste/cflow";
export const ContractFlowAPI = {
  meta: () => api.get(`${cf}/meta`).then((r) => r.data),
  seed: () => api.post(`${cf}/seed`).then((r) => r.data),
  getSettings: () => api.get(`${cf}/settings`).then((r) => r.data),
  saveSettings: (b) => api.put(`${cf}/settings`, b).then((r) => r.data),
  // Types
  types: (params) => api.get(`${cf}/types`, { params }).then((r) => r.data),
  createType: (b) => api.post(`${cf}/types`, b).then((r) => r.data),
  updateType: (id, b) => api.put(`${cf}/types/${id}`, b).then((r) => r.data),
  deleteType: (id) => api.delete(`${cf}/types/${id}`).then((r) => r.data),
  // Templates
  templates: (params) => api.get(`${cf}/templates`, { params }).then((r) => r.data),
  template: (id) => api.get(`${cf}/templates/${id}`).then((r) => r.data),
  createTemplate: (b) => api.post(`${cf}/templates`, b).then((r) => r.data),
  updateTemplate: (id, b) => api.put(`${cf}/templates/${id}`, b).then((r) => r.data),
  deleteTemplate: (id) => api.delete(`${cf}/templates/${id}`).then((r) => r.data),
  uploadTemplate: (formData, params) =>
    api.post(`${cf}/templates/upload`, formData, { params, headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  // Legal profile
  legalProfile: (customerId) => api.get(`${cf}/legal-profile/${customerId}`).then((r) => r.data),
  saveLegalProfile: (customerId, b) => api.put(`${cf}/legal-profile/${customerId}`, b).then((r) => r.data),
  // Contracts
  contracts: (params) => api.get(`${cf}/contracts`, { params }).then((r) => r.data),
  contract: (id) => api.get(`${cf}/contracts/${id}`).then((r) => r.data),
  createContract: (b) => api.post(`${cf}/contracts`, b).then((r) => r.data),
  patchContract: (id, b) => api.patch(`${cf}/contracts/${id}`, b).then((r) => r.data),
  regenerate: (id) => api.post(`${cf}/contracts/${id}/regenerate`, {}).then((r) => r.data),
  send: (id) => api.post(`${cf}/contracts/${id}/send`, {}).then((r) => r.data),
  issueInvoice: (id) => api.post(`${cf}/contracts/${id}/invoice`, {}).then((r) => r.data),
  confirmPayment: (id, b = {}) => api.post(`${cf}/contracts/${id}/confirm-payment`, b).then((r) => r.data),
  rejectPayment: (id, b = {}) => api.post(`${cf}/contracts/${id}/reject-payment`, b).then((r) => r.data),
  approve: (id) => api.post(`${cf}/contracts/${id}/approve`, {}).then((r) => r.data),
  pdfUrl: (id) => `${BASE}/api/waste/cflow/contracts/${id}/pdf`,
  fileUrl: (id) => `${BASE}/api/waste/cflow/files/${id}`,
};

// ── Admin auth/settings (Google Sign-In Client ID, etc.) ──────────────
export const SettingsAPI = {
  getAuth: () => api.get("/admin/settings/auth").then((r) => r.data),
  patchAuth: (body) => api.patch("/admin/settings/auth", body).then((r) => r.data),
};

// ── Footer (public-site footer content — admin-editable) ──────────────
export const FooterAPI = {
  // Public (anonymous) — rendered by EcoFooter
  getPublic: () => api.get("/public/footer").then((r) => r.data),
  subscribe: (email, source = "footer") =>
    api.post("/public/newsletter/subscribe", { email, source }).then((r) => r.data),
  // Admin
  getAdmin: () => api.get("/admin/settings/footer").then((r) => r.data),
  save: (footer) => api.put("/admin/settings/footer", { footer }).then((r) => r.data),
};

// ── Admin integrations (Resend / email, etc.) ─────────────────────────
export const IntegrationsAPI = {
  list: () => api.get("/admin/integrations").then((r) => r.data),
  patch: (provider, body) => api.patch(`/admin/integrations/${provider}`, body).then((r) => r.data),
  test: (provider, body) => api.post(`/admin/integrations/${provider}/test`, body || {}).then((r) => r.data),
};

// ── Account security — per-user 2FA (Google Authenticator / TOTP) ──
export const AccountAPI = {
  twofaStatus: () => api.get("/account/2fa/status").then((r) => r.data),
  twofaSetup: () => api.post("/account/2fa/setup").then((r) => r.data),
  twofaVerify: (code) => api.post("/account/2fa/verify", { code }).then((r) => r.data),
  twofaDisable: (code) => api.post("/account/2fa/disable", { code }).then((r) => r.data),
};

// ── Staff Center (admin-only) — manager control room ──
const sc = "/staff-center";
export const StaffAPI = {
  overview: () => api.get(`${sc}/overview`).then((r) => r.data),
  members: (params) => api.get(`${sc}/members`, { params }).then((r) => r.data),
  member: (id) => api.get(`${sc}/members/${id}`).then((r) => r.data),
  createMember: (b) => api.post(`${sc}/members`, b).then((r) => r.data),
  updateMember: (id, b) => api.patch(`${sc}/members/${id}`, b).then((r) => r.data),
  toggleActive: (id) => api.post(`${sc}/members/${id}/toggle-active`).then((r) => r.data),
  resetPassword: (id, newPassword) => api.post(`${sc}/members/${id}/reset-password`, { newPassword }).then((r) => r.data),
  deleteMember: (id) => api.delete(`${sc}/members/${id}`).then((r) => r.data),
  leads: (params) => api.get(`${sc}/leads`, { params }).then((r) => r.data),
  assign: (leadIds, managerId) => api.post(`${sc}/assign`, { leadIds, managerId }).then((r) => r.data),
};

// ── Manager Cabinet (self-contained CRM workspace, scoped to current user) ──
const mc = "/manager-cabinet";
export const ManagerAPI = {
  overview: () => api.get(`${mc}/overview`).then((r) => r.data),
  seed: () => api.post(`${mc}/seed`).then((r) => r.data),
  // Leads
  leads: (params) => api.get(`${mc}/leads`, { params }).then((r) => r.data),
  lead: (id) => api.get(`${mc}/leads/${id}`).then((r) => r.data),
  createLead: (b) => api.post(`${mc}/leads`, b).then((r) => r.data),
  updateLead: (id, b) => api.patch(`${mc}/leads/${id}`, b).then((r) => r.data),
  deleteLead: (id) => api.delete(`${mc}/leads/${id}`).then((r) => r.data),
  convertLead: (id, b = {}) => api.post(`${mc}/leads/${id}/convert`, b).then((r) => r.data),
  // Deals
  deals: (params) => api.get(`${mc}/deals`, { params }).then((r) => r.data),
  createDeal: (b) => api.post(`${mc}/deals`, b).then((r) => r.data),
  updateDeal: (id, b) => api.patch(`${mc}/deals/${id}`, b).then((r) => r.data),
  deleteDeal: (id) => api.delete(`${mc}/deals/${id}`).then((r) => r.data),
  // Tasks
  tasks: (params) => api.get(`${mc}/tasks`, { params }).then((r) => r.data),
  createTask: (b) => api.post(`${mc}/tasks`, b).then((r) => r.data),
  updateTask: (id, b) => api.patch(`${mc}/tasks/${id}`, b).then((r) => r.data),
  deleteTask: (id) => api.delete(`${mc}/tasks/${id}`).then((r) => r.data),
  // Calls
  calls: (params) => api.get(`${mc}/calls`, { params }).then((r) => r.data),
  logCall: (b) => api.post(`${mc}/calls`, b).then((r) => r.data),
};

// ── Admin (Wave 4A): pricing, licenses, waste codes management ────
export const AdminAPI = {
  // Pricing Engine v2
  pricingMeta: () => api.get("/waste/pricing/meta").then((r) => r.data),
  pricingDefaults: () => api.get("/waste/pricing/defaults").then((r) => r.data),
  updatePricingDefaults: (b) => api.put("/waste/pricing/defaults", b).then((r) => r.data),
  priceRules: (params) => api.get("/waste/price_rules", { params }).then((r) => r.data),
  createPriceRule: (b) => api.post("/waste/price_rules", b).then((r) => r.data),
  updatePriceRule: (id, b) => api.put(`/waste/price_rules/${id}`, b).then((r) => r.data),
  deletePriceRule: (id) => api.delete(`/waste/price_rules/${id}`).then((r) => r.data),
  seedPriceRules: () => api.post("/waste/price_rules/seed").then((r) => r.data),
  // Public price quote (re-used for "Test rule" preview)
  price: (b) => api.post("/waste/price", b).then((r) => r.data),
  // License Matrix
  licenses: (params) => api.get("/waste/licenses", { params }).then((r) => r.data),
  upsertLicense: (b) => api.post("/waste/licenses", b).then((r) => r.data),
  deleteLicense: (id) => api.delete(`/waste/licenses/${id}`).then((r) => r.data),
  seedLicenses: (force = false) => api.post(`/waste/licenses/seed?force=${force ? "true" : "false"}`).then((r) => r.data),
  recomputeAccepted: () => api.post("/waste/licenses/recompute").then((r) => r.data),
  licenseCheck: (code) => api.get("/waste/license/check", { params: { code } }).then((r) => r.data),
  // Waste Directory (codes management)
  categories: () => api.get("/waste/categories").then((r) => r.data),
  codes: (params) => api.get("/waste/codes", { params }).then((r) => r.data),
  codeByCode: (code) => api.get("/waste/codes/by-code", { params: { code } }).then((r) => r.data),
  createCode: (b) => api.post("/waste/codes", b).then((r) => r.data),
  updateCode: (code, patch) => api.put("/waste/codes/by-code", patch, { params: { code } }).then((r) => r.data),
  deleteCode: (code) => api.delete("/waste/codes/by-code", { params: { code } }).then((r) => r.data),
  importCodes: (items) => api.post("/waste/admin/import", items).then((r) => r.data),
  reseedCodes: (force = false) => api.post(`/waste/admin/seed?force=${force ? "true" : "false"}`).then((r) => r.data),
  adminStats: () => api.get("/waste/admin/stats").then((r) => r.data),
};

// ── Admin: Catalog Category management (Content Center → Каталог відходів) ──
export const WasteCategoryAdminAPI = {
  list: () => api.get("/waste/admin/categories").then((r) => r.data),
  icons: () => api.get("/waste/admin/icons").then((r) => r.data),
  allCodes: (params) =>
    api.get("/waste/codes", { params: { limit: 2000, ...(params || {}) } }).then((r) => r.data),
  create: (body) => api.post("/waste/admin/categories", body).then((r) => r.data),
  update: (key, patch) => api.put(`/waste/admin/categories/${key}`, patch).then((r) => r.data),
  remove: (key) => api.delete(`/waste/admin/categories/${key}`).then((r) => r.data),
  reorder: (order) => api.post("/waste/admin/categories/reorder", { order }).then((r) => r.data),
  uploadImage: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/admin/media/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
};

/** Build an absolute URL for a media/GridFS relative path (`/api/media/...`). */
export function mediaUrl(u) {
  if (!u) return "";
  if (/^https?:\/\//i.test(u)) return u;
  return `${BASE}${u.startsWith("/") ? "" : "/"}${u}`;
}

// ── Unified Admin Platform (Phase D1.5) — Global Search / Dashboard / Relations ──
export const UnifiedAPI = {
  search: (q, opts = {}) =>
    api.get("/admin/unified/search", { params: { q, per_type: opts.perType || 5, ...(opts.types ? { types: opts.types } : {}) } }).then((r) => r.data),
  dashboard: () => api.get("/admin/unified/dashboard").then((r) => r.data),
  relations: (type, q = "", limit = 20) =>
    api.get("/admin/unified/relations", { params: { type, q, limit } }).then((r) => r.data),
  relationTypes: () => api.get("/admin/unified/relation-types").then((r) => r.data),

  // ── Slice 2: universal subsystems ──
  activity: (params = {}) => api.get("/admin/unified/activity", { params }).then((r) => r.data),
  // Comments
  comments: (entity_type, entity_id) => api.get("/admin/unified/comments", { params: { entity_type, entity_id } }).then((r) => r.data),
  addComment: (body) => api.post("/admin/unified/comments", body).then((r) => r.data),
  editComment: (id, text) => api.patch(`/admin/unified/comments/${id}`, { text }).then((r) => r.data),
  deleteComment: (id) => api.delete(`/admin/unified/comments/${id}`).then((r) => r.data),
  // Attachments
  attachments: (entity_type, entity_id) => api.get("/admin/unified/attachments", { params: { entity_type, entity_id } }).then((r) => r.data),
  uploadAttachment: (entity_type, entity_id, formData) =>
    api.post("/admin/unified/attachments/upload", formData, { params: { entity_type, entity_id }, headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data),
  deleteAttachment: (id) => api.delete(`/admin/unified/attachments/${id}`).then((r) => r.data),
  // Audit
  audit: (entity_type, entity_id) => api.get("/admin/unified/audit", { params: { entity_type, entity_id } }).then((r) => r.data),
  // Lifecycle (Draft adapter)
  lifecycle: (entity_type, entity_id) => api.get("/admin/unified/lifecycle", { params: { entity_type, entity_id } }).then((r) => r.data),
  lifecycleMap: () => api.get("/admin/unified/lifecycle-map").then((r) => r.data),
  // Timeline
  timeline: (entity_type, entity_id) => api.get("/admin/unified/timeline", { params: { entity_type, entity_id } }).then((r) => r.data),
  // Notifications
  notifications: () => api.get("/admin/unified/notifications").then((r) => r.data),
  markNotificationsSeen: (signature) => api.post("/admin/unified/notifications/seen", { signature }).then((r) => r.data),
};

// ── Public contract e-sign client (NO auth token) ─────────────────────
// Окремий axios-інстанс без інтерсептора токена — публічна сторінка
// підписання договору за токеном (/contract/:token).
const publicApi = axios.create({ baseURL: `${BASE}/api` });

export const ContractSignAPI = {
  // Tries the waste e-sign system first; falls back to the contracts_v2 public
  // viewer (used by the IBAN invoice online e-sign flow). The v2 payload is
  // already normalized server-side (status/esign_status/signed_by/has_pdf).
  view: async (token) => {
    try {
      return await publicApi.get(`/public/waste-contract/${token}`).then((r) => r.data);
    } catch (e) {
      if (e?.response?.status === 404) {
        const r = await publicApi.get(`/contracts/view/${token}`);
        return { ...r.data, _v2: true };
      }
      throw e;
    }
  },
  sign: async (token, payload) => {
    try {
      return await publicApi.post(`/public/waste-contract/${token}/sign`, payload).then((r) => r.data);
    } catch (e) {
      if (e?.response?.status === 404) {
        const r = await publicApi.post(`/contracts/view/${token}/sign`, payload);
        const c = r.data?.contract || {};
        return {
          ...r.data,
          contract: { ...c, status: c.lifecycle, esign_status: c.lifecycle, signed_by: c.signed_full_name },
        };
      }
      throw e;
    }
  },
  pdfUrl: (token) => `${BASE}/api/public/waste-contract/${token}/pdf`,
};
