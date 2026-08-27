/**
 * TrackingLayout — единый хаб для всей логики отслеживания контейнеров/судов.
 *
 * V2 redesign (Wave 3.x):
 *   • Полностью убрал negative-margin "break-out" — страница теперь подчиняется
 *     стандартному 50px padding'у Layout-овского <main>, как и любой другой
 *     раздел админки. Никаких inline `marginLeft: calc(-1*pad)` хаков.
 *   • Убран тёмно-синий gradient hero и пёстрый набор цветных pill'ов.
 *     Заменено единым card-стилем в духе остальной админки:
 *       — белый фон, граница #E4E4E7, скругление rounded-2xl,
 *       — KPI группа на сером chip'е с цветной точкой статуса вместо
 *         перекрашенного фона,
 *       — типографика Mazzard, цвета #18181B / #71717A / #3F3F46.
 *   • Tabs — flat secondary-nav (border-bottom вместо filled background),
 *     одинаковая высота, иконки только в одном весе, без двух подзаголовков
 *     стэком — sub-метка в tooltip.
 *   • Используются Tailwind-классы вместо inline-styles, чтобы стиль был
 *     синхронизирован с design tokens проекта.
 *
 * Раньше в левом sidebar были разрозненные пункты — теперь одна точка входа
 * `/admin/tracking`, переключение — через эти tabs. Старые URL остаются
 * рабочими через redirect (см. App.js).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import axios from 'axios';
import { useLang } from '../../i18n';
import {
  Anchor,
  Warning,
  Shield,
  Compass,
  Truck,
  CircleNotch,
  CheckCircle,
} from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL || '';

function authHeaders() {
  const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Tabs are built inside the component so they pick up the active locale. */
function buildTabs(t) {
  return [
    {
      to: '/admin/tracking/vesselfinder',
      label: t('tabVesselFinder'),
      sub: t('tabVesselFinderSub'),
      icon: Anchor,
      testid: 'tab-vesselfinder',
    },
    {
      to: '/admin/tracking/shipments',
      label: t('tabShipmentJournal'),
      sub: t('tabShipmentJournalSub'),
      icon: Compass,
      testid: 'tab-shipment-journey',
    },
    {
      to: '/admin/tracking/exceptions/shipments',
      label: t('tabShipmentExceptions'),
      sub: t('tabShipmentExceptionsSub'),
      icon: Truck,
      testid: 'tab-shipment-exceptions',
    },
    {
      to: '/admin/tracking/exceptions/automation',
      label: t('tabAutomationExceptions'),
      sub: t('tabAutomationExceptionsSub'),
      icon: Warning,
      testid: 'tab-automation-exceptions',
      badgeKey: 'automationExceptions',
    },
    {
      to: '/admin/tracking/ext-clients',
      label: t('tabExtClients'),
      sub: t('tabExtClientsSub'),
      icon: Shield,
      testid: 'tab-ext-clients',
    },
  ];
}

/**
 * KpiItem — stat-card в стиле Ringostat overview.
 * Каждая карточка — независимая outlined card с uppercase-label сверху + цветной точкой
 * и крупным значением снизу. Никаких truncate / ellipsis — длинные значения переносятся.
 * Emoji-префиксы из переводов вырезаются автоматически (legacy баги в i18n).
 */
const stripEmoji = (s) =>
  String(s ?? '')
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F1E6}-\u{1F1FF}]/gu, '')
    .replace(/[⚠️⚠🔒🟢🔴🟡🟠]/g, '')
    .trim();

function KpiItem({ label, value, dotColor = '#A1A1AA', testid }) {
  const cleanValue = stripEmoji(value);
  return (
    <div
      data-testid={testid}
      className="bg-white border border-[#E4E4E7] rounded-xl sm:rounded-2xl px-3 py-2.5 sm:px-4 sm:py-3.5 flex flex-col gap-1 sm:gap-1.5 min-w-0"
    >
      <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
        <span
          className="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ background: dotColor }}
        />
        <span className="text-[9.5px] sm:text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] leading-snug truncate">
          {label}
        </span>
      </div>
      <span className="text-[13px] sm:text-sm md:text-base font-semibold text-[#18181B] leading-snug break-words [overflow-wrap:anywhere]">
        {cleanValue || '—'}
      </span>
    </div>
  );
}

const DOTS = {
  ok: '#16A34A',
  warn: '#F59E0B',
  danger: '#DC2626',
  neutral: '#A1A1AA',
  info: '#2563EB',
};

