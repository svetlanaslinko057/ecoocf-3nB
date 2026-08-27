import React, { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck } from "lucide-react";
import { PortalAPI } from "@/lib/api";

function timeAgo(iso) {
  try {
    const d = new Date(iso);
    const s = Math.floor((Date.now() - d.getTime()) / 1000);
    if (s < 60) return "щойно";
    if (s < 3600) return `${Math.floor(s / 60)} хв тому`;
    if (s < 86400) return `${Math.floor(s / 3600)} год тому`;
    return d.toLocaleDateString("uk-UA");
  } catch { return ""; }
}

/**
 * NotificationBell — lightweight queue alert for the portal header.
 * Polls the ECO waste-notification feed (new client requests, etc.).
 */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef(null);

  const load = useCallback(async () => {
    try {
      const r = await PortalAPI.notifications({ limit: 15 });
      setItems(r.items || []);
      setUnread(r.unread || 0);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const markAll = async () => {
    try { await PortalAPI.markAllNotificationsRead(); setUnread(0); setItems((p) => p.map((n) => ({ ...n, read: true }))); }
    catch { /* silent */ }
  };

  const openItem = async (n) => {
    try { if (!n.read) await PortalAPI.markNotificationRead(n.id); } catch { /* silent */ }
    setOpen(false);
    if (n.company_id) navigate(`/app/companies/${n.company_id}`);
    else navigate("/app/requests");
    load();
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
        aria-label="Сповіщення"
        data-testid="notif-bell"
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#DC2626] px-1 text-[10px] font-bold text-white" data-testid="notif-badge">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed right-3 top-[60px] z-50 w-[calc(100vw-1.5rem)] max-w-[360px] overflow-hidden rounded-2xl border border-[#0B1A14]/10 bg-white shadow-xl sm:absolute sm:right-0 sm:top-auto sm:mt-2 sm:w-[340px]" data-testid="notif-panel">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <span className="text-sm font-semibold text-slate-800">Сповіщення</span>
            {unread > 0 && (
              <button onClick={markAll} className="flex items-center gap-1 text-xs font-medium text-[#0E5E3A] hover:underline" data-testid="notif-mark-all">
                <CheckCheck className="h-3.5 w-3.5" /> Прочитати всі
              </button>
            )}
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-slate-400">Немає сповіщень</div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => openItem(n)}
                  className={`flex w-full flex-col items-start gap-0.5 border-b border-slate-50 px-4 py-3 text-left transition-colors hover:bg-slate-50 ${n.read ? "" : "bg-[#F4FBEF]"}`}
                  data-testid="notif-item"
                >
                  <span className="flex w-full items-center justify-between">
                    <span className="text-sm font-medium text-slate-800">{n.title}</span>
                    {!n.read && <span className="ml-2 h-2 w-2 shrink-0 rounded-full bg-[#5BC47A]" />}
                  </span>
                  <span className="text-xs text-slate-500">{n.body}</span>
                  <span className="text-[11px] text-slate-400">{timeAgo(n.created_at)}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
