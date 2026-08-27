import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import axios from 'axios';
import { API_URL } from '../App';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { useLang, getLocale, CUSTOMER_LANGUAGES } from '../i18n';
import { tSeed } from '../utils/seedI18n';
import ShipmentTrackingMap from '../components/shipping/ShipmentTrackingMap';
import JourneyPanel from '../components/shipping/JourneyPanel';
import PaymentMethodPicker from '../components/payments/PaymentMethodPicker';
import CustomerOrders from '../components/cabinet/CustomerOrders';
import { HelpTooltip } from '../components/ui/HelpTooltip';
import { useShipmentNotifications } from '../hooks/useShipmentNotifications';
import {
  House,
  FileText,
  Car,
  Wallet,
  ClockCounterClockwise,
  User,
  CaretRight,
  Check,
  Clock,
  Truck,
  Warning,
  Bell,
  Heart,
  SignOut,
  ArrowLeft,
  MapPin,
  Anchor,
  Package,
  Phone,
  Envelope,
  PencilSimple,
  ArrowRight,
  CircleNotch,
  ShareNetwork,
  Scales,
  Compass,
  List as MenuIcon,
  X as CloseIcon,
  ShieldCheck,
  EnvelopeSimple,
  Copy,
  Key,
  DownloadSimple,
} from '@phosphor-icons/react';
import { useCustomerAuth } from './public/CustomerAuth';
import { useCabinetTheme } from '../context/CabinetThemeContext';
import CabinetLangPicker from '../components/cabinet/CabinetLangPicker';

/**
 * Customer Cabinet - BIBI Cars Customer Journey UI
 * 
 * Головний фокус: де моя машина + що мені робити + що вже зроблено
 * НЕ CRM dashboard, а ПРОЦЕС покупки авто
 */

// Simplified Sidebar Navigation
const NAV_ITEMS = [
  { path: '', labelKey: 'cab_nav_home', icon: House },
  { path: 'favorites', labelKey: 'cab_nav_favorites', icon: Heart },
  { path: 'compare', labelKey: 'cab_nav_comparison', icon: Scales },
  { path: 'shared', labelKey: 'cab_nav_shared', icon: ShareNetwork },
  { path: 'orders', labelKey: 'cab_nav_my_orders', icon: Car },
  { path: 'roadmap', labelKey: 'cab_nav_roadmap', icon: Compass },
  { path: 'watchlist', labelKey: 'cab_nav_vin_tracking', icon: Bell },
  { path: 'invoices', labelKey: 'cab_nav_invoices', icon: Wallet },
  { path: 'shipping', labelKey: 'cab_nav_delivery', icon: Truck },
  { path: 'contracts', labelKey: 'cab_nav_contracts', icon: FileText },
  { path: 'carfax', labelKey: 'cab_nav_carfax', icon: FileText },
  { path: 'notifications', labelKey: 'cab_nav_notifications', icon: Bell },
  { path: 'profile', labelKey: 'cab_nav_profile', icon: User },
];

// Process Steps
const PROCESS_STEPS = [
  { code: 'selection', labelKey: 'cab_step_selection', icon: Car },
  { code: 'contract', labelKey: 'cab_step_contract', icon: FileText },
  { code: 'payment', labelKey: 'cab_step_payment', icon: Wallet },
  { code: 'shipping', labelKey: 'cab_step_delivery', icon: Truck },
  { code: 'received', labelKey: 'cab_step_obtaining', icon: Check },
];

// Status to Step mapping
const STATUS_TO_STEP = {
  'new': 0,
  'negotiation': 0,
  'contract_pending': 1,
  'contract_signed': 1,
  'deposit_pending': 2,
  'deposit_paid': 2,
  'payment_pending': 2,
  'payment_complete': 2,
  'auction_won': 2,
  'in_transit': 3,
  'shipping': 3,
  'at_port': 3,
  'customs': 3,
  'delivered': 4,
  'completed': 4,
};

// ── Premium 5-step process tracker (dark-theme native) ──────────────────
// Brand amber #FEAE00 → emerald #10B981 progress, used inside the
// "Process Progress" card on the cabinet home. Node centres sit at
// 10/30/50/70/90% of the row, so the connector spans left-[10%]→right-[10%].
//
// Every node state (completed / current / upcoming) is explained in plain
// language: a small legend under the row + an on-hover tooltip on each step,
// so the customer always understands what each colour/state means.
const PROC_STATE = {
  done: {
    label: { en: 'Completed', bg: 'Завършен', uk: 'Завершено' },
    desc: {
      en: 'This step is complete.',
      bg: 'Този етап е завършен.',
      uk: 'Цей етап завершено.',
    },
  },
  current: {
    label: { en: 'In progress', bg: 'В процес', uk: 'В роботі' },
    desc: {
      en: 'We are working on this step right now.',
      bg: 'В момента работим по този етап.',
      uk: 'Зараз ми працюємо над цим етапом.',
    },
  },
  upcoming: {
    label: { en: 'Upcoming', bg: 'Очаква', uk: 'Очікує' },
    desc: {
      en: 'This step is still ahead — not started yet.',
      bg: 'Този етап предстои — все още не е започнат.',
      uk: 'Цей етап ще попереду — поки не розпочато.',
    },
  },
};
const procPick = (m, lang) => (m && (m[lang] || m.en)) || '';

