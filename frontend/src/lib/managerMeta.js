// Manager Cabinet metadata — labels, tones, formatters (uk-UA).

export const LEAD_STATUS_ORDER = ["new", "contacted", "qualified", "negotiation", "won", "lost"];
export const LEAD_STATUS_LABELS = {
  new: "Новий", contacted: "В роботі", qualified: "Кваліфікований",
  negotiation: "Перемовини", won: "Виграно", lost: "Втрачено",
};
export const LEAD_STATUS_TONE = {
  new: "info", contacted: "warn", qualified: "info",
  negotiation: "warn", won: "pos", lost: "danger",
};

export const DEAL_STAGE_ORDER = ["new", "negotiation", "contract", "pickup", "utilization", "won", "lost"];
export const DEAL_STAGE_LABELS = { new: "Нова", negotiation: "Перемовини", contract: "Договір", pickup: "Вивіз", utilization: "Утилізація", won: "Виграно", lost: "Втрачено" };
export const DEAL_STAGE_TONE = { new: "info", negotiation: "warn", contract: "info", pickup: "warn", utilization: "warn", won: "pos", lost: "danger" };

export const TASK_STATUS_ORDER = ["pending", "in_progress", "completed"];
export const TASK_STATUS_LABELS = { pending: "Очікує", in_progress: "В роботі", completed: "Виконано" };
export const TASK_STATUS_TONE = { pending: "info", in_progress: "warn", completed: "pos" };

export const CALL_STATUS_LABELS = { answered: "Відповіли", missed: "Пропущений", no_answer: "Без відповіді" };
export const CALL_STATUS_TONE = { answered: "pos", missed: "danger", no_answer: "warn" };
export const CALL_DIR_LABELS = { inbound: "Вхідний", outbound: "Вихідний" };

export const fmtMoney = (v, cur = "₴") =>
  `${new Intl.NumberFormat("uk-UA").format(Math.round(Number(v) || 0))} ${cur}`;

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

// "сьогодні / завтра / прострочено 2д / через 3д"
export function dueMeta(iso) {
  if (!iso) return { label: "—", overdue: false, soon: false };
  const d = new Date(iso);
  if (isNaN(d.getTime())) return { label: "—", overdue: false, soon: false };
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startDue = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startDue - startToday) / 86400000);
  const time = d.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
  if (diffDays < 0) return { label: `Прострочено ${Math.abs(diffDays)}д`, overdue: true, soon: false };
  if (diffDays === 0) return { label: `Сьогодні · ${time}`, overdue: false, soon: true };
  if (diffDays === 1) return { label: `Завтра · ${time}`, overdue: false, soon: true };
  return { label: `${fmtDate(iso)}`, overdue: false, soon: false };
}

export function durationStr(sec) {
  const s = Number(sec) || 0;
  if (!s) return "—";
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m ? `${m}хв ${r}с` : `${r}с`;
}
