import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { LanguageProvider } from "@/i18n";
import { ClientAuthProvider } from "@/context/ClientAuthContext";
import PublicLayout from "@/components/layout/PublicLayout";
import SeoHead from "@/components/seo/SeoHead";
import SeoRuntimeInjector from "@/components/seo/SeoRuntimeInjector";
import RouteFallback from "@/components/RouteFallback";

// Home is the primary landing — keep it eager for the fastest first paint (LCP).
import Home from "@/pages/public/Home";

// Everything else is code-split (React.lazy): a public visitor no longer
// downloads the entire admin / CRM / portal / client bundles up front. Each
// page's JS chunk is fetched on demand, dramatically shrinking the initial load.
const PortalLayout = lazy(() => import("@/components/layout/PortalLayout"));

// Client (B2B customer) self-serve area
const ClientLogin = lazy(() => import("@/pages/client/ClientLogin"));
const ClientResetPassword = lazy(() => import("@/pages/client/ClientResetPassword"));
const ClientLayout = lazy(() => import("@/pages/client/ClientLayout"));
const ClientOverview = lazy(() => import("@/pages/client/ClientOverview"));
const ClientRequests = lazy(() => import("@/pages/client/ClientRequests"));
const ClientContracts = lazy(() => import("@/pages/client/ClientContracts"));
const ClientInvoices = lazy(() => import("@/pages/client/ClientInvoices"));
const ClientNotifications = lazy(() => import("@/pages/client/ClientNotifications"));
const ClientRequestDetail = lazy(() => import("@/pages/client/ClientRequestDetail"));
const ClientDocuments = lazy(() => import("@/pages/client/ClientDocuments"));
const ClientProfile = lazy(() => import("@/pages/client/ClientProfile"));
const ClientContractFlow = lazy(() => import("@/pages/client/ClientContractFlow"));

// Universal Contract Flow (admin)
const ContractsFlowPage = lazy(() => import("@/pages/contractflow/ContractsFlowPage"));
const ContractTypesPage = lazy(() => import("@/pages/contractflow/ContractTypesPage"));
const TemplateLibraryPage = lazy(() => import("@/pages/contractflow/TemplateLibraryPage"));

// Public (secondary pages)
const Contacts = lazy(() => import("@/pages/public/Contacts"));
const Calculator = lazy(() => import("@/pages/public/Calculator"));
const WasteDirectory = lazy(() => import("@/pages/public/WasteDirectory"));
const WasteCategory = lazy(() => import("@/pages/public/WasteCategory"));
const WasteCodePage = lazy(() => import("@/pages/public/WasteCodePage"));
const BlogIndex = lazy(() => import("@/pages/public/BlogIndex"));
const BlogArticle = lazy(() => import("@/pages/public/BlogArticle"));
const LegalPage = lazy(() => import("@/pages/public/LegalPage"));
const WasteContractSign = lazy(() => import("@/pages/public/WasteContractSign"));

