import React from "react";

// Shared visual atoms for the Manager Cabinet — consistent with the ECO theme.

const TONE_CLS = {
  pos: "border-[#A7F3D0] bg-[#ECFDF5] text-[#065F46]",
  warn: "border-[#FDE68A] bg-[#FFFBEB] text-[#92400E]",
  info: "border-[#BAE6FD] bg-[#F0F9FF] text-[#075985]",
  muted: "border-slate-200 bg-slate-50 text-slate-600",
  danger: "border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]",
};

export const StatusPill = ({ tone = "muted", children, testid }) => (
  <span
    data-testid={testid}
    className={`inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-medium ${TONE_CLS[tone] || TONE_CLS.muted}`}
  >
    {children}
  </span>
);

export const FunnelBar = ({ label, value, max, tone = "primary" }) => {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  const bar = tone === "pos" ? "bg-[#0E5E3A]" : tone === "danger" ? "bg-[#B91C1C]" : "bg-[#0E5E3A]";
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 shrink-0 text-sm text-slate-600">{label}</div>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-[#E7F0EA]">
        <div className={`h-full rounded-full ${bar} transition-[width] duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <div className="w-8 shrink-0 text-right text-sm font-semibold text-slate-800">{value}</div>
    </div>
  );
};

export const Avatar = ({ name }) => {
  const ch = (name || "?").trim().charAt(0).toUpperCase();
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0E5E3A] text-sm font-semibold text-[#5BC47A]">
      {ch}
    </span>
  );
};

export const SectionCard = ({ title, subtitle, actions, children, className = "", testid }) => (
  <div data-testid={testid} className={`rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-6 shadow-[0_1px_3px_rgba(11,26,20,0.06)] ${className}`}>
    {(title || actions) && (
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          {title && <h2 className="text-lg font-semibold text-slate-900">{title}</h2>}
          {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
        </div>
        {actions}
      </div>
    )}
    {children}
  </div>
);
