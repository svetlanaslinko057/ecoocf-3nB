/**
 * Wave 6 — PipelineStageBadge
 * Canonical 10-stage badge. Pure presentational. No state, no fetches.
 */
import React from 'react';

const STAGE_LABELS = {
  inquiry:          'Inquiry',
  negotiating:      'Negotiating',
  awaiting_deposit: 'Awaiting Deposit',
  deposit_paid:     'Deposit Paid',
  bidding:          'Bidding',
  won:              'Won',
  contract_signed:  'Contract Signed',
  shipping:         'Shipping',
  delivered:        'Delivered',
  cancelled:        'Cancelled',
};

const STAGE_COLORS = {
  inquiry:          { bg: '#E0E7FF', fg: '#4338CA', dot: '#6366F1' },
  negotiating:      { bg: '#FEF3C7', fg: '#92400E', dot: '#D97706' },
  awaiting_deposit: { bg: '#FEE2E2', fg: '#991B1B', dot: '#DC2626' },
  deposit_paid:     { bg: '#D1FAE5', fg: '#065F46', dot: '#059669' },
  bidding:          { bg: '#FDF4FF', fg: '#86198F', dot: '#C026D3' },
  won:              { bg: '#DBEAFE', fg: '#1E40AF', dot: '#2563EB' },
  contract_signed:  { bg: '#E0F2FE', fg: '#075985', dot: '#0284C7' },
  shipping:         { bg: '#EDE9FE', fg: '#5B21B6', dot: '#7C3AED' },
  delivered:        { bg: '#DCFCE7', fg: '#14532D', dot: '#16A34A' },
  cancelled:        { bg: '#F4F4F5', fg: '#3F3F46', dot: '#71717A' },
};

export default function PipelineStageBadge({ stage, size = 'md', className = '' }) {
  const s = stage || 'inquiry';
  const label = STAGE_LABELS[s] || s;
  const c = STAGE_COLORS[s] || STAGE_COLORS.inquiry;
  const pad = size === 'sm' ? '2px 8px' : '4px 12px';
  const fs  = size === 'sm' ? 11 : 13;
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold rounded-full ${className}`}
      style={{ background: c.bg, color: c.fg, padding: pad, fontSize: fs, lineHeight: 1.2 }}
    >
      <span
        aria-hidden
        style={{
          width: 6, height: 6, borderRadius: 9999,
          background: c.dot, display: 'inline-block',
        }}
      />
      {label}
    </span>
  );
}
