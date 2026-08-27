/**
 * ActivityTab.jsx — единый компонент «Активность на сайте».
 *
 * Используется одинаково в Customer360 и Lead360. Полностью бизнес-ориентированный:
 *   • Никаких технических терминов (session_id, tracker.js, API endpoints)
 *   • События переведены в действия на человеческом языке
 *   • KPI-карточки сверху: статус 🟢🟡🔴, последний визит, визитов за 30 дней,
 *     форм отправлено, обратных звонков
 *   • Лента событий с группировкой по дням
 *   • i18n: uk / en / bg (Russian не поддерживается)
 *
 * Endpoint: GET /api/v1/site-activity/by-entity/{entityId}
 *
 * Props:
 *   - entityId   (required) — customer.id или lead.id
 *   - entityKind (optional, default 'customer') — 'customer' | 'lead'
 *   - refreshKey (optional) — bump to force reload (parent's nonce)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Pulse,
  Clock,
  PaperPlaneTilt,
  PhoneCall,
  House,
  Calculator,
  Globe,
  FireSimple,
  Thermometer,
  Snowflake,
  ArrowsClockwise,
  CheckCircle,
  ListMagnifyingGlass,
  CursorClick,
  SignIn,
  Browser,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ─────────────────────────────────────────────────────────────────────────────
// i18n micro-dictionary  (uk / en / bg)                                      ─
// ─────────────────────────────────────────────────────────────────────────────
const T = {
  uk: {
    activity_title:        'Активність на сайті',
    activity_subtitle:     'Як цей клієнт поводиться у вашому веб-сайті — у режимі реального часу.',
    refresh:               'Оновити',
    loading:               'Завантаження…',
    no_data_title:         'Поки немає активності',
    no_data_subtitle:      'Як тільки клієнт зайде на сайт або заповнить форму — події з\'являться тут.',
    kpi_last_visit:        'Останній візит',
    kpi_status:            'Статус',
    kpi_visits_30d:        'Візити за 30 днів',
    kpi_forms:             'Заявки',
    kpi_callbacks:         'Зворотні дзвінки',
    kpi_logins:            'Входи в кабінет',
    status_active:         'Активний',
    status_warm:           'Теплий',
    status_inactive:       'Неактивний',
    status_active_hint:    'Був на сайті за останні 24 години',
    status_warm_hint:      'Був на сайті 1–7 днів тому',
    status_inactive_hint:  'Не з\'являвся більше 7 днів',
    timeline_title:        'Стрічка дій',
    open_link:             'Відкрити сторінку',
    just_now:              'щойно',
    minutes_ago:           'хв тому',
    hours_ago:             'год тому',
    days_ago:              'дн тому',
    never:                 'ніколи',
    today:                 'Сьогодні',
    yesterday:             'Вчора',
    // event labels
    event_form_active:     'Почав заповнювати форму',
    event_form_submitted:  'Надіслав заявку',
    event_callback_request:'Замовив зворотний дзвінок',
    event_cabinet_login:   'Увійшов в особистий кабінет',
    event_unknown:         'Активність на сайті',
  },
  en: {
    activity_title:        'Site activity',
    activity_subtitle:     'How this customer behaves on your website — in real time.',
    refresh:               'Refresh',
    loading:               'Loading…',
    no_data_title:         'No activity yet',
    no_data_subtitle:      'Events will appear here as soon as the customer visits the site or fills a form.',
    kpi_last_visit:        'Last visit',
    kpi_status:            'Status',
    kpi_visits_30d:        'Visits (30 days)',
    kpi_forms:             'Form submits',
    kpi_callbacks:         'Callback requests',
    kpi_logins:            'Cabinet logins',
    status_active:         'Active',
    status_warm:           'Warm',
    status_inactive:       'Inactive',
    status_active_hint:    'Visited within last 24 hours',
    status_warm_hint:      'Visited 1–7 days ago',
    status_inactive_hint:  'No visits in 7+ days',
    timeline_title:        'Action stream',
    open_link:             'Open page',
    just_now:              'just now',
    minutes_ago:           'min ago',
    hours_ago:             'h ago',
    days_ago:              'd ago',
    never:                 'never',
    today:                 'Today',
    yesterday:             'Yesterday',
    event_form_active:     'Started filling a form',
    event_form_submitted:  'Submitted a request',
    event_callback_request:'Requested a call back',
    event_cabinet_login:   'Logged into the cabinet',
    event_unknown:         'Site activity',
  },
  bg: {
    activity_title:        'Активност на сайта',
    activity_subtitle:     'Как се държи този клиент във вашия уебсайт — в реално време.',
    refresh:               'Обнови',
    loading:               'Зарежда…',
    no_data_title:         'Все още няма активност',
    no_data_subtitle:      'Събитията ще се появят, щом клиентът посети сайта или попълни форма.',
    kpi_last_visit:        'Последно посещение',
    kpi_status:            'Статус',
    kpi_visits_30d:        'Посещения (30 дни)',
    kpi_forms:             'Подадени форми',
    kpi_callbacks:         'Заявки за обаждане',
    kpi_logins:            'Влизания в кабинета',
    status_active:         'Активен',
    status_warm:           'Топъл',
    status_inactive:       'Неактивен',
    status_active_hint:    'Посетен през последните 24 часа',
    status_warm_hint:      'Посетен преди 1–7 дни',
    status_inactive_hint:  'Без посещения над 7 дни',
    timeline_title:        'Лента с действия',
    open_link:             'Отвори страница',
    just_now:              'сега',
    minutes_ago:           'мин',
    hours_ago:             'ч',
    days_ago:              'д',
    never:                 'никога',
    today:                 'Днес',
    yesterday:             'Вчера',
    event_form_active:     'Започна да попълва формуляр',
    event_form_submitted:  'Изпрати заявка',
    event_callback_request:'Поиска обратно обаждане',
    event_cabinet_login:   'Влезе в личния кабинет',
    event_unknown:         'Активност на сайта',
  },
};

const useT = () => {
  const { lang } = useLang() || { lang: 'uk' };
  const dict = T[lang] || T.uk;
  return (k) => dict[k] || T.uk[k] || k;
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers                                                                     ─
// ─────────────────────────────────────────────────────────────────────────────

const EVENT_META = {
  form_active:       { icon: ListMagnifyingGlass, color: 'text-indigo-500',  bg: 'bg-indigo-50',  ring: 'border-indigo-200',  labelKey: 'event_form_active' },
  form_submitted:    { icon: PaperPlaneTilt,      color: 'text-emerald-600', bg: 'bg-emerald-50', ring: 'border-emerald-200', labelKey: 'event_form_submitted' },
  callback_request:  { icon: PhoneCall,           color: 'text-rose-600',    bg: 'bg-rose-50',    ring: 'border-rose-200',    labelKey: 'event_callback_request' },
  cabinet_login:     { icon: SignIn,              color: 'text-sky-600',     bg: 'bg-sky-50',     ring: 'border-sky-200',     labelKey: 'event_cabinet_login' },
};

const STATUS_META = {
  active:   { icon: FireSimple,  color: 'text-emerald-600', dot: 'bg-emerald-500', pill: 'bg-emerald-50 text-emerald-700 border-emerald-200', hintKey: 'status_active_hint',   labelKey: 'status_active'   },
  warm:     { icon: Thermometer, color: 'text-amber-600',   dot: 'bg-amber-500',   pill: 'bg-amber-50 text-amber-700 border-amber-200',       hintKey: 'status_warm_hint',     labelKey: 'status_warm'     },
  inactive: { icon: Snowflake,   color: 'text-rose-600',    dot: 'bg-rose-500',    pill: 'bg-rose-50 text-rose-700 border-rose-200',          hintKey: 'status_inactive_hint', labelKey: 'status_inactive' },
};

const _authHeaders = () => {
  const tok = (typeof window !== 'undefined' && localStorage.getItem('token')) || '';
  return tok ? { Authorization: `Bearer ${tok}` } : {};
};

function relativeTime(iso, t) {
  if (!iso) return t('never');
  const ts = new Date(iso).getTime();
  if (!ts) return t('never');
  const diffSec = Math.max(0, (Date.now() - ts) / 1000);
  if (diffSec < 60)        return t('just_now');
  const m = Math.floor(diffSec / 60);
  if (m < 60)              return `${m} ${t('minutes_ago')}`;
  const h = Math.floor(m / 60);
  if (h < 24)              return `${h} ${t('hours_ago')}`;
  const d = Math.floor(h / 24);
  return `${d} ${t('days_ago')}`;
}

function dayBucketLabel(iso, t) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const day = new Date(d); day.setHours(0, 0, 0, 0);
  if (day.getTime() === today.getTime()) return t('today');
  if (day.getTime() === yesterday.getTime()) return t('yesterday');
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'long' });
}

function clockTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Try to extract a friendly page name from a tracked URL.
//   "https://bibi.cars/calculator/hyundai-tucson-2022" → "Calculator · Hyundai Tucson 2022"
//   "https://bibi.cars/cabinet/contracts" → "Cabinet · Contracts"
function prettyPath(url) {
  if (!url) return null;
  try {
    const u = new URL(url);
    const parts = u.pathname.split('/').filter(Boolean);
    if (parts.length === 0) return u.hostname;
    return parts.map((p) => p.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())).join(' · ');
  } catch {
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components                                                              ─
// ─────────────────────────────────────────────────────────────────────────────

const KpiCard = ({ icon: Icon, title, value, hint, accent = 'text-zinc-900', subValue, testId }) => (
  <div
    className="rounded-2xl border border-zinc-200 bg-white p-4 hover:shadow-sm transition-shadow"
    data-testid={testId}
  >
    <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-2">
      <Icon size={14} weight="duotone" /> {title}
    </div>
    <div className={`text-2xl font-bold ${accent} tabular-nums leading-none`}>{value}</div>
    {subValue ? (
      <div className="text-xs text-zinc-500 mt-1">{subValue}</div>
    ) : null}
    {hint ? (
      <div className="text-[11px] text-zinc-400 mt-1">{hint}</div>
    ) : null}
  </div>
);

const StatusPill = ({ status, t }) => {
  const meta = STATUS_META[status] || STATUS_META.inactive;
  const Icon = meta.icon;
  return (
    <div
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-semibold ${meta.pill}`}
      data-testid={`activity-status-pill-${status}`}
    >
      <span className={`w-2 h-2 rounded-full ${meta.dot}`} />
      <Icon size={14} weight="duotone" />
      {t(meta.labelKey)}
    </div>
  );
};

const TimelineEntry = ({ event, t, isFirst, isLast }) => {
  const meta = EVENT_META[event.event_type] || {
    icon: CursorClick, color: 'text-zinc-500', bg: 'bg-zinc-50', ring: 'border-zinc-200', labelKey: 'event_unknown',
  };
  const Icon = meta.icon;
  const path = prettyPath(event.page_url);
  return (
    <li className="relative pl-12" data-testid={`activity-event-${event.event_type}`}>
      {/* connector */}
      {!isLast && <span className="absolute left-[1.05rem] top-9 bottom-0 w-px bg-zinc-200" />}
      {/* dot */}
      <span
        className={`absolute left-0 top-1 inline-flex w-9 h-9 items-center justify-center rounded-xl border ${meta.bg} ${meta.ring}`}
      >
        <Icon size={18} className={meta.color} weight="duotone" />
      </span>
      <div className="pb-5">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <p className="font-medium text-zinc-900 text-sm">{t(meta.labelKey)}</p>
          <time className="text-xs text-zinc-400 tabular-nums shrink-0" title={new Date(event.received_at).toLocaleString()}>
            {clockTime(event.received_at)}
          </time>
        </div>
        {path && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-zinc-500">
            <Browser size={12} className="text-zinc-400" />
            <span className="truncate" title={event.page_url}>{path}</span>
          </div>
        )}
        {event.page_url && (
          <a
            href={event.page_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 mt-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-700"
          >
            <Globe size={11} /> {t('open_link')}
          </a>
        )}
      </div>
    </li>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main component                                                              ─
// ─────────────────────────────────────────────────────────────────────────────

const ActivityTab = ({ entityId, entityKind = 'customer', refreshKey = 0 }) => {
  const t = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [, force] = useState(0); // re-render for "X min ago" labels

  const load = useCallback(async (silent = false) => {
    if (!entityId) return;
    if (silent) setRefreshing(true); else setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/v1/site-activity/by-entity/${encodeURIComponent(entityId)}?limit=100`,
        { headers: _authHeaders() },
      );
      const j = await res.json();
      if (!res.ok) throw new Error(j?.detail || `HTTP ${res.status}`);
      setData(j);
    } catch (err) {
      // graceful empty state — don't toast spam users on missing data
      setData({ found: false, kpi: null, timeline: [] });
      // eslint-disable-next-line no-console
      console.warn('[ActivityTab] load failed', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [entityId]);

  useEffect(() => { load(false); }, [load, refreshKey]);

  // Refresh relative timestamps every 60s so labels stay accurate.
  useEffect(() => {
    const id = setInterval(() => force((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  // Group timeline events by day-bucket
  const groupedTimeline = useMemo(() => {
    if (!data?.timeline?.length) return [];
    const out = [];
    let currentLabel = null;
    let currentList = null;
    for (const ev of data.timeline) {
      const label = dayBucketLabel(ev.received_at, t);
      if (label !== currentLabel) {
        currentLabel = label;
        currentList = { label, items: [] };
        out.push(currentList);
      }
      currentList.items.push(ev);
    }
    return out;
  }, [data, t]);

  const kpi = data?.kpi || {};
  const statusKey = kpi.status || 'inactive';

  // ── render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-4" data-testid="activity-tab-loading">
        <div className="h-32 bg-zinc-100 rounded-2xl animate-pulse" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {[0,1,2,3,4].map((i) => <div key={i} className="h-24 bg-zinc-100 rounded-2xl animate-pulse" />)}
        </div>
        <div className="h-96 bg-zinc-100 rounded-2xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid={`activity-tab-${entityKind}`}>
      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-start gap-3 justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-flex w-10 h-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <Pulse size={18} weight="duotone" />
          </span>
          <div>
            <h2 className="text-base font-semibold text-zinc-900">{t('activity_title')}</h2>
            <p className="text-sm text-zinc-500">{t('activity_subtitle')}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 disabled:opacity-60 text-zinc-700"
          data-testid="activity-refresh-btn"
        >
          <ArrowsClockwise size={14} className={refreshing ? 'animate-spin' : ''} />
          {t('refresh')}
        </button>
      </header>

      {/* ── Empty state ─────────────────────────────────────────────── */}
      {!data?.found ? (
        <div
          className="rounded-2xl border-2 border-dashed border-zinc-200 bg-zinc-50/40 px-6 py-12 text-center"
          data-testid="activity-empty-state"
        >
          <span className="inline-flex w-14 h-14 items-center justify-center rounded-2xl bg-white border border-zinc-200 mb-3">
            <Pulse size={22} weight="duotone" className="text-zinc-400" />
          </span>
          <p className="font-semibold text-zinc-900">{t('no_data_title')}</p>
          <p className="text-sm text-zinc-500 mt-1 max-w-md mx-auto">{t('no_data_subtitle')}</p>
        </div>
      ) : (
        <>
          {/* ── KPI ─────────────────────────────────────────────────── */}
          <section
            className="grid grid-cols-2 lg:grid-cols-5 gap-3"
            data-testid="activity-kpi-grid"
          >
            <KpiCard
              icon={Clock}
              title={t('kpi_last_visit')}
              value={relativeTime(kpi.last_visit_at, t)}
              subValue={kpi.last_visit_at ? new Date(kpi.last_visit_at).toLocaleString() : null}
              testId="activity-kpi-last-visit"
            />
            <div
              className="rounded-2xl border border-zinc-200 bg-white p-4 flex flex-col justify-between"
              data-testid="activity-kpi-status"
            >
              <div className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-2 flex items-center gap-1">
                <Pulse size={14} weight="duotone" /> {t('kpi_status')}
              </div>
              <div>
                <StatusPill status={statusKey} t={t} />
                <p className="text-[11px] text-zinc-400 mt-2">{t(STATUS_META[statusKey].hintKey)}</p>
              </div>
            </div>
            <KpiCard
              icon={Browser}
              title={t('kpi_visits_30d')}
              value={kpi.visits_30d ?? 0}
              testId="activity-kpi-visits"
            />
            <KpiCard
              icon={PaperPlaneTilt}
              title={t('kpi_forms')}
              value={kpi.forms_count ?? 0}
              accent={(kpi.forms_count ?? 0) > 0 ? 'text-emerald-600' : 'text-zinc-900'}
              testId="activity-kpi-forms"
            />
            <KpiCard
              icon={PhoneCall}
              title={t('kpi_callbacks')}
              value={kpi.callbacks_count ?? 0}
              accent={(kpi.callbacks_count ?? 0) > 0 ? 'text-rose-600' : 'text-zinc-900'}
              testId="activity-kpi-callbacks"
            />
          </section>

          {/* ── Timeline ────────────────────────────────────────────── */}
          <section
            className="rounded-2xl border border-zinc-200 bg-white p-5 sm:p-6"
            data-testid="activity-timeline"
          >
            <h3 className="text-sm font-semibold text-zinc-900 mb-4 flex items-center gap-2">
              <House size={16} weight="duotone" className="text-zinc-500" />
              {t('timeline_title')}
            </h3>
            {groupedTimeline.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center py-6">{t('no_data_subtitle')}</p>
            ) : (
              <div className="space-y-6">
                {groupedTimeline.map((group, gIdx) => (
                  <div key={`${group.label}-${gIdx}`} data-testid={`activity-day-${gIdx}`}>
                    <div className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 mb-3">
                      {group.label}
                    </div>
                    <ul className="relative">
                      {group.items.map((ev, idx) => (
                        <TimelineEntry
                          key={`${ev.received_at}-${ev.event_type}-${idx}`}
                          event={ev}
                          t={t}
                          isFirst={idx === 0}
                          isLast={idx === group.items.length - 1}
                        />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default ActivityTab;
