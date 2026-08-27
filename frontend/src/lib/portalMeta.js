// Portal lifecycle metadata — mirrors backend service.py constants.

export const STAGE_ORDER = ["new", "quote", "contract", "pickup", "utilization", "act", "archived"];
export const STAGE_LABELS = {
  new: "Нова", quote: "Прорахунок", contract: "Договір", pickup: "Вивіз",
  utilization: "Утилізація", act: "Акт готовий", archived: "Архів",
};

export const CONTRACT_ORDER = ["draft", "sent", "agreed", "signed", "active", "closed", "cancelled"];
export const CONTRACT_LABELS = {
  draft: "Чернетка", sent: "Надіслано", agreed: "Погоджено", signed: "Підписано",
  active: "Активний", closed: "Закритий", cancelled: "Скасовано",
};

export const PICKUP_ORDER = ["planning", "route", "driver_assigned", "picked_up", "delivered", "cancelled"];
export const PICKUP_LABELS = {
  planning: "Планування", route: "Маршрут", driver_assigned: "Водій призначений",
  picked_up: "Забір виконано", delivered: "Доставлено", cancelled: "Скасовано",
};

export const ACT_ORDER = ["expected", "created", "signed", "archived", "cancelled"];
export const ACT_LABELS = {
  expected: "Очікується", created: "Створено", signed: "Підписано",
  archived: "Архів", cancelled: "Скасовано",
};

export const ALL_LABELS = { ...STAGE_LABELS, ...CONTRACT_LABELS, ...PICKUP_LABELS, ...ACT_LABELS };

// status -> semantic tone
const TONE = {
  // positive (green)
  signed: "pos", active: "pos", agreed: "pos", delivered: "pos", picked_up: "pos", act: "pos",
  // warning / in-progress (amber)
  sent: "warn", route: "warn", driver_assigned: "warn", created: "warn", quote: "warn", utilization: "warn",
  // info (blue)
  contract: "info", pickup: "info", planning: "info", expected: "info", new: "info",
  // neutral
  draft: "muted", closed: "muted", archived: "muted",
  // danger
  cancelled: "danger",
};

export function toneFor(status) { return TONE[status] || "muted"; }
export function labelFor(status) { return ALL_LABELS[status] || status || "—"; }

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
  return d.toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function itemsSummary(items) {
  if (!Array.isArray(items) || !items.length) return "—";
  const head = items.slice(0, 2).map((i) => i.waste_code).join(", ");
  return items.length > 2 ? `${head} +${items.length - 2}` : head;
}
