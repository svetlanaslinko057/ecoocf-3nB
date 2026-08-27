import React, { useState } from 'react';
import { Info } from '@phosphor-icons/react';

/**
 * LabelWithTip — replaces programmer-style labels (`max_bid_usd`, `fx`)
 * with human-readable text + an Info icon that surfaces a contextual
 * explanation on hover/tap.
 *
 * Wave 5 — applied across Legal & Pipeline Workflow so a manager (not a
 * developer) can understand every field at a glance.
 *
 * Props
 * ─────
 *  label    — visible field label (translated)
 *  hint     — popover text shown on hover/click (translated)
 *  required — render a red asterisk
 *  example  — optional small grey hint shown under the field
 *  htmlFor  — optional `for=` association for the input
 *
 *  ┌──────────────────────────────────────────────┐
 *  │  MAXIMUM AUCTION BUDGET *  ⓘ                 │
 *  │  e.g. 35 000 — what the client agrees to bid │
 *  └──────────────────────────────────────────────┘
 */
const LabelWithTip = ({ label, hint, required, example, htmlFor, className = '' }) => {
  const [open, setOpen] = useState(false);

  return (
    <div className={`mb-2 ${className}`}>
      <div className="flex items-center gap-1.5">
        <label
          htmlFor={htmlFor}
          className="block text-xs font-semibold uppercase tracking-wider text-[#71717A]"
        >
          {label}
          {required && <span className="text-[#DC2626] ml-0.5">*</span>}
        </label>
        {hint && (
          <span
            className="relative inline-flex"
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
            onClick={() => setOpen((v) => !v)}
          >
            <button
              type="button"
              aria-label="Info"
              className="text-[#A1A1AA] hover:text-[#4F46E5] focus:text-[#4F46E5] transition-colors p-0.5 rounded"
            >
              <Info size={13} weight="bold" />
            </button>
            {open && (
              <span
                role="tooltip"
                className="absolute z-50 left-0 top-full mt-1.5 w-[260px] rounded-lg bg-[#18181B] text-white text-[11px] leading-snug normal-case font-normal tracking-normal px-2.5 py-2 shadow-xl"
              >
                {hint}
                <span className="absolute -top-1 left-2 w-2 h-2 bg-[#18181B] rotate-45" />
              </span>
            )}
          </span>
        )}
      </div>
      {example && (
        <div className="text-[10px] text-[#A1A1AA] mt-0.5 normal-case font-normal tracking-normal">
          {example}
        </div>
      )}
    </div>
  );
};

export default LabelWithTip;
