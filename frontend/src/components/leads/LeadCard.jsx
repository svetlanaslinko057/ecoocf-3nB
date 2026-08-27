import React from 'react';
import { Phone, Car, EnvelopeSimple, CurrencyEur, User, ArrowsClockwise } from '@phosphor-icons/react';
import { STATUS_THEME, sourceLabel } from './leadConstants';
import LeadPriorityBadge from './LeadPriorityBadge';

/**
 * Wave 8 + Wave 10B Kanban card.
 *
 *   - Top border colored by status (Wave 8)
 *   - LEFT strip colored by heat (Wave 10B) — visual urgency
 *   - Top-right: priority A/B/C/D bucket badge (Wave 10A)
 *   - Bottom-right: source chip + reassign on hover
 */
const HEAT_HEX = {
  green:   '#10B981',
  yellow:  '#F59E0B',
  orange:  '#FB923C',
  red:     '#DC2626',
  success: '#16A34A',
  neutral: 'transparent',
};

const LeadCard = ({ lead, lang, managers, onOpen, onReassign, canReassign, isDragging }) => {
  const mgr = lead.managerId ? (managers || {})[lead.managerId] : null;
  const theme = STATUS_THEME[lead.status] || STATUS_THEME.new;
  const heat = HEAT_HEX[lead.heatColor] || 'transparent';

  return (
    <div
      onClick={onOpen}
      data-testid={`lead-kanban-card-${lead.id}`}
      data-heat={lead.heatColor || 'neutral'}
      data-priority={lead.priorityBucket || ''}
      className={`group relative bg-white border rounded-xl pl-4 pr-3 pt-2.5 pb-3 cursor-grab active:cursor-grabbing shadow-sm hover:shadow-md transition-all
                  ${isDragging ? 'shadow-xl ring-2 ring-[#4F46E5] -rotate-1 scale-[1.02]' : 'border-[#E4E4E7] hover:border-[#A1A1AA]'}`}
      style={{ borderTopColor: theme.hex, borderTopWidth: 3 }}
    >
      {/* Heatmap left strip */}
      <span
        aria-hidden
        className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl"
        style={{ backgroundColor: heat }}
      />

      {/* Header — name + priority + phone */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-[#18181B] text-sm leading-tight truncate" title={`${lead.firstName||''} ${lead.lastName||''}`}>
            {lead.firstName} {lead.lastName}
            {!lead.firstName && !lead.lastName ? (lead.name || '—') : null}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {lead.priorityBucket ? (
            <LeadPriorityBadge
              bucket={lead.priorityBucket}
              size="xs"
              showLabel={false}
              testId={`lead-card-priority-${lead.id}`}
            />
          ) : null}
          {lead.phone ? (
            <a
              href={`tel:${String(lead.phone).replace(/\s+/g,'')}`}
              onClick={(e) => e.stopPropagation()}
              className="shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-lg bg-[#F4F4F5] hover:bg-[#4F46E5] hover:text-white text-[#52525B] transition-colors"
              title={lead.phone}
              data-testid={`lead-kanban-call-${lead.id}`}
            >
              <Phone size={14} weight="fill" />
            </a>
          ) : null}
        </div>
      </div>

      {/* Phone visible */}
      {lead.phone ? (
        <div className="text-[12px] text-[#52525B] font-medium tabular-nums truncate mb-1.5">{lead.phone}</div>
      ) : null}

      {/* Vehicle interest */}
      {(lead.vehicleInterest || lead.vin) ? (
        <div className="flex items-center gap-1.5 text-[11px] text-[#71717A] mb-1.5">
          <span className="inline-flex items-center gap-1 truncate">
            <Car size={12} className="shrink-0" />
            <span className="truncate">{lead.vehicleInterest || lead.vin}</span>
          </span>
        </div>
      ) : null}

      {/* Budget */}
      {(lead.budgetEur || lead.budgetUsd) ? (
        <div className="flex items-center gap-1 text-[11px] font-semibold text-[#15803D] mb-1.5">
          <CurrencyEur size={12} weight="bold" />
          {Number(lead.budgetEur || lead.budgetUsd).toLocaleString()}
        </div>
      ) : null}

      {/* Footer — manager + source + days-since chip */}
      <div className="flex items-center justify-between gap-1.5 pt-1.5 border-t border-[#F4F4F5]">
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          {mgr ? (
            <>
              <div className="w-5 h-5 rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] text-white flex items-center justify-center font-semibold text-[9px] shrink-0">
                {(mgr.name || mgr.email || '?').slice(0,1).toUpperCase()}
              </div>
              <span className="text-[10px] text-[#52525B] truncate">{mgr.name || mgr.email}</span>
            </>
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] text-[#A1A1AA] italic">
              <User size={11} /> unassigned
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {typeof lead.daysSinceContact === 'number' ? (
            <span
              className="text-[9px] font-bold tabular-nums px-1 rounded"
              style={{ color: heat !== 'transparent' ? heat : '#A1A1AA' }}
              title={
                lead.lastContactAt
                  ? `Last contact: ${new Date(lead.lastContactAt).toLocaleString()} (${lead.daysSinceContact}d ago)`
                  : `Last contact: ${lead.daysSinceContact}d ago`
              }
            >
              {Math.round(lead.daysSinceContact)}d
            </span>
          ) : null}
          {lead.source ? (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#F4F4F5] text-[#52525B]">
              {sourceLabel(lang, lead.source)}
            </span>
          ) : null}
          {canReassign ? (
            <button
              onClick={(e) => { e.stopPropagation(); onReassign && onReassign(lead); }}
              className="p-1 rounded hover:bg-[#EEF2FF] text-[#4F46E5] opacity-0 group-hover:opacity-100 transition-opacity"
              title="Reassign"
              data-testid={`lead-kanban-reassign-${lead.id}`}
            >
              <ArrowsClockwise size={12} weight="bold" />
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default LeadCard;
