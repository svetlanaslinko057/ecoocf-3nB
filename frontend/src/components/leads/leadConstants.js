/**
 * BIBI Cars — Wave 8 — Lead Workspace shared constants
 *
 * Canonical 8-stage pipeline used by the Kanban board AND the table view.
 * Legacy values (proposal, won, archived) are silently normalised by the
 * backend's GET /api/leads, so the UI never has to deal with them.
 */

export const LEAD_PIPELINE = [
  'new',
  'contacted',
  'qualified',
  'negotiation',
  'decision',
  'not_qualified',
  'converted',
  'lost',
];

// Per-stage UI tokens — header color, dot, ring on the card etc.
// Tuned to read well on a white card background.
export const STATUS_THEME = {
  new:            { hex: '#3B82F6', soft: '#EFF6FF', text: '#1D4ED8', dot: '#3B82F6' },
  contacted:      { hex: '#0EA5E9', soft: '#F0F9FF', text: '#0369A1', dot: '#0EA5E9' },
  qualified:      { hex: '#8B5CF6', soft: '#F5F3FF', text: '#6D28D9', dot: '#8B5CF6' },
  negotiation:    { hex: '#F59E0B', soft: '#FFFBEB', text: '#B45309', dot: '#F59E0B' },
  decision:       { hex: '#0F172A', soft: '#F1F5F9', text: '#0F172A', dot: '#1E293B' },
  not_qualified:  { hex: '#DC2626', soft: '#FEF2F2', text: '#B91C1C', dot: '#DC2626' },
  converted:      { hex: '#16A34A', soft: '#F0FDF4', text: '#15803D', dot: '#16A34A' },
  lost:           { hex: '#71717A', soft: '#FAFAFA', text: '#52525B', dot: '#A1A1AA' },
};

// Status labels in three languages — keep colocated here so the Kanban
// doesn't need to wait for translations.js round-trips. The Workspace still
// prefers t(...) when a matching key exists, falling back to these maps.
export const STATUS_LABELS = {
  uk: {
    new:            'Новий',
    contacted:      'Контакт встановлено',
    qualified:      'Кваліфікований',
    negotiation:    'Перемовини',
    decision:       'Приймає рішення',
    not_qualified:  'Не кваліфікований',
    converted:      'Конвертований',
    lost:           'Втрачений',
  },
  en: {
    new:            'New',
    contacted:      'Contacted',
    qualified:      'Qualified',
    negotiation:    'Negotiation',
    decision:       'Decision making',
    not_qualified:  'Not qualified',
    converted:      'Converted',
    lost:           'Lost',
  },
  ru: {
    new:            'Новый',
    contacted:      'Контакт установлен',
    qualified:      'Квалифицирован',
    negotiation:    'Переговоры',
    decision:       'Принимает решение',
    not_qualified:  'Не квалифицирован',
    converted:      'Конвертирован',
    lost:           'Утрачен',
  },
  bg: {
    new:            'Нов',
    contacted:      'Установен контакт',
    qualified:      'Квалифициран',
    negotiation:    'Преговори',
    decision:       'Взема решение',
    not_qualified:  'Неквалифициран',
    converted:      'Конвертиран',
    lost:           'Загубен',
  },
};

export function statusLabel(lang, status) {
  const dict = STATUS_LABELS[lang] || STATUS_LABELS.en;
  return dict[status] || status;
}

// Sources — same vocabulary as the legacy Leads.js.
export const LEAD_SOURCES = [
  'website', 'referral', 'social_media', 'cold_call',
  'advertisement', 'partner', 'other',
];

export const SOURCE_LABELS = {
  uk: {
    website: 'Сайт', referral: 'Рекомендація', social_media: 'Соцмережі',
    cold_call: 'Холодний дзвінок', advertisement: 'Реклама',
    partner: 'Партнер', other: 'Інше',
  },
  en: {
    website: 'Website', referral: 'Referral', social_media: 'Social media',
    cold_call: 'Cold call', advertisement: 'Advertisement',
    partner: 'Partner', other: 'Other',
  },
  ru: {
    website: 'Сайт', referral: 'Рекомендация', social_media: 'Соцсети',
    cold_call: 'Холодный звонок', advertisement: 'Реклама',
    partner: 'Партнер', other: 'Другое',
  },
  bg: {
    website: 'Сайт', referral: 'Препоръка', social_media: 'Соц. мрежи',
    cold_call: 'Студено обаждане', advertisement: 'Реклама',
    partner: 'Партньор', other: 'Друго',
  },
};

export function sourceLabel(lang, source) {
  const dict = SOURCE_LABELS[lang] || SOURCE_LABELS.en;
  return dict[source] || source || '—';
}
