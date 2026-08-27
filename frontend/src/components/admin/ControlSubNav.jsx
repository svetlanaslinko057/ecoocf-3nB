/**
 * Shared horizontal sub-navigation for the Admin → Control section.
 *
 * Renders 5 pill-style tabs that link to every Control page:
 *   • Business Metrics      /admin/business-metrics
 *   • Provider Pressure     /admin/provider-health
 *   • Routing Rules         /admin/routing-rules
 *   • Cadences              /admin/cadences
 *   • Score Rules           /admin/score-rules
 *
 * Behaviour:
 *   - Horizontal-scroll on mobile (no wrap, no broken layout)
 *   - Larger touch-friendly pills with generous vertical padding
 *   - Active state is derived from `useLocation()` so works without a prop
 *   - Sticky just below the main app header so it acts as a section header
 *
 * Usage:  <ControlSubNav /> at the very top of every Control page.
 */
import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  ChartLine,
  Gauge,
  Path,
  Timer,
  ChartLineUp,
  Lightning,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const ControlSubNav = () => {
  const { t } = useLang();
  const { pathname } = useLocation();

  const tabs = [
    {
      to: '/admin/business-metrics',
      icon: ChartLine,
      label: t('adm_business_metrics') || 'Business Metrics',
    },
    {
      to: '/admin/provider-health',
      icon: Gauge,
      label: 'Provider Pressure',
    },
    {
      to: '/admin/routing-rules',
      icon: Path,
      label: t('routingRules') || 'Routing Rules',
    },
    {
      to: '/admin/cadences',
      icon: Timer,
      label: t('cadences') || 'Cadences',
    },
    {
      to: '/admin/score-rules',
      icon: ChartLineUp,
      label: t('scoreRules') || 'Score Rules',
    },
  ];

  return (
    <div data-testid="control-subnav-wrapper">
      {/* Section heading — mirrors the Settings / Workflow / Workspace pattern.
          Dark-square icon block + title with subtitle gives the Control hub the
          same breathing room every other admin section has. */}
      <div className="px-1 mb-3 sm:mb-4 flex items-start gap-3">
        <div className="w-10 h-10 rounded-2xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <Lightning size={20} weight="bold" />
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold text-[#18181B] leading-tight tracking-tight" style={{ fontFamily: 'Mazzard, Mazzard H, Mazzard M, system-ui, sans-serif' }}>
            {t('adm_control_hub_title') || 'Control Hub'}
          </h1>
          <p className="mt-0.5 text-[12px] text-[#71717A] leading-relaxed">
            {t('adm_control_hub_subtitle') || 'Business metrics, provider pressure, routing, cadences and scoring — all in one place.'}
          </p>
        </div>
      </div>

      {/* Tabs strip */}
      <div
        className="mb-5 sm:mb-6"
        data-testid="control-subnav"
      >
        <div className="overflow-x-auto scrollbar-none">
          {/* Unified PageTabs visual: white track + solid black active pill */}
          <div
            role="tablist"
            aria-label="Control sections"
            className="inline-flex p-1 bg-white border border-[#E4E4E7] rounded-2xl gap-1 max-w-full"
          >
            {tabs.map(({ to, icon: Icon, label }) => {
              const active = pathname === to;
              return (
                <NavLink
                  key={to}
                  to={to}
                  role="tab"
                  aria-selected={active}
                  className={`inline-flex items-center justify-center gap-1.5 sm:gap-2 px-3 py-2 rounded-xl text-[12px] font-semibold whitespace-nowrap shrink-0 transition-colors focus:outline-none focus-visible:ring-4 focus-visible:ring-black/10 ${
                    active
                      ? 'bg-[#18181B] text-white hover:bg-black'
                      : 'bg-transparent text-[#52525B] hover:bg-[#FAFAFA] hover:text-[#18181B]'
                  }`}
                  style={{ fontFamily: 'inherit' }}
                  data-testid={`control-tab-${to.split('/').pop()}`}
                >
                  <Icon size={14} weight="bold" />
                  <span className="truncate">{label}</span>
                </NavLink>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ControlSubNav;
