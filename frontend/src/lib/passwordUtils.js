// Shared password helpers for the client auth screens.

export const PWD_RULES = [
  { key: "len", label: { uk: "8+ символів", en: "8+ characters" }, test: (v) => v.length >= 8 },
  { key: "upper", label: { uk: "Велика літера", en: "Uppercase letter" }, test: (v) => /[A-ZА-ЯҐЄІЇ]/.test(v) },
  { key: "lower", label: { uk: "Мала літера", en: "Lowercase letter" }, test: (v) => /[a-zа-яґєії]/.test(v) },
  { key: "digit", label: { uk: "Цифра", en: "Digit" }, test: (v) => /\d/.test(v) },
  { key: "special", label: { uk: "Спецсимвол", en: "Special character" }, test: (v) => /[^A-Za-zА-Яа-я0-9]/.test(v) },
];

export function passwordScore(v) {
  if (!v) return 0;
  return PWD_RULES.reduce((n, r) => n + (r.test(v) ? 1 : 0), 0);
}

export const STRENGTH = [
  { label: { uk: "—", en: "—" }, color: "rgba(20,30,18,0.18)", pct: 0 },
  { label: { uk: "Дуже слабкий", en: "Very weak" }, color: "#DC2626", pct: 20 },
  { label: { uk: "Слабкий", en: "Weak" }, color: "#EA580C", pct: 40 },
  { label: { uk: "Прийнятний", en: "Fair" }, color: "#D9A21B", pct: 60 },
  { label: { uk: "Надійний", en: "Strong" }, color: "#3F8F4E", pct: 82 },
  { label: { uk: "Дуже надійний", en: "Very strong" }, color: "#2F5D3D", pct: 100 },
];

export function generatePassword(len = 14) {
  const sets = [
    "ABCDEFGHJKLMNPQRSTUVWXYZ",
    "abcdefghijkmnopqrstuvwxyz",
    "23456789",
    "!@#$%^&*?-_+=",
  ];
  const all = sets.join("");
  const pick = (s) => s[Math.floor(Math.random() * s.length)];
  // guarantee one of each class, then fill
  let chars = sets.map(pick);
  for (let i = chars.length; i < len; i++) chars.push(pick(all));
  // shuffle
  for (let i = chars.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join("");
}