const ProcessTracker = ({ currentStep, t, lang = 'en' }) => {
  const total = PROCESS_STEPS.length;
  const fillPct = total > 1 ? (Math.max(0, Math.min(currentStep, total - 1)) / (total - 1)) * 80 : 0;
  return (
    <div className="relative pt-1 pb-1" data-testid="process-tracker">
      {/* track + animated fill (sit behind the nodes) */}
      <div className="absolute top-[22px] left-[10%] right-[10%] h-[3px] rounded-full bg-[#222227]" />
      <motion.div
        className="absolute top-[22px] left-[10%] h-[3px] rounded-full bg-gradient-to-r from-[#FEAE00] to-[#10B981]"
        initial={{ width: 0 }}
        animate={{ width: `${fillPct}%` }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
      <div className="relative grid grid-cols-5 gap-1">
        {PROCESS_STEPS.map((step, idx) => {
          const Icon = step.icon;
          const done = idx < currentStep;
          const current = idx === currentStep;
          const stateKey = done ? 'done' : current ? 'current' : 'upcoming';
          const stepName = t(step.labelKey);
          const tip = `${stepName} — ${procPick(PROC_STATE[stateKey].desc, lang)}`;
          let node = 'bg-[#222227] border border-[#34343A] text-[#71717A]';
          if (done) node = 'bg-emerald-500 border border-emerald-400 text-white shadow-[0_4px_14px_rgba(16,185,129,0.35)]';
          else if (current) node = 'bg-[#17171A] border-2 border-[#FEAE00] text-[#FEAE00] shadow-[0_0_0_4px_rgba(254,174,0,0.12)]';
          return (
            <HelpTooltip key={step.code} text={tip}>
              <div className="flex flex-col items-center gap-2 cursor-help" data-testid={`process-step-${step.code}`}>
                <div className={`relative z-10 w-11 h-11 rounded-2xl flex items-center justify-center transition-colors ${node}`}>
                  {done ? <Check size={20} weight="bold" /> : <Icon size={20} weight="duotone" />}
                  {current && (
                    <span className="absolute inset-0 rounded-2xl border-2 border-[#FEAE00] animate-ping opacity-40" />
                  )}
                </div>
                <span className={`text-[10px] sm:text-[11px] text-center leading-tight font-medium ${
                  current ? 'text-[#FEAE00]' : done ? 'text-zinc-100' : 'text-zinc-400'
                }`}>
                  {stepName}
                </span>
              </div>
            </HelpTooltip>
          );
        })}
      </div>

      {/* Plain-language legend — so the colours are never a mystery */}
      <div
        className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2"
        data-testid="process-legend"
      >
        {[
          { key: 'done', dot: 'bg-emerald-500' },
          { key: 'current', dot: 'bg-[#FEAE00]' },
          { key: 'upcoming', dot: 'bg-[#34343A] border border-[#52525B]' },
        ].map((it) => (
          <HelpTooltip key={it.key} text={procPick(PROC_STATE[it.key].desc, lang)}>
            <span className="flex items-center gap-1.5 cursor-help" data-testid={`process-legend-${it.key}`}>
              <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${it.dot}`} />
              <span className="text-[11px] text-zinc-400">{procPick(PROC_STATE[it.key].label, lang)}</span>
            </span>
          </HelpTooltip>
        ))}
      </div>
    </div>
  );
};

// Layout Component
export const CabinetLayout = () => {
  return <CabinetLayoutInner />;
};

const CabinetLayoutInner = () => {
  const { t, lang, changeLang } = useLang();
  const { customerId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, customer: authCustomer } = useCustomerAuth();
  const { theme } = useCabinetTheme();
  const basePath = `/cabinet/${customerId}`;

  // Header-level customer state (fetched from cabinet endpoint, stays in sync)
  const [customer, setCustomer] = useState(authCustomer || null);

  // ── Phase B3.1+ — mobile drawer state ─────────────────────────────────
  // The sidebar used to stack ABOVE the page content on `<lg` screens, so
  // a mobile user opened the cabinet and only saw the nav — they had to
  // scroll past the entire 14-item menu to reach the actual page. We now
  // hide the sidebar by default on mobile and surface a hamburger that
  // slides it in as an overlay drawer.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  // Close the drawer whenever the route changes (selecting an item).
  useEffect(() => { setMobileNavOpen(false); }, [location.pathname]);
  // Lock body scroll while the drawer is open so the page underneath
  // doesn't bounce around when the user swipes.
  useEffect(() => {
    if (!mobileNavOpen) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [mobileNavOpen]);

  const refreshCustomer = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/profile`);
      if (res.data?.customer) {
        setCustomer((prev) => ({ ...(prev || {}), ...res.data.customer }));
      }
    } catch (err) {
      // silent
    }
  }, [customerId]);

  useEffect(() => {
    refreshCustomer();
  }, [refreshCustomer]);

  // Re-fetch when route changes (cheap, ensures header stays in sync after profile edits)
  useEffect(() => {
    refreshCustomer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const isActive = (path) => {
    const fullPath = path ? `${basePath}/${path}` : basePath;
    return location.pathname === fullPath || (path && location.pathname.startsWith(`${basePath}/${path}`));
  };

  const handleLogout = async () => {
    await logout();
    navigate('/cabinet/login');
    toast.success(t('adm_you_have_logged_out'));
  };

  const avatarUrl = customer?.picture || customer?.avatar;
  const initial = (customer?.firstName?.[0] || customer?.name?.[0] || 'B').toUpperCase();

  return (
    <div className="cabinet-scope min-h-screen bg-[#F8F8F8]" data-theme={theme} data-testid="cabinet-root">
      {/* ── Mobile top bar (only `<lg`) ─────────────────────────────────
       *  Hamburger + page-aware label + avatar. Keeps the cabinet usable
       *  on phones — the legacy stack-everything-above-content layout
       *  buried the actual page below 14 sidebar items. */}
      <header
        className="lg:hidden sticky top-0 z-30 flex items-center justify-between gap-3 px-4 h-14 bg-[#0F0F0E] border-b border-[#27272A]"
        data-testid="cabinet-mobile-topbar"
      >
        <button
          type="button"
          onClick={() => setMobileNavOpen(true)}
          className="w-10 h-10 -ml-2 rounded-lg flex items-center justify-center text-zinc-100 hover:bg-white/5 active:bg-white/10 transition-colors"
          aria-label={t('cab_open_menu') || 'Open menu'}
          data-testid="cabinet-mobile-menu-open"
        >
          <MenuIcon size={22} weight="regular" />
        </button>
        <div className="flex-1 min-w-0 text-center">
          <div className="text-[11px] uppercase tracking-[0.14em] text-zinc-500 leading-none">
            BIBI Cars
          </div>
          <div className="text-[13px] font-semibold text-zinc-100 truncate leading-tight mt-0.5">
            {customer?.firstName || customer?.name || t('adm3_2e8ee1588e')}
          </div>
        </div>
        <div className="w-9 h-9 rounded-lg overflow-hidden bg-[#18181B] text-white flex items-center justify-center font-bold text-sm shrink-0">
          {avatarUrl
            ? <img src={avatarUrl} alt="" className="w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display='none'; }} />
            : initial}
        </div>
      </header>

      {/* Cabinet body — single column on mobile, 2-col grid on lg+ */}
      <div className="max-w-7xl mx-auto px-4 py-4 lg:py-6 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4 lg:gap-6">

        {/* ── Mobile drawer overlay backdrop ───────────────────────────── */}
        {/* Phase B3.2.1 — z-index lifted above Leaflet's panes (400) and
           controls (1000). Without this the shipment map punches through
           the drawer because Leaflet sets its own stacking context. */}
        {mobileNavOpen && (
          <button
            type="button"
            aria-label="Close menu"
            className="lg:hidden fixed inset-0 z-[1050] bg-black/60 backdrop-blur-[2px] animate-[bibi-fade-in_0.18s_ease-out_both]"
            onClick={() => setMobileNavOpen(false)}
            data-testid="cabinet-mobile-drawer-backdrop"
          />
        )}

        {/* Sidebar — desktop in-flow, mobile slide-in drawer */}
        <aside
          className={`
            bg-white border border-[#E4E4E7] rounded-2xl p-4
            lg:h-fit lg:sticky lg:top-6 lg:translate-x-0 lg:relative lg:z-auto lg:shadow-none
            fixed inset-y-0 left-0 z-[1100] w-[86%] max-w-[320px] lg:w-auto lg:max-w-none
            rounded-none lg:rounded-2xl
            shadow-[0_24px_48px_rgba(0,0,0,0.5)] lg:shadow-none
            overflow-y-auto
            transition-transform duration-250 ease-out
            ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full'}
            lg:transform-none
          `}
          data-testid="cabinet-sidebar"
        >
          {/* Mobile-only close button inside the drawer */}
          <div className="lg:hidden flex justify-end -mt-1 -mr-1 mb-2">
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-zinc-400 hover:bg-white/5"
              aria-label="Close menu"
              data-testid="cabinet-mobile-menu-close"
            >
              <CloseIcon size={20} />
            </button>
          </div>
          <div className="mb-4 pb-3 border-b border-[#E4E4E7]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl overflow-hidden bg-[#18181B] text-white flex items-center justify-center font-bold text-sm shrink-0">
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt="avatar"
                    className="w-full h-full object-cover"
                    onError={(e) => { e.currentTarget.style.display = 'none'; }}
                  />
                ) : (
                  initial
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-[#18181B] text-sm truncate">
                  {customer?.firstName || customer?.name || t('adm3_2e8ee1588e')}
                </h2>
                <p className="text-xs text-[#71717A] truncate">{t('adm_bibi_cars_2')}</p>
              </div>
            </div>

            {/* Language switcher — Phase B3.1: dropdown matches the public
             *  header (ENG ▾ style); cabinet auto-inherits the language
             *  the user picked on the site (shared LanguageProvider).
             *  Theme is locked to dark — no toggle here anymore. */}
            <div className="mt-3 flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-[0.12em] text-[#71717A] font-semibold">
                {t('cab_language') || 'Language'}
              </span>
              <CabinetLangPicker data-testid="cabinet-lang-switcher" />
            </div>
          </div>
          
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path ? `${basePath}/${item.path}` : basePath}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-sm ${
                    active
                      ? 'bg-[#18181B] text-white'
                      : 'text-[#71717A] hover:bg-[#F4F4F5] hover:text-[#18181B]'
                  }`}
                  data-testid={`nav-${item.path || 'dashboard'}`}
                >
                  <Icon size={18} weight={active ? 'fill' : 'regular'} />
                  <span className="font-medium">{t(item.labelKey)}</span>
                </Link>
              );
            })}
          </nav>

          {/* Back & Logout */}
          <div className="mt-4 pt-3 border-t border-[#E4E4E7] space-y-1">
            <Link
              to="/"
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-[#71717A] hover:bg-[#F4F4F5] text-sm"
              data-testid="back-to-site"
            >
              <ArrowLeft size={18} />
              <span>{t('adm_to_website')}</span>
            </Link>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-red-500 hover:bg-red-50 text-sm"
              data-testid="logout-btn"
            >
              <SignOut size={18} />
              <span>{t('adm_log_out')}</span>
            </button>
          </div>
        </aside>

        {/* Main Content — expose setCustomer/refreshCustomer to children via Outlet context */}
        <main className="min-w-0">
          <Outlet context={{ customer, setCustomer, refreshCustomer }} />
        </main>
      </div>

      {/* Keyframe used by the drawer backdrop (defined here so we keep the
          cabinet's styles self-contained — no global stylesheet pollution). */}
      <style>{`
        @keyframes bibi-fade-in { from { opacity: 0 } to { opacity: 1 } }
      `}</style>
    </div>
  );
};

// ============ NEW DASHBOARD - CUSTOMER JOURNEY UI ============
export const CabinetDashboard = () => {
  const { t, lang } = useLang();
  const { customerId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, [customerId]);

  const loadDashboard = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/dashboard`);
      setData(res.data);
    } catch (error) {
      toast.error(t('adm_loading_error'));
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingState />;
  if (!data) return <ErrorState />;

  const { customer, activeDeals, latestTimeline, nextAction, manager } = data;
  
  // Get primary active deal (most recent or in-progress)
  const primaryDeal = activeDeals?.[0];
  const currentStep = primaryDeal ? (STATUS_TO_STEP[primaryDeal.status] || 0) : 0;
  const progressPercent = primaryDeal ? Math.round(((currentStep + 1) / PROCESS_STEPS.length) * 100) : 0;

  // Determine CTA based on status
  const getCTA = () => {
    if (!primaryDeal) return null;
    
    const status = primaryDeal.status;
    
    if (status === 'contract_pending') {
      return { label: t('adm_sign_contract'), action: 'contract', urgent: true };
    }
    if (status === 'deposit_pending' || status === 'payment_pending') {
      return { label: t('adm_pay'), action: 'payment', urgent: true };
    }
    if (['in_transit', 'shipping', 'at_port'].includes(status)) {
      return { label: t('adm_view_delivery'), action: 'shipping', urgent: false };
    }
    return null;
  };

  const cta = getCTA();
  const statusLabels = {
    'new': t('adm3_9db2488492'),
    'negotiation': t('adm3_c366cc7eed'),
    'contract_pending': t('adm3_fc2ebbddad'),
    'contract_signed': t('adm3_df82fecabe'),
    'deposit_pending': t('adm3_c0d1b23405'),
    'deposit_paid': t('adm3_38a653a066'),
    'payment_pending': t('adm3_68c17f3945'),
    'payment_complete': t('adm3_6d8c085082'),
    'auction_won': t('adm3_949a1ca031'),
    'in_transit': t('adm3_2ddf5e05c5'),
    'shipping': t('adm3_b973ee8690'),
    'at_port': t('adm3_54e8e23710'),
    'customs': t('adm3_e7a53a452b'),
    'delivered': t('adm3_f5cce37a63'),
    'completed': t('adm3_0083ce05cc'),
  };

  return (
    <div className="space-y-4" data-testid="cabinet-dashboard">
      
      {/* 1. HEADER - Compact Greeting + Status + CTA */}
      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white border border-[#E4E4E7] rounded-2xl p-5"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-[#18181B]">
              {t('r9_hello')}{customer.firstName || customer.name || t('adm3_313ec9c7c2')}!
            </h1>
            {primaryDeal && (
              <p className="text-sm text-[#71717A] mt-1">
                {t('adm_status_3')} <span className={`font-semibold ${
                  cta?.urgent ? 'text-amber-600' : 'text-[#18181B]'
                }`}>{statusLabels[primaryDeal.status] || primaryDeal.status}</span>
              </p>
            )}
          </div>
          
          {cta && (
            <Link
              to={`/cabinet/${customerId}/${cta.action === 'contract' ? 'contracts' : cta.action === 'payment' ? 'invoices' : 'shipping'}`}
              className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                cta.urgent 
                  ? 'bg-[#18181B] text-white hover:bg-[#27272A]' 
                  : 'bg-[#F4F4F5] text-[#18181B] hover:bg-[#E4E4E7]'
              }`}
              data-testid="main-cta"
            >
              {cta.label}
            </Link>
          )}
        </div>

        {/* Progress Bar */}
        {primaryDeal && (
          <div className="mt-4">
            <div className="h-2 bg-[#E4E4E7] rounded-full overflow-hidden">
              <motion.div 
                className="h-full bg-[#18181B]" 
                initial={{ width: 0 }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
            <p className="text-xs text-[#71717A] mt-2">
              {t('r9_stage')} {currentStep + 1} {t('r9_from')} {PROCESS_STEPS.length} {t('r9_em_dash')} {t(PROCESS_STEPS[currentStep]?.labelKey || '')}
            </p>
          </div>
        )}
      </motion.div>

      {/* 2. ACTION ALERT - If urgent action needed */}
      {nextAction && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className={`rounded-2xl p-5 ${
            nextAction.urgency === 'high' 
              ? 'bg-amber-50 border border-amber-200' 
              : 'bg-emerald-50 border border-emerald-200'
          }`}
          data-testid="action-alert"
        >
          <div className="flex items-start gap-4">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              nextAction.urgency === 'high' ? 'bg-amber-500' : 'bg-emerald-500'
            }`}>
              <Warning size={20} weight="fill" className="text-white" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-[#18181B]">{tSeed(nextAction.title, lang)}</h3>
              <p className="text-sm text-[#71717A] mt-1">{tSeed(nextAction.description, lang)}</p>
            </div>
            {nextAction.dealId && (
              <Link 
                to={`/cabinet/${customerId}/orders/${nextAction.dealId}`}
                className="bg-[#18181B] text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-[#27272A]"
              >
                {t('adm_view_2')}
              </Link>
            )}
          </div>
        </motion.div>
      )}

      {/* 3. VEHICLE BLOCK - The main thing customer wants to see */}
      {primaryDeal && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden"
          data-testid="vehicle-block"
        >
          <div className="p-5">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-[#F4F4F5] rounded-xl flex items-center justify-center shrink-0">
                <Car size={24} className="text-[#18181B]" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="font-bold text-lg text-[#18181B]">
                  {primaryDeal.title || primaryDeal.vehicleTitle || t('adm3_6bb3f7cdae')}
                </h2>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-[#71717A]">
                  <span>VIN: {primaryDeal.vin || '—'}</span>
                  {primaryDeal.lot && <span>{t('adm3_f7e5135666')} {primaryDeal.lot}</span>}
                </div>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-[#18181B]">${(primaryDeal.clientPrice || 0).toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Shipping Status - If applicable */}
          {['in_transit', 'shipping', 'at_port', 'customs', 'delivered'].includes(primaryDeal.status) && (
            <div className="border-t border-[#E4E4E7] p-5 bg-[#FAFAFA]">
              <div className="flex items-center gap-3 mb-3">
                <MapPin size={18} className="text-[#71717A]" />
                <span className="text-sm font-medium text-[#18181B]">{t('adm_current_status')}</span>
                <span className="text-sm text-emerald-600 font-semibold">
                  {primaryDeal.shippingStatus || statusLabels[primaryDeal.status]}
                </span>
              </div>
              
              {primaryDeal.eta && (
                <div className="flex items-center gap-3">
                  <Clock size={18} className="text-[#71717A]" />
                  <span className="text-sm text-[#71717A]">{t('adm_eta')}</span>
                  <span className="text-sm font-semibold text-[#18181B]">
                    {primaryDeal.etaDays ? `${primaryDeal.etaDays}${t('r9_days')}` : new Date(primaryDeal.eta).toLocaleDateString(getLocale())}
                  </span>
                </div>
              )}

              {primaryDeal.containerNumber && (
                <div className="flex items-center gap-3 mt-2">
                  <Package size={18} className="text-[#71717A]" />
                  <span className="text-sm text-[#71717A]">{t('adm_container_4')}</span>
                  <span className="text-sm font-mono text-[#18181B]">{primaryDeal.containerNumber}</span>
                </div>
              )}
            </div>
          )}

          {/* View Details Link */}
          <Link 
            to={`/cabinet/${customerId}/orders/${primaryDeal.id}`}
            className="block border-t border-[#E4E4E7] p-3 text-center text-sm font-medium text-[#18181B] hover:bg-[#F4F4F5] transition-colors"
          >
            {t('adm_order_details')} <ArrowRight size={14} className="inline ml-1" />
          </Link>
        </motion.div>
      )}

      {/* 4. PROCESS PROGRESS — premium 5-step tracker + recent events (only with an active deal) */}
      {primaryDeal && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-[#17171A] border border-[#27272A] rounded-2xl p-5 sm:p-6"
          data-testid="timeline-block"
        >
          <div className="mb-6">
            <h2 className="font-semibold text-zinc-100">{t('adm_process_progress')}</h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              {t('r9_stage')} {currentStep + 1} {t('r9_from')} {PROCESS_STEPS.length} {t('r9_em_dash')} {t(PROCESS_STEPS[currentStep]?.labelKey || '')}
            </p>
          </div>

          <ProcessTracker currentStep={currentStep} t={t} lang={lang} />

          {latestTimeline && latestTimeline.length > 0 && (
            <div className="mt-7 pt-5 border-t border-[#27272A]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-zinc-300">{t('adm_history')}</h3>
                <Link to={`/cabinet/${customerId}/timeline`} className="text-xs text-zinc-500 hover:text-zinc-200 transition-colors">
                  {t('adm_all_events')}
                </Link>
              </div>
              <div className="space-y-0">
                {latestTimeline.slice(0, 5).map((event, idx) => {
                  const last = idx === Math.min(latestTimeline.length, 5) - 1;
                  return (
                    <div key={event.id} className="flex gap-3" data-testid={`timeline-event-${idx}`}>
                      <div className="flex flex-col items-center">
                        <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-1.5 ${
                          idx === 0 ? 'bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.18)]' : 'bg-[#3A3A40]'
                        }`} />
                        {!last && <div className="w-[2px] flex-1 min-h-[34px] bg-[#27272A]" />}
                      </div>
                      <div className={last ? 'pb-0' : 'pb-5'}>
                        <p className={`text-sm font-medium ${idx === 0 ? 'text-zinc-100' : 'text-zinc-400'}`}>
                          {tSeed(event.title || formatEventType(event.type), lang)}
                        </p>
                        <p className="text-xs text-zinc-500 mt-0.5 tabular-nums">
                          {event.timestamp || event.createdAt
                            ? new Date(event.timestamp || event.createdAt).toLocaleDateString(lang === 'en' ? 'en-US' : getLocale())
                            : ''}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* 5. MANAGER CONTACT - Compact */}
      {manager && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-[#18181B] text-white rounded-2xl p-5"
          data-testid="manager-block"
        >
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 bg-white/10 rounded-xl flex items-center justify-center shrink-0">
              <User size={22} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white/60 text-xs">{t('adm_your_manager')}</p>
              <h3 className="font-semibold">{manager.name}</h3>
            </div>
            <div className="flex gap-2">
              {manager.phone && (
                <a href={`tel:${manager.phone}`} className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center hover:bg-white/20">
                  <Phone size={18} />
                </a>
              )}
              {manager.email && (
                <a href={`mailto:${manager.email}`} className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center hover:bg-white/20">
                  <Envelope size={18} />
                </a>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* No active orders — premium designed empty state with journey preview */}
      {!primaryDeal && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-[#17171A] border border-[#27272A] rounded-2xl overflow-hidden"
          data-testid="cabinet-empty-state"
        >
          <div className="relative p-6 sm:p-8">
            <div className="absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-[#FEAE00] via-[#FEAE00]/50 to-transparent" />

            <div className="flex flex-col items-center text-center max-w-lg mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-[#FEAE00]/15 border border-[#FEAE00]/30 flex items-center justify-center mb-4">
                <Compass size={32} weight="duotone" className="text-[#FEAE00]" />
              </div>
              <h2 className="text-lg font-bold text-zinc-100">{t('adm_no_active_orders_yet')}</h2>
              <p className="text-sm text-zinc-400 mt-2">
                {t('adm_browse_our_catalog_and_choose_your_dream_car')}
              </p>
            </div>

            {/* Journey preview — show the 5 steps the customer will go through */}
            <div className="mt-8">
              <p className="text-[11px] uppercase tracking-[0.16em] text-zinc-500 font-semibold mb-5 text-center">
                {t('adm_process_progress')}
              </p>
              <ProcessTracker currentStep={0} t={t} lang={lang} />
            </div>

            <div className="mt-8 flex justify-center">
              <Link
                to="/vehicles"
                className="inline-flex items-center gap-2 bg-[#FEAE00] text-[#18181B] px-6 py-3 rounded-xl font-semibold hover:bg-[#FFBF2D] transition-colors"
                data-testid="empty-browse-cta"
              >
                <Car size={18} weight="bold" />
                {t('adm_view_car')}
              </Link>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
};

// Helper function
const formatEventType = (type) => {
  const labels = {
    'lead_created': t('adm3_ed6602e2d0'),
    'deal_created': t('adm3_d91bd5227b'),
    'deposit_created': t('adm3_47c22c3f3f'),
    'deposit_confirmed': t('adm3_aedbdb6d44'),
    'contract_sent': t('adm3_851dfb0115'),
    'contract_signed': t('adm3_df82fecabe'),
    'payment_received': t('adm3_f8109de19d'),
    'auction_won': t('adm3_949a1ca031'),
    'shipping_started': t('adm3_cfb41abe6a'),
    'arrived_at_port': t('adm3_9536f28936'),
    'customs_cleared': t('adm3_850228c963'),
    'delivered': t('adm3_f5cce37a63'),
  };
  return labels[type] || type;
};

// ============ ORDERS PAGE ============
export const CabinetOrders = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  return (
    <div className="space-y-4" data-testid="cabinet-orders">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{t('cab_nav_my_orders')}</h1>
        <p className="text-sm text-[#71717A] mt-1">{t('adm_service_execution_status_for_paid_invoices_updates')}</p>
      </div>
      <CustomerOrders customerId={customerId} />
    </div>
  );
};

// ============ ORDER DETAILS PAGE ============
export const CabinetOrderDetails = () => {
  const { t, lang } = useLang();
  const { customerId, dealId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadOrderDetails();
  }, [customerId, dealId]);

  const loadOrderDetails = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/orders/${dealId}`);
      setData(res.data);
    } catch (error) {
      toast.error(t('adm_loading_error'));
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingState />;
  if (!data) return <ErrorState />;

  const { deal, processState, whatsNext, deposits, depositSummary, timeline } = data;
  const currentStep = STATUS_TO_STEP[deal.status] || 0;
  const progressPercent = Math.round(((currentStep + 1) / PROCESS_STEPS.length) * 100);

  return (
    <div className="space-y-4" data-testid="cabinet-order-details">
      {/* Back + Header */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <Link to={`/cabinet/${customerId}/orders`} className="text-sm text-[#71717A] hover:text-[#18181B] mb-3 inline-flex items-center gap-1">
          <ArrowLeft size={14} /> {t('adm_back')}
        </Link>
        <h1 className="text-xl font-bold text-[#18181B] mt-2">
          {deal.title || deal.vehicleTitle || `${t('r9_order')}`}
        </h1>
        <p className="text-sm text-[#71717A]">VIN: {deal.vin || '—'}</p>

        {/* Progress */}
        <div className="mt-4">
          <div className="h-2 bg-[#E4E4E7] rounded-full overflow-hidden">
            <div className="h-full bg-[#18181B] transition-all" style={{ width: `${progressPercent}%` }} />
          </div>
          <div className="flex justify-between mt-3">
            {PROCESS_STEPS.map((step, idx) => (
              <div key={step.code} className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs ${
                  idx < currentStep ? 'bg-emerald-500 text-white' :
                  idx === currentStep ? 'bg-[#18181B] text-white' :
                  'bg-[#E4E4E7] text-[#71717A]'
                }`}>
                  {idx < currentStep ? <Check size={14} /> : idx + 1}
                </div>
                <span className="text-[10px] mt-1 text-[#71717A]">{t(step.labelKey)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* What's Next */}
      {whatsNext && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-5">
          <h3 className="font-semibold text-[#18181B]">{tSeed(whatsNext.title, lang)}</h3>
          <p className="text-sm text-[#71717A] mt-1">{tSeed(whatsNext.description, lang)}</p>
        </div>
      )}

      {/* Deal Info + Deposits */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <h2 className="font-semibold text-[#18181B] mb-3">{t('adm_details_2')}</h2>
          <div className="space-y-2 text-sm">
            <InfoRow label={t('adm_status_2')} value={deal.status} />
            <InfoRow label={t('adm_price')} value={`$${(deal.clientPrice || 0).toLocaleString()}`} />
            <InfoRow label={t('adm_date_2')} value={new Date(deal.createdAt).toLocaleDateString(lang === 'en' ? 'en-US' : getLocale())} />
          </div>
        </div>

        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <h2 className="font-semibold text-[#18181B] mb-3">{t('adm_payments')}</h2>
          <div className="space-y-2 text-sm">
            <InfoRow label={t('adm_deposits_3')} value={depositSummary?.total || 0} />
            <InfoRow label={t('adm_amount')} value={`$${(depositSummary?.totalAmount || 0).toLocaleString()}`} />
            <InfoRow label={t('adm_confirmed')} value={`$${(depositSummary?.confirmedAmount || 0).toLocaleString()}`} />
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h2 className="font-semibold text-[#18181B] mb-4">{t('adm_history')}</h2>
        {timeline?.length > 0 ? (
          <div className="space-y-3">
            {timeline.map((event, idx) => (
              <div key={event.id} className="flex gap-3">
                <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${idx === 0 ? 'bg-emerald-500' : 'bg-[#E4E4E7]'}`} />
                <div>
                  <p className="text-sm font-medium text-[#18181B]">{tSeed(event.title || formatEventType(event.type), lang)}</p>
                  <p className="text-xs text-[#A1A1AA]">{new Date(event.createdAt).toLocaleDateString(lang === 'en' ? 'en-US' : getLocale())}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[#71717A] text-center py-4">{t('adm_no_events')}</p>
        )}
      </div>
    </div>
  );
};

// ============ SIMPLE PAGES (Keep existing logic, simplified UI) ============

export const CabinetRequests = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/requests`);
        setData(res.data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-requests">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{t('adm_my_requests')}</h1>
      </div>
      {data?.data?.length > 0 ? (
        <div className="space-y-3">
          {data.data.map((lead) => (
            <div key={lead.id} className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-[#18181B]">{lead.firstName} {lead.lastName}</h3>
                  <p className="text-sm text-[#71717A]">VIN: {lead.vin || '—'}</p>
                </div>
                <span className="text-xs px-2 py-1 rounded-full bg-[#F4F4F5]">{lead.status}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_a0527f7252')} />
      )}
    </div>
  );
};

export const CabinetDeposits = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/deposits`);
        setData(res.data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-deposits">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{t('adm_deposits_2')}</h1>
        {data?.summary && (
          <div className="flex gap-4 mt-3">
            <div className="bg-[#F4F4F5] rounded-xl px-4 py-2">
              <p className="text-xs text-[#71717A]">{t('adm_total_3')}</p>
              <p className="font-bold">${data.summary.totalAmount?.toLocaleString() || 0}</p>
            </div>
            <div className="bg-emerald-50 rounded-xl px-4 py-2">
              <p className="text-xs text-emerald-600">{t('adm_confirmed')}</p>
              <p className="font-bold text-emerald-600">{data.summary.confirmed || 0}</p>
            </div>
          </div>
        )}
      </div>
      {data?.data?.length > 0 ? (
        <div className="space-y-3">
          {data.data.map((dep) => (
            <div key={dep.id} className="bg-white border border-[#E4E4E7] rounded-2xl p-4 flex justify-between items-center">
              <div>
                <p className="font-bold text-[#18181B]">${(dep.amount || 0).toLocaleString()}</p>
                <p className="text-xs text-[#71717A]">{new Date(dep.createdAt).toLocaleDateString(getLocale())}</p>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full ${
                dep.status === 'confirmed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
              }`}>{dep.status}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_69d4d1c50f')} />
      )}
    </div>
  );
};

export const CabinetTimeline = () => {
  const { t, lang } = useLang();
  const { customerId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/timeline`);
        setData(res.data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-timeline">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{t('adm_event_history')}</h1>
      </div>
      {data?.data?.length > 0 ? (
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5 space-y-4">
          {data.data.map((event, idx) => (
            <div key={event.id} className="flex gap-3">
              <div className={`w-3 h-3 rounded-full mt-1.5 shrink-0 ${idx === 0 ? 'bg-emerald-500' : 'bg-[#E4E4E7]'}`} />
              <div>
                <p className="font-medium text-[#18181B]">{tSeed(event.title || formatEventType(event.type), lang)}</p>
                {event.description && <p className="text-sm text-[#71717A]">{tSeed(event.description, lang)}</p>}
                <p className="text-xs text-[#A1A1AA] mt-1">{new Date(event.createdAt).toLocaleString(lang === 'en' ? 'en-US' : getLocale())}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_f090fb0fe9')} />
      )}
    </div>
  );
};

export const CabinetNotifications = () => {
  const { t, lang } = useLang();
  const { customerId } = useParams();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/notifications?limit=50`);
        setNotifications(res.data?.data || res.data || []);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-notifications">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B] flex items-center gap-2">
          <Bell size={24} /> {t('notifications')}
        </h1>
      </div>
      {notifications.length > 0 ? (
        <div className="space-y-3">
          {notifications.map((n) => (
            <div key={n.id} className={`bg-white border rounded-2xl p-4 ${n.isRead ? 'border-[#E4E4E7]' : 'border-blue-300 bg-blue-50'}`}>
              <h3 className="font-medium text-[#18181B]">{tSeed(n.title, lang)}</h3>
              <p className="text-sm text-[#71717A] mt-1">{tSeed(n.message, lang)}</p>
              <p className="text-xs text-[#A1A1AA] mt-2">{new Date(n.createdAt).toLocaleString(lang === 'en' ? 'en-US' : getLocale())}</p>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_41b3ccdbd7')} />
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────
// Two-Factor Authentication (customer TOTP) — enable wizard, backup codes,
// disable, regenerate. Mirrors the backend /api/customer-auth/2fa/* endpoints.
// ─────────────────────────────────────────────────────────────────────────
const TwoFactorSection = ({ t, getAuthHeaders, hasPassword }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  // setup wizard
  const [setupOpen, setSetupOpen] = useState(false);
  const [setupStep, setSetupStep] = useState('password'); // password | scan | backup
  const [pwd, setPwd] = useState('');
  const [qr, setQr] = useState(null);
  const [manualKey, setManualKey] = useState('');
  const [code, setCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);

  // disable / regenerate
  const [disableOpen, setDisableOpen] = useState(false);
  const [regenOpen, setRegenOpen] = useState(false);
  const [opPwd, setOpPwd] = useState('');
  const [opCode, setOpCode] = useState('');
  const [copied, setCopied] = useState(false);

  // email-OTP method (alternative to authenticator app)
  const [emailEnableOpen, setEmailEnableOpen] = useState(false);
  const [emailDisableOpen, setEmailDisableOpen] = useState(false);
  const [emailPwd, setEmailPwd] = useState('');

  const loadStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/api/customer-auth/2fa/status`, { headers: getAuthHeaders() });
      setStatus(res.data);
    } catch (e) {
      setStatus({ enabled: false, available: true });
    } finally {
      setLoading(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const resetSetup = () => {
    setSetupOpen(false); setSetupStep('password'); setPwd(''); setQr(null);
    setManualKey(''); setCode(''); setBackupCodes([]); setErr('');
  };

  const errMsg = (e) => e?.response?.data?.detail || t('cab_2fa_err_generic');

  // Step 1 → request QR + manual key (re-auth with password when set)
  const beginSetup = async () => {
    setBusy(true); setErr('');
    try {
      const res = await axios.post(
        `${API_URL}/api/customer-auth/2fa/setup`,
        hasPassword ? { password: pwd } : {},
        { headers: getAuthHeaders() }
      );
      setQr(res.data.qrCode);
      setManualKey(res.data.manualKey);
      setSetupStep('scan');
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  // Step 2 → verify code, enable, receive backup codes
  const verifyEnable = async () => {
    setBusy(true); setErr('');
    try {
      const res = await axios.post(
        `${API_URL}/api/customer-auth/2fa/verify`,
        { code: code.trim() },
        { headers: getAuthHeaders() }
      );
      setBackupCodes(res.data.backupCodes || []);
      setSetupStep('backup');
      toast.success(t('cab_2fa_success_enabled'));
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const finishSetup = async () => { resetSetup(); await loadStatus(); };

  const doDisable = async () => {
    setBusy(true); setErr('');
    try {
      await axios.post(
        `${API_URL}/api/customer-auth/2fa/disable`,
        { password: opPwd, code: opCode.trim() },
        { headers: getAuthHeaders() }
      );
      toast.success(t('cab_2fa_success_disabled'));
      setDisableOpen(false); setOpPwd(''); setOpCode('');
      await loadStatus();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const doRegenerate = async () => {
    setBusy(true); setErr('');
    try {
      const res = await axios.post(
        `${API_URL}/api/customer-auth/2fa/backup/regenerate`,
        { password: opPwd, code: opCode.trim() },
        { headers: getAuthHeaders() }
      );
      setBackupCodes(res.data.backupCodes || []);
      toast.success(t('cab_2fa_success_regen'));
      setRegenOpen(false); setOpPwd(''); setOpCode('');
      // surface fresh codes via the setup "backup" view
      setSetupOpen(true); setSetupStep('backup');
      await loadStatus();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const copyCodes = () => {
    try {
      navigator.clipboard.writeText(backupCodes.join('\n'));
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const downloadCodes = () => {
    const blob = new Blob([`BIBI Cars — backup codes\n\n${backupCodes.join('\n')}\n`], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'bibi-cars-backup-codes.txt';
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  };

  const doEmailEnable = async () => {
    setBusy(true); setErr('');
    try {
      await axios.post(
        `${API_URL}/api/customer-auth/2fa/email/enable`,
        { password: emailPwd },
        { headers: getAuthHeaders() }
      );
      toast.success(t('cab_2fa_email_success_on'));
      setEmailEnableOpen(false); setEmailPwd('');
      await loadStatus();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const doEmailDisable = async () => {
    setBusy(true); setErr('');
    try {
      await axios.post(
        `${API_URL}/api/customer-auth/2fa/email/disable`,
        { password: emailPwd },
        { headers: getAuthHeaders() }
      );
      toast.success(t('cab_2fa_email_success_off'));
      setEmailDisableOpen(false); setEmailPwd('');
      await loadStatus();
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  const enabled = !!status?.enabled;
  const emailEnabled = !!status?.emailEnabled;
  const remaining = status?.backupCodesRemaining ?? 0;

  const inputCls = 'w-full px-3 py-2 border border-[#E4E4E7] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#18181B]/10';
  const overlay = 'fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4';
  const sheet = 'bg-white rounded-2xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto';

  return (
    <div className="border-t border-[#F4F4F5] pt-1" data-testid="cabinet-2fa-section">
      {/* Method A — Authenticator app (TOTP) */}
      <div className="flex items-start justify-between py-2">
      <div className="flex gap-3">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${enabled ? 'bg-emerald-50 text-emerald-600' : 'bg-[#F4F4F5] text-[#71717A]'}`}>
          <ShieldCheck size={18} weight={enabled ? 'fill' : 'regular'} />
        </div>
        <div>
          <p className="font-medium text-[#18181B] flex items-center gap-2">
            {t('cab_2fa_title')}
            <span
              className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-[#F4F4F5] text-[#71717A]'}`}
              data-testid="2fa-status-badge"
            >
              {enabled ? t('cab_2fa_status_on') : t('cab_2fa_status_off')}
            </span>
          </p>
          <p className="text-xs text-[#71717A] mt-1 max-w-md">{t('cab_2fa_desc')}</p>
          {enabled && status?.enabledAt && (
            <p className="text-xs text-[#A1A1AA] mt-1" data-testid="2fa-enabled-at">
              {t('cab_2fa_enabled_at')}: {new Date(status.enabledAt).toLocaleDateString()}
            </p>
          )}
          {enabled && (
            <p className="text-xs text-[#A1A1AA] mt-1" data-testid="2fa-backup-remaining">
              {remaining} {t('cab_2fa_backup_remaining')}
              {' · '}
              <button onClick={() => { setErr(''); setOpPwd(''); setOpCode(''); setRegenOpen(true); }} className="text-[#18181B] hover:underline" data-testid="2fa-regenerate-btn">
                {t('cab_2fa_regenerate')}
              </button>
            </p>
          )}
        </div>
      </div>
      <div className="shrink-0">
        {loading ? (
          <CircleNotch size={18} className="animate-spin text-[#A1A1AA]" />
        ) : enabled ? (
          <button onClick={() => { setErr(''); setOpPwd(''); setOpCode(''); setDisableOpen(true); }} className="text-xs text-red-600 hover:underline" data-testid="2fa-disable-btn">
            {t('cab_2fa_disable')}
          </button>
        ) : (
          <button
            onClick={() => { setErr(''); setPwd(''); setSetupStep(hasPassword ? 'password' : 'scan'); setSetupOpen(true); if (!hasPassword) beginSetup(); }}
            disabled={emailEnabled}
            title={emailEnabled ? t('cab_2fa_switch_hint') : ''}
            className="text-xs font-medium text-white bg-[#18181B] px-3 py-1.5 rounded-lg hover:bg-black disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="2fa-enable-btn"
          >
            {t('cab_2fa_enable')}
          </button>
        )}
      </div>
      </div>

      {/* Method B — Email login code */}
      <div className="flex items-start justify-between py-2 border-t border-[#F4F4F5]/70 mt-1 pt-3" data-testid="cabinet-2fa-email-section">
        <div className="flex gap-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${emailEnabled ? 'bg-emerald-50 text-emerald-600' : 'bg-[#F4F4F5] text-[#71717A]'}`}>
            <EnvelopeSimple size={18} weight={emailEnabled ? 'fill' : 'regular'} />
          </div>
          <div>
            <p className="font-medium text-[#18181B] flex items-center gap-2">
              {t('cab_2fa_email_title')}
              <span
                className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${emailEnabled ? 'bg-emerald-100 text-emerald-700' : 'bg-[#F4F4F5] text-[#71717A]'}`}
                data-testid="2fa-email-status-badge"
              >
                {emailEnabled ? t('cab_2fa_status_on') : t('cab_2fa_status_off')}
              </span>
            </p>
            <p className="text-xs text-[#71717A] mt-1 max-w-md">{t('cab_2fa_email_desc')}</p>
            {emailEnabled && status?.email && (
              <p className="text-xs text-[#A1A1AA] mt-1" data-testid="2fa-email-target">
                {t('cab_2fa_email_sent_to')}: {status.email}
              </p>
            )}
          </div>
        </div>
        <div className="shrink-0">
          {loading ? null : emailEnabled ? (
            <button onClick={() => { setErr(''); setEmailPwd(''); setEmailDisableOpen(true); }} className="text-xs text-red-600 hover:underline" data-testid="2fa-email-disable-btn">
              {t('cab_2fa_disable')}
            </button>
          ) : (
            <button
              onClick={() => { setErr(''); setEmailPwd(''); setEmailEnableOpen(true); }}
              disabled={enabled}
              title={enabled ? t('cab_2fa_switch_hint') : ''}
              className="text-xs font-medium text-white bg-[#18181B] px-3 py-1.5 rounded-lg hover:bg-black disabled:opacity-40 disabled:cursor-not-allowed"
              data-testid="2fa-email-enable-btn"
            >
              {t('cab_2fa_enable')}
            </button>
          )}
        </div>
      </div>

      {/* Email enable modal */}
      {emailEnableOpen && (
        <div className={overlay} onClick={() => setEmailEnableOpen(false)}>
          <div className={sheet} onClick={(e) => e.stopPropagation()} data-testid="2fa-email-enable-modal">
            <h3 className="text-lg font-semibold text-[#18181B] mb-1">{t('cab_2fa_email_enable_title')}</h3>
            <p className="text-sm text-[#71717A] mt-1 mb-3">{t('cab_2fa_email_enable_desc')}</p>
            <div className="space-y-3">
              {hasPassword && (
                <input type="password" value={emailPwd} onChange={(e) => setEmailPwd(e.target.value)} placeholder={t('cab_2fa_password_label')} className={inputCls} data-testid="2fa-email-enable-password" autoFocus />
              )}
              {err && <p className="text-xs text-red-600" data-testid="2fa-error">{err}</p>}
              <div className="flex gap-2 justify-end pt-2">
                <button onClick={() => setEmailEnableOpen(false)} className="px-4 py-2 text-sm text-[#71717A] hover:text-[#18181B]">{t('cab_2fa_cancel')}</button>
                <button onClick={doEmailEnable} disabled={busy || (hasPassword && !emailPwd)} className="px-4 py-2 text-sm font-medium text-white bg-[#18181B] rounded-lg disabled:opacity-50 flex items-center gap-2" data-testid="2fa-email-enable-confirm">
                  {busy && <CircleNotch size={16} className="animate-spin" />}{t('cab_2fa_enable')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Email disable modal */}
      {emailDisableOpen && (
        <div className={overlay} onClick={() => setEmailDisableOpen(false)}>
          <div className={sheet} onClick={(e) => e.stopPropagation()} data-testid="2fa-email-disable-modal">
            <h3 className="text-lg font-semibold text-[#18181B] mb-1">{t('cab_2fa_email_disable_title')}</h3>
            <p className="text-sm text-[#71717A] mt-1 mb-3">{t('cab_2fa_email_disable_desc')}</p>
            <div className="space-y-3">
              {hasPassword && (
                <input type="password" value={emailPwd} onChange={(e) => setEmailPwd(e.target.value)} placeholder={t('cab_2fa_password_label')} className={inputCls} data-testid="2fa-email-disable-password" autoFocus />
              )}
              {err && <p className="text-xs text-red-600" data-testid="2fa-error">{err}</p>}
              <div className="flex gap-2 justify-end pt-2">
                <button onClick={() => setEmailDisableOpen(false)} className="px-4 py-2 text-sm text-[#71717A] hover:text-[#18181B]">{t('cab_2fa_cancel')}</button>
                <button onClick={doEmailDisable} disabled={busy || (hasPassword && !emailPwd)} className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg disabled:opacity-50 flex items-center gap-2" data-testid="2fa-email-disable-confirm">
                  {busy && <CircleNotch size={16} className="animate-spin" />}{t('cab_2fa_disable')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Setup wizard */}
      {setupOpen && (
        <div className={overlay} onClick={resetSetup}>
          <div className={sheet} onClick={(e) => e.stopPropagation()} data-testid="2fa-setup-modal">
            <h3 className="text-lg font-semibold text-[#18181B] mb-1">{t('cab_2fa_setup_title')}</h3>

            {setupStep === 'password' && (
              <div className="space-y-3 mt-3">
                <p className="text-sm text-[#71717A]">{t('cab_2fa_step_password')}</p>
                <input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder={t('cab_2fa_password_label')} className={inputCls} data-testid="2fa-setup-password" autoFocus />
                {err && <p className="text-xs text-red-600" data-testid="2fa-error">{err}</p>}
                <div className="flex gap-2 justify-end pt-2">
                  <button onClick={resetSetup} className="px-4 py-2 text-sm text-[#71717A] hover:text-[#18181B]">{t('cab_2fa_cancel')}</button>
                  <button onClick={beginSetup} disabled={busy || !pwd} className="px-4 py-2 text-sm font-medium text-white bg-[#18181B] rounded-lg disabled:opacity-50 flex items-center gap-2" data-testid="2fa-setup-continue">
                    {busy && <CircleNotch size={16} className="animate-spin" />}{t('cab_2fa_continue')}
                  </button>
                </div>
              </div>
            )}

            {setupStep === 'scan' && (
              <div className="space-y-3 mt-3">
                <p className="text-sm text-[#71717A]">{t('cab_2fa_step_scan')}</p>
                <div className="flex justify-center">
                  {qr ? <img src={qr} alt="2FA QR" className="w-44 h-44 rounded-xl border border-[#E4E4E7]" data-testid="2fa-qr" /> : <CircleNotch size={32} className="animate-spin text-[#A1A1AA] my-10" />}
                </div>
                <div>
                  <p className="text-xs text-[#71717A] mb-1">{t('cab_2fa_manual_key')}</p>
                  <div className="flex items-center gap-2 bg-[#F4F4F5] rounded-lg px-3 py-2">
                    <Key size={14} className="text-[#71717A]" />
                    <code className="text-xs font-mono text-[#18181B] break-all flex-1" data-testid="2fa-manual-key">{manualKey}</code>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-[#71717A] block mb-1">{t('cab_2fa_enter_code')}</label>
                  <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" placeholder="000000" className={`${inputCls} tracking-[0.4em] text-center font-mono`} data-testid="2fa-setup-code" autoFocus />
                </div>
                {err && <p className="text-xs text-red-600" data-testid="2fa-error">{err}</p>}
                <div className="flex gap-2 justify-end pt-2">
                  <button onClick={resetSetup} className="px-4 py-2 text-sm text-[#71717A] hover:text-[#18181B]">{t('cab_2fa_cancel')}</button>
                  <button onClick={verifyEnable} disabled={busy || code.length !== 6} className="px-4 py-2 text-sm font-medium text-white bg-[#18181B] rounded-lg disabled:opacity-50 flex items-center gap-2" data-testid="2fa-verify-btn">
                    {busy && <CircleNotch size={16} className="animate-spin" />}{t('cab_2fa_verify_enable')}
                  </button>
                </div>
              </div>
            )}

            {setupStep === 'backup' && (
              <div className="space-y-3 mt-3">
                <div className="flex items-center gap-2 text-emerald-600">
                  <Check size={18} weight="bold" /><p className="text-sm font-medium">{t('cab_2fa_backup_title')}</p>
                </div>
                <p className="text-xs text-[#71717A]">{t('cab_2fa_backup_desc')}</p>
                <div className="grid grid-cols-2 gap-2 bg-[#F4F4F5] rounded-xl p-3" data-testid="2fa-backup-codes">
                  {backupCodes.map((c, i) => (
                    <code key={i} className="text-sm font-mono text-[#18181B] text-center py-1">{c}</code>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button onClick={copyCodes} className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm border border-[#E4E4E7] rounded-lg hover:bg-[#F4F4F5]" data-testid="2fa-copy-codes">
                    <Copy size={15} />{copied ? t('cab_2fa_copied') : t('cab_2fa_copy')}
                  </button>
                  <button onClick={downloadCodes} className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm border border-[#E4E4E7] rounded-lg hover:bg-[#F4F4F5]" data-testid="2fa-download-codes">
                    <DownloadSimple size={15} />{t('cab_2fa_download')}
                  </button>
                </div>
                <div className="flex justify-end pt-2">
                  <button onClick={finishSetup} className="px-4 py-2 text-sm font-medium text-white bg-[#18181B] rounded-lg" data-testid="2fa-backup-done">{t('cab_2fa_backup_done')}</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Disable modal */}
      {disableOpen && (
        <div className={overlay} onClick={() => setDisableOpen(false)}>
          <div className={sheet} onClick={(e) => e.stopPropagation()} data-testid="2fa-disable-modal">
            <h3 className="text-lg font-semibold text-[#18181B] mb-1">{t('cab_2fa_disable_title')}</h3>
            <p className="text-sm text-[#71717A] mt-1 mb-3">{t('cab_2fa_disable_desc')}</p>
            <div className="space-y-3">
              {hasPassword && (
                <input type="password" value={opPwd} onChange={(e) => setOpPwd(e.target.value)} placeholder={t('cab_2fa_password_label')} className={inputCls} data-testid="2fa-disable-password" />
              )}
              <input value={opCode} onChange={(e) => setOpCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" placeholder={t('cab_2fa_code_label')} className={`${inputCls} tracking-[0.3em] text-center font-mono`} data-testid="2fa-disable-code" />
              {err && <p className="text-xs text-red-600" data-testid="2fa-error">{err}</p>}
              <div className="flex gap-2 justify-end pt-2">
                <button onClick={() => setDisableOpen(false)} className="px-4 py-2 text-sm text-[#71717A] hover:text-[#18181B]">{t('cab_2fa_cancel')}</button>
                <button onClick={doDisable} disabled={busy || opCode.length !== 6 || (hasPassword && !opPwd)} className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg disabled:opacity-50 flex items-center gap-2" data-testid="2fa-disable-confirm">
                  {busy && <CircleNotch size={16} className="animate-spin" />}{t('cab_2fa_disable')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Regenerate modal */}
      {regenOpen && (
        <div className={overlay} onClick={() => setRegenOpen(false)}>
          <div className={sheet} onClick={(e) => e.stopPropagation()} data-testid="2fa-regen-modal">
            <h3 className="text-lg font-semibold text-[#18181B] mb-1">{t('cab_2fa_regen_title')}</h3>
            <p className="text-sm text-[#71717A] mt-1 mb-3">{t('cab_2fa_regen_desc')}</p>
            <div className="space-y-3">
              {hasPassword && (
                <input type="password" value={opPwd} onChange={(e) => setOpPwd(e.target.value)} placeholder={t('cab_2fa_password_label')} className={inputCls} data-testid="2fa-regen-password" />
              )}
              <input value={opCode} onChange={(e) => setOpCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" placeholder={t('cab_2fa_code_label')} className={`${inputCls} tracking-[0.3em] text-center font-mono`} data-testid="2fa-regen-code" />
              {err && <p className="text-xs text-red-600" data-testid="2fa-error">{err}</p>}
              <div className="flex gap-2 justify-end pt-2">
                <button onClick={() => setRegenOpen(false)} className="px-4 py-2 text-sm text-[#71717A] hover:text-[#18181B]">{t('cab_2fa_cancel')}</button>
                <button onClick={doRegenerate} disabled={busy || opCode.length !== 6 || (hasPassword && !opPwd)} className="px-4 py-2 text-sm font-medium text-white bg-[#18181B] rounded-lg disabled:opacity-50 flex items-center gap-2" data-testid="2fa-regen-confirm">
                  {busy && <CircleNotch size={16} className="animate-spin" />}{t('cab_2fa_continue')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export const CabinetProfile = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  const outletCtx = useOutletContext() || {};
  const setLayoutCustomer = outletCtx.setCustomer;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Form states
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [city, setCity] = useState('');
  const [phone, setPhone] = useState('');
  
  // Password change
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  // Email change
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  
  // Avatar
  const [avatarUploading, setAvatarUploading] = useState(false);
  const fileInputRef = React.useRef(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/profile`);
        setData(res.data);
        const c = res.data.customer;
        if (c) {
          setFirstName(c.firstName || '');
          setLastName(c.lastName || '');
          setCity(c.city || '');
          setPhone(c.phone || '');
          // sync sidebar immediately
          if (setLayoutCustomer) setLayoutCustomer((prev) => ({ ...(prev || {}), ...c }));
        }
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId, setLayoutCustomer]);

  // Helper to get auth headers
  const getAuthHeaders = () => {
    const headers = {};
    // Try JWT token first (email/password login)
    const token = localStorage.getItem('customer_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
      return headers;
    }
    
    // Try session token from Google OAuth
    const session = localStorage.getItem('customer_session');
    if (session) {
      try {
        const sessionData = JSON.parse(session);
        if (sessionData.sessionToken) {
          headers['Authorization'] = `Bearer ${sessionData.sessionToken}`;
        }
      } catch {}
    }
    return headers;
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const res = await axios.patch(
        `${API_URL}/api/customer-cabinet/${customerId}/profile`,
        { firstName, lastName, city, phone }
      );
      toast.success(t('adm_profile_updated'));
      setEditing(false);
      const updated = res.data?.customer || {};
      setData(prev => ({
        ...prev,
        customer: { ...prev.customer, ...updated, firstName, lastName, city, phone }
      }));
      if (setLayoutCustomer) {
        setLayoutCustomer((prev) => ({
          ...(prev || {}),
          ...updated,
          firstName,
          lastName,
          city,
          phone,
        }));
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || t('adm3_d1b0c19159'));
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    const currentlyHasPassword = !!data?.customer?.hasPassword;
    if (newPassword !== confirmPassword) {
      toast.error(t('adm_passwords_do_not_match'));
      return;
    }
    if (newPassword.length < 6) {
      toast.error(t('adm_minimum_6_characters'));
      return;
    }
    setSaving(true);
    try {
      const headers = getAuthHeaders();
      if (!headers['Authorization']) {
        toast.error(t('adm_password_change_is_only_available_for_accounts_wit'));
        return;
      }
      // Google users without a password only SET a new one (no current password).
      const body = currentlyHasPassword
        ? { currentPassword, newPassword }
        : { newPassword };
      await axios.patch(`${API_URL}/api/customer-auth/me/password`,
        body,
        { headers, withCredentials: true }
      );
      toast.success(t('adm_password_changed'));
      setShowPasswordModal(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      // Reflect new credential state locally so UI switches to "Change password".
      setData(prev => ({
        ...prev,
        customer: { ...prev.customer, hasPassword: true },
      }));
    } catch (error) {
      if (error.response?.status === 401) {
        toast.error(t('adm_incorrect_current_password'));
        return;
      }
      toast.error(error.response?.data?.message || error.response?.data?.detail || t('adm3_9e20c56932'));
    } finally {
      setSaving(false);
    }
  };

  const handleChangeEmail = async () => {
    if (!newEmail.includes('@')) {
      toast.error(t('adm_invalid_email'));
      return;
    }
    setSaving(true);
    try {
      const headers = getAuthHeaders();
      if (!headers['Authorization']) {
        toast.error(t('adm_email_change_is_only_available_through_the_persona'));
        return;
      }
      await axios.patch(`${API_URL}/api/customer-auth/me/email`,
        { email: newEmail, password: emailPassword },
        { headers, withCredentials: true }
      );
      toast.success(t('adm_email_changed'));
      setShowEmailModal(false);
      setData(prev => ({ ...prev, customer: { ...prev.customer, email: newEmail } }));
      setNewEmail('');
      setEmailPassword('');
    } catch (error) {
      toast.error(error.response?.data?.message || error.response?.data?.detail || t('adm3_bcb9e18a8e'));
    } finally {
      setSaving(false);
    }
  };

  // Завантаження аватара — використовує cabinet endpoint БЕЗ OAuth/Google redirect
  const handleAvatarChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      toast.error(t('adm_image_file_required'));
      e.target.value = '';
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error(t('adm_file_is_too_large_maximum_5mb'));
      e.target.value = '';
      return;
    }

    setAvatarUploading(true);
    const formData = new FormData();
    formData.append('avatar', file);

    try {
      const res = await axios.post(
        `${API_URL}/api/customer-cabinet/${customerId}/avatar`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      const url = res.data?.url || res.data?.avatar || res.data?.picture;
      setData(prev => ({
        ...prev,
        customer: {
          ...prev.customer,
          avatar: url,
          picture: url,
        },
      }));
      // Push to sidebar layout immediately
      if (setLayoutCustomer) {
        setLayoutCustomer((prev) => ({
          ...(prev || {}),
          avatar: url,
          picture: url,
        }));
      }

      // Sync session cache if present
      const session = localStorage.getItem('customer_session');
      if (session) {
        try {
          const s = JSON.parse(session);
          s.picture = url;
          s.avatar = url;
          localStorage.setItem('customer_session', JSON.stringify(s));
        } catch {}
      }

      toast.success(t('adm_avatar_updated'));
    } catch (err) {
      console.error('Avatar upload error:', err?.response?.data || err.message);
      toast.error(err?.response?.data?.detail || t('adm3_1a5253f4e8'));
    } finally {
      setAvatarUploading(false);
      if (e?.target) e.target.value = '';
    }
  };

  // Видалення аватара
  const handleAvatarDelete = async () => {
    setAvatarUploading(true);
    try {
      await axios.delete(`${API_URL}/api/customer-cabinet/${customerId}/avatar`);
      setData(prev => ({
        ...prev,
        customer: { ...prev.customer, avatar: null, picture: null },
      }));
      if (setLayoutCustomer) {
        setLayoutCustomer((prev) => ({ ...(prev || {}), avatar: null, picture: null }));
      }
      toast.success(t('adm_avatar_deleted'));
    } catch (err) {
      toast.error(t('adm_error_2'));
    } finally {
      setAvatarUploading(false);
    }
  };

  if (loading) return <LoadingState />;
  if (!data) return <ErrorState />;

  const { customer, stats, manager } = data;
  const avatar = customer?.picture || customer?.avatar;
  const hasPassword = !!customer?.hasPassword;
  const authProvider = customer?.authProvider || 'email';
  const loginMethodLabel = authProvider === 'google'
    ? (hasPassword ? t('adm_login_google_password') : t('adm_login_google'))
    : t('adm_login_password');

  return (
    <div className="space-y-4" data-testid="cabinet-profile">
      {/* Header with Avatar */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <div className="flex items-center gap-4">
          {/* Avatar */}
          <div className="relative group">
            <div 
              className={`w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold overflow-hidden bg-[#18181B] text-white ${avatarUploading ? 'opacity-50' : 'cursor-pointer'}`}
              onClick={() => !avatarUploading && fileInputRef.current?.click()}
            >
              {avatarUploading ? (
                <CircleNotch size={24} className="animate-spin" />
              ) : avatar ? (
                <img src={avatar} alt={t('adm_avatar')} className="w-full h-full object-cover" />
              ) : (
                (customer?.firstName?.[0] || 'C').toUpperCase()
              )}
            </div>
            {!avatarUploading && (
              <div 
                className="absolute inset-0 bg-black/50 rounded-2xl flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                onClick={() => fileInputRef.current?.click()}
              >
                <PencilSimple size={20} className="text-white" />
              </div>
            )}
            <input 
              ref={fileInputRef}
              type="file" 
              accept="image/*" 
              className="hidden" 
              onChange={handleAvatarChange}
            />
          </div>
          
          <div className="flex-1">
            <h1 className="text-xl font-bold text-[#18181B]">
              {customer?.firstName} {customer?.lastName || customer?.name}
            </h1>
            <p className="text-sm text-[#71717A]">{customer?.email}</p>
          </div>
          
          {!editing ? (
            <button 
              onClick={() => setEditing(true)}
              className="p-2 hover:bg-[#F4F4F5] rounded-xl transition-colors"
              data-testid="edit-profile-btn"
            >
              <PencilSimple size={20} className="text-[#71717A]" />
            </button>
          ) : (
            <div className="flex gap-2">
              <button 
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 text-sm text-[#71717A] hover:bg-[#F4F4F5] rounded-lg"
              >
                {t('adm_cancel_3')}
              </button>
              <button 
                onClick={handleSaveProfile}
                disabled={saving}
                className="px-3 py-1.5 text-sm bg-[#18181B] text-white rounded-lg disabled:opacity-50"
              >
                {saving ? t('adm3_034bf16d6c') : t('r9_save')}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Profile Info */}
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <h2 className="font-semibold text-[#18181B] mb-4">{t('adm_personal_data')}</h2>
          
          {editing ? (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_name')}</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#18181B] outline-none text-sm"
                  placeholder={t('adm_name')}
                  data-testid="profile-firstname-input"
                />
              </div>
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_last_name')}</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#18181B] outline-none text-sm"
                  placeholder={t('adm_last_name')}
                  data-testid="profile-lastname-input"
                />
              </div>
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_city')}</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#18181B] outline-none text-sm"
                  placeholder={t('adm_city')}
                  data-testid="profile-city-input"
                />
              </div>
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_phone_2')}</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl focus:ring-2 focus:ring-[#18181B] outline-none text-sm"
                  placeholder="+380..."
                  data-testid="profile-phone-input"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <InfoRow label={t('adm_name')} value={customer?.firstName || '—'} />
              <InfoRow label={t('adm_last_name')} value={customer?.lastName || '—'} />
              <InfoRow label={t('adm_city')} value={customer?.city || '—'} />
              <InfoRow label={t('adm_phone_2')} value={customer?.phone || '—'} />
            </div>
          )}
        </div>

        {/* Account Security */}
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <h2 className="font-semibold text-[#18181B] mb-4">{t('adm_account_security')}</h2>
          <div className="space-y-3">
            {/* Login method */}
            <div className="flex items-center justify-between py-2 border-b border-[#F4F4F5]">
              <div>
                <p className="text-sm text-[#71717A]">{t('adm_login_method')}</p>
                <p className="font-medium text-[#18181B]" data-testid="login-method-value">{loginMethodLabel}</p>
              </div>
            </div>

            {/* Email */}
            <div className="flex items-center justify-between py-2 border-b border-[#F4F4F5]">
              <div>
                <p className="text-sm text-[#71717A]">{t('adm_email')}</p>
                <p className="font-medium text-[#18181B]">{customer?.email || '—'}</p>
              </div>
              <button 
                onClick={() => { setShowEmailModal(true); setNewEmail(customer?.email || ''); }}
                className="text-xs text-[#18181B] hover:underline"
                data-testid="change-email-btn"
              >
                {t('adm_change')}
              </button>
            </div>
            
            {/* Password */}
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm text-[#71717A]">{t('adm_password_2')}</p>
                <p className="font-medium text-[#18181B]" data-testid="password-state-value">
                  {hasPassword ? '••••••••' : t('adm_password_not_set')}
                </p>
              </div>
              <button 
                onClick={() => setShowPasswordModal(true)}
                className="text-xs text-[#18181B] hover:underline"
                data-testid="change-password-btn"
              >
                {hasPassword ? t('adm_change') : t('adm_set_password')}
              </button>
            </div>

            {/* Two-Factor Authentication */}
            <TwoFactorSection t={t} getAuthHeaders={getAuthHeaders} hasPassword={hasPassword} />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h2 className="font-semibold text-[#18181B] mb-3">{t('adm_statistics')}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div className="bg-[#F4F4F5] rounded-xl p-3">
            <p className="text-[#71717A]">{t('adm_orders')}</p>
            <p className="text-lg font-bold">{stats?.totalDeals || 0}</p>
          </div>
          <div className="bg-emerald-50 rounded-xl p-3">
            <p className="text-emerald-600">{t('adm_completed_2')}</p>
            <p className="text-lg font-bold text-emerald-700">{stats?.completedDeals || 0}</p>
          </div>
          <div className="bg-[#F4F4F5] rounded-xl p-3">
            <p className="text-[#71717A]">{t('adm_deposits_3')}</p>
            <p className="text-lg font-bold">{stats?.totalDeposits || 0}</p>
          </div>
          <div className="bg-[#F4F4F5] rounded-xl p-3">
            <p className="text-[#71717A]">{t('adm_customer_from')}</p>
            <p className="text-lg font-bold">{stats?.memberSince ? new Date(stats.memberSince).toLocaleDateString(getLocale()) : '—'}</p>
          </div>
        </div>
      </div>

      {/* Manager */}
      {manager && (
        <div className="bg-[#18181B] text-white rounded-2xl p-5">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 bg-white/10 rounded-xl flex items-center justify-center">
              <User size={22} />
            </div>
            <div>
              <p className="text-white/60 text-xs">{t('adm_your_manager')}</p>
              <h3 className="font-semibold">{manager.name}</h3>
              <p className="text-white/60 text-sm">{manager.phone}</p>
            </div>
          </div>
        </div>
      )}

      {/* Password Change Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-[#18181B] mb-4">
              {hasPassword ? t('adm_change_password') : t('adm_set_password')}
            </h3>
            <div className="space-y-3">
              {hasPassword && (
                <div>
                  <label className="text-xs text-[#71717A] block mb-1">{t('adm_current_password')}</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl text-sm"
                    data-testid="current-password-input"
                  />
                </div>
              )}
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_new_password')}</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl text-sm"
                  data-testid="new-password-input"
                />
              </div>
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_confirm_password')}</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl text-sm"
                  data-testid="confirm-password-input"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button 
                type="button"
                onClick={() => setShowPasswordModal(false)} 
                className="flex-1 py-2 text-sm text-[#71717A] hover:bg-[#F4F4F5] rounded-xl"
                data-testid="cancel-password-btn"
              >
                {t('adm_cancel_3')}
              </button>
              <button 
                type="button"
                onClick={handleChangePassword} 
                disabled={saving} 
                className="flex-1 py-2 text-sm bg-[#18181B] text-white rounded-xl disabled:opacity-50"
                data-testid="submit-password-btn"
              >
                {saving ? t('adm3_034bf16d6c') : t('adm3_e292a5b19f')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Email Change Modal */}
      {showEmailModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-[#18181B] mb-4">{t('adm_change_email')}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_new_email')}</label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl text-sm"
                  data-testid="new-email-input"
                />
              </div>
              <div>
                <label className="text-xs text-[#71717A] block mb-1">{t('adm_confirmation_password')}</label>
                <input
                  type="password"
                  value={emailPassword}
                  onChange={(e) => setEmailPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-[#E4E4E7] rounded-xl text-sm"
                  data-testid="email-password-input"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button 
                type="button"
                onClick={() => setShowEmailModal(false)} 
                className="flex-1 py-2 text-sm text-[#71717A] hover:bg-[#F4F4F5] rounded-xl"
                data-testid="cancel-email-btn"
              >
                {t('adm_cancel_3')}
              </button>
              <button 
                type="button"
                onClick={handleChangeEmail} 
                disabled={saving} 
                className="flex-1 py-2 text-sm bg-[#18181B] text-white rounded-xl disabled:opacity-50"
                data-testid="submit-email-btn"
              >
                {saving ? t('adm3_034bf16d6c') : t('adm3_e292a5b19f')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export const CabinetCarfax = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/carfax`);
        setReports(res.data?.data || res.data || []);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-carfax">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{t('adm_carfax_reports')}</h1>
      </div>
      {reports.length > 0 ? (
        <div className="space-y-3">
          {reports.map((r) => (
            <div key={r.id} className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium text-[#18181B]">VIN: {r.vin}</p>
                  <p className="text-xs text-[#71717A]">{(r.issuedAt || r.createdAt) ? new Date(r.issuedAt || r.createdAt).toLocaleDateString(getLocale()) : ''}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  r.status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                }`}>{r.status}</span>
              </div>
              {r.pdfUrl && (
                <a href={r.pdfUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
                  {t('adm_download_pdf')}
                </a>
              )}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_1a811ebb86')} />
      )}
    </div>
  );
};

export const CabinetContracts = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/contracts`);
        setContracts(res.data?.data || res.data || []);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  const handleSign = async (id) => {
    try {
      const res = await axios.post(`${API_URL}/api/docusign/envelopes/${id}/sign`, {
        customerId,
        returnUrl: window.location.href
      });
      if (res.data?.signingUrl) window.location.href = res.data.signingUrl;
    } catch (error) {
      toast.error(t('adm_signing_error'));
    }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-contracts">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{'Contracts'}</h1>
      </div>
      {contracts.length > 0 ? (
        <div className="space-y-3">
          {contracts.map((c) => (
            <div key={c.id} className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium text-[#18181B]">{c.title || `${t('r9_agreement_hash')}${c.id?.slice(0, 8)}`}</p>
                  <p className="text-sm text-[#71717A]">VIN: {c.vin || c.dealVin || '—'}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    c.status === 'signed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                  }`}>{c.status === 'signed' ? t('adm3_0dc2b733c3') : t('adm3_37bd1bb076')}</span>
                  {(c.status === 'pending' || c.status === 'sent') && (
                    <button onClick={() => handleSign(c.id)} className="px-3 py-1.5 bg-[#18181B] text-white text-sm rounded-lg">
                      {t('adm_sign')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_9c5c41a938')} />
      )}
    </div>
  );
};

export const CabinetInvoices = () => {
  const { t, lang } = useLang();
  const { customerId } = useParams();
  const [data, setData] = useState({ invoices: [], summary: {} });
  const [loading, setLoading] = useState(true);
  const [pickerInvoice, setPickerInvoice] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/invoices`);
        const invoices = res.data?.data || res.data?.invoices || [];
        const summary = res.data?.summary || {
          totalAmount: invoices.reduce((s, i) => s + (Number(i.amount) || 0), 0),
          paid: invoices.filter((i) => i.status === 'paid').length,
          pending: invoices.filter((i) => i.status !== 'paid').length,
        };
        setData({ invoices, summary });
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [customerId]);

  const handlePay = (invoice) => {
    if (typeof invoice === 'string') {
      // Backwards-compatible: caller passed an id
      const found = data.invoices.find((i) => i.id === invoice);
      if (found) setPickerInvoice(found); else toast.error(t('adm_invoice_not_found'));
      return;
    }
    setPickerInvoice(invoice);
  };

  const proceedPay = async (selectedMethod) => {
    if (!pickerInvoice) return;
    try {
      const res = await axios.post(`${API_URL}/api/stripe/create-checkout-session`, {
        invoiceId: pickerInvoice.id,
        amount: pickerInvoice.amount,
        description: pickerInvoice.description || `${t('r9_invoice_label')} #${pickerInvoice.id}`,
        customerId,
        currency: pickerInvoice.currency,
        originUrl: window.location.origin,
        preferredMethod: selectedMethod,
      });
      if (res.data?.url) window.location.href = res.data.url;
      else toast.error(t('adm_failed_to_get_payment_url'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('adm3_02c05fb66b'));
    } finally {
      setPickerInvoice(null);
    }
  };

  if (loading) return <LoadingState />;

  return (
    <div className="space-y-4" data-testid="cabinet-invoices">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
        <h1 className="text-xl font-bold text-[#18181B]">{t('adm_invoices_and_payments')}</h1>
        <div className="flex gap-4 mt-3">
          <div className="bg-[#F4F4F5] rounded-xl px-4 py-2">
            <p className="text-xs text-[#71717A]">{t('adm_total_3')}</p>
            <p className="font-bold">${data.summary.totalAmount?.toLocaleString() || 0}</p>
          </div>
          <div className="bg-emerald-50 rounded-xl px-4 py-2">
            <p className="text-xs text-emerald-600">{t('adm_paid')}</p>
            <p className="font-bold text-emerald-600">{data.summary.paid || 0}</p>
          </div>
          <div className="bg-amber-50 rounded-xl px-4 py-2">
            <p className="text-xs text-amber-600">{t('adm_awaiting')}</p>
            <p className="font-bold text-amber-600">{data.summary.pending || 0}</p>
          </div>
        </div>
      </div>
      {data.invoices.length > 0 ? (
        <div className="space-y-3">
          {data.invoices.map((inv) => (
            <div key={inv.id} className="bg-white border border-[#E4E4E7] rounded-2xl p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-bold text-lg text-[#18181B]">${(inv.amount || 0).toLocaleString()}</p>
                  <p className="text-sm text-[#71717A]">{tSeed(inv.description, lang) || `${t('r9_invoice_label')} #${inv.id?.slice(0, 8)}`}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    inv.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                  }`}>{inv.status === 'paid' ? t('adm3_6d8c085082') : t('adm3_37bd1bb076')}</span>
                  {inv.status === 'pending' && (
                    <button onClick={() => handlePay(inv)} className="px-3 py-1.5 bg-emerald-600 text-white text-sm rounded-lg flex items-center gap-1">
                      <Wallet size={14} /> {t('adm_pay')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={t('adm3_3ccc626328')} />
      )}

      {/* Payment method picker */}
      <PaymentMethodPicker
        open={!!pickerInvoice}
        onClose={() => setPickerInvoice(null)}
        amount={pickerInvoice?.amount}
        currency={pickerInvoice?.currency}
        description={pickerInvoice?.description || `${t('r9_invoice_label')} #${pickerInvoice?.id || ''}`}
        onProceed={proceedPay}
      />
    </div>
  );
};

export const CabinetShipping = () => {
  const { t } = useLang();
  const { customerId } = useParams();
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const {
    isConnected,
    positionUpdate,
    reconnectTimestamp,
    subscribe,
  } = useShipmentNotifications();

  const loadShipments = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/api/customer-cabinet/${customerId}/shipping`);
      const list = res.data?.data || res.data?.shipments || res.data || [];
      setShipments(Array.isArray(list) ? list : []);
      // auto-expand first active
      const active = (Array.isArray(list) ? list : []).find(
        (s) => !['delivered', 'cancelled'].includes(s.status)
      );
      if (active) setExpandedId(active.id);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    loadShipments();
  }, [loadShipments]);

  // Refetch on reconnect
  useEffect(() => {
    if (reconnectTimestamp > 0) loadShipments();
  }, [reconnectTimestamp, loadShipments]);

  // Subscribe to each active shipment room
  useEffect(() => {
    if (!isConnected) return;
    shipments.forEach((s) => {
      if (!['delivered', 'cancelled'].includes(s.status)) subscribe(s.id);
    });
  }, [isConnected, shipments, subscribe]);

  // Apply live position updates
  useEffect(() => {
    if (!positionUpdate || !positionUpdate.shipmentId) return;
    const pos = positionUpdate.currentPosition;
    const valid =
      pos &&
      Number.isFinite(pos.lat) &&
      Number.isFinite(pos.lng) &&
      pos.lat >= -90 && pos.lat <= 90 &&
      pos.lng >= -180 && pos.lng <= 180;
    setShipments((prev) =>
      prev.map((s) =>
        s.id === positionUpdate.shipmentId
          ? {
              ...s,
              progress:
                typeof positionUpdate.progress === 'number'
                  ? Math.max(0, Math.min(1, positionUpdate.progress))
                  : s.progress,
              liveEta: positionUpdate.eta || s.liveEta,
              trackingSource: positionUpdate.type || s.trackingSource,
              currentPosition: valid ? pos : s.currentPosition,
            }
          : s
      )
    );
  }, [positionUpdate]);

  if (loading) return <LoadingState />;

  const activeShipments = shipments.filter(
    (s) => !['delivered', 'cancelled'].includes(s.status)
  );
  const deliveredShipments = shipments.filter((s) => s.status === 'delivered');

  const statusBadge = (status) => {
    if (status === 'delivered') return { label: t('adm_delivered'), cls: 'bg-emerald-100 text-emerald-700' };
    if (status === 'in_transit') return { label: t('adm_in_transit'), cls: 'bg-blue-100 text-blue-700' };
    if (status === 'at_port') return { label: t('adm_in_port'), cls: 'bg-indigo-100 text-indigo-700' };
    if (status === 'customs') return { label: t('adm_customs'), cls: 'bg-purple-100 text-purple-700' };
    return { label: status || t('adm3_37bd1bb076'), cls: 'bg-amber-100 text-amber-700' };
  };

  return (
    <div className="space-y-4" data-testid="cabinet-shipping">
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#18181B] flex items-center gap-2">
            <Truck size={24} /> {'Delivery'}
          </h1>
          <p className="text-sm text-[#71717A] mt-1">
            {t('adm_live_car_tracking_from_port_to_you')}
          </p>
        </div>
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
            isConnected ? 'bg-emerald-100 text-emerald-700' : 'bg-zinc-100 text-zinc-500'
          }`}
        >
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'
            }`}
          />
          {isConnected ? 'Real-time' : 'Offline'}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl p-5 text-white">
          <div className="flex items-center gap-2 mb-2">
            <Truck size={20} /> <span className="text-sm font-medium opacity-90">{t('adm_in_transit')}</span>
          </div>
          <div className="text-3xl font-bold">{activeShipments.length}</div>
        </div>
        <div className="bg-white border border-[#E4E4E7] rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Check size={20} className="text-emerald-500" />{' '}
            <span className="text-sm font-medium text-[#71717A]">{t('adm_delivered')}</span>
          </div>
          <div className="text-3xl font-bold text-[#18181B]">{deliveredShipments.length}</div>
        </div>
      </div>

      {shipments.length > 0 ? (
        <div className="space-y-4">
          {shipments.map((s) => {
            const badge = statusBadge(s.status);
            const expanded = expandedId === s.id;
            const liveUpdate =
              positionUpdate?.shipmentId === s.id ? positionUpdate : null;
            // Derive current vessel/container from the active stage (falls back
            // to top-level for legacy shipments).
            const curStage = (s.stages || []).find((st) => st.id === s.currentStageId);
            const curVessel = curStage?.vessel || s.vessel;
            const curContainer = curStage?.container || s.container;
            // Live status pill: 🟢 live / 🟡 estimated / 🔴 stale / ⚪ no-data
            // Uses backend-computed trackingHealth (which accounts for > 3h staleness).
            const src = s.trackingSource || s.currentPosition?.source;
            const health = s.trackingHealth;   // ok | estimated | stale | no_data
            const livePill = (() => {
              if (health === 'stale') {
                return { dot: 'bg-rose-500 animate-pulse', text: t('adm3_3dcf35d5f8'), cls: 'bg-rose-50 text-rose-700 border-rose-200' };
              }
              if (health === 'ok') {
                return { dot: 'bg-emerald-500 animate-pulse', text: 'Live', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
              }
              if (health === 'estimated') {
                return { dot: 'bg-amber-500', text: 'Estimated', cls: 'bg-amber-50 text-amber-700 border-amber-200' };
              }
              return { dot: 'bg-slate-400', text: t('adm3_ab301504ad'), cls: 'bg-slate-100 text-slate-600 border-slate-200' };
            })();
            const progressPct = Math.min(100, Math.max(0, Math.round((s.progress || 0) * 100)));
            return (
              <div
                key={s.id}
                className="bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden"
                data-testid={`shipment-card-${s.id}`}
              >
                <div
                  className="p-5 cursor-pointer hover:bg-[#FAFAFA]"
                  onClick={() =>
                    setExpandedId(expanded ? null : s.id)
                  }
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="w-10 h-10 bg-[#F4F4F5] rounded-xl flex items-center justify-center shrink-0">
                        <Truck size={20} className="text-[#18181B]" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-[#18181B] truncate">
                          {s.vehicleTitle || `${t('r9_delivery_label')} #${s.id?.slice(-6)}`}
                        </h3>
                        <p className="text-sm text-[#71717A] font-mono truncate">
                          VIN: {s.vin || '—'}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${livePill.cls}`}
                        data-testid="live-pill"
                        title={`Tracking source: ${src || 'unknown'}`}
                      >
                        <span className={`w-2 h-2 rounded-full ${livePill.dot}`} />
                        {livePill.text}
                      </span>
                      <span
                        className={`text-xs px-2.5 py-1 rounded-full whitespace-nowrap ${badge.cls}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                  </div>

                  {/* Vessel / container / region chips — CONTAINER-FIRST
                      (клиенту важнее контейнер, чем название судна) */}
                  {(curVessel?.name || curContainer?.number || s.location) && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                      {curContainer?.number && (
                        <span className="inline-flex items-center gap-1 bg-indigo-50 text-indigo-800 border border-indigo-100 rounded-full px-2 py-0.5 font-mono">
                          📦 {curContainer.number}
                        </span>
                      )}
                      {curVessel?.name && (
                        <span className="inline-flex items-center gap-1 bg-sky-50 text-sky-800 border border-sky-100 rounded-full px-2 py-0.5 font-medium">
                          ⚓ {curVessel.name}
                        </span>
                      )}
                      {s.location && (
                        <span className="inline-flex items-center gap-1 bg-zinc-50 text-zinc-700 border border-zinc-200 rounded-full px-2 py-0.5">
                          📍 {s.location}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Emotional status line -- "Автомобіль в Атлантичному океані" */}
                  {s.emotionalText && (
                    <div className="mt-2 text-sm text-zinc-700 italic">
                      {s.emotionalText}
                    </div>
                  )}

                  {/* Inline progress */}
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-700"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-zinc-700 min-w-[2.5rem] text-right">{progressPct}%</span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
                    {s.originPort && (
                      <div>
                        <div className="text-xs text-[#71717A]">{t('adm_from_where')}</div>
                        <div className="text-sm">{s.originPort}</div>
                      </div>
                    )}
                    {s.destinationPort && (
                      <div>
                        <div className="text-xs text-[#71717A]">{t('adm_where_to')}</div>
                        <div className="text-sm">{s.destinationPort}</div>
                      </div>
                    )}
                    {(s.liveEta || s.estimatedArrivalDate) && (
                      <div>
                        <div className="text-xs text-[#71717A]">ETA</div>
                        <div className="text-sm font-medium text-blue-600">
                          {new Date(s.liveEta || s.estimatedArrivalDate).toLocaleDateString(getLocale())}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {expanded && (
                  <div className="border-t border-[#E4E4E7] p-5 bg-[#FAFAFA] space-y-4">
                    {/* Full Journey Panel (map + overlay + stages + vessel
                        history + container + events). Replaces ad-hoc
                        map + events rendering. */}
                    <JourneyPanel
                      shipmentId={s.id}
                      initialJourney={s.stages ? s : null}
                      liveUpdate={liveUpdate}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState message={t('adm3_0632aec17d')} />
      )}
    </div>
  );
};


// ============ COMPONENTS ============

const OrderCard = ({ deal, customerId }) => {
  const { t } = useLang();
  const currentStep = STATUS_TO_STEP[deal.status] || 0;
  
  return (
    <Link 
      to={`/cabinet/${customerId}/orders/${deal.id}`}
      className="block bg-white border border-[#E4E4E7] rounded-2xl p-4 hover:border-[#18181B] transition-colors"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-[#F4F4F5] rounded-xl flex items-center justify-center shrink-0">
            <Car size={20} className="text-[#71717A]" />
          </div>
          <div>
            <h3 className="font-medium text-[#18181B]">{deal.title || deal.vehicleTitle || deal.vin}</h3>
            <p className="text-sm text-[#71717A]">VIN: {deal.vin || '—'}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-bold text-[#18181B]">${(deal.clientPrice || 0).toLocaleString()}</p>
          <span className="text-xs px-2 py-0.5 rounded-full bg-[#F4F4F5] text-[#71717A]">
            {deal.status}
          </span>
        </div>
      </div>
      {/* Mini Progress */}
      <div className="flex items-center gap-1 mt-3">
        {PROCESS_STEPS.map((_, idx) => (
          <div key={idx} className={`h-1 flex-1 rounded-full ${
            idx < currentStep ? 'bg-emerald-500' :
            idx === currentStep ? 'bg-[#18181B]' :
            'bg-[#E4E4E7]'
          }`} />
        ))}
      </div>
    </Link>
  );
};

const InfoRow = ({ label, value }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-[#F4F4F5] last:border-0">
    <span className="text-[#71717A]">{label}</span>
    <span className="font-medium text-[#18181B]">{value}</span>
  </div>
);

const LoadingState = () => (
  <div className="flex items-center justify-center py-20">
    <CircleNotch size={32} className="animate-spin text-[#71717A]" />
  </div>
);

const ErrorState = () => {
  const { t } = useLang();
  return (
    <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
      <p className="text-red-600">{t('adm_data_loading_error')}</p>
    </div>
  );
};

const EmptyState = ({ message }) => (
  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-8 text-center text-[#71717A]">
    {message}
  </div>
);

export default CabinetDashboard;
