// Calls Live Layer — global, lightweight bar + realtime toasts for the
// ECO CRM workspace (admin + manager). Mounted once in PortalLayout.
//  • Compact banner with today's call counters (limited admin view).
//  • Realtime Ringostat events via Socket.IO (default namespace, eco_token).
//  • "Awaiting outcome" guard — opens the OutcomeDialog so a manager can
//    fix the result before the lead can close.
import React, { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { io } from "socket.io-client";
import { Phone, PhoneIncoming, PhoneMissed, AlertTriangle, CalendarClock, ClipboardCheck } from "lucide-react";
import { toast } from "sonner";
import { CrmAPI, getToken } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import OutcomeDialog from "@/components/calls/OutcomeDialog";

const WS_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
const POLL_MS = 25000;

function Counter({ icon: Icon, label, value, tone = "slate" }) {
  const toneCls = {
    slate: "text-slate-600",
    emerald: "text-emerald-600",
    rose: "text-rose-600",
    amber: "text-amber-600",
    blue: "text-sky-600",
  }[tone];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500">
      <Icon className={`h-3.5 w-3.5 ${toneCls}`} />
      <span className="hidden sm:inline">{label}:</span>
      <span className={`font-bold ${value ? toneCls : "text-slate-400"}`}>{value ?? 0}</span>
    </span>
  );
}

export default function CallsLiveLayer() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [outcomeCall, setOutcomeCall] = useState(null);
  const socketRef = useRef(null);

  const isStaff = ["admin", "manager", "master_admin", "team_lead"].includes(user?.role);

  const loadSummary = useCallback(async () => {
    try { setSummary(await CrmAPI.callsSummary()); } catch { /* silent */ }
  }, []);

  // Poll summary
  useEffect(() => {
    if (!isStaff) return;
    loadSummary();
    const id = setInterval(loadSummary, POLL_MS);
    return () => clearInterval(id);
  }, [isStaff, loadSummary]);

  // Realtime socket (default namespace — rooms user:{id}/role:{role})
  useEffect(() => {
    if (!isStaff) return;
    const token = getToken();
    if (!token || !WS_URL) return;
    let socket;
    try {
      socket = io(WS_URL, {
        auth: { token },
        query: { token },
        transports: ["websocket", "polling"],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 2000,
      });
      socketRef.current = socket;

      socket.on("ringostat:incoming_call", (d) => {
        toast(
          <div className="flex items-center gap-2">
            <PhoneIncoming className="h-5 w-5 text-emerald-600" />
            <div>
              <div className="font-semibold text-sm">Вхідний дзвінок</div>
              <div className="text-xs text-slate-500">{d?.lead_name || d?.from || "невідомий номер"}</div>
            </div>
          </div>, { duration: 12000 }
        );
      });
      socket.on("ringostat:missed_call", (d) => {
        toast.error(`Пропущений дзвінок: ${d?.lead_name || d?.from || ""}`, { duration: 8000 });
        loadSummary();
      });
      socket.on("ringostat:call_needs_outcome", (d) => {
        toast.warning(
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-amber-600" />
            <div className="text-sm">Дзвінок завершено — вкажіть результат</div>
          </div>, { duration: 9000 }
        );
        loadSummary();
      });
    } catch { /* socket optional */ }
    return () => { try { socket && socket.disconnect(); } catch { /* noop */ } };
  }, [isStaff, loadSummary]);

  const openFirstAwaiting = async () => {
    try {
      const r = await CrmAPI.callsAwaiting();
      const first = (r.calls || [])[0];
      if (first) setOutcomeCall(first);
      else { toast.success("Усі результати заповнені"); navigate("/app/crm/calls?tab=awaiting"); }
    } catch { navigate("/app/crm/calls?tab=awaiting"); }
  };

  if (!isStaff || !summary) return null;
  const awaiting = summary.awaiting_outcome ?? 0;

  return (
    <>
      <div
        className={`flex items-center gap-2 border-b px-4 py-2 sm:px-6 ${awaiting > 0 ? "border-amber-300 bg-amber-50" : "border-[#0B1A14]/10 bg-white"}`}
        data-testid="calls-live-banner"
      >
        <div className="flex min-w-0 flex-1 items-center gap-x-3 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
          <span className="hidden shrink-0 items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#0E5E3A] sm:inline-flex">
            <Phone className="h-3.5 w-3.5" /> Дзвінки
          </span>
          <Counter icon={Phone} label="Сьогодні" value={summary.today_total} tone="slate" />
          <Counter icon={PhoneIncoming} label="Відповіли" value={summary.today_answered} tone="emerald" />
          <Counter icon={PhoneMissed} label="Пропущені" value={summary.today_missed} tone="rose" />
          <Counter icon={CalendarClock} label="Передзвони" value={summary.scheduled_callbacks} tone="blue" />
          <Counter icon={AlertTriangle} label="Очікують" value={awaiting} tone="amber" />
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {awaiting > 0 && (
            <button
              onClick={openFirstAwaiting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-2.5 py-1 text-xs font-semibold text-white shadow-sm transition hover:bg-amber-600 sm:px-3"
              data-testid="calls-banner-fill"
            >
              <ClipboardCheck className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Заповнити результат</span>
            </button>
          )}
          <button
            onClick={() => navigate("/app/crm/calls")}
            className="whitespace-nowrap text-xs font-medium text-[#0E5E3A] hover:underline"
            data-testid="calls-banner-open"
          >
            Консоль →
          </button>
        </div>
      </div>

      <OutcomeDialog
        open={!!outcomeCall}
        onOpenChange={(v) => !v && setOutcomeCall(null)}
        call={outcomeCall}
        onSaved={() => { setOutcomeCall(null); loadSummary(); }}
      />
    </>
  );
}
