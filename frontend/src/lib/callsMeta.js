// Calls / Ringostat shared metadata for the ECO CRM console.
import {
  PhoneIncoming, PhoneOutgoing, Phone, PhoneMissed, PhoneOff,
} from "lucide-react";

// ── Outcome catalogue (ECO CRM) ──────────────────────────────────────
// Replaces the legacy auto-domain outcomes (vin_request / ready_deposit …)
// with a clean B2B sales-call set. `requiresDate` forces a callback date.
export const OUTCOME_OPTIONS = [
  { value: "interested", label: "Зацікавлений", tone: "green" },
  { value: "callback", label: "Передзвонити", tone: "amber", requiresDate: true },
  { value: "thinking", label: "Думає / вагається", tone: "blue" },
  { value: "no_answer", label: "Не відповів", tone: "slate" },
  { value: "busy", label: "Зайнято", tone: "slate" },
  { value: "deal", label: "Уклали угоду", tone: "emerald" },
  { value: "reject", label: "Відмова", tone: "rose" },
];

export const OUTCOME_MAP = OUTCOME_OPTIONS.reduce((acc, o) => {
  acc[o.value] = o;
  return acc;
}, {});

const TONE_STYLE = {
  green: { c: "#065F46", bg: "#ECFDF5", b: "#A7F3D0" },
  emerald: { c: "#065F46", bg: "#ECFDF5", b: "#6EE7B7" },
  amber: { c: "#92400E", bg: "#FFFBEB", b: "#FDE68A" },
  blue: { c: "#1E40AF", bg: "#EFF6FF", b: "#BFDBFE" },
  slate: { c: "#475569", bg: "#F1F5F9", b: "#E2E8F0" },
  rose: { c: "#991B1B", bg: "#FEF2F2", b: "#FECACA" },
};

export function outcomeStyle(value) {
  const o = OUTCOME_MAP[value];
  return TONE_STYLE[o?.tone] || TONE_STYLE.slate;
}

export function outcomeLabel(value) {
  return OUTCOME_MAP[value]?.label || (value || "—");
}

// ── Call status pills ────────────────────────────────────────────────
export function callStatusMeta(status) {
  const k = String(status || "").toUpperCase();
  const map = {
    ANSWERED: { l: "відповів", ...TONE_STYLE.green },
    PROPER: { l: "відповів", ...TONE_STYLE.green },
    COMPLETED: { l: "завершено", ...TONE_STYLE.green },
    MISSED: { l: "пропущений", ...TONE_STYLE.rose },
    "NO ANSWER": { l: "не відповів", ...TONE_STYLE.amber },
    NO_ANSWER: { l: "не відповів", ...TONE_STYLE.amber },
    BUSY: { l: "зайнято", ...TONE_STYLE.amber },
    RINGING: { l: "дзвонить", ...TONE_STYLE.blue },
  };
  return map[k] || { l: status || "—", ...TONE_STYLE.slate };
}

export const DIRECTION_META = {
  inbound: { label: "вхідний", Icon: PhoneIncoming, color: "text-emerald-600" },
  outbound: { label: "вихідний", Icon: PhoneOutgoing, color: "text-sky-600" },
};

export function DirectionIcon({ d, className = "h-4 w-4" }) {
  const m = DIRECTION_META[d];
  if (!m) return <Phone className={`${className} text-slate-400`} />;
  const Icon = m.Icon;
  return <Icon className={`${className} ${m.color}`} />;
}

export { Phone, PhoneMissed, PhoneOff };

// ── Formatters ───────────────────────────────────────────────────────
export function durFmt(s) {
  if (!s && s !== 0) return "—";
  const n = Number(s);
  if (isNaN(n) || n <= 0) return "—";
  const m = Math.floor(n / 60);
  const r = n % 60;
  return m > 0 ? `${m}хв ${r}с` : `${r}с`;
}

export function dtFmt(v) {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString("uk-UA", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return String(v);
  }
}

// A call needs an outcome when answered, > threshold seconds, and no outcome saved.
export function needsOutcome(call, threshold = 10) {
  const st = String(call?.status || "").toUpperCase();
  const answered = ["ANSWERED", "PROPER", "COMPLETED"].includes(st);
  return answered && Number(call?.duration || 0) > threshold && !call?.outcome;
}
