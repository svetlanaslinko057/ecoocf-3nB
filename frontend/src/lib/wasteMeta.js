import {
  Stethoscope, Pill, Syringe, BatteryCharging, CarFront, Cpu, FlaskConical, Lightbulb,
  Bug, Sprout, PaintBucket, Droplet, CircleDot, Recycle, Boxes, Leaf, ShieldAlert,
  AlertTriangle, Skull, Fuel, Biohazard, Radiation, Atom, Trash2, Package, Factory,
  Wind, Flame, Trees, GlassWater,
} from "lucide-react";

// ── Icon registry ─────────────────────────────────────────────────
// Maps the backend `icon` string keys (stored per-category and editable from
// the admin) to lucide-react components. Category cards render whatever icon
// the operator picked in the CRM. Keys MUST stay in sync with
// backend/app/waste/service.py::AVAILABLE_ICON_KEYS.
export const ICON_REGISTRY = {
  stethoscope: Stethoscope,
  pill: Pill,
  syringe: Syringe,
  battery: BatteryCharging,
  "car-battery": CarFront,
  cpu: Cpu,
  "alert-triangle": AlertTriangle,
  "shield-alert": ShieldAlert,
  lightbulb: Lightbulb,
  skull: Skull,
  flask: FlaskConical,
  "paint-bucket": PaintBucket,
  droplet: Droplet,
  fuel: Fuel,
  "circle-dot": CircleDot,
  recycle: Recycle,
  boxes: Boxes,
  leaf: Leaf,
  sprout: Sprout,
  biohazard: Biohazard,
  radiation: Radiation,
  atom: Atom,
  "trash-2": Trash2,
  package: Package,
  factory: Factory,
  wind: Wind,
  flame: Flame,
  bug: Bug,
  trees: Trees,
  "glass-water": GlassWater,
};

export const ICON_KEYS = Object.keys(ICON_REGISTRY);

/** Resolve a lucide icon component from a backend icon-key string. */
export function iconByName(name) {
  return ICON_REGISTRY[name] || ShieldAlert;
}

// Legacy map (category-key → icon) kept for backward compatibility.
export const CATEGORY_ICONS = {
  medical: Stethoscope,
  pharma: Pill,
  batteries: BatteryCharging,
  accumulators: CarFront,
  electronics: Cpu,
  mercury: FlaskConical,
  lamps: Lightbulb,
  pesticides: Bug,
  agrochem: Sprout,
  paints: PaintBucket,
  oils: Droplet,
  tires: CircleDot,
  plastic: Recycle,
  polymers: Boxes,
  organic: Leaf,
  other_hazard: ShieldAlert,
};

export function categoryIcon(key) {
  return CATEGORY_ICONS[key] || ShieldAlert;
}

// English names for waste categories (keys are stable; backend serves UA names).
export const CATEGORY_NAMES_EN = {
  medical: "Medical waste",
  pharma: "Pharmaceutical waste",
  batteries: "Batteries",
  accumulators: "Accumulators",
  electronics: "Electronics (WEEE)",
  mercury: "Mercury-containing waste",
  lamps: "Lamps",
  pesticides: "Pesticides",
  agrochem: "Agrochemicals",
  paints: "Paints & coatings (PCM)",
  oils: "Used oils",
  tires: "Tires",
  plastic: "Plastic",
  polymers: "Polymers",
  organic: "Organic waste",
  other_hazard: "Other hazardous waste",
};

/**
 * Resolve a category display name for the active language.
 * Falls back to the (Ukrainian) name served by the backend when no EN
 * translation exists.
 */
export function categoryName(key, lang, fallback) {
  if (lang === "en" && CATEGORY_NAMES_EN[key]) return CATEGORY_NAMES_EN[key];
  return fallback || key;
}

/**
 * Resolve the localized display name from an API category object
 * ({ name_uk, name_en, name }). Prefers the language-specific field and
 * gracefully falls back to the other language / legacy static map.
 */
export function categoryLabel(cat, lang) {
  if (!cat) return "";
  if (lang === "en") return cat.name_en || cat.name_uk || cat.name || categoryName(cat.key, "en", cat.name);
  return cat.name_uk || cat.name || cat.name_en || cat.key;
}

export const HAZARD_CLASS_LABEL = {
  1: "I клас — надзвичайно небезпечні",
  2: "II клас — високонебезпечні",
  3: "III клас — помірно небезпечні",
  4: "IV клас — малонебезпечні",
};

export const HAZARD_CLASS_LABEL_EN = {
  1: "Class I — extremely hazardous",
  2: "Class II — highly hazardous",
  3: "Class III — moderately hazardous",
  4: "Class IV — low-hazard",
};

export function hazardClassLabel(cls, lang) {
  if (!cls) return null;
  const map = lang === "en" ? HAZARD_CLASS_LABEL_EN : HAZARD_CLASS_LABEL;
  return map[cls] || (lang === "en" ? `Class ${cls}` : `Клас ${cls}`);
}

/**
 * Correct plural form of the word "code(s)" for the active language.
 * EN: 1 → code, else codes. UK: full 1/2-4/many rule.
 */
export function codesWord(count, lang) {
  const n = Math.abs(Number(count) || 0);
  if (lang === "en") return n === 1 ? "code" : "codes";
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "код";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "коди";
  return "кодів";
}

export function money(n) {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("uk-UA").format(n);
}

export const REGIONS = [
  { value: "kyiv", label: "Київ" },
  { value: "center", label: "Центр (область)" },
  { value: "north", label: "Північ" },
  { value: "west", label: "Захід" },
  { value: "east", label: "Схід" },
  { value: "south", label: "Південь" },
];
