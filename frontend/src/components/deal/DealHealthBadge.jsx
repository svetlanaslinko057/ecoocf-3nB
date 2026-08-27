/**
 * Wave 6 — DealHealthBadge
 * Renders the computed health state (never stored on the deal).
 * Shape: { state, reason, i18n_key, pipeline_stage }
 */
import React from 'react';
import { CheckCircle, Clock, Warning, XCircle, ShieldWarning, Hourglass } from '@phosphor-icons/react';

const HEALTH_STYLE = {
  healthy:          { bg: '#DCFCE7', fg: '#14532D', label: 'Healthy',          Icon: CheckCircle },
  waiting_customer: { bg: '#FEF3C7', fg: '#92400E', label: 'Waiting Customer', Icon: Hourglass },
  blocked:          { bg: '#FEE2E2', fg: '#991B1B', label: 'Blocked',          Icon: ShieldWarning },
  overdue:          { bg: '#FFE4E6', fg: '#9F1239', label: 'Overdue',          Icon: Clock },
  risk:             { bg: '#FFEDD5', fg: '#9A3412', label: 'Risk',             Icon: Warning },
  cancelled:        { bg: '#F4F4F5', fg: '#3F3F46', label: 'Cancelled',        Icon: XCircle },
};

export default function DealHealthBadge({ health, size = 'md', className = '' }) {
  if (!health) return null;
  const s = HEALTH_STYLE[health.state] || HEALTH_STYLE.healthy;
  const { Icon } = s;
  const pad = size === 'sm' ? '2px 8px' : '6px 12px';
  const fs  = size === 'sm' ? 11 : 13;
  const iconSize = size === 'sm' ? 14 : 16;
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold rounded-md ${className}`}
      style={{ background: s.bg, color: s.fg, padding: pad, fontSize: fs, lineHeight: 1.2 }}
      title={health.reason || s.label}
      data-testid="deal-health-badge"
    >
      <Icon size={iconSize} weight="fill" />
      <span>{s.label}</span>
    </span>
  );
}
