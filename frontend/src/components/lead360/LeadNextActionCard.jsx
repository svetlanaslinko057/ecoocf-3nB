import React from 'react';
import { Phone, Receipt, CheckCircle, Lightning, Archive, UserCircle, ArrowsClockwise, ArrowRight } from '@phosphor-icons/react';
import { useNavigate } from 'react-router-dom';

const ICON_BY_KIND = {
  first_call:    Phone,
  qualify:       Phone,
  send_quote:    Receipt,
  close_deal:    CheckCircle,
  follow_up:     Phone,
  reanimate:     ArrowsClockwise,
  complete_task: Lightning,
  archive:       Archive,
  view_customer: UserCircle,
  call:          Phone,
};

const URGENCY = {
  critical: { ring: 'ring-2 ring-[#DC2626]', dot: 'bg-[#DC2626]', label: 'CRITICAL' },
  high:     { ring: 'ring-2 ring-[#F59E0B]', dot: 'bg-[#F59E0B]', label: 'HIGH' },
  normal:   { ring: 'ring-1 ring-[#E4E4E7]', dot: 'bg-[#3B82F6]', label: 'NORMAL' },
  low:      { ring: 'ring-1 ring-[#E4E4E7]', dot: 'bg-[#71717A]', label: 'LOW' },
  none:     { ring: 'ring-1 ring-[#E4E4E7]', dot: 'bg-[#A1A1AA]', label: '' },
};

const LeadNextActionCard = ({ health, lead, onCall }) => {
  const navigate = useNavigate();
  const next = (health || {}).next_action;
  if (!next) return null;
  const Icon = ICON_BY_KIND[next.kind] || Phone;
  const u = URGENCY[next.urgency] || URGENCY.normal;

  const onClick = () => {
    if (next.kind === 'view_customer' && next.customer_id) {
      navigate(`/admin/customers/${next.customer_id}/360`);
      return;
    }
    if (next.phone || lead?.phone) {
      const ph = String(next.phone || lead.phone).replace(/\s+/g, '');
      if (onCall) onCall(ph);
      else window.location.href = `tel:${ph}`;
      return;
    }
  };

  const ctaLabel = (() => {
    if (next.kind === 'view_customer') return 'Open customer';
    if (next.kind === 'archive')       return 'Archive';
    if (next.kind === 'send_quote')    return 'Send proposal';
    if (next.kind === 'complete_task') return 'Open task';
    if (next.phone || lead?.phone)     return 'Call now';
    return 'Take action';
  })();

  return (
    <div
      className={`bg-white rounded-2xl p-4 ${u.ring} shadow-sm`}
      data-testid="lead-next-action-card"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] uppercase tracking-wider font-bold text-[#71717A]">Next Action</div>
        {u.label ? (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-[#52525B]">
            <span className={`w-1.5 h-1.5 rounded-full ${u.dot}`}></span> {u.label}
          </span>
        ) : null}
      </div>

      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-[#F4F4F5] flex items-center justify-center shrink-0">
          <Icon size={20} weight="duotone" className="text-[#18181B]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-bold text-[#18181B] leading-tight">{next.title}</div>
          {next.phone || lead?.phone ? (
            <div className="text-[12px] text-[#71717A] mt-0.5 truncate">{next.phone || lead?.phone}</div>
          ) : null}
        </div>
      </div>

      <button
        onClick={onClick}
        className="mt-3 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[13px] bg-[#18181B] hover:bg-black text-white rounded-xl font-semibold transition-colors"
        data-testid="lead-next-action-cta"
      >
        {ctaLabel}
        <ArrowRight size={14} weight="bold" />
      </button>
    </div>
  );
};

export default LeadNextActionCard;
