/**
 * activityLabels.js — shared "business-language" mappers for site-activity.
 *
 * PHASE: Launch-prep UX repackaging (presentation-only). Translates the raw
 * telemetry the tracker collects (event_type / last_seen_at) into manager-
 * friendly wording. NO new data, NO new API — pure formatting helpers used by
 * Customer360 / Lead360 strips and the Leads-list temperature badge.
 *
 * App languages: uk / en (ru kept as a harmless fallback). Mirrors the
 * dictionary already used in components/shared/ActivityTab.jsx.
 */

// ── raw event_type → human action ────────────────────────────────────────
const EVENT_LABELS = {
  uk: {
    cabinet_login:    'Увійшов в кабінет',
    cabinet_active:   'Активний у кабінеті',
    form_active:      'Заповнював форму заявки',
    form_submitted:   'Надіслав заявку',
    callback_request: 'Замовив зворотний дзвінок',
    session_end:      'Завершив сесію',
    _unknown:         'Активність на сайті',
  },
  en: {
    cabinet_login:    'Logged into the cabinet',
    cabinet_active:   'Active in the cabinet',
    form_active:      'Was filling a form',
    form_submitted:   'Submitted a request',
    callback_request: 'Requested a call back',
    session_end:      'Ended the session',
    _unknown:         'Site activity',
  },
  ru: {
    cabinet_login:    'Вошёл в кабинет',
    cabinet_active:   'Активен в кабинете',
    form_active:      'Заполнял форму заявки',
    form_submitted:   'Отправил заявку',
    callback_request: 'Запросил обратный звонок',
    session_end:      'Завершил сессию',
    _unknown:         'Активность на сайте',
  },
};

export function eventLabel(eventType, lang = 'uk') {
  const dict = EVENT_LABELS[lang] || EVENT_LABELS.uk;
  return dict[eventType] || dict._unknown;
}

// ── site-activity temperature (visited <24h / 1–7d / >7d) ─────────────────
// Mirrors the backend `_classify_status` buckets exactly (24h / 7d).
export const TEMP_META = {
  hot:  {
    key: 'hot',  dot: '#22C55E', bg: '#DCFCE7', fg: '#15803D', ring: '#BBF7D0',
    labels: { uk: 'Гарячий', en: 'Hot', ru: 'Горячий' },
  },
  warm: {
    key: 'warm', dot: '#F59E0B', bg: '#FEF3C7', fg: '#92400E', ring: '#FDE68A',
    labels: { uk: 'Теплий', en: 'Warm', ru: 'Тёплый' },
  },
  cold: {
    key: 'cold', dot: '#EF4444', bg: '#FEE2E2', fg: '#B91C1C', ring: '#FECACA',
    labels: { uk: 'Охолов', en: 'Cold', ru: 'Остыл' },
  },
};

const TEMP_HINTS = {
  uk: { hot: 'Був на сайті за останні 24 години', warm: 'Був на сайті 1–7 днів тому', cold: 'Не заходив понад 7 днів' },
  en: { hot: 'On site within last 24 hours', warm: 'On site 1–7 days ago', cold: 'No visits in 7+ days' },
  ru: { hot: 'Заходил за последние 24 часа', warm: 'Заходил 1–7 дней назад', cold: 'Не заходил больше 7 дней' },
};

/**
 * Map a last-seen ISO timestamp to a temperature bucket.
 * Returns 'hot' | 'warm' | 'cold', or null when there is no site data
 * (so untracked leads are NOT mislabelled as "cold").
 */
export function temperatureFromLastSeen(lastSeenIso) {
  if (!lastSeenIso) return null;
  const ts = new Date(lastSeenIso).getTime();
  if (!ts || Number.isNaN(ts)) return null;
  const hours = (Date.now() - ts) / 3_600_000;
  if (hours <= 24) return 'hot';
  if (hours <= 24 * 7) return 'warm';
  return 'cold';
}

export function temperatureLabel(key, lang = 'uk') {
  const meta = TEMP_META[key];
  if (!meta) return '';
  return meta.labels[lang] || meta.labels.uk;
}

export function temperatureHint(key, lang = 'uk') {
  return (TEMP_HINTS[lang] || TEMP_HINTS.uk)[key] || '';
}

// ── compact "N min ago" phrasing for the online strips ────────────────────
const AGO = {
  uk: { now: 'щойно', min: 'хв тому', prefix: 'На сайті' },
  en: { now: 'just now', min: 'min ago', prefix: 'On site' },
  ru: { now: 'только что', min: 'мин назад', prefix: 'На сайте' },
};

export function minutesAgoLabel(minutes, lang = 'uk') {
  const d = AGO[lang] || AGO.uk;
  if (minutes === null || minutes === undefined) return '';
  return minutes <= 1 ? d.now : `${minutes} ${d.min}`;
}

export function onSitePrefix(lang = 'uk') {
  return (AGO[lang] || AGO.uk).prefix;
}
