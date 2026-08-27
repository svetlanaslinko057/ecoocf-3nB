import React from 'react';
import {
  Clock, NotePencil, CurrencyEur, Cube, FileText, Trophy, Truck, CheckCircle, XCircle, ArrowsClockwise,
} from '@phosphor-icons/react';

const ICONS = {
  deal_created:       Cube,
  stage_changed:      ArrowsClockwise,
  deposit_requested:  CurrencyEur,
  deposit_confirmed:  CurrencyEur,
  deposit_refunded:   CurrencyEur,
  deposit_forfeited:  CurrencyEur,
  contract_sent:      FileText,
  contract_signed:    FileText,
  payment_received:   CurrencyEur,
  auction_won:        Trophy,
  auction_lost:       XCircle,
  shipping_started:   Truck,
  customs_cleared:    CheckCircle,
  delivered:          CheckCircle,
  cancelled:          XCircle,
  note_added:         NotePencil,
  owner_changed:      ArrowsClockwise,
};

const DealTimelineTab = ({ timeline = [] }) => {
  if (!timeline.length) {
    return (
      <div className="bg-white border border-[#E4E4E7] rounded-2xl p-8 text-center" data-testid="deal-timeline-empty">
        <Clock size={32} className="mx-auto text-[#A1A1AA] mb-2" />
        <div className="text-[#71717A]">No events yet</div>
      </div>
    );
  }

  return (
    <div className="relative bg-white border border-[#E4E4E7] rounded-2xl p-4" data-testid="deal-timeline-tab">
      <div className="absolute left-7 top-4 bottom-4 w-px bg-[#E4E4E7]" />
      <ul className="space-y-3">
        {timeline.map((e, i) => {
          const Icon = ICONS[e.event_type] || Clock;
          return (
            <li key={e.id || i} className="relative pl-10">
              <div className="absolute left-3 top-0 w-7 h-7 rounded-full bg-white border border-[#E4E4E7] flex items-center justify-center text-[#52525B]">
                <Icon size={14} weight="bold" />
              </div>
              <div className="bg-[#FAFAFA] border border-[#F4F4F5] rounded-xl px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] uppercase tracking-wider font-bold text-[#52525B]">{(e.event_type || '').replace(/_/g, ' ')}</span>
                  <span className="text-[11px] text-[#A1A1AA] whitespace-nowrap">{e.at ? new Date(e.at).toLocaleString() : ''}</span>
                </div>
                <div className="text-sm text-[#18181B] mt-0.5">{e.message}</div>
                {e.actor?.email ? (
                  <div className="text-[11px] text-[#71717A] mt-1">— {e.actor.email}</div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default DealTimelineTab;
