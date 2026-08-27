/**
 * Integrations Admin Page
 * 
 * Керування всіма зовнішніми інтеграціями:
 * - Stripe, DocuSign, Ringostat, Telegram, Viber, Email, Shipping
 * - Test connections
 * - Enable/disable
 * - Health status
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useLang } from '../../i18n';
import {
  CreditCard,
  Phone,
  Mail,
  Brain,
  LogIn,
  Check,
  X,
  AlertTriangle,
  RefreshCw,
  Settings,
  Eye,
  EyeOff,
  TestTube,
  Power,
  Activity,
  Pencil,
  ChevronDown,
  Smartphone,
} from 'lucide-react';
// WhiteSelect — canonical white dropdown (portal-rendered, design-system).
// Replaces native <select> (gray OS picker) per UI consistency requirement.
import WhiteSelect from '../../components/ui/WhiteSelect';
import RefreshButton from '../../components/ui/RefreshButton';
import ResendDomainsPanel from './ResendDomainsPanel';
import ResendApiKeysPanel from './ResendApiKeysPanel';
import ResendWebhooksPanel from './ResendWebhooksPanel';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const PROVIDER_CONFIG = {
  google_oauth: {
    name: 'Google Sign-In',
    icon: LogIn,
    color: '#4285F4',
    description: 'Customer cabinet login via Google Identity Services (direct, no intermediate screens).',
    fields: [
      { key: 'clientId', label: 'Google Client ID', type: 'text', placeholder: 'xxxxx.apps.googleusercontent.com' },
      { key: 'clientSecret', label: 'Client Secret (optional, kept private)', type: 'password' },
    ],
    settings: [],
  },
  stripe: {
    name: 'Stripe',
    icon: CreditCard,
    color: '#635BFF',
    description: 'Real card payments + Apple Pay / Google Pay / Link / Klarna / Crypto. Master-admin sees every charge in /admin/payments.',
    fields: [
      { key: 'publishableKey', label: 'Publishable Key', type: 'text', placeholder: 'pk_test_… or pk_live_…' },
      { key: 'secretKey', label: 'Secret Key', type: 'password', placeholder: 'sk_test_… or sk_live_…' },
      { key: 'restrictedKey', label: 'Restricted Key (optional)', type: 'password', placeholder: 'rk_test_… or rk_live_…' },
      { key: 'webhookSecret', label: 'Webhook Secret (optional)', type: 'password', placeholder: 'whsec_… (set after configuring /api/stripe/webhook)' },
    ],
    settings: [
      {
        key: 'currency', label: 'Default currency', type: 'select',
        options: ['USD', 'EUR', 'UAH', 'BGN', 'GBP', 'PLN', 'RON', 'CZK', 'CHF', 'CAD'],
      },
      {
        key: 'automaticPaymentMethods', label: 'Automatic Payment Methods', type: 'toggle',
        help: 'Recommended. Stripe auto-renders methods enabled in Dashboard + wallets (Apple Pay / Google Pay / Link) based on browser & locale.',
      },
      {
        key: 'enabledMethods', label: 'Payment methods', type: 'methods-grid',
        help: 'Each method must also be activated in Stripe Dashboard → Settings → Payment methods. Apple Pay / Google Pay use the Card method type plus wallet activation.',
        groups: [
          { title: 'Cards & Wallets', methods: [
            { value: 'card',       label: 'Cards',      hint: 'adm_visa_mastercard_amex_discover',     accent: '#635BFF', icon: '💳' },
            { value: 'apple_pay',  label: 'adm_apple_pay',  hint: 'adm_onetap_on_safari_ios',              accent: '#000',    icon: '' },
            { value: 'google_pay', label: 'adm_google_pay', hint: 'adm_onetap_on_chrome_android',          accent: '#4285F4', icon: '🅖' },
            { value: 'link',       label: 'adm_link',       hint: 'adm_stripe_oneclick_checkout',            accent: '#00D924', icon: '🔗' },
          ]},
          { title: 'Buy Now, Pay Later', methods: [
            { value: 'klarna',            label: 'adm_klarna',            hint: 'Pay in 4',           accent: '#FFB3C7', icon: 'K' },
            { value: 'afterpay_clearpay', label: 'adm_afterpay_clearpay', hint: 'Pay in 4',         accent: '#B2FCE4', icon: 'A' },
            { value: 'cashapp',           label: 'adm_cash_app_pay',      hint: 'adm_usd_only',           accent: '#00D632', icon: '$' },
          ]},
          { title: 'Crypto', methods: [
            { value: 'crypto', label: 'Crypto (USDC)', hint: 'Stripe Crypto onramp / stablecoin', accent: '#F7931A', icon: '₿' },
          ]},
          { title: 'Bank debits & local methods', methods: [
            { value: 'us_bank_account', label: 'US Bank (ACH)',    hint: 'USA',         accent: '#0F62FE' },
            { value: 'sepa_debit',      label: 'adm_sepa_direct_debit', hint: 'EU',          accent: '#3B82F6' },
            { value: 'ideal',           label: 'iDEAL',            hint: 'adm_netherlands', accent: '#CC0066' },
            { value: 'bancontact',      label: 'adm_bancontact',       hint: 'adm_belgium',     accent: '#005498' },
            { value: 'p24',             label: 'adm_przelewy24',       hint: 'adm_poland',      accent: '#D40028' },
            { value: 'blik',            label: 'BLIK',             hint: 'adm_poland',      accent: '#000' },
            { value: 'alipay',          label: 'adm_alipay',           hint: 'adm_china',       accent: '#1677FF' },
            { value: 'wechat_pay',      label: 'adm_wechat_pay',       hint: 'adm_china',       accent: '#07C160' },
          ]},
        ],
      },
      {
        key: 'checkoutMode', label: 'Checkout UI', type: 'select',
        options: ['hosted', 'embedded'],
        help: 'hosted = redirect to Stripe page · embedded = inline on your site',
      },
      {
        key: 'captureMethod', label: 'Capture method', type: 'select',
        options: ['automatic', 'manual'],
        help: 'automatic = charge on confirm · manual = authorize first, capture later',
      },
      { key: 'statementDescriptor', label: 'Statement descriptor', type: 'text', placeholder: 'ECO.NOVA', help: 'Up to 22 characters shown on customer card statement.' },
      {
        key: 'billingAddressCollection', label: 'Billing address', type: 'select',
        options: ['auto', 'required'],
      },
      { key: 'phoneNumberCollection', label: 'Collect phone number', type: 'toggle' },
      { key: 'allowPromotionCodes',    label: 'Allow promo codes',    type: 'toggle' },
      { key: 'successUrl', label: 'Success URL', type: 'text', placeholder: '/cabinet/payment/success' },
      { key: 'cancelUrl',  label: 'Cancel URL',  type: 'text', placeholder: '/cabinet/payment/cancel' },
    ],
  },
  ringostat: {
    name: 'Ringostat',
    icon: Phone,
    color: '#00D4AA',
    fields: [
      { key: 'apiKey', label: 'API Key', type: 'password' },
      { key: 'projectId', label: 'Project ID', type: 'text' },
    ],
    settings: [],
  },
  email: {
    name: 'Email (SMTP)',
    icon: Mail,
    color: '#EA4335',
    descriptionKey: 'integSmtpDesc',
    fields: [
      { key: 'smtpHost', label: 'SMTP Host', type: 'text' },
      { key: 'smtpPort', label: 'SMTP Port', type: 'text' },
      { key: 'smtpLogin', label: 'Login', type: 'text' },
      { key: 'smtpPassword', label: 'Password', type: 'password' },
    ],
    settings: [
      { key: 'senderEmail', label: 'Sender Email', type: 'text' },
    ],
  },
  resend: {
    name: 'Resend (Email API)',
    icon: Mail,
    color: '#000000',
    descriptionKey: 'integResendDesc',
    fields: [
      { key: 'apiKey', label: 'Resend API Key', type: 'password', placeholder: 're_xxxxxxxxxxxxxxxx' },
      { key: 'from',   label: 'From (verified sender)', type: 'text', placeholder: 'ECO.NOVA <noreply@eco.ua>' },
      { key: 'replyTo', label: 'Reply-To (optional)', type: 'text', placeholder: 'support@bibi.cars' },
    ],
    settings: [],
  },
  sms: {
    name: 'SMS (TextBelt)',
    icon: Smartphone,
    color: '#0EA5E9',
    descriptionKey: 'integSmsDesc',
    fields: [
      {
        key: 'apiKey',
        labelKey: 'integTextbeltKey',
        type: 'password',
        placeholderKey: 'integTextbeltPlaceholder',
      },
    ],
    settings: [
      { key: 'sender', label: 'Sender name (≤ 11 chars)', type: 'text' },
      { key: 'provider', label: 'Provider', type: 'select', options: ['textbelt'] },
    ],
  },
  openai: {
    name: 'OpenAI',
    icon: Brain,
    color: '#10A37F',
    fields: [
      { key: 'apiKey', label: 'API Key', type: 'password' },
    ],
    settings: [
      { key: 'model', label: 'Model', type: 'select', options: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'] },
    ],
  },
};

const STATUS_COLORS = {
  ok: 'bg-green-100 text-green-800',
  degraded: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
  unknown: 'bg-gray-100 text-gray-800',
  not_configured: 'bg-gray-100 text-gray-500',
};

const STATUS_ICONS = {
  ok: Check,
  degraded: AlertTriangle,
  failed: X,
  unknown: Activity,
  not_configured: Settings,
};

export default function IntegrationsPage({ filterProviders = null, embedded = false }) {
  const { t } = useLang();
  const [configs, setConfigs] = useState([]);
  const [health, setHealth] = useState({});
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(null);
  const [expandedProvider, setExpandedProvider] = useState(null);
  const [editMode, setEditMode] = useState({});
  const [editValues, setEditValues] = useState({});
  const [showPasswords, setShowPasswords] = useState({});
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailTesting, setEmailTesting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  // Auto-expand single filtered provider (when embedded in a host page)
  useEffect(() => {
    if (filterProviders && filterProviders.length === 1 && !expandedProvider) {
      setExpandedProvider(filterProviders[0]);
    }
  }, [filterProviders, expandedProvider]);

  const loadData = async () => {
    try {
      const [configsRes, healthRes] = await Promise.all([
        axios.get(`${API_URL}/api/admin/integrations`),
        axios.get(`${API_URL}/api/admin/integrations/health`),
      ]);
      setConfigs(configsRes.data);
      setHealth(healthRes.data);
      try {
        const es = await axios.get(`${API_URL}/api/admin/integrations/email/status`);
        setEmailStatus(es.data);
      } catch { /* non-blocking */ }
    } catch (error) {
      toast.error(t('adm_failed_to_load_integrations'));
    } finally {
      setLoading(false);
    }
  };

  const testConnection = async (provider) => {
    setTesting(provider);
    try {
      const res = await axios.post(`${API_URL}/api/admin/integrations/${provider}/test`);
      if (res.data.success) {
        toast.success(`${PROVIDER_CONFIG[provider]?.name}: ${res.data.message}`);
      } else {
        toast.error(`${PROVIDER_CONFIG[provider]?.name}: ${res.data.message}`);
      }
      await loadData();
    } catch (error) {
      toast.error(`Test failed: ${error.message}`);
    } finally {
      setTesting(null);
    }
  };

  const sendTestEmail = async () => {
    setEmailTesting(true);
    try {
      const res = await axios.post(`${API_URL}/api/admin/integrations/email/test`, {});
      const d = res.data || {};
      if (d.delivered) toast.success(d.message || 'Тестовий лист надіслано');
      else if (d.status === 'failed') toast.error(d.message || 'Помилка надсилання');
      else toast(d.message || 'dry-run: провайдер не налаштований', { icon: '📨' });
      const es = await axios.get(`${API_URL}/api/admin/integrations/email/status`);
      setEmailStatus(es.data);
    } catch (e) {
      toast.error(`Test failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setEmailTesting(false);
    }
  };

  const toggleEnabled = async (provider, currentState) => {
    try {
      await axios.post(`${API_URL}/api/admin/integrations/${provider}/toggle`, {
        isEnabled: !currentState,
      });
      toast.success(`${PROVIDER_CONFIG[provider]?.name} ${!currentState ? 'enabled' : 'disabled'}`);
      await loadData();
    } catch (error) {
      toast.error(t('adm_failed_to_toggle_integration'));
    }
  };

  const saveConfig = async (provider) => {
    const values = editValues[provider];
    if (!values) return;

    try {
      // Special handling for Ringostat
      if (provider === 'ringostat') {
        await axios.post(`${API_URL}/api/admin/integrations/ringostat/configure`, {
          api_key: values.credentials?.apiKey || '',
          project_id: values.credentials?.projectId || '',
          extension_mapping: values.settings?.extensionMapping || {}
        });
      } else {
        await axios.patch(`${API_URL}/api/admin/integrations/${provider}`, {
          credentials: values.credentials,
          settings: values.settings,
          mode: values.mode,
        });
      }
      
      toast.success(`${PROVIDER_CONFIG[provider]?.name} saved`);
      setEditMode({ ...editMode, [provider]: false });
      await loadData();
    } catch (error) {
      toast.error(t('adm_failed_to_save_configuration'));
    }
  };

  const getConfigByProvider = (provider) => {
    return configs.find(c => c.provider === provider) || {
      provider,
      credentials: {},
      settings: {},
      mode: 'disabled',
      isEnabled: false,
    };
  };

  const startEdit = (provider) => {
    const config = getConfigByProvider(provider);
    setEditValues({
      ...editValues,
      [provider]: {
        credentials: { ...config.credentials },
        settings: { ...config.settings },
        mode: config.mode,
      },
    });
    setEditMode({ ...editMode, [provider]: true });
  };

  /** Has the provider got at least ONE credential value entered? */
  const hasCreds = (provider) => {
    const c = getConfigByProvider(provider).credentials || {};
    return Object.values(c).some((v) => typeof v === 'string' && v.length > 0);
  };

  /** Open a row + enter edit mode if there are no creds yet. */
  const openProvider = (provider) => {
    setExpandedProvider(provider);
    if (!hasCreds(provider) && !editMode[provider]) {
      // Use a microtask delay so the row mounts before we mutate editValues
      setTimeout(() => startEdit(provider), 0);
    }
  };

  /** Test button click — if creds missing, redirect user to the form
   *  instead of just toasting an error. */
  const handleTestClick = (provider) => {
    if (!hasCreds(provider)) {
      toast.info(`${PROVIDER_CONFIG[provider]?.name}: enter your keys first.`);
      openProvider(provider);
      return;
    }
    testConnection(provider);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-5 sm:space-y-6">
      {!embedded && (
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0 flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
              <Activity className="w-[18px] h-[18px]" />
            </div>
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">{t('integrationsTitle')}</h1>
              <p className="text-xs sm:text-sm text-gray-500 mt-1.5">{t('integrationsSubtitle')}</p>
            </div>
          </div>
          <RefreshButton
            onClick={loadData}
            ariaLabel={t('refresh')}
            testId="integrations-refresh-btn"
          />
        </div>
      )}

      {/* Consolidated email delivery status (production readiness) */}
      {(!embedded || (filterProviders && (filterProviders.includes('email') || filterProviders.includes('resend')))) && emailStatus && (
        <div className={`rounded-xl border p-4 ${emailStatus.status === 'ready' ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`} data-testid="email-delivery-status">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                <span className={`inline-block h-2 w-2 rounded-full ${emailStatus.status === 'ready' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                Email-доставка: {emailStatus.status === 'ready' ? 'налаштовано' : 'dry-run (не налаштовано)'}
              </div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-600">
                <span>Провайдер: <b>{emailStatus.active_provider}</b></span>
                {emailStatus.from_email ? <span>From: <b>{emailStatus.from_email}</b></span> : null}
                {emailStatus.key_hint ? <span>Ключ: <b>{emailStatus.key_hint}</b></span> : null}
                <span>Sent: {emailStatus.recent_counts?.sent ?? 0} · Failed: {emailStatus.recent_counts?.failed ?? 0} · Dry-run: {emailStatus.recent_counts?.dry_run ?? 0}</span>
              </div>
              {emailStatus.last_error?.error ? (
                <div className="mt-1 text-xs text-red-600" data-testid="email-last-error">Остання помилка: {emailStatus.last_error.error}</div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={sendTestEmail}
              disabled={emailTesting}
              className="shrink-0 rounded-lg bg-[#18181B] px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
              data-testid="email-test-btn"
            >
              {emailTesting ? 'Надсилаємо…' : 'Надіслати тестовий лист'}
            </button>
          </div>
        </div>
      )}

      {/* Health Summary — uniform tiles, 8px radius, no shadow, no inner pills */}
      {!embedded && (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
        {Object.entries(health).map(([provider, data]) => {
          const config = PROVIDER_CONFIG[provider];
          if (!config || config.hidden) return null;
          if (filterProviders && !filterProviders.includes(provider)) return null;
          const StatusIcon = STATUS_ICONS[data.status] || Activity;
          const Icon = config.icon;
          return (
            <button
              type="button"
              key={provider}
              onClick={() => {
                openProvider(provider);
                setTimeout(() => {
                  const el = document.getElementById(`integration-row-${provider}`);
                  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 60);
              }}
              className={`text-left p-3 rounded-lg border bg-white transition-all hover:border-blue-400 hover:shadow-sm min-w-0 ${data.isEnabled ? 'border-gray-200' : 'border-gray-100 opacity-70'}`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <Icon className="w-4 h-4 flex-shrink-0" style={{ color: config.color }} />
                <span className="font-medium text-xs sm:text-sm truncate">{config.name}</span>
              </div>
              <div className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium ${STATUS_COLORS[data.status]}`}>
                <StatusIcon className="w-3 h-3" />
                <span className="truncate">{data.status}</span>
              </div>
            </button>
          );
        })}
      </div>
      )}

      {/* Integration Cards */}
      <div className="space-y-3">
        {Object.entries(PROVIDER_CONFIG)
          .filter(([, c]) => !c.hidden)
          .filter(([p]) => !filterProviders || filterProviders.includes(p))
          .map(([provider, config]) => {
          const integrationConfig = getConfigByProvider(provider);
          const healthData = health[provider] || {};
          const isExpanded = expandedProvider === provider;
          const isEditing = editMode[provider];
          const Icon = config.icon;
          const StatusIcon = STATUS_ICONS[healthData.status] || Activity;
          const showConfigCta = !hasCreds(provider);

          return (
            <div
              key={provider}
              id={`integration-row-${provider}`}
              className={`bg-white rounded-lg border ${integrationConfig.isEnabled ? 'border-gray-200' : 'border-gray-100'} overflow-hidden`}
            >
              {/* === Collapsed Header ===
                  Layout: icon | name + status chips below | chevron.
                  The only right-side control is the expand chevron — all heavy
                  actions live inside the expanded panel, so on mobile the name
                  is never truncated and chips never collide with action icons. */}
              <button
                type="button"
                onClick={() => isExpanded ? setExpandedProvider(null) : openProvider(provider)}
                className="w-full text-left p-4 flex items-start gap-3 hover:bg-gray-50/50 transition-colors"
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: `${config.color}20` }}
                >
                  <Icon className="w-5 h-5" style={{ color: config.color }} />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-gray-900 text-sm sm:text-base">
                    {config.name}
                  </h3>
                  <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium ${STATUS_COLORS[healthData.status]}`}>
                      <StatusIcon className="w-3 h-3" />
                      {healthData.status}
                    </span>
                    {integrationConfig.mode && (
                      <span className={`px-2 py-0.5 rounded-md text-[11px] font-medium ${
                        integrationConfig.mode === 'live' ? 'bg-green-100 text-green-800' :
                        integrationConfig.mode === 'sandbox' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {integrationConfig.mode}
                      </span>
                    )}
                    {integrationConfig.isEnabled && (
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-100 text-emerald-700">
                        enabled
                      </span>
                    )}
                    {showConfigCta && (
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-blue-50 text-blue-700">
                        {t('clickToConfigure')}
                      </span>
                    )}
                  </div>
                </div>
                <ChevronDown
                  className={`w-5 h-5 text-gray-400 flex-shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                />
              </button>

              {/* === Expanded Content === */}
              {isExpanded && (
                <div className="border-t border-gray-100 bg-gray-50/40">
                  {/* Action Bar — full-width text-buttons, identical heights, mobile-friendly */}
                  <div className="px-4 py-3 border-b border-gray-200 bg-white">
                    <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-stretch gap-2">
                      <button
                        type="button"
                        onClick={() => handleTestClick(provider)}
                        disabled={testing === provider}
                        className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white text-xs sm:text-sm font-medium disabled:opacity-50 whitespace-nowrap transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15"
                      >
                        {testing === provider ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <TestTube className="w-3.5 h-3.5" />
                        )}
                        {t('testConnectionAction')}
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleEnabled(provider, integrationConfig.isEnabled)}
                        className={`inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap ${
                          integrationConfig.isEnabled
                            ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        <Power className="w-3.5 h-3.5" />
                        {integrationConfig.isEnabled ? 'Enabled' : 'Disabled'}
                      </button>
                      {!isEditing ? (
                        <button
                          type="button"
                          onClick={() => startEdit(provider)}
                          className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg bg-[#18181B] text-white text-xs sm:text-sm font-medium hover:bg-[#27272A] whitespace-nowrap col-span-2 sm:col-span-1 sm:ml-auto"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                          {t('adm_edit')}
                        </button>
                      ) : (
                        <div className="contents sm:flex sm:gap-2 sm:ml-auto">
                          <button
                            type="button"
                            onClick={() => setEditMode({ ...editMode, [provider]: false })}
                            className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg border border-gray-200 bg-white text-xs sm:text-sm text-gray-600 hover:bg-gray-50 whitespace-nowrap"
                          >
                            {t('cancelAction')}
                          </button>
                          <button
                            type="button"
                            onClick={() => saveConfig(provider)}
                            className="inline-flex items-center justify-center gap-1.5 h-9 px-3 rounded-lg bg-emerald-600 text-white text-xs sm:text-sm font-medium hover:bg-emerald-700 whitespace-nowrap"
                          >
                            <Check className="w-3.5 h-3.5" />
                            {t('adm_save')}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <form
                    autoComplete="off"
                    onSubmit={(e) => e.preventDefault()}
                    className="p-4 space-y-5"
                  >
                    {/* Description */}
                    {(config.description || config.descriptionKey) && (
                      <p className="text-xs text-gray-500 leading-relaxed">{config.descriptionKey ? t(config.descriptionKey) : config.description}</p>
                    )}

                    {/* CREDENTIALS — labels on top, inputs full-width, mono font for keys */}
                    <div>
                      <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2.5">
                        {t('credentialsLabel')}
                      </p>
                      <div className="space-y-3">
                        {config.fields.map((field) => {
                          const passVisible = !!showPasswords[`${provider}_${field.key}`];
                          const value = editValues[provider]?.credentials?.[field.key] || '';
                          const setValue = (val) => setEditValues({
                            ...editValues,
                            [provider]: {
                              ...editValues[provider],
                              credentials: {
                                ...editValues[provider]?.credentials,
                                [field.key]: val,
                              },
                            },
                          });
                          return (
                            <div key={field.key}>
                              <label className="block text-xs font-medium text-gray-600 mb-1">
                                {field.labelKey ? t(field.labelKey) : field.label}
                              </label>
                              {isEditing ? (
                                field.type === 'textarea' ? (
                                  <textarea
                                    autoComplete="off"
                                    spellCheck="false"
                                    rows={3}
                                    placeholder={field.placeholderKey ? t(field.placeholderKey) : (field.placeholder || '')}
                                    value={value}
                                    onChange={(e) => setValue(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono bg-white focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF]"
                                  />
                                ) : (
                                  <div className="relative">
                                    <input
                                      type={field.type === 'password' && !passVisible ? 'password' : 'text'}
                                      autoComplete="off"
                                      autoCorrect="off"
                                      autoCapitalize="off"
                                      spellCheck="false"
                                      name={`int_${provider}_${field.key}`}
                                      placeholder={field.placeholderKey ? t(field.placeholderKey) : (field.placeholder || '')}
                                      value={value}
                                      onChange={(e) => setValue(e.target.value)}
                                      className={`w-full h-10 ${field.type === 'password' ? 'pr-10' : 'pr-3'} pl-3 border border-gray-200 rounded-lg text-sm font-mono bg-white focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF]`}
                                    />
                                    {field.type === 'password' && (
                                      <button
                                        type="button"
                                        onClick={() => setShowPasswords({
                                          ...showPasswords,
                                          [`${provider}_${field.key}`]: !passVisible,
                                        })}
                                        className="absolute inset-y-0 right-1 w-8 inline-flex items-center justify-center text-gray-400 hover:text-gray-600"
                                        tabIndex={-1}
                                      >
                                        {passVisible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                      </button>
                                    )}
                                  </div>
                                )
                              ) : (
                                <div className="text-sm font-mono text-gray-800 bg-white border border-gray-200 px-3 py-2 rounded-lg break-all">
                                  {integrationConfig.credentials?.[field.key] || <span className="text-gray-300">—</span>}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* SETTINGS */}
                    {config.settings.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2.5">
                          {t('settings')}
                        </p>
                        <div className="space-y-3">
                          {config.settings.map((setting) => {
                            const currentVal = isEditing
                              ? editValues[provider]?.settings?.[setting.key]
                              : integrationConfig.settings?.[setting.key];
                            const updateSetting = (newVal) => setEditValues({
                              ...editValues,
                              [provider]: {
                                ...editValues[provider],
                                settings: {
                                  ...editValues[provider]?.settings,
                                  [setting.key]: newVal,
                                },
                              },
                            });
                            return (
                              <div key={setting.key}>
                                <div className={setting.type === 'toggle' ? 'flex items-center justify-between gap-3' : ''}>
                                  <label className="block text-xs font-medium text-gray-600 mb-1">
                                    {setting.label}
                                  </label>
                                  {isEditing && setting.type === 'toggle' && (
                                    <button
                                      type="button"
                                      onClick={() => updateSetting(!currentVal)}
                                      className={`w-12 h-6 rounded-full transition-colors flex-shrink-0 mb-1 ${currentVal ? 'bg-emerald-500' : 'bg-gray-300'}`}
                                      aria-label={setting.label}
                                    >
                                      <div className={`w-5 h-5 bg-white rounded-full shadow transform transition-transform ${currentVal ? 'translate-x-6' : 'translate-x-0.5'}`} />
                                    </button>
                                  )}
                                </div>
                                {isEditing ? (
                                  setting.type === 'select' ? (
                                    <WhiteSelect
                                      value={currentVal || ''}
                                      onChange={(e) => updateSetting(e.target.value)}
                                      placeholder={t('adm_select')}
                                    >
                                      <option value="">{t('adm_select')}</option>
                                      {setting.options?.map((opt) => (
                                        <option key={opt} value={opt}>{opt}</option>
                                      ))}
                                    </WhiteSelect>
                                  ) : setting.type === 'toggle' ? null : setting.type === 'multiselect' ? (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      {setting.options?.map((opt) => {
                                        const optVal = typeof opt === 'string' ? opt : opt.value;
                                        const optLabel = typeof opt === 'string' ? opt : opt.label;
                                        const arr = Array.isArray(currentVal) ? currentVal : [];
                                        const checked = arr.includes(optVal);
                                        return (
                                          <label key={optVal} className={`flex items-center gap-2 px-3 py-2 border rounded-lg text-sm cursor-pointer transition-colors ${checked ? 'bg-blue-50 border-blue-300' : 'border-gray-200 hover:bg-gray-50 bg-white'}`}>
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={() => updateSetting(checked ? arr.filter(v => v !== optVal) : [...arr, optVal])}
                                              className="rounded border-gray-300"
                                            />
                                            <span className="flex-1">{optLabel}</span>
                                          </label>
                                        );
                                      })}
                                    </div>
                                  ) : setting.type === 'methods-grid' ? (
                                    <div className="space-y-4 w-full">
                                      {(setting.groups || []).map((grp) => (
                                        <div key={grp.title}>
                                          <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 mb-2">{grp.title}</p>
                                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {grp.methods.map((m) => {
                                              const obj = (currentVal && typeof currentVal === 'object' && !Array.isArray(currentVal)) ? currentVal : {};
                                              const checked = !!obj[m.value];
                                              return (
                                                <label
                                                  key={m.value}
                                                  className={`flex items-start gap-3 p-3 border-2 rounded-lg text-sm cursor-pointer transition-all ${checked ? 'border-[#635BFF] bg-[#635BFF]/5' : 'border-gray-200 hover:border-gray-300 bg-white'}`}
                                                >
                                                  <input
                                                    type="checkbox"
                                                    checked={checked}
                                                    onChange={() => updateSetting({ ...obj, [m.value]: !checked })}
                                                    className="mt-1 rounded border-gray-300"
                                                  />
                                                  <div
                                                    className="w-9 h-9 rounded-lg flex items-center justify-center text-base font-bold shrink-0"
                                                    style={{ backgroundColor: `${m.accent}15`, color: m.accent }}
                                                  >
                                                    {m.icon || m.label.charAt(0)}
                                                  </div>
                                                  <div className="flex-1 min-w-0">
                                                    <div className="font-semibold text-gray-900">{m.label}</div>
                                                    <div className="text-xs text-gray-500">{m.hint}</div>
                                                  </div>
                                                </label>
                                              );
                                            })}
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  ) : (
                                    <input
                                      type={setting.type || 'text'}
                                      autoComplete="off"
                                      spellCheck="false"
                                      className="w-full h-10 px-3 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF]"
                                      placeholder={setting.placeholder || ''}
                                      value={currentVal || ''}
                                      onChange={(e) => updateSetting(e.target.value)}
                                    />
                                  )
                                ) : (
                                  setting.type === 'methods-grid' ? (
                                    <div className="flex flex-wrap gap-1.5">
                                      {Object.entries(currentVal || {}).filter(([, v]) => v).map(([k]) => (
                                        <span key={k} className="px-2 py-0.5 rounded-md bg-[#635BFF]/10 text-[#635BFF] text-xs font-medium">{k}</span>
                                      ))}
                                      {!Object.values(currentVal || {}).some(Boolean) && (
                                        <span className="text-sm text-gray-400">{t('adm_none')}</span>
                                      )}
                                    </div>
                                  ) : setting.type === 'toggle' ? (
                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium ${currentVal ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                                      {currentVal ? 'Enabled' : 'Disabled'}
                                    </span>
                                  ) : (
                                    <div className="text-sm text-gray-800 bg-white border border-gray-200 px-3 py-2 rounded-lg break-words">
                                      {Array.isArray(currentVal)
                                        ? (currentVal.length ? currentVal.join(', ') : '—')
                                        : (currentVal ? String(currentVal) : <span className="text-gray-300">—</span>)}
                                    </div>
                                  )
                                )}
                                {setting.help && isEditing && (
                                  <p className="text-[11px] text-gray-500 mt-1.5 leading-relaxed">{setting.help}</p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Mode Selection */}
                    {isEditing && (
                      <div className="pt-3 border-t border-gray-200">
                        <label className="block text-xs font-medium text-gray-600 mb-1.5">{t('modeLabel')}</label>
                        <WhiteSelect
                          value={editValues[provider]?.mode || 'disabled'}
                          onChange={(e) => setEditValues({
                            ...editValues,
                            [provider]: { ...editValues[provider], mode: e.target.value },
                          })}
                          data-testid={`integration-mode-select-${provider}`}
                        >
                          <option value="disabled">{t('disabledStatus')}</option>
                          <option value="sandbox">{t('sandboxMode')}</option>
                          <option value="live">{t('liveLabel')}</option>
                        </WhiteSelect>
                      </div>
                    )}

                    {/* Resend Domains Panel — управление доменами прямо из админки */}
                    {provider === 'resend' && (
                      <div className="pt-3 border-t border-gray-200">
                        <ResendDomainsPanel
                          hasApiKey={Boolean(
                            (integrationConfig?.credentials?.apiKey)
                            || (editValues[provider]?.credentials?.apiKey)
                          )}
                        />
                      </div>
                    )}

                    {/* Resend API Keys Panel — управление дополнительными ключами */}
                    {provider === 'resend' && (
                      <div className="pt-3 border-t border-gray-200">
                        <ResendApiKeysPanel
                          hasApiKey={Boolean(
                            (integrationConfig?.credentials?.apiKey)
                            || (editValues[provider]?.credentials?.apiKey)
                          )}
                        />
                      </div>
                    )}

                    {/* Resend Webhooks Panel — управление webhook'ами + статистика событий */}
                    {provider === 'resend' && (
                      <div className="pt-3 border-t border-gray-200">
                        <ResendWebhooksPanel
                          hasApiKey={Boolean(
                            (integrationConfig?.credentials?.apiKey)
                            || (editValues[provider]?.credentials?.apiKey)
                          )}
                        />
                      </div>
                    )}

                    {/* Last Check Info */}
                    {healthData.lastCheck && (
                      <div className="pt-3 border-t border-gray-200 text-[11px] text-gray-500">
                        Last checked: {new Date(healthData.lastCheck).toLocaleString()}
                        {healthData.error && (
                          <span className="block text-red-500 mt-1 break-words">Error: {healthData.error}</span>
                        )}
                      </div>
                    )}
                  </form>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
