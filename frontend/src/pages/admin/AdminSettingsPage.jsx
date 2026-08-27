/**
 * AdminSettingsPage — General tab inside System.
 *
 * Two collapsible sections:
 *   • CRM pipelines (read-only) — Lead pipeline + Deal lifecycle as native
 *     `<select>` dropdowns instead of the noisy chip palette. Each option
 *     keeps its color dot so the visual hierarchy is preserved without
 *     occupying half the screen.
 *   • Security · 2FA (TOTP) — interactive, unchanged behaviour.
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useLang } from '../../i18n';
import {
  Gear,
  ShieldCheck,
  CheckCircle,
  Copy,
  X,
  CaretDown,
} from '@phosphor-icons/react';
import SectionTabs from '../../components/ui/SectionTabs';
import WhiteSelect from '../../components/ui/WhiteSelect';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ── Tabs ────────────────────────────────────────────────
const TABS = [
  { id: 'crm', label: 'CRM' },
  { id: 'security', label: 'Security · 2FA' },
];

export default function AdminSettingsPage({ embedded = false }) {
  const { t } = useLang();
  const [tab, setTab] = useState('crm');
  return (
    <div className={embedded ? '' : 'p-6 max-w-6xl mx-auto'}>
      {!embedded && (
        <div className="flex items-start gap-3 mb-6">
          <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
            <Gear size={20} weight="bold" />
          </div>
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-[#18181B] leading-tight">{t('settings')}</h1>
            <p className="text-[12px] text-[#71717A] mt-0.5">
              {t('adm_productionready_settings_only_what_is_actually_use')}
            </p>
          </div>
        </div>
      )}

      {/* Secondary tabs (CRM / Security) — same unified component */}
      <div className="mb-5">
        <SectionTabs
          tabs={TABS}
          activeId={tab}
          onChange={setTab}
          testIdPrefix="settings-tab"
          ariaLabel="General sections"
        />
      </div>

      {/* Content */}
      {tab === 'crm' && <CRMSettings />}
      {tab === 'security' && <SecurityTab />}
    </div>
  );
}

// ────────────────────────────────────────────────────────
// CRM pipelines (read-only catalog rendered as dropdowns)
// ────────────────────────────────────────────────────────
const LEAD_STATUSES = [
  { code: 'new',         label: 'New',           dot: '#3B82F6' },
  { code: 'contacted',   label: 'Contacted',     dot: '#06B6D4' },
  { code: 'qualified',   label: 'Qualified',     dot: '#6366F1' },
  { code: 'negotiation', label: 'Negotiations',  dot: '#A855F7' },
  { code: 'won',         label: 'Won',           dot: '#10B981' },
  { code: 'lost',        label: 'Lost',          dot: '#71717A' },
];

const DEAL_STATUSES = [
  { code: 'pending',     label: 'Awaiting',     dot: '#F59E0B' },
  { code: 'in_progress', label: 'In Progress',  dot: '#3B82F6' },
  { code: 'contract',    label: 'Contract',     dot: '#6366F1' },
  { code: 'payment',     label: 'Payment',      dot: '#A855F7' },
  { code: 'shipping',    label: 'Delivery',     dot: '#06B6D4' },
  { code: 'delivered',   label: 'Delivered',    dot: '#10B981' },
  { code: 'cancelled',   label: 'Canceled',     dot: '#71717A' },
];

function CRMSettings() {
  const { t } = useLang();
  return (
    <div className="space-y-4">
      <StatusDropdown
        title={t('leadStatuses') || 'Lead pipeline'}
        description={
          t('adm_sales_funnel_pipeline_from_lead_to_deal') ||
          'Sales funnel — from Lead to Deal'
        }
        items={LEAD_STATUSES}
        testId="lead-statuses"
      />
      <StatusDropdown
        title={t('dealStatuses') || 'Deal statuses'}
        description={
          t('dealLifecycle') || 'Deal lifecycle from creation to delivery'
        }
        items={DEAL_STATUSES}
        testId="deal-statuses"
      />

      <div className="rounded-xl border border-[#E4E4E7] bg-[#FAFAFA] px-4 py-3 flex items-start gap-2.5">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#F59E0B] mt-1.5 shrink-0" />
        <p className="text-[12.5px] text-[#3F3F46] leading-relaxed">
          <span className="font-semibold text-[#18181B]">
            {t('pipelineLocked') || 'Pipeline is locked.'}
          </span>{' '}
          {t('adm3_a6c4d0e909') ||
            'Codes are referenced by reports, workers and Stripe — they cannot be edited from the UI.'}
        </p>
      </div>
    </div>
  );
}

