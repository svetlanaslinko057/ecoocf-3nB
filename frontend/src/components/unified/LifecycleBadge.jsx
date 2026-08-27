// LifecycleBadge — Phase D1.5 Slice 2 (Draft Adapter UI).
// Renders a consistent status badge for ANY entity from the universal lifecycle
// resolver. Accepts either a resolved `lifecycle` object or {entityType,entityId}
// (then it fetches). Never writes — display only.
import React, { useEffect, useState } from "react";
import { UnifiedAPI } from "@/lib/api";

const COLORS = {
  slate: "bg-slate-100 text-slate-600",
  amber: "bg-amber-100 text-amber-700",
  green: "bg-emerald-100 text-emerald-700",
  emerald: "bg-emerald-100 text-emerald-700",
  zinc: "bg-zinc-100 text-zinc-600",
  rose: "bg-rose-100 text-rose-700",
  blue: "bg-blue-100 text-blue-700",
  teal: "bg-teal-100 text-teal-700",
  cyan: "bg-cyan-100 text-cyan-700",
  violet: "bg-violet-100 text-violet-700",
};

export default function LifecycleBadge({ lifecycle, entityType, entityId, showStepper = false }) {
  const [lc, setLc] = useState(lifecycle || null);

  useEffect(() => {
    let alive = true;
    if (!lifecycle && entityType && entityId) {
      UnifiedAPI.lifecycle(entityType, entityId).then((d) => alive && setLc(d)).catch(() => {});
    } else if (lifecycle) {
      setLc(lifecycle);
    }
    return () => { alive = false; };
  }, [lifecycle, entityType, entityId]);

  if (!lc) return null;
  const cls = COLORS[lc.color] || COLORS.slate;

  return (
    <span className="inline-flex items-center gap-2" data-testid="lifecycle-badge">
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
        {lc.label}
        {lc.native_status && lc.native_status !== "unknown" && lc.lifecycle_type === "custom" && (
          <span className="ml-1.5 opacity-60">· {lc.native_status}</span>
        )}
      </span>
      {showStepper && (lc.stages || []).length > 0 && (
        <span className="hidden items-center gap-1 sm:inline-flex">
          {lc.stages.map((s) => (
            <span key={s} className={`h-1.5 w-1.5 rounded-full ${s === lc.native_status ? "bg-[#0E5E3A]" : "bg-slate-200"}`} title={s} />
          ))}
        </span>
      )}
    </span>
  );
}
