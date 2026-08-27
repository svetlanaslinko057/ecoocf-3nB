import React, { useState } from 'react';
import {
  UsersThree,
  ListChecks,
  ChartLineUp,
  IdentificationCard,
  Info,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

/**
 * RoleZoneBadge (formerly SharedZoneBadge — CRM variant kept for backward
 * compatibility via the default export below).
 * ───────────────────────────────────────────────────────────────────
 *
 * Visual marker used at the top of any page that is intentionally
 * shared across roles. The point is *cognitive consistency* — the user
 * must instantly understand:
 *
 *   "This is the SAME entity (humans / tasks / KPIs) — I'm just looking
 *    at it through a different role-specific viewport."
 *
 * Variants:
 *   • crm        — Customers / Leads / Legal workflow (Manager · Team-lead · Admin)
 *   • hr         — Staff registry + Manager Load Board (one `users` collection)
 *   • tasks      — Admin allocator / Team-lead coordinator / Manager executor
 *   • dashboard  — A slice of the master dashboard (Team Dashboard = team subset)
 *
 * Renders:
 *   ┌──────────────────────────────────────────────────────┐
 *   │  ⚙  Shared Tasks zone                            ⓘ    │
 *   │     Admin · Team-lead · Manager                       │
 *   └──────────────────────────────────────────────────────┘
 *
 * Hover popover (dark style, same as Dashboard.js tooltips) explains
 * the role split. Mobile: tap-to-toggle.
 */

// Unified visual style — ALL variants use the canonical PURPLE palette
// (matching CRM "Shared CRM zone" badge). This is the design lead's
// June-2026 decision: cognitive consistency across HR / Tasks / Dashboard /
// CRM means SAME color, only the icon + label change.
const PURPLE_STYLE = {
  iconBg: 'bg-violet-100',
  iconFg: 'text-[#7C3AED]',
  border: 'border-[#A78BFA]/60',
  bg: 'bg-[#F5F3FF]',
  fg: 'text-[#5B21B6]',
  subFg: 'text-[#7C3AED]/80',
};

const VARIANTS = {
  crm: {
    icon: UsersThree,
    ...PURPLE_STYLE,
    badgeKey: 'rzb_crm_title',
    rolesKey: 'rzb_crm_roles',
    tipKey:   'rzb_crm_tip',
    fallbackTitle: 'Shared CRM zone',
    fallbackRoles: 'Manager · Team-lead · Admin',
    fallbackTip:
      "This page is duplicated for managers and team-leads — it's their day-to-day responsibility. Admin sees the exact same CRM logic but is not expected to create leads / customers manually.",
  },
  hr: {
    icon: IdentificationCard,
    ...PURPLE_STYLE,
    badgeKey: 'rzb_hr_title',
    rolesKey: 'rzb_hr_roles',
    tipKey:   'rzb_hr_tip',
    fallbackTitle: 'Shared HR zone',
    fallbackRoles: 'Admin · Team-lead · Manager',
    fallbackTip:
      "Same people, two viewports. The Staff registry is the HR side (CRUD, roles, status). The Manager Load Board is the workload/perf side. Both read from the same `users` collection.",
  },
  tasks: {
    icon: ListChecks,
    ...PURPLE_STYLE,
    badgeKey: 'rzb_tasks_title',
    rolesKey: 'rzb_tasks_roles',
    tipKey:   'rzb_tasks_tip',
    fallbackTitle: 'Shared Tasks zone',
    fallbackRoles: 'Admin allocator · Team-lead coordinator · Manager executor',
    fallbackTip:
      "All three pages read from the same `tasks` collection. Admin = free-form CRUD; Team-lead = team-wide coordination & overdue triage; Manager = single-active-task executor queue. Same data, different operational mode.",
  },
  dashboard: {
    icon: ChartLineUp,
    ...PURPLE_STYLE,
    badgeKey: 'rzb_dashboard_title',
    rolesKey: 'rzb_dashboard_roles',
    tipKey:   'rzb_dashboard_tip',
    fallbackTitle: 'Team slice of master dashboard',
    fallbackRoles: 'Subset of /admin/ KPIs',
    fallbackTip:
      "This dashboard is a focused slice of the master /admin/ dashboard — same data sources, narrower scope (team-only). The master dashboard is the source of truth for cross-team metrics.",
  },
  wave360: {
    icon: ChartLineUp,
    ...PURPLE_STYLE,
    badgeKey: 'rzb_wave360_title',
    rolesKey: 'rzb_wave360_roles',
    tipKey:   'rzb_wave360_tip',
    fallbackTitle: 'Shared 360 zone',
    fallbackRoles: 'Admin · Team-lead · Manager',
    fallbackTip:
      "Same 360° dataset rendered through three role viewports. Admin sees the full company-wide scope; Team-lead sees their team's slice; Manager sees their own deals. The data engine is identical — only the WHERE clause differs.",
  },
};

const RoleZoneBadge = ({
  variant = 'crm',
  className = '',
  // Optional cross-link rendered next to the badge as a thin pill
  link,   // { href, label }
}) => {
  const { t } = useLang();
  const [showTip, setShowTip] = useState(false);
  const cfg = VARIANTS[variant] || VARIANTS.crm;
  const Icon = cfg.icon;

  // Backward-compat for CRM legacy keys (so we don't have to migrate all 3
  // locales at once — the new generic keys fall back to the old ones).
  const title =
    t(cfg.badgeKey) || t('shared_crm_badge') || cfg.fallbackTitle;
  const roles =
    t(cfg.rolesKey) || t('shared_crm_roles') || cfg.fallbackRoles;
  const tip =
    t(cfg.tipKey) || t('shared_crm_tooltip') || cfg.fallbackTip;

  return (
    <div className={`hidden sm:inline-flex items-center gap-2 flex-wrap ${className}`}>
      <div
        className={`relative inline-flex items-center gap-2 rounded-xl border border-dashed ${cfg.border} ${cfg.bg} px-3 py-1.5 ${cfg.fg}`}
        data-testid={`role-zone-badge-${variant}`}
        onMouseEnter={() => setShowTip(true)}
        onMouseLeave={() => setShowTip(false)}
        onClick={() => setShowTip((v) => !v)}
        role="note"
        aria-label={title}
      >
        <span className={`p-1 rounded-lg ${cfg.iconBg} ${cfg.iconFg} flex-shrink-0`}>
          <Icon size={14} weight="duotone" />
        </span>
        <div className="flex flex-col leading-tight min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-wider truncate">
            {/* fallback for variants whose i18n keys are absent — show fallback text directly */}
            {title === cfg.badgeKey ? cfg.fallbackTitle : title}
          </span>
          <span className={`text-[10px] ${cfg.subFg} truncate hidden sm:inline`}>
            {roles === cfg.rolesKey ? cfg.fallbackRoles : roles}
          </span>
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); setShowTip((v) => !v); }}
          className="ml-0.5 rounded-full p-0.5 hover:bg-black/5 transition-colors"
          aria-label="Info"
          data-testid={`role-zone-info-${variant}`}
        >
          <Info size={14} weight="bold" className={cfg.iconFg} />
        </button>

        {showTip && (
          <div
            role="tooltip"
            className="absolute top-full left-0 mt-2 z-50 w-[280px] sm:w-[340px] rounded-xl bg-[#18181B] text-white text-[12px] leading-relaxed px-3 py-2.5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            {tip === cfg.tipKey ? cfg.fallbackTip : tip}
            <div className="absolute -top-1 left-4 w-2 h-2 bg-[#18181B] rotate-45" />
          </div>
        )}
      </div>

      {link?.href && (
        <a
          href={link.href}
          className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-lg border ${cfg.border} ${cfg.bg} ${cfg.fg} hover:bg-white/60 transition-colors`}
          data-testid={`role-zone-link-${variant}`}
        >
          {link.label}
          <span aria-hidden="true">↗</span>
        </a>
      )}
    </div>
  );
};

export default RoleZoneBadge;