// Staff auth + portal (admin / manager)
const AdminLogin = lazy(() => import("@/pages/auth/AdminLogin"));
const Dashboard = lazy(() => import("@/pages/portal/Dashboard"));
const Companies = lazy(() => import("@/pages/portal/Companies"));
const Company360 = lazy(() => import("@/pages/portal/Company360"));
const Customer360 = lazy(() => import("@/pages/portal/Customer360"));
const CustomersList = lazy(() => import("@/pages/portal/CustomersList"));
const Requests = lazy(() => import("@/pages/portal/Requests"));
const Operations = lazy(() => import("@/pages/portal/Operations"));
const ContractExecution = lazy(() => import("@/pages/portal/ContractExecution"));
const Pricing = lazy(() => import("@/pages/portal/Pricing"));
const LicenseMatrix = lazy(() => import("@/pages/portal/Licenses"));
const Directory = lazy(() => import("@/pages/portal/Directory"));
const ObjectDetail = lazy(() => import("@/pages/portal/ObjectDetail"));
const CrmHub = lazy(() => import("@/pages/portal/CrmHub"));
const CrmTasks = lazy(() => import("@/pages/portal/CrmTasks"));
const CrmCalls = lazy(() => import("@/pages/portal/CrmCalls"));
const CrmInvoices = lazy(() => import("@/pages/portal/CrmInvoices"));
const CrmDocuments = lazy(() => import("@/pages/portal/CrmDocuments"));
const CrmNotifications = lazy(() => import("@/pages/portal/CrmNotifications"));
const MessageCenter = lazy(() => import("@/pages/portal/MessageCenter"));
const ActionCenter = lazy(() => import("@/pages/portal/ActionCenter"));
const Finance360 = lazy(() => import("@/pages/portal/Finance360"));
const Operations360 = lazy(() => import("@/pages/portal/Operations360"));
const ExecutiveCenter = lazy(() => import("@/pages/portal/ExecutiveCenter"));
const Contract360 = lazy(() => import("@/pages/portal/Contract360"));
const Deal360 = lazy(() => import("@/pages/portal/Deal360"));
const FilesManager = lazy(() => import("@/pages/portal/FilesManager"));
const Inquiries = lazy(() => import("@/pages/portal/Inquiries"));
const Settings = lazy(() => import("@/pages/portal/Settings"));
const Cabinet = lazy(() => import("@/pages/manager/Cabinet"));
const ManagerLeads = lazy(() => import("@/pages/manager/Leads"));
const ManagerDeals = lazy(() => import("@/pages/manager/Deals"));
const ManagerTasks = lazy(() => import("@/pages/manager/Tasks"));
const ManagerCalls = lazy(() => import("@/pages/manager/Calls"));
const Security = lazy(() => import("@/pages/manager/Security"));
const StaffCenter = lazy(() => import("@/pages/admin/StaffCenter"));
const Assignment = lazy(() => import("@/pages/admin/Assignment"));
const WasteCodesAdmin = lazy(() => import("@/pages/admin/WasteCodesAdmin"));
const RingostatAdmin = lazy(() => import("@/pages/admin/RingostatAdmin"));
const CallIntelligence = lazy(() => import("@/pages/admin/CallIntelligence"));
const AdminFooterPage = lazy(() => import("@/pages/admin/AdminFooterPage"));
const AdminContactsPage = lazy(() => import("@/pages/admin/AdminContactsPage"));
const AdminInfoPage = lazy(() => import("@/pages/admin/AdminInfoPage"));
const AdminBlogPage = lazy(() => import("@/pages/admin/AdminBlogPage"));
const WasteLeads = lazy(() => import("@/pages/portal/WasteLeads"));
const AdminSeoSettingsPage = lazy(() => import("@/pages/admin/AdminSeoSettingsPage"));
const AdminSeoCenter = lazy(() => import("@/pages/admin/seo/AdminSeoCenter"));
const SeoGlobalSettings = lazy(() => import("@/pages/admin/seo/SeoGlobalSettings"));
const SeoCompanyProfile = lazy(() => import("@/pages/admin/seo/SeoCompanyProfile"));
const SeoAnalytics = lazy(() => import("@/pages/admin/seo/SeoAnalytics"));
const SeoPages = lazy(() => import("@/pages/admin/seo/SeoPages"));
const SeoSitemap = lazy(() => import("@/pages/admin/seo/SeoSitemap"));
const SeoRobots = lazy(() => import("@/pages/admin/seo/SeoRobots"));
const SeoPrerender = lazy(() => import("@/pages/admin/seo/SeoPrerender"));
// Phase D1 — Content Platform (block-based CMS)
const AdminContentCenter = lazy(() => import("@/pages/admin/content/AdminContentCenter"));
const ContentPagesList = lazy(() => import("@/pages/admin/content/ContentPagesList"));
const ContentPageEditor = lazy(() => import("@/pages/admin/content/ContentPageEditor"));
const MediaLibrary = lazy(() => import("@/pages/admin/content/MediaLibrary"));
const FAQManager = lazy(() => import("@/pages/admin/content/FAQManager"));
const WasteCatalogManager = lazy(() => import("@/pages/admin/content/WasteCatalogManager"));
// Phase D1.5 — Unified Admin Platform (hub dashboard)
const UnifiedDashboard = lazy(() => import("@/pages/admin/unified/UnifiedDashboard"));
const ActivityPage = lazy(() => import("@/pages/admin/unified/ActivityPage"));

