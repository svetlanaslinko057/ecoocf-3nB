import React from 'react';
import { Car, ArrowSquareOut, Receipt, Tag } from '@phosphor-icons/react';
import { Link } from 'react-router-dom';

const SOURCE_BADGE = {
  lead:       { label: 'Interest',   cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  calculator: { label: 'Calculator', cls: 'bg-violet-50 text-violet-700 border-violet-200' },
  quote:      { label: 'Quote',      cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
};

const LeadRelatedCars = ({ items, loading }) => {
  if (loading) return <div className="text-[12px] text-[#71717A] text-center py-6">Loading…</div>;
  if (!items || items.length === 0) {
    return (
      <div className="text-[12px] text-[#A1A1AA] italic text-center py-8">
        Немає повʼязаних авто — джерело VIN/calculator/quote
      </div>
    );
  }

  return (
    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="lead-related-cars">
      {items.map((c, idx) => {
        const badge = SOURCE_BADGE[c.source] || { label: c.source, cls: 'bg-zinc-100 text-zinc-700 border-zinc-200' };
        const linkProps = c.link ? { to: c.link } : null;
        const Wrap = linkProps ? Link : 'div';
        return (
          <Wrap
            key={idx}
            {...(linkProps || {})}
            className="block bg-white border border-[#E4E4E7] rounded-2xl p-3 hover:border-[#A1A1AA] hover:shadow-sm transition-all"
            data-testid={`lead-related-car-${idx}`}
          >
            <div className="flex items-start gap-2">
              <div className="w-9 h-9 rounded-lg bg-[#F4F4F5] flex items-center justify-center shrink-0">
                <Car size={18} weight="duotone" className="text-[#18181B]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className={`inline-block text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border ${badge.cls}`}>
                    {badge.label}
                  </span>
                  {c.link ? <ArrowSquareOut size={11} className="text-[#A1A1AA]" /> : null}
                </div>
                <div className="text-[13px] font-semibold text-[#18181B] mt-1 truncate">
                  {c.title || c.vin || '—'}
                </div>
                {c.vin ? (
                  <div className="text-[10px] font-mono text-[#71717A] mt-0.5 truncate">VIN: {c.vin}</div>
                ) : null}
                {(c.price || c.price === 0) ? (
                  <div className="text-[12px] font-bold text-[#15803D] mt-1 tabular-nums">
                    {(c.currency || 'EUR') === 'EUR' ? '€' : ''}
                    {Number(c.price).toLocaleString()} {(c.currency && c.currency !== 'EUR') ? c.currency : ''}
                  </div>
                ) : null}
              </div>
            </div>
          </Wrap>
        );
      })}
    </ul>
  );
};

export default LeadRelatedCars;