/**
 * Compact dropdown that lists statuses with their color dot + code.
 * Uses a native `<select>` underneath so it remains accessible / keyboard-
 * navigable and mobile-friendly, while the visible "row" mimics the look of
 * the surrounding cards.
 */
function StatusDropdown({ title, description, items, testId }) {
  const [selected, setSelected] = useState(items[0]?.code || '');
  const current = items.find((x) => x.code === selected) || items[0];

  return (
    <details
      className="group bg-white border border-[#E4E4E7] rounded-2xl overflow-hidden"
      data-testid={testId}
    >
      <summary
        className="list-none cursor-pointer px-4 sm:px-5 py-4 flex items-center justify-between gap-3 hover:bg-[#FAFAFA] transition-colors"
      >
        <div className="min-w-0">
          <h3 className="text-[14.5px] font-semibold text-[#18181B] leading-tight">
            {title}
          </h3>
          <p className="text-[12px] text-[#71717A] mt-0.5 truncate">
            {description}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="hidden sm:inline-flex items-center gap-1.5 text-[12px] text-[#52525B]">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: current.dot }}
            />
            {items.length} statuses
          </span>
          <CaretDown
            size={14}
            className="text-[#71717A] transition-transform group-open:rotate-180"
          />
        </div>
      </summary>

      <div className="border-t border-[#F4F4F5] bg-[#FAFAFA] px-4 sm:px-5 py-4 space-y-3">
        {/* White-themed select matching the design system. Keeps a colored
            dot decoration to mirror the surrounding row visuals. */}
        <label className="block">
          <span className="block text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#71717A] mb-1.5">
            Status
          </span>
          <div className="relative">
            <span
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 z-10 inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: current.dot }}
            />
            <div className="pl-7">
              <WhiteSelect
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                ariaLabel="Status"
                data-testid={`${testId}-select`}
                options={items.map((it) => ({
                  value: it.code,
                  label: `${it.label} · ${it.code}`,
                }))}
              />
            </div>
          </div>
        </label>

        {/* Compact list with all codes (informational) */}
        <ul className="divide-y divide-[#E4E4E7] rounded-xl border border-[#E4E4E7] bg-white overflow-hidden">
          {items.map((it) => (
            <li
              key={it.code}
              className="flex items-center justify-between gap-3 px-3.5 py-2.5 text-[12.5px]"
            >
              <span className="flex items-center gap-2.5 min-w-0">
                <span
                  className="inline-block w-2 h-2 rounded-full shrink-0"
                  style={{ background: it.dot }}
                />
                <span className="font-semibold text-[#18181B] truncate">
                  {it.label}
                </span>
              </span>
              <span className="text-[11.5px] text-[#71717A] tabular-nums whitespace-nowrap">
                {it.code}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}

// ────────────────────────────────────────────────────────
// Security — 2FA (Google Authenticator / TOTP)
// ────────────────────────────────────────────────────────
function SecurityTab() {
  const { t } = useLang();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);

  const load = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/admin/security/2fa/status`);
      setStatus(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const startSetup = async () => {
    try {
      const res = await axios.post(`${API_URL}/api/admin/security/2fa/setup`);
      setSetup(res.data);
      setCode('');
    } catch {
      toast.error(t('adm_failed_to_generate_qr'));
    }
  };

  const verify = async () => {
    if (!code.trim()) return;
    setVerifying(true);
    try {
      await axios.post(`${API_URL}/api/admin/security/2fa/verify`, { code: code.trim() });
      toast.success(t('adm_2fa_enabled_2'));
      setSetup(null);
      setCode('');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm3_80a84dca0b'));
    } finally {
      setVerifying(false);
    }
  };

  const disable = async () => {
    const c = prompt(t('adm3_9f3b3510e5'));
    if (!c) return;
    try {
      await axios.post(`${API_URL}/api/admin/security/2fa/disable`, { code: c.trim() });
      toast.success(t('adm_2fa_disabled_2'));
      setSetup(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || t('adm3_fd77287f02'));
    }
  };

  if (loading) {
    return <div className="text-center text-[#71717A] py-10">{t('adm_loading_3')}</div>;
  }

  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <ShieldCheck size={17} weight="duotone" />
        </div>
        <h2 className="text-[15px] font-semibold text-[#18181B] leading-tight truncate">
          {t('adm3_1c25c4c013') || 'Two-factor authentication (TOTP)'}
        </h2>
      </div>
      <p className="mt-2 mb-4 text-[12.5px] text-[#71717A] leading-relaxed">
        {t('adm_protect_access_to_the_admin_panel_with_onetime_tot')}
      </p>

      {status?.enabled ? (
        <div>
          <div className="flex items-center gap-2 text-emerald-600 mb-4">
            <CheckCircle size={20} weight="fill" />
            <span className="font-medium text-[14px]">{t('adm_2fa_enabled_2')}</span>
          </div>
          <button
            onClick={disable}
            className="px-4 py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-[13px] font-medium"
          >
            {t('adm_disable_2fa')}
          </button>
        </div>
      ) : setup ? (
        <div className="space-y-4">
          <p className="text-[13px] text-[#52525B]">
            {t('adm_1_scan_the_qr_code_in_google_authenticator_or_auth')}
          </p>
          <div className="flex gap-5 items-start flex-wrap">
            {setup.qrCode && (
              <img
                src={setup.qrCode}
                alt={t('adm_2fa_qr')}
                className="w-40 h-40 border border-[#E4E4E7] rounded-xl bg-white"
              />
            )}
            <div className="flex-1 min-w-[260px]">
              <p className="text-[11.5px] text-[#71717A] mb-1">{t('orEnterManually')}</p>
              <div className="flex items-center gap-2 mb-4">
                <code className="bg-[#F4F4F5] px-3 py-2 rounded-lg text-[13px] tracking-wide flex-1 break-all">
                  {setup.secret}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(setup.secret);
                    toast.success(t('copied'));
                  }}
                  className="p-2 rounded-lg bg-[#F4F4F5] hover:bg-[#E4E4E7]"
                >
                  <Copy size={15} />
                </button>
              </div>

              <p className="text-[13px] text-[#52525B] mb-2">
                {t('adm_2_enter_the_code_from_the_app')}
              </p>
              <div className="flex gap-2">
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  inputMode="numeric"
                  maxLength={6}
                  className="flex-1 px-3 py-2.5 rounded-lg border border-[#E4E4E7] text-center text-lg tracking-[0.3em] font-semibold"
                  data-testid="2fa-code-input"
                />
                <button
                  onClick={verify}
                  disabled={verifying || code.length !== 6}
                  className="px-5 py-2.5 rounded-lg bg-[#18181B] text-white disabled:opacity-40 text-[13px] font-semibold"
                  data-testid="2fa-verify-btn"
                >
                  {verifying ? '…' : t('adm3_d15a1ace8d')}
                </button>
              </div>
            </div>
          </div>
          <button
            onClick={() => setSetup(null)}
            className="text-[12.5px] text-[#71717A] hover:underline flex items-center gap-1"
          >
            <X size={13} />
            {t('cancelAction')}
          </button>
        </div>
      ) : (
        <button
          onClick={startSetup}
          className="px-5 py-2.5 rounded-lg bg-[#18181B] text-white text-[13px] font-semibold hover:bg-[#27272A]"
          data-testid="2fa-enable-btn"
        >
          {t('adm_enable_2fa')}
        </button>
      )}
    </div>
  );
}