export default function TrackingLayout() {
  const { t } = useLang();
  const [status, setStatus] = useState(null);
  const [automationCount, setAutomationCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchHealth = useCallback(async () => {
    try {
      const [sR, cR] = await Promise.all([
        axios.get(`${API}/api/admin/identity/tracking-status`, { headers: authHeaders() }),
        axios.get(`${API}/api/admin/identity/exceptions/count`, { headers: authHeaders() }),
      ]);
      setStatus(sR.data);
      setAutomationCount(cR.data?.pending || 0);
    } catch {
      // soft-fail — controls page still usable
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const intervalId = setInterval(fetchHealth, 30000);
    return () => clearInterval(intervalId);
  }, [fetchHealth]);

  const TABS = buildTabs(t);
  const trackingDot = status?.trackingEnabled ? DOTS.ok : DOTS.danger;
  const nonceDot = status?.enforceNonce ? DOTS.ok : DOTS.warn;
  const lastHb = status?.extensionLastHeartbeatAt;
  const hbAge = lastHb ? Math.round((Date.now() - new Date(lastHb).getTime()) / 1000) : null;
  const hbDot = hbAge == null ? DOTS.neutral : hbAge < 180 ? DOTS.ok : hbAge < 600 ? DOTS.warn : DOTS.danger;
  const pendingDot = automationCount > 0 ? DOTS.warn : DOTS.ok;

  return (
    <div className="space-y-4 sm:space-y-6" data-testid="tracking-layout">
      {/* ── Page header — unified PageHeader spec ── */}
      <div className="flex items-start gap-3 min-w-0">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <Compass size={20} weight="bold" />
        </div>
        <div className="min-w-0">
          <h1
            data-testid="tracking-title"
            className="text-2xl font-bold text-[#18181B] leading-tight"
            style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}
          >
            {t('trackingHubTitle')}
          </h1>
          <p className="text-[12px] text-[#71717A] mt-0.5 max-w-2xl leading-relaxed">
            {t('trackingHubSubtitle')}
          </p>
        </div>
      </div>

      {/* ── Health KPI strip — 2 cols on mobile, expand on bigger screens ── */}
      <div
        data-testid="tracking-health-strip"
        className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-2 sm:gap-3"
      >
        {loading && (
          <div className="col-span-full bg-white border border-[#E4E4E7] rounded-2xl px-4 py-3.5 flex items-center gap-2 text-sm text-[#71717A]">
            <CircleNotch size={14} className="animate-spin" />
            {t('trackingHubLoadingHealth')}
          </div>
        )}
        {!loading && status && (
          <>
            <KpiItem
              label={t('trackingLabel')}
              dotColor={trackingDot}
              testid="pill-tracking"
              value={status.trackingEnabled ? t('trackingHubKillSwitchOn') : t('trackingHubKillSwitchOff')}
            />
            <KpiItem
              label="Enforce nonce"
              dotColor={nonceDot}
              testid="pill-nonce"
              value={status.enforceNonce ? t('trackingHubNonceStrict') : t('trackingHubNonceSoft')}
            />
            <KpiItem
              label={t('hmacWindow')}
              dotColor={DOTS.info}
              testid="pill-hmac-window"
              value={`±${status.hmacWindowSec}s`}
            />
            <KpiItem
              label={t('extHeartbeat')}
              dotColor={hbDot}
              testid="pill-heartbeat"
              value={
                hbAge == null
                  ? t('trackingHubNoSignal')
                  : hbAge < 180
                  ? `${hbAge} ${t('trackingHubSecondsAgo')}`
                  : hbAge < 600
                  ? `${Math.round(hbAge / 60)} ${t('trackingHubMinAbbr')}`
                  : `${Math.round(hbAge / 60)} ${t('trackingHubMinAbbr')} ${t('trackingHubStaleSuffix')}`
              }
            />
            <KpiItem
              label={t('resolverTick')}
              dotColor={DOTS.info}
              testid="pill-resolver"
              value={`${status.resolverIntervalSec}s`}
            />
            <KpiItem
              label={t('transferTick')}
              dotColor={DOTS.info}
              testid="pill-transfer"
              value={`${status.transferDetectIntervalSec}s`}
            />
            <KpiItem
              label={t('pendingExceptions')}
              dotColor={pendingDot}
              testid="pill-pending-exceptions"
              value={automationCount === 0 ? `0 ${t('trackingHubClean')}` : `${automationCount} ${t('trackingHubWaiting')}`}
            />
          </>
        )}
      </div>

      {/* ── Sub-nav tabs — unified black-outline standard ── */}
      <div
        className="inline-flex p-1 bg-[#FAFAFA] border border-[#E4E4E7] rounded-xl gap-1 max-w-full overflow-x-auto"
        style={{ scrollbarWidth: 'none' }}
        role="tablist"
        aria-label="Tracking sections"
        data-testid="tracking-tabs"
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const showBadge = tab.badgeKey === 'automationExceptions' && automationCount > 0;
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              data-testid={tab.testid}
              title={tab.sub}
              role="tab"
              className={({ isActive }) =>
                [
                  'inline-flex items-center justify-center gap-2 px-3.5 py-1.5 rounded-lg text-[12.5px] sm:text-[13px] whitespace-nowrap shrink-0 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10',
                  isActive
                    ? 'bg-white text-[#18181B] font-semibold shadow-[0_0_0_1.5px_#18181B]'
                    : 'bg-transparent text-[#52525B] hover:text-[#18181B] font-medium',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={14} weight={isActive ? 'fill' : 'regular'} />
                  <span>{tab.label}</span>
                  {showBadge && (
                    <span
                      data-testid={`${tab.testid}-badge`}
                      className={[
                        'ml-0.5 inline-flex items-center justify-center min-w-[16px] h-[16px] px-1 rounded-full text-[10px] font-semibold',
                        isActive ? 'bg-[#18181B] text-white' : 'bg-[#F59E0B] text-white',
                      ].join(' ')}
                    >
                      {automationCount}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* ── Active tab content ── */}
      <div data-testid="tracking-outlet" className="min-h-[400px]">
        <Outlet />
      </div>
    </div>
  );
}

/** Empty index — shown when the user lands on `/admin/tracking` without a sub-path. */
export function TrackingIndex() {
  const { t } = useLang();
  return (
    <div className="bg-white border border-[#E4E4E7] rounded-2xl py-12 px-6 text-center">
      <CheckCircle size={40} weight="duotone" className="text-[#18181B] mx-auto mb-3" />
      <div className="text-[15px] font-semibold text-[#18181B]" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
        {t('trackingHubChooseSection')}
      </div>
      <div className="text-[13px] text-[#71717A] mt-2 max-w-[440px] mx-auto">
        {t('trackingHubChooseHint')}
      </div>
    </div>
  );
}
