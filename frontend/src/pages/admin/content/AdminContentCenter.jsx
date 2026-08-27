/**
 * Content Center layout — Phase D1.
 *
 * Left rail: Pages / Media / FAQ (three sub-sections).
 * Right pane: React-Router outlet.
 *
 * Matches the visual language of AdminSeoCenter so the two consoles feel
 * like siblings under one "Content & SEO" cluster.
 */
import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  FileText, Image as ImageIcon, Question, House, ArrowSquareOut, SquaresFour,
} from '@phosphor-icons/react';

const NAV = [
  { to: 'pages',  label: 'Сторінки',        icon: FileText,  hint: 'Content Center — CMS-керовані сторінки' },
  { to: 'catalog', label: 'Каталог відходів', icon: SquaresFour, hint: 'Категорії каталогу: іконки, назви UA/EN, коди' },
  { to: 'media',  label: 'Медіа-бібліотека', icon: ImageIcon, hint: 'Зображення, PDF, alt / кепшени' },
  { to: 'faq',    label: 'FAQ Engine',       icon: Question,  hint: 'Глобальні та пер-сторінкові FAQ' },
];

export default function AdminContentCenter() {
  const loc = useLocation();
  const inside = loc.pathname.replace(/^\/app\/content\/?/, '');

  return (
    <div className="min-h-[calc(100vh-64px)] bg-[#FAFAFA]">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2 text-[11.5px] text-[#71717A] uppercase tracking-wider">
              <House size={12} weight="bold" /> Content Platform • Phase D1
            </div>
            <h1 className="mt-1 text-[22px] font-semibold text-[#18181B] leading-tight">Content Center</h1>
            <p className="mt-1 text-[13px] text-[#52525B] max-w-[680px]">
              Блокова СМС для публічних сторінок. Керуйте контентом, медіа та FAQ; кожна
              публікація автоматично оновлює prerender-кеш і SEO-метадані.
            </p>
          </div>
          <a
            href="/app/seo/prerender"
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[12.5px] font-medium text-[#3F3F46] hover:bg-[#F4F4F5]"
          >
            <ArrowSquareOut size={13} weight="bold" /> Prerender Cache
          </a>
        </div>

        {/* Sub-nav */}
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-5">
          <nav className="lg:sticky lg:top-4 self-start rounded-2xl border border-[#E4E4E7] bg-white p-2 space-y-0.5">
            {NAV.map(({ to, label, icon: Icon, hint }) => (
              <NavLink
                key={to}
                to={to}
                data-testid={`content-nav-${to}`}
                className={({ isActive }) =>
                  `flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-[13px] transition ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                      : 'text-[#3F3F46] hover:bg-[#F4F4F5] border border-transparent'
                  }`
                }
              >
                <Icon size={15} weight="bold" className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{label}</div>
                  <div className="text-[11px] text-[#71717A] mt-0.5 leading-snug">{hint}</div>
                </div>
              </NavLink>
            ))}
          </nav>

          <div className="min-w-0">
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  );
}
