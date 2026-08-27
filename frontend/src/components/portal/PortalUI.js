import React from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { toneFor, labelFor } from "@/lib/portalMeta";

export const PageHeader = ({ title, subtitle, actions, breadcrumb, testid }) => (
  <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between" data-testid={testid}>
    <div className="min-w-0">
      {breadcrumb}
      <h1 className="truncate text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
    </div>
    {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
  </div>
);

export const StatCard = ({ icon: Icon, label, value, hint, testid }) => (
  <div className="group relative overflow-hidden rounded-2xl border border-[#0B1A14]/[0.06] bg-white p-4 sm:p-5 shadow-[0_1px_3px_rgba(11,26,20,0.06)] ring-1 ring-black/[0.02] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(11,26,20,0.10)]" data-testid={testid}>
    <span className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#0E5E3A] to-[#5BC47A] opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
    <div className="flex items-start justify-between gap-2">
      <span className="min-w-0 text-[12.5px] leading-snug sm:text-sm font-medium text-slate-500">{label}</span>
      {Icon && (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[hsl(var(--accent))] text-[#0E5E3A] sm:h-9 sm:w-9">
          <Icon className="h-[18px] w-[18px]" />
        </span>
      )}
    </div>
    <div className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 break-words sm:mt-3 sm:text-3xl">{value}</div>
    {hint && <div className="mt-1 truncate text-xs text-slate-400">{hint}</div>}
  </div>
);

export const EmptyState = ({ icon: Icon, title, hint, action, testid }) => (
  <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[hsl(var(--border))] bg-white/60 px-6 py-16 text-center" data-testid={testid}>
    {Icon && (
      <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[hsl(var(--secondary))] text-slate-400">
        <Icon className="h-6 w-6" />
      </span>
    )}
    <div className="text-base font-medium text-slate-700">{title}</div>
    {hint && <div className="mt-1 max-w-sm text-sm text-slate-500">{hint}</div>}
    {action && <div className="mt-5">{action}</div>}
  </div>
);

export const TableSkeleton = ({ rows = 5 }) => (
  <div className="space-y-2" data-testid="loading-skeleton">
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} className="h-12 w-full rounded-xl" />
    ))}
  </div>
);

const TONE_CLS = {
  pos: "border-[#A7F3D0] bg-[#ECFDF5] text-[#065F46]",
  warn: "border-[#FDE68A] bg-[#FFFBEB] text-[#92400E]",
  info: "border-[#BAE6FD] bg-[#F0F9FF] text-[#075985]",
  muted: "border-[hsl(var(--border))] bg-[hsl(var(--secondary))] text-slate-600",
  danger: "border-[#FECACA] bg-[#FEF2F2] text-[#991B1B]",
};

export const StatusBadge = ({ status, testid }) => (
  <span
    className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${TONE_CLS[toneFor(status)]}`}
    data-testid={testid}
  >
    {labelFor(status)}
  </span>
);
