/**
 * AuthSettingsPage — admin UI for dynamic auth configuration
 * ------------------------------------------------------------
 * GET  /api/admin/settings/auth   — current values (jwt.secret masked)
 * PATCH /api/admin/settings/auth  — deep-merge update
 *
 * Sections (each saves its own slice via PATCH):
 *   1. Public URLs       (baseUrl, frontendUrl)
 *   2. Google Sign-In    (clientId, allowed domains, enable/disable)
 *   3. Password & reset  (min length, reset TTL, feature toggles)
 *   4. JWT               (secret, expiries)
 *   5. Email transport   (mode, from, reply-to)
 *
 * UX redesign notes:
 *   • The "Currently effective" panel sits as a discrete, dense banner at the
 *     top — no double-border / no monospace dev font, just neat key/value
 *     rows with subtle background.
 *   • Each block uses the same white card + 40px icon pill + inline Save
 *     button. No more mixed colour palettes (blue card next to white cards).
 *   • All-Mazzard typography.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useLang } from '../../i18n';
import {
  Link as LinkIcon,
  GoogleLogo,
  Key,
  ToggleLeft,
  ShieldCheck,
  EnvelopeSimple,
  FloppyDisk,
  ArrowCounterClockwise,
  CheckCircle,
  WarningCircle,
  Info,
} from '@phosphor-icons/react';
import WhiteSelect from '../../components/ui/WhiteSelect';
import IntegrationsPage from './IntegrationsPage';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ── building blocks ───────────────────────────────────────────────
const Block = ({ icon: Icon, title, description, children, onSave, saving, testId }) => (
  <div
    className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5"
    data-testid={testId}
  >
    {/* Header row — icon + title on the left, Save on the right.
        The description sits BELOW this row at full width so long copy
        doesn't get squeezed into a 60px ribbon on mobile. */}
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        {Icon && (
          <div className="w-9 h-9 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Icon size={17} weight="duotone" />
          </div>
        )}
        <h2 className="text-[15px] font-semibold text-[#18181B] leading-tight truncate">
          {title}
        </h2>
      </div>
      {onSave && (
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="shrink-0 inline-flex items-center justify-center gap-1.5 sm:gap-2 h-9 px-3 sm:px-4 rounded-xl bg-[#18181B] hover:bg-[#27272A] text-white text-[12.5px] font-semibold disabled:opacity-50 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10"
          data-testid={`${testId}-save`}
        >
          <FloppyDisk size={14} weight="bold" />
          <span className="hidden xs:inline sm:inline">{saving ? 'Saving…' : 'Save'}</span>
        </button>
      )}
    </div>
    {description && (
      <p className="mt-2 text-[12.5px] text-[#71717A] leading-relaxed">
        {description}
      </p>
    )}
    <div className="mt-4 space-y-4">{children}</div>
  </div>
);

const Field = ({ label, hint, error, children }) => (
  <div>
    <label className="block text-[10.5px] font-semibold text-[#71717A] mb-1.5 uppercase tracking-[0.12em]">
      {label}
    </label>
    {children}
    {hint && <p className="text-[11.5px] text-[#71717A] mt-1 leading-snug">{hint}</p>}
    {error && <p className="text-[11.5px] text-red-600 mt-1">{error}</p>}
  </div>
);

const Input = (props) => (
  <input
    {...props}
    className={
      'w-full px-3 py-2.5 rounded-xl border border-[#E4E4E7] text-[13px] bg-white text-[#18181B] placeholder-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-[#18181B]/15 focus:border-[#18181B] ' +
      (props.className || '')
    }
  />
);

const Toggle = ({ checked, onChange, disabled, ...rest }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    onClick={() => !disabled && onChange(!checked)}
    disabled={disabled}
    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
      checked ? 'bg-[#18181B]' : 'bg-[#E4E4E7]'
    } disabled:opacity-40 focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10`}
    {...rest}
  >
    <span
      className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform shadow ${
        checked ? 'translate-x-5' : 'translate-x-0.5'
      }`}
    />
  </button>
);

