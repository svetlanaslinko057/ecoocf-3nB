import React from 'react';
import * as Icons from '@phosphor-icons/react';

const formatWhen = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch { return String(iso); }
};

const LeadTimelinePanel = ({ items, loading, emptyText = 'No events yet' }) => {
  if (loading) return <div className="text-[12px] text-[#71717A] py-6 text-center">Loading…</div>;
  if (!items || items.length === 0) return <div className="text-[12px] text-[#A1A1AA] italic py-6 text-center">{emptyText}</div>;
  return (
    <div className="relative pl-7" data-testid="lead-timeline-panel">
      <div className="absolute left-2 top-3 bottom-3 w-px bg-[#E4E4E7]"></div>
      <ul className="space-y-3">
        {items.map((e, idx) => {
          const IconCmp = (Icons[e.icon] || Icons.Clock);
          return (
            <li key={e.id || idx} className="relative" data-testid={`lead-timeline-event-${idx}`}>
              <div
                className="absolute -left-7 top-1 w-5 h-5 rounded-full border-2 border-white shadow-sm flex items-center justify-center text-white"
                style={{ backgroundColor: e.color || '#71717A' }}
              >
                <IconCmp size={10} weight="bold" />
              </div>
              <div className="bg-white border border-[#F4F4F5] rounded-xl px-3 py-2 hover:border-[#E4E4E7] transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-[13px] font-semibold text-[#18181B] leading-tight">{e.title}</div>
                  <span className="text-[10px] text-[#A1A1AA] whitespace-nowrap shrink-0">{formatWhen(e.at)}</span>
                </div>
                {e.subtitle ? (
                  <div className="text-[11px] text-[#71717A] mt-1 break-words">{e.subtitle}</div>
                ) : null}
                {e.by ? (
                  <div className="text-[10px] text-[#A1A1AA] mt-1">by {e.by}</div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default LeadTimelinePanel;
