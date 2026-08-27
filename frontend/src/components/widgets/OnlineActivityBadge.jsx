/**
 * OnlineActivityBadge — visual chip showing site online status (Доопр #19).
 *
 * Props:
 *   - status: 'callback' | 'online_now' | 'recent' | 'offline' | undefined
 *   - minutesAgo: number
 *   - compact: boolean — when true, only colored dot is rendered
 */
import React from 'react';

const STYLE_BY_STATUS = {
  callback:   { bg: '#FEE2E2', fg: '#B91C1C', dot: '#DC2626', label: 'Callback' },
  online_now: { bg: '#DCFCE7', fg: '#166534', dot: '#16A34A', label: 'Online' },
  recent:     { bg: '#FEF3C7', fg: '#92400E', dot: '#D97706', label: 'Recent' },
  offline:    { bg: '#F4F4F5', fg: '#71717A', dot: '#A1A1AA', label: 'Offline' },
};

export default function OnlineActivityBadge({ status, minutesAgo, compact = false }) {
  const st = STYLE_BY_STATUS[status] || STYLE_BY_STATUS.offline;
  if (compact) {
    return (
      <span
        title={`${st.label}${typeof minutesAgo === 'number' ? ` · ${minutesAgo} min ago` : ''}`}
        className="inline-block w-2 h-2 rounded-full shrink-0"
        style={{ backgroundColor: st.dot }}
        data-testid={`online-dot-${status || 'offline'}`}
      />
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10.5px] font-semibold"
      style={{ backgroundColor: st.bg, color: st.fg }}
      data-testid={`online-badge-${status || 'offline'}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: st.dot }} />
      {st.label}
      {typeof minutesAgo === 'number' && status !== 'offline' && (
        <span className="text-[10px] opacity-70">· {minutesAgo}m</span>
      )}
    </span>
  );
}
