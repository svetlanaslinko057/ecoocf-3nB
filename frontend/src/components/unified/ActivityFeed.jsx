// ActivityFeed — Phase D1.5 Slice 2 (Universal Activity Feed).
// Renders the hybrid cross-domain event stream (native u_activity events merged
// with live-derived domain updates). Read-only.
import React, { useEffect, useState } from "react";
import {
  Activity, MessageSquare, Paperclip, Handshake, ScrollText, Truck, Users,
  FileText, Image as ImageIcon, Globe, History, Loader2,
} from "lucide-react";
import { UnifiedAPI } from "@/lib/api";

const ICONS = {
  activity: Activity, message: MessageSquare, paperclip: Paperclip, handshake: Handshake,
  scroll: ScrollText, truck: Truck, users: Users, file: FileText, image: ImageIcon,
  globe: Globe, history: History,
};
const DOT = {
  blue: "bg-blue-500", green: "bg-emerald-500", emerald: "bg-emerald-500", amber: "bg-amber-500",
  violet: "bg-violet-500", cyan: "bg-cyan-500", teal: "bg-teal-500", rose: "bg-rose-500", slate: "bg-slate-400",
};

const fmtTime = (ts) => {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "щойно";
    if (diff < 3600) return `${Math.floor(diff / 60)} хв тому`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} год тому`;
    return d.toLocaleDateString("uk-UA", { day: "2-digit", month: "short" });
  } catch { return ""; }
};

export default function ActivityFeed({ limit = 25, compact = false }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    UnifiedAPI.activity({ limit }).then((d) => alive && setItems(d.items || [])).catch(() => {}).finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [limit]);

  if (loading) return <div className="flex h-32 items-center justify-center text-slate-400"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  if (!items.length) return <div className="py-8 text-center text-sm text-slate-400">Немає подій</div>;

  return (
    <ul className={compact ? "space-y-1" : "space-y-2"} data-testid="activity-feed">
      {items.map((ev) => {
        const Icon = ICONS[ev.icon] || Activity;
        const dot = DOT[ev.color] || DOT.slate;
        return (
          <li key={ev.id} className="flex items-start gap-3 rounded-lg px-2 py-2 hover:bg-slate-50" data-testid="activity-item">
            <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-50`}>
              <Icon className="h-3.5 w-3.5 text-slate-500" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
                <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{ev.entity_label}</span>
                <span className="text-[11px] text-slate-300">· {ev.action}</span>
              </div>
              <div className="truncate text-[13px] text-slate-700">{ev.title || "—"}</div>
              <div className="text-[11px] text-slate-400">{ev.actor?.name || "Система"} · {fmtTime(ev.created_at)}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
