/**
 * SystemPage — Unified hub for all system configuration.
 *
 * Tabs: General · Auth & URLs · Email outbox
 *
 * Active tab is reflected in the URL via ?tab= so deep-links and the
 * legacy redirects from /admin/settings/auth and /admin/settings/email-outbox
 * still land on the right sub-section.
 *
 * UX note: header uses a clean Mazzard title with a subtle icon pill, and a
 * single segmented control for tabs (no per-tab borders / no yellow halo) so
 * the page reads as one calm surface instead of three competing UI rectangles.
 */
import React, { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Wrench,
  ShieldCheck,
  EnvelopeSimple,
  DeviceMobile,
  Brain,
  Pulse,
} from '@phosphor-icons/react';

import AdminSettingsPage from './AdminSettingsPage';
import AuthSettingsPage from './AuthSettingsPage';
import EmailOutboxPage from './EmailOutboxPage';
import SmsOutboxPage from './SmsOutboxPage';
import IntegrationsPage from './IntegrationsPage';
import AdminWorkersPage from './AdminWorkersPage';

import { useLang } from '../../i18n';
import SectionTabs from '../../components/ui/SectionTabs';

const TABS_DEF = [
  { id: 'general', labelKey: 'adm_general',        tipKey: 'sys_tip_general', icon: Wrench },
  { id: 'auth',    labelKey: 'adm_auth_urls',      tipKey: 'sys_tip_auth',    icon: ShieldCheck },
  { id: 'email',   labelKey: 'adm_email_outbox',   tipKey: 'sys_tip_email',   icon: EnvelopeSimple },
  { id: 'sms',     labelKey: 'adm_sms_outbox',     tipKey: 'sys_tip_sms',     icon: DeviceMobile },
  { id: 'ai',      labelKey: 'adm_ai_openai',      tipKey: 'sys_tip_ai',      icon: Brain },
  { id: 'workers', labelKey: 'adm_workers_health', tipKey: 'sys_tip_workers', icon: Pulse },
];

export default function SystemPage() {
  const { t } = useLang();
  const location = useLocation();
  const navigate = useNavigate();

  // Resolve translated labels + tooltips reactively so that switching the
  // platform language re-renders the tab strip in the new locale.
  const TABS = useMemo(
    () =>
      TABS_DEF.map((tab) => ({
        id: tab.id,
        icon: tab.icon,
        label: t(tab.labelKey),
        tip: t(tab.tipKey),
      })),
    [t],
  );

  const activeTab = useMemo(() => {
    const search = new URLSearchParams(location.search);
    const tab = search.get('tab') || 'general';
    return TABS.find((x) => x.id === tab) ? tab : 'general';
  }, [location.search, TABS]);

  const setTab = (id) => {
    const search = new URLSearchParams(location.search);
    search.set('tab', id);
    navigate({ pathname: '/admin/settings', search: search.toString() }, { replace: false });
  };

  const active = TABS.find((x) => x.id === activeTab) || TABS[0];

  return (
    <div className="min-h-full bg-[#FAFAFA]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
      {/* ────────────── Header ────────────── */}
      <div className="px-4 sm:px-6 pt-5 sm:pt-6 pb-4 bg-white border-b border-[#E4E4E7]">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
              <Wrench size={20} weight="bold" />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold tracking-tight text-[#18181B] leading-tight">
                {t('notifSystem') || 'System'}
              </h1>
              <p className="text-[12px] text-[#71717A] mt-0.5">
                {t('adm3_7cc60ff3e9') || 'Pipelines, authentication, URLs and email transport.'}
              </p>
            </div>
          </div>

          {/* ────────────── Tabs (unified) ────────────── */}
          <div className="mt-5">
            <SectionTabs
              tabs={TABS}
              activeId={activeTab}
              onChange={setTab}
              testIdPrefix="system-tab"
              ariaLabel="System sections"
            />
          </div>
        </div>
      </div>

      {/* ────────────── Content ────────────── */}
      <div className="px-4 sm:px-6 py-5 sm:py-6">
        <div className="max-w-6xl mx-auto" data-active-tab={active.id}>
          {activeTab === 'general' && <AdminSettingsPage embedded />}
          {activeTab === 'auth'    && <AuthSettingsPage    embedded />}
          {activeTab === 'email'   && <EmailOutboxPage     embedded />}
          {activeTab === 'sms'     && <SmsOutboxPage       embedded />}
          {activeTab === 'ai'      && (
            <div className="space-y-4">
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-gray-900 leading-tight">
                  {t('sys_ai_heading')}
                </h2>
                <p className="text-xs sm:text-sm text-gray-500 mt-1">
                  {t('sys_ai_subtitle')}
                </p>
              </div>
              <IntegrationsPage embedded filterProviders={['openai']} />
            </div>
          )}
          {activeTab === 'workers' && <AdminWorkersPage embedded />}
        </div>
      </div>
    </div>
  );
}