// Role-aware landing for /app: managers go straight to their personal cabinet,
// admins (and any other staff) see the operations dashboard.
function AppHome() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user && String(user.role || "").toLowerCase() === "manager") {
    return <Navigate to="/app/cabinet" replace />;
  }
  return <Dashboard />;
}

export default function App() {
  return (
    <LanguageProvider>
    <AuthProvider>
      <ClientAuthProvider>
        <BrowserRouter>
          <SeoHead />
          <SeoRuntimeInjector />
          <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route element={<PublicLayout />}>
              <Route path="/" element={<Home />} />
              <Route path="/calculator" element={<Calculator />} />
              <Route path="/contacts" element={<Contacts />} />
              <Route path="/waste" element={<WasteDirectory />} />
              <Route path="/waste/category/:key" element={<WasteCategory />} />
              <Route path="/waste-code/:slug" element={<WasteCodePage />} />
              <Route path="/blog" element={<BlogIndex />} />
              <Route path="/blog/:slug" element={<BlogArticle />} />
              <Route path="/terms" element={<LegalPage docKey="terms" />} />
              <Route path="/privacy" element={<LegalPage docKey="privacy" />} />
              <Route path="/cookies" element={<LegalPage docKey="cookies" />} />
            </Route>
            <Route path="/contract/:token" element={<WasteContractSign />} />
            {/* Unified staff login — the light /login screen is retired; everything
                routes through the dark /admin CRM console (admin + manager). */}
            <Route path="/login" element={<Navigate to="/admin" replace />} />
            <Route path="/admin" element={<AdminLogin />} />
            <Route path="/admin/login" element={<AdminLogin />} />

            {/* ── Client (B2B customer) self-serve area ── */}
            <Route path="/client/login" element={<ClientLogin />} />
            <Route path="/client/reset-password" element={<ClientResetPassword />} />
            <Route path="/cabinet/reset-password" element={<ClientResetPassword />} />
            <Route path="/client" element={<ClientLayout />}>
              <Route index element={<ClientOverview />} />
              <Route path="requests" element={<ClientRequests />} />
              <Route path="contracts" element={<ClientContracts />} />
              <Route path="invoices" element={<ClientInvoices />} />
              <Route path="messages" element={<ClientNotifications />} />
              <Route path="requests/:id" element={<ClientRequestDetail />} />
              <Route path="documents" element={<ClientDocuments />} />
              <Route path="contract-flow" element={<ClientContractFlow />} />
              <Route path="profile" element={<ClientProfile />} />
            </Route>

            <Route path="/app" element={<PortalLayout />}>
            <Route index element={<AppHome />} />
            {/* Phase D1.5 — Unified Admin hub (additive; legacy dashboard stays at /app) */}
            <Route path="hub" element={<UnifiedDashboard />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="cabinet" element={<Cabinet />} />
            <Route path="cabinet/leads" element={<ManagerLeads />} />
            <Route path="cabinet/deals" element={<ManagerDeals />} />
            <Route path="cabinet/tasks" element={<ManagerTasks />} />
            <Route path="cabinet/calls" element={<ManagerCalls />} />
            <Route path="cabinet/security" element={<Security />} />
            <Route path="staff" element={<StaffCenter />} />
            <Route path="staff/assignment" element={<Assignment />} />
            <Route path="waste-codes" element={<WasteCodesAdmin />} />
            <Route path="companies" element={<Companies />} />
            <Route path="companies/:id" element={<Company360 />} />
            <Route path="customers" element={<CustomersList />} />
            <Route path="customers/:id" element={<Customer360 />} />
            <Route path="leads" element={<WasteLeads />} />
            <Route path="objects/:id" element={<ObjectDetail />} />
            <Route path="requests" element={<Requests />} />
            <Route path="operations" element={<Operations />} />
            <Route path="operations/contracts/:contractId" element={<ContractExecution />} />
            <Route path="contract-flow" element={<ContractsFlowPage />} />
            <Route path="contract-flow/types" element={<ContractTypesPage />} />
            <Route path="contract-flow/templates" element={<TemplateLibraryPage />} />
            <Route path="inquiries" element={<Inquiries />} />
            <Route path="settings" element={<Settings />} />
            <Route path="settings/footer" element={<AdminFooterPage />} />
            <Route path="settings/contacts" element={<AdminContactsPage />} />
            <Route path="settings/seo" element={<AdminSeoSettingsPage />} />
            {/* SEO Center — Phase B2 (admin-managed SEO / E-E-A-T / analytics / pages / sitemap / robots) */}
            <Route path="seo" element={<AdminSeoCenter />}>
              <Route index element={<Navigate to="settings" replace />} />
              <Route path="settings"  element={<SeoGlobalSettings />} />
              <Route path="company"   element={<SeoCompanyProfile />} />
              <Route path="analytics" element={<SeoAnalytics />} />
              <Route path="pages"     element={<SeoPages />} />
              <Route path="sitemap"   element={<SeoSitemap />} />
              <Route path="robots"    element={<SeoRobots />} />
              <Route path="prerender" element={<SeoPrerender />} />
            </Route>
            {/* Content Center — Phase D1 (block-based CMS + Media Library + FAQ Engine) */}
            <Route path="content" element={<AdminContentCenter />}>
              <Route index element={<Navigate to="pages" replace />} />
              <Route path="pages" element={<ContentPagesList />} />
              <Route path="catalog" element={<WasteCatalogManager />} />
              <Route path="media" element={<MediaLibrary />} />
              <Route path="faq"   element={<FAQManager />} />
            </Route>
            <Route path="content/pages/:pageId" element={<ContentPageEditor />} />
            <Route path="info" element={<AdminInfoPage />} />
            <Route path="info/:tab" element={<AdminInfoPage />} />
            <Route path="blog" element={<AdminBlogPage />} />
            <Route path="pricing" element={<Pricing />} />
            <Route path="licenses" element={<LicenseMatrix />} />
            <Route path="directory" element={<Directory />} />
            <Route path="crm" element={<CrmHub />} />
            <Route path="crm/tasks" element={<CrmTasks />} />
            <Route path="crm/calls" element={<CrmCalls />} />
            <Route path="crm/invoices" element={<CrmInvoices />} />
            <Route path="crm/documents" element={<CrmDocuments />} />
            <Route path="crm/notifications" element={<CrmNotifications />} />
            <Route path="crm/messages" element={<MessageCenter />} />
            <Route path="crm/actions" element={<ActionCenter />} />
            <Route path="finance" element={<Finance360 />} />
            <Route path="operations360" element={<Operations360 />} />
            <Route path="executive" element={<ExecutiveCenter />} />
            <Route path="contracts" element={<Contract360 />} />
            <Route path="cabinet/deals/:dealId" element={<Deal360 />} />
            <Route path="deals/:dealId" element={<Deal360 />} />
            <Route path="crm/files" element={<FilesManager />} />
            <Route path="ringostat" element={<RingostatAdmin />} />
            <Route path="crm/ringostat" element={<RingostatAdmin />} />
            <Route path="call-intelligence" element={<CallIntelligence />} />
          </Route>
          {/* Catch-all: unknown paths → public home (avoids blank white screens) */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
        <Toaster position="top-right" richColors />
      </BrowserRouter>
      </ClientAuthProvider>
    </AuthProvider>
    </LanguageProvider>
  );
}