// ── effective values row ──────────────────────────────────────────
const EffRow = ({ label, value, valueClassName = '', testId }) => (
  <div className="flex items-center justify-between gap-3 py-1.5">
    <dt className="text-[12px] text-[#71717A] shrink-0">{label}</dt>
    <dd
      className={
        'text-[12.5px] text-[#18181B] truncate min-w-0 max-w-[60%] text-right ' +
        valueClassName
      }
      data-testid={testId}
    >
      {value}
    </dd>
  </div>
);

// ── main page ──────────────────────────────────────────────────────
export default function AuthSettingsPage({ embedded = false }) {
  const { t } = useLang();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState('');

  const [urls, setUrls] = useState({ baseUrl: '', frontendUrl: '' });
  const [google, setGoogle] = useState({ clientId: '', allowedDomains: '' });
  const [jwt, setJwt] = useState({ secret: '', accessExpires: '15m', refreshExpires: '7d' });
  const [features, setFeatures] = useState({
    googleEnabled: true,
    passwordEnabled: true,
    registerEnabled: true,
    resetPasswordEnabled: true,
  });
  const [password, setPassword] = useState({ minLength: 6, resetTokenTtlMinutes: 60 });
  const [email, setEmail] = useState({ mode: 'dry_run', from: '', replyTo: '' });
  const [jwtDirty, setJwtDirty] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/api/admin/settings/auth`);
      const data = res.data || {};
      setDoc(data);
      setUrls({ baseUrl: data.baseUrl || '', frontendUrl: data.frontendUrl || '' });
      setGoogle({
        clientId: (data.google && data.google.clientId) || '',
        allowedDomains: Array.isArray(data.google?.allowedDomains)
          ? data.google.allowedDomains.join(', ')
          : (data.google?.allowedDomains || ''),
      });
      setJwt({
        secret: (data.jwt && data.jwt.secret) || '',
        accessExpires: (data.jwt && data.jwt.accessExpires) || '15m',
        refreshExpires: (data.jwt && data.jwt.refreshExpires) || '7d',
      });
      setJwtDirty(false);
      setFeatures({
        googleEnabled: data.features?.googleEnabled ?? true,
        passwordEnabled: data.features?.passwordEnabled ?? true,
        registerEnabled: data.features?.registerEnabled ?? true,
        resetPasswordEnabled: data.features?.resetPasswordEnabled ?? true,
      });
      setPassword({
        minLength: Number(data.password?.minLength ?? 6),
        resetTokenTtlMinutes: Number(data.password?.resetTokenTtlMinutes ?? 60),
      });
      setEmail({
        mode: data.email?.mode || 'dry_run',
        from: data.email?.from || '',
        replyTo: data.email?.replyTo || '',
      });
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_2e8823d0ce'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const patch = async (slice, key) => {
    setSaving(key);
    try {
      await axios.patch(`${API_URL}/api/admin/settings/auth`, slice);
      toast.success(t('saved'));
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm2_d1b0c19159'));
    } finally {
      setSaving('');
    }
  };

  if (loading) {
    return (
      <div className="p-10 text-center text-[#71717A]">
        <div className="animate-spin w-6 h-6 border-2 border-[#18181B] border-t-transparent rounded-full mx-auto mb-3" />
        {t('adm_loading_3')}
      </div>
    );
  }

  const resolved = doc?._resolved || {};

  return (
    <div className={embedded ? '' : 'p-6 max-w-5xl mx-auto'} data-testid="auth-settings-page">
      {!embedded && (
        <div className="mb-6">
          <div className="flex items-center gap-3">
            <ShieldCheck size={26} weight="duotone" className="text-[#18181B]" />
            <h1 className="text-[22px] font-semibold text-[#18181B]">
              {t('adm_auth_url_settings') || 'Auth & URLs'}
            </h1>
          </div>
        </div>
      )}

      {/* ── Effective values (compact, single-panel) ─────────────────── */}
      <div
        className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5 mb-5"
        data-testid="auth-resolved-panel"
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#F4F4F5] border border-[#E4E4E7] text-[#18181B] flex items-center justify-center shrink-0">
            <Info size={16} weight="duotone" />
          </div>
          <h2 className="text-[14px] font-semibold text-[#18181B] leading-tight truncate">
            {t('adm2_fallback_c34694fc28') || 'Currently effective (with fallback)'}
          </h2>
        </div>
        <p className="mt-2 text-[12px] text-[#71717A] leading-relaxed">
          Values your backend resolves at runtime — after env + DB overrides.
        </p>

        <dl className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-x-6 divide-y md:divide-y-0 divide-[#F4F4F5]">
          <EffRow
            label="baseUrl"
            value={resolved.baseUrl || '—'}
            testId="resolved-baseUrl"
          />
          <EffRow
            label="frontendUrl"
            value={resolved.frontendUrl || '—'}
            testId="resolved-frontendUrl"
          />
          <EffRow
            label={t('adm_googleclientid') || 'google.clientId'}
            value={
              resolved.googleClientId ? (
                <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold">
                  <CheckCircle size={13} weight="fill" />
                  {t('adm_installed') || 'installed'}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-amber-700 font-semibold">
                  <WarningCircle size={13} weight="fill" />
                  {t('adm_not_configured') || 'not configured'}
                </span>
              )
            }
          />
          <EffRow
            label="request base_url"
            value={resolved.requestBaseUrl || '—'}
            valueClassName="text-[#71717A]"
          />
        </dl>
      </div>

      <div className="space-y-4">
        {/* ── 1. Public URLs ─────────────────────────────────────────── */}
        <Block
          icon={LinkIcon}
          title={t('publicUrls') || 'Public URLs'}
          description={
            t('adm2_baseurl_url_callback_ema_b07c2ed7d7') ||
            'baseUrl — public backend URL (callback, email); frontendUrl — frontend URL (reset links).'
          }
          testId="auth-urls-block"
          saving={saving === 'urls'}
          onSave={() => patch({ baseUrl: urls.baseUrl, frontendUrl: urls.frontendUrl }, 'urls')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field
              label="Base URL (backend)"
              hint={t('adm_example_httpseconovaua_no_trailing_slash')}
            >
              <Input
                value={urls.baseUrl}
                onChange={(e) => setUrls({ ...urls, baseUrl: e.target.value })}
                placeholder="https://eco-nova.ua"
                data-testid="auth-input-baseUrl"
              />
            </Field>
            <Field
              label={t('frontendUrl') || 'Frontend URL'}
              hint={t('adm_where_resetpassword_emails_lead_and_redirect_after')}
            >
              <Input
                value={urls.frontendUrl}
                onChange={(e) => setUrls({ ...urls, frontendUrl: e.target.value })}
                placeholder="https://eco-nova.ua"
                data-testid="auth-input-frontendUrl"
              />
            </Field>
          </div>
        </Block>

        {/* ── 2. Google Sign-In ──────────────────────────────────────── */}
        <Block
          icon={GoogleLogo}
          title="Google Sign-In (GIS popup)"
          description={t('adm_google_identity_services_popup_id_token_verificati')}
          testId="auth-google-block"
          saving={saving === 'google'}
          onSave={() =>
            patch(
              {
                google: {
                  clientId: google.clientId.trim(),
                  allowedDomains: google.allowedDomains
                    .split(/[,\n]/)
                    .map((d) => d.trim().replace(/^@/, '').toLowerCase())
                    .filter(Boolean),
                },
              },
              'google',
            )
          }
        >
          <Field
            label={t('clientId') || 'Client ID'}
            hint={t('adm2_xxxxxxxxxxxx_apps_google_3320c64959')}
          >
            <Input
              value={google.clientId}
              onChange={(e) => setGoogle({ ...google, clientId: e.target.value })}
              placeholder={t('adm_123456789abcappsgoogleusercontentcom')}
              data-testid="auth-input-googleClientId"
            />
          </Field>
          <Field
            label="Allowed domains"
            hint="Comma-separated (e.g. eco-nova.ua, partner.com). Leave empty to allow any verified Google account."
          >
            <Input
              value={google.allowedDomains}
              onChange={(e) => setGoogle({ ...google, allowedDomains: e.target.value })}
              placeholder="eco-nova.ua, partner.com"
              data-testid="auth-input-googleAllowedDomains"
            />
          </Field>
          <div className="flex items-center justify-between rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] px-3.5 py-2.5">
            <div className="min-w-0 pr-3">
              <div className="text-[13px] font-medium text-[#18181B]">
                {t('adm_enable_google_signin') || 'Enable Google Sign-In'}
              </div>
              <div className="text-[11.5px] text-[#71717A] mt-0.5">
                {t('adm_if_disabled_the_google_button_is_hidden_on_the_log')}
              </div>
            </div>
            <Toggle
              checked={features.googleEnabled}
              onChange={(v) => {
                setFeatures({ ...features, googleEnabled: v });
                patch({ features: { googleEnabled: v } }, 'features-google');
              }}
              data-testid="auth-toggle-googleEnabled"
            />
          </div>
        </Block>

        {/* ── 3. Password & reset policy ─────────────────────────────── */}
        <Block
          icon={Key}
          title={t('adm_password_auth_reset') || 'Password auth & reset'}
          description={t('adm_emailpassword_registration_settings_and_password_r')}
          testId="auth-password-block"
          saving={saving === 'password'}
          onSave={() =>
            patch(
              {
                password: {
                  minLength: Number(password.minLength) || 6,
                  resetTokenTtlMinutes: Number(password.resetTokenTtlMinutes) || 60,
                },
              },
              'password',
            )
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('adm_min_password_length') || 'Min password length'} hint={t('adm_applies_to_register_and_reset')}>
              <Input
                type="number"
                min={4}
                max={64}
                value={password.minLength}
                onChange={(e) => setPassword({ ...password, minLength: e.target.value })}
                data-testid="auth-input-minLength"
              />
            </Field>
            <Field label={t('adm2_ttl_reset_ad4f34ff62') || 'Reset link TTL (minutes)'} hint={t('adm_how_long_is_the_link_valid')}>
              <Input
                type="number"
                min={1}
                max={1440}
                value={password.resetTokenTtlMinutes}
                onChange={(e) => setPassword({ ...password, resetTokenTtlMinutes: e.target.value })}
                data-testid="auth-input-resetTtl"
              />
            </Field>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
            {[
              ['passwordEnabled', 'Password login'],
              ['registerEnabled', t('adm2_ec89a714bb') || 'Self-registration'],
              ['resetPasswordEnabled', t('adm2_38ff59c865') || 'Password reset'],
            ].map(([key, label]) => (
              <div
                key={key}
                className="flex items-center justify-between bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl px-3 py-2.5"
              >
                <span className="text-[12.5px] text-[#18181B] font-medium">{label}</span>
                <Toggle
                  checked={features[key]}
                  onChange={(v) => {
                    setFeatures({ ...features, [key]: v });
                    patch({ features: { [key]: v } }, `features-${key}`);
                  }}
                  data-testid={`auth-toggle-${key}`}
                />
              </div>
            ))}
          </div>
        </Block>

        {/* ── 4. JWT ─────────────────────────────────────────────────── */}
        <Block
          icon={ToggleLeft}
          title="JWT (staff tokens)"
          description={t('adm2_staff_env_jwt_secret_ap_9cb437968d')}
          testId="auth-jwt-block"
          saving={saving === 'jwt'}
          onSave={() => {
            const slice = {
              jwt: {
                accessExpires: jwt.accessExpires,
                refreshExpires: jwt.refreshExpires,
              },
            };
            if (jwtDirty) slice.jwt.secret = jwt.secret;
            patch(slice, 'jwt');
          }}
        >
          <Field
            label={t('secretLabel') || 'JWT secret'}
            hint={
              doc?.jwt?.secretIsSet
                ? t('adm2_19525c9b2e')
                : t('adm2_env_jwt_secret_ce7597c4ac')
            }
          >
            <div className="flex gap-2">
              <Input
                type="password"
                value={jwt.secret}
                onChange={(e) => {
                  setJwt({ ...jwt, secret: e.target.value });
                  setJwtDirty(true);
                }}
                placeholder={doc?.jwt?.secretIsSet ? '********' : 'super-secret-string'}
                data-testid="auth-input-jwtSecret"
              />
              {jwtDirty && (
                <button
                  type="button"
                  onClick={() => {
                    setJwt({ ...jwt, secret: doc?.jwt?.secret || '' });
                    setJwtDirty(false);
                  }}
                  className="shrink-0 px-3 py-2 rounded-xl border border-[#E4E4E7] text-[12.5px] text-[#71717A] hover:bg-[#FAFAFA] flex items-center gap-1"
                >
                  <ArrowCounterClockwise size={13} /> {t('adm_reset') || 'Reset'}
                </button>
              )}
            </div>
          </Field>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('accessTokenTtl') || 'Access TTL'} hint={t('adm_go_duration_format_15m_1h_24h')}>
              <Input
                value={jwt.accessExpires}
                onChange={(e) => setJwt({ ...jwt, accessExpires: e.target.value })}
                data-testid="auth-input-accessExpires"
              />
            </Field>
            <Field label={t('refreshTokenTtl') || 'Refresh TTL'}>
              <Input
                value={jwt.refreshExpires}
                onChange={(e) => setJwt({ ...jwt, refreshExpires: e.target.value })}
                data-testid="auth-input-refreshExpires"
              />
            </Field>
          </div>
        </Block>

        {/* ── 5. Email transport ─────────────────────────────────────── */}
        <Block
          icon={EnvelopeSimple}
          title="Email (reset-password transport)"
          description={
            email.mode === 'dry_run'
              ? t('adm2_dry_run_response_reset_p_cfca72e015')
              : t('adm2_smtp_resend_outbox_4561795943')
          }
          testId="auth-email-block"
          saving={saving === 'email'}
          onSave={() =>
            patch(
              {
                email: {
                  mode: email.mode,
                  from: email.from.trim(),
                  replyTo: email.replyTo.trim(),
                },
              },
              'email',
            )
          }
        >
          <Field label={t('adm_mode') || 'Mode'}>
            <WhiteSelect
              value={email.mode}
              onChange={(e) => setEmail({ ...email, mode: e.target.value })}
              data-testid="auth-select-emailMode"
            >
              <option value="dry_run">{t('adm2_dry_run_b66359ea15') || 'dry-run (log only)'}</option>
              <option value="smtp" disabled>{t('adm3_4733065469') || 'SMTP (not configured)'}</option>
              <option value="resend" disabled>{t('adm3_77e3eecbd2') || 'Resend (not configured)'}</option>
            </WhiteSelect>
          </Field>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('fromLabel') || 'From'}>
              <Input
                value={email.from}
                onChange={(e) => setEmail({ ...email, from: e.target.value })}
                placeholder={t('adm_noreplyeconovaua') || 'no-reply@eco-nova.ua'}
                data-testid="auth-input-emailFrom"
              />
            </Field>
            <Field label={t('replyTo') || 'Reply-to'}>
              <Input
                value={email.replyTo}
                onChange={(e) => setEmail({ ...email, replyTo: e.target.value })}
                placeholder={t('adm_supporteconovaua') || 'support@eco-nova.ua'}
                data-testid="auth-input-emailReplyTo"
              />
            </Field>
          </div>
        </Block>
      </div>

      {/* ─── Google OAuth Client (full credentials + domain restrictions) ─── */}
      <div className="mt-10">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <GoogleLogo size={18} weight="bold" color="#ffffff" />
          </div>
          <div className="min-w-0">
            <h2 className="text-lg sm:text-xl font-bold text-gray-900 leading-tight">
              Google Sign-In Integration
            </h2>
            <p className="text-xs sm:text-sm text-gray-500 mt-1">
              Client ID / Client Secret для Google OAuth. Тестируйте через Test Connection.
            </p>
          </div>
        </div>
        <GoogleOauthIntegrationCard />
      </div>
    </div>
  );
}

/**
 * Google OAuth provider configuration card.
 *
 * Wave-3 refactor: API keys now live inside the tab where the feature lives
 * (Auth & URLs) instead of a separate /admin/integrations hub. We embed the
 * canonical IntegrationsPage component pre-filtered to a single provider so
 * we keep ONE source of truth for credentials editing + test connection.
 */
function GoogleOauthIntegrationCard() {
  return <IntegrationsPage embedded filterProviders={['google_oauth']} />;
}
