// UnifiedNotifications — Phase D1.5 Slice 2 (Header Notification Centre).
// ONE aggregated notification surface: content-review, new leads, pickups in
// planning, overdue invoices, contracts awaiting signature. Read-only compute
// on the backend; "mark seen" persists a per-user signature.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell, FileText, Users, Truck, Receipt, ScrollText, Check, Loader2,
} from "lucide-react";
import { UnifiedAPI } from "@/lib/api";

const ICON = { file: FileText, users: Users, truck: Truck, receipt: Receipt, scroll: ScrollText };
const DOT = { violet: "bg-violet-500", blue: "bg-blue-500", amber: "bg-amber-500", rose: "bg-rose-500", emerald: "bg-emerald-500" };

export default function UnifiedNotifications() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], total: 0, unread: false, signature: "" });
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await UnifiedAPI.notifications();
      setData(d);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000); // refresh every minute
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    const onClick = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const markSeen = async () => {
    await UnifiedAPI.markNotificationsSeen(data.signature).catch(() => {});
    setData((d) => ({ ...d, unread: false }));
  };

  const openItem = (url) => { setOpen(false); if (url) navigate(url); };

  return (
    <div className="relative" ref={boxRef} data-testid="unified-notifications">
      <button
        type="button"
        onClick={() => { setOpen((o) => !o); if (!open && data.unread) markSeen(); }}
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
        title="Центр сповіщень"
        data-testid="unified-notifications-trigger"
      >
        <Bell className="h-[18px] w-[18px]" />
        {data.total > 0 && (
          <span className={`absolute -right-0.5 -top-0.5 flex min-w-[16px] items-center justify-center rounded-full px-1 text-[10px] font-bold text-white ${data.unread ? "bg-[#0E5E3A]" : "bg-slate-400"}`} data-testid="unified-notifications-badge">
            {data.total}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-xl" data-testid="unified-notifications-panel">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold text-slate-700">Центр сповіщень</span>
            {data.total > 0 && (
              <button type="button" onClick={markSeen} className="flex items-center gap-1 text-xs text-[#0E5E3A] hover:underline">
                <Check className="h-3.5 w-3.5" /> Прочитано
              </button>
            )}
          </div>
          <div className="max-h-[60vh] overflow-y-auto">
            {loading ? (
              <div className="flex h-24 items-center justify-center text-slate-400"><Loader2 className="h-5 w-5 animate-spin" /></div>
            ) : data.items.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-400">Немає активних сповіщень</div>
            ) : (
              <ul className="py-1">
                {data.items.map((it) => {
                  const Icon = ICON[it.icon] || Bell;
                  return (
                    <li key={it.key}>
                      <button type="button" onClick={() => openItem(it.url)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-50" data-testid="unified-notification-item">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-50"><Icon className="h-4 w-4 text-slate-500" /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-slate-700">{it.title}</span>
                          <span className="block text-[11px] uppercase tracking-wide text-slate-400">{it.category}</span>
                        </span>
                        <span className={`flex h-5 min-w-[20px] items-center justify-center rounded-full px-1 text-[11px] font-bold text-white ${DOT[it.color] || "bg-slate-400"}`}>{it.count}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
