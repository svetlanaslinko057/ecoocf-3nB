/**
 * BIBI Cars — Block 6.2 — Lead SLA Badge
 * ========================================
 *
 * Compact chip showing the current SLA state for a lead.
 * Used in Lead360, LeadCard, and LeadTableView.
 *
 * Accepts either:
 *   - a precomputed ``sla`` object (from the /sla endpoint), or
 *   - raw ``lead`` props (firstResponseAt, slaRemindedAt, createdAt) +
 *     ``remindMinutes`` / ``escalateMinutes`` — falls back to client-side compute.
 */
import React, { useMemo } from 'react';
import { Clock, WarningCircle, ShieldWarning, CheckCircle } from '@phosphor-icons/react';

const STATE_STYLES = {
  green:     { bg: '#DCFCE7', fg: '#15803D', label: 'In time',     icon: Clock },
  amber:     { bg: '#FEF3C7', fg: '#92400E', label: 'Heads-up',    icon: Clock },
  overdue:   { bg: '#FEE2E2', fg: '#B91C1C', label: 'SLA breach',  icon: WarningCircle },
  escalated: { bg: '#FDE2FA', fg: '#9D174D', label: 'Escalated',   icon: ShieldWarning },
  responded: { bg: '#E0F2FE', fg: '#075985', label: 'Responded',   icon: CheckCircle },
  na:        { bg: '#F4F4F5', fg: '#52525B', label: '—',           icon: Clock },
};

export function computeSlaClient(lead, remindMinutes = 30, escalateMinutes = 120) {
  if (!lead) return { state: 'na' };
  if (lead.first_response_at || lead.firstResponseAt) return { state: 'responded' };
  const createdRaw = lead.created_at || lead.createdAt;
  if (!createdRaw) return { state: 'na' };
  const created = new Date(createdRaw);
  if (Number.isNaN(created.getTime())) return { state: 'na' };
  const elapsedMin = (Date.now() - created.getTime()) / 60000;
  if (elapsedMin >= escalateMinutes) return { state: 'escalated', minutes_elapsed: Math.round(elapsedMin) };
  if (elapsedMin >= remindMinutes)   return { state: 'overdue',   minutes_elapsed: Math.round(elapsedMin), minutes_remaining: 0 };
  if (elapsedMin >= remindMinutes * 0.5) return { state: 'amber', minutes_remaining: Math.round(remindMinutes - elapsedMin) };
  return { state: 'green', minutes_remaining: Math.round(remindMinutes - elapsedMin) };
}

const LeadSlaBadge = ({ sla, lead, remindMinutes = 30, escalateMinutes = 120, size = 'sm', showLabel = true }) => {
  const data = useMemo(() => {
    if (sla && sla.state) return sla;
    return computeSlaClient(lead || {}, remindMinutes, escalateMinutes);
  }, [sla, lead, remindMinutes, escalateMinutes]);

  const style = STATE_STYLES[data.state] || STATE_STYLES.na;
  const Icon = style.icon;

  let text = style.label;
  if (data.state === 'amber' || data.state === 'green') {
    if (typeof data.minutes_remaining === 'number') {
      text = `${data.minutes_remaining}m left`;
    }
  }
  if (data.state === 'overdue') {
    text = data.minutes_elapsed ? `Overdue ${data.minutes_elapsed}m` : 'SLA breach';
  }
  if (data.state === 'escalated') text = 'Escalated';

  const cls = size === 'xs'
    ? 'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold'
    : 'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold';

  return (
    <span
      className={cls}
      style={{ background: style.bg, color: style.fg }}
      data-testid={`lead-sla-badge-${data.state}`}
      title={data.deadline_at ? `Deadline: ${new Date(data.deadline_at).toLocaleString()}` : style.label}
    >
      <Icon size={size === 'xs' ? 10 : 12} weight="fill" />
      {showLabel ? text : null}
    </span>
  );
};

export default LeadSlaBadge;
