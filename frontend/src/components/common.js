import React from "react";
import { AlertTriangle, BadgeCheck, Ban, Split } from "lucide-react";

export const Container = ({ className = "", children }) => (
  <div className={`mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 ${className}`}>{children}</div>
);

export const Section = ({ className = "", children }) => (
  <section className={`py-12 sm:py-16 lg:py-20 ${className}`}>{children}</section>
);

export const Eyebrow = ({ children }) => (
  <div className="inline-flex items-center gap-2 rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--accent))] px-3 py-1 text-xs font-semibold text-[hsl(var(--primary))]">{children}</div>
);

export const HazardBadge = ({ hazardous }) =>
  hazardous ? (
    <span className="inline-flex items-center gap-1 rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-2 py-0.5 text-xs font-semibold text-[#065F46]">
      <AlertTriangle className="h-3.5 w-3.5" /> Небезпечні *
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-md border border-[#BBF7D0] bg-[#F0FDF4] px-2 py-0.5 text-xs font-medium text-[#166534]">
      Ненебезпечні
    </span>
  );

export const AcceptBadge = ({ accepted }) =>
  accepted ? (
    <span className="inline-flex items-center gap-1 rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-2 py-0.5 text-xs font-semibold text-[#065F46]"><BadgeCheck className="h-3.5 w-3.5" /> Приймаємо</span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-md border border-[#FECACA] bg-[#FEF2F2] px-2 py-0.5 text-xs font-semibold text-[#991B1B]"><Ban className="h-3.5 w-3.5" /> За запитом</span>
  );

export const MirrorBadge = ({ code }) => (
  <span className="inline-flex items-center gap-1 rounded-md border border-[#BBF7D0] bg-[#F0FDF4] px-2 py-0.5 text-xs font-medium text-[#166534]"><Split className="h-3.5 w-3.5" /> Дзеркальний: {code}</span>
);
