/**
 * LeadSiteTemperatureBadge — compact "site engagement" chip.
 *
 * PHASE: Launch-prep UX repackaging (presentation-only). Shows whether a lead /
 * customer has recently been ACTIVE ON THE WEBSITE (visited <24h / 1–7d / >7d),
 * derived from the existing site-activity telemetry — NOT from manager contact
 * recency (which the kanban heat-strip already covers). Renders nothing when
 * there is no site data, so untracked entities are never mislabelled.
 *
 * Props:
 *   - lastSeen (ISO string | null) — last site-activity timestamp
 *   - size     ('xs' | 'sm')       — default 'xs'
 *   - showLabel (bool)             — default false (dot + icon only)
 */
import React from 'react';
import { FireSimple, Thermometer, Snowflake } from '@phosphor-icons/react';
import { useLang } from '../../i18n';
import {
  TEMP_META,
  temperatureFromLastSeen,
  temperatureLabel,
  temperatureHint,
} from '../shared/activityLabels';

const ICONS = { hot: FireSimple, warm: Thermometer, cold: Snowflake };

const LeadSiteTemperatureBadge = ({ lastSeen, size = 'xs', showLabel = false }) => {
  const { lang } = useLang() || { lang: 'uk' };
  const key = temperatureFromLastSeen(lastSeen);
  if (!key) return null; // no site data → no badge

  const meta = TEMP_META[key];
  const Icon = ICONS[key] || Thermometer;
  const label = temperatureLabel(key, lang);
  const hint = temperatureHint(key, lang);
  const iconSize = size === 'sm' ? 12 : 11;

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border font-semibold leading-none whitespace-nowrap"
      style={{
        backgroundColor: meta.bg,
        color: meta.fg,
        borderColor: meta.ring,
        padding: showLabel ? '2px 7px' : '2px 5px',
        fontSize: size === 'sm' ? 11 : 10,
      }}
      title={`${label} — ${hint}`}
      data-testid={`lead-site-temp-${key}`}
      aria-label={`${label}: ${hint}`}
    >
      <Icon size={iconSize} weight="duotone" />
      {showLabel ? label : null}
    </span>
  );
};

export default LeadSiteTemperatureBadge;
