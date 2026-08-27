/**
 * AdminSeoCenter — hub layout for the Admin SEO Center (Phase B2).
 *
 * Provides the shared header, tabbed nav and <Outlet/> for the six
 * sub-consoles (settings / company / analytics / pages / sitemap / robots).
 *
 * Every setting is admin-managed — nothing (domain, EDRPOU, license, GA4,
 * OG image, robots, etc.) is hardcoded in the source anymore.
 */
import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  Gear, Buildings, ChartLineUp, FileText, MapTrifold, Robot, MagnifyingGlass, Lightning,
} from '@phosphor-icons/react';
import HelpTooltip from '../../../components/ui/HelpTooltip';

const TABS = [
  { to: '/app/seo/settings',  label: 'Глобальні',   icon: Gear,        hint: 'Домен, мова, canonical, індексація' },
  { to: '/app/seo/company',   label: 'Компанія',    icon: Buildings,   hint: 'E-E-A-T: юр.особа, ліцензія, адреса, контакти' },
  { to: '/app/seo/analytics', label: 'Аналітика',   icon: ChartLineUp, hint: 'GA4, GTM, Google Ads, Pixel, верифікації' },
  { to: '/app/seo/pages',     label: 'Сторінки',    icon: FileText,    hint: 'Метадані per-route + FAQ + breadcrumbs' },
  { to: '/app/seo/sitemap',   label: 'Sitemap',     icon: MapTrifold,  hint: 'Прев\u2019ю та регенерація sitemap' },
  { to: '/app/seo/robots',    label: 'Robots.txt',  icon: Robot,       hint: 'Індексація, disallow/allow, sitemap URL' },
  { to: '/app/seo/prerender', label: 'Prerender',   icon: Lightning,   hint: 'HTML для ботів: кеш, метрики, теплення' },
];

const AdminSeoCenter = () => {
  const location = useLocation();
  const active = TABS.find(t => location.pathname === t.to || location.pathname.startsWith(`${t.to}/`)) || TABS[0];
  return (
    <div className="space-y-5" data-testid="admin-seo-center">
      {/* Header */}
      <div className="flex items-start gap-3 flex-wrap">
        <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <MagnifyingGlass size={18} weight="bold" />
        </div>
        <div className="flex-1 min-w-0">
          <HelpTooltip text="Центр SEO: керується з адмінки. Домен, компанія (E-E-A-T), верифікації, теги, per-route мета, sitemap і robots — все без редеплою." side="bottom" align="start">
            <h1 className="inline text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight cursor-help underline decoration-dotted decoration-1 decoration-[#A1A1AA] underline-offset-4" data-testid="seo-center-title">
              SEO Center
            </h1>
          </HelpTooltip>
          <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed max-w-3xl">
            {active.hint}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-[#E4E4E7] overflow-x-auto">
        <div className="flex items-stretch gap-1 min-w-max">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) => `
                  inline-flex items-center gap-2 px-3.5 py-2 -mb-px border-b-2 text-[13px] font-medium transition
                  ${isActive
                    ? 'text-[#18181B] border-emerald-600'
                    : 'text-[#71717A] border-transparent hover:text-[#18181B]'}
                `}
                data-testid={`seo-tab-${tab.to.split('/').pop()}`}
              >
                <Icon size={15} weight="bold" />
                {tab.label}
              </NavLink>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div>
        <Outlet />
      </div>
    </div>
  );
};

export default AdminSeoCenter;
