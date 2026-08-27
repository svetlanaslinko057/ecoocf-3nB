/**
 * AdminSiteTrackerPage — installation guide for the public-site JS tracker.
 *
 * The backend already implements the ingest endpoint at
 *   POST /api/v1/site-activity
 * and serves the public JS snippet at
 *   GET  /api/v1/site-activity/tracker.js
 *
 * This page renders the install instructions returned by
 *   GET  /api/v1/site-activity/setup
 * along with copy-to-clipboard buttons for every code block. Admins paste
 * the snippet on the bibi.cars website and the CRM starts receiving
 * online/offline events in real time (Customer 360 → Activity tab).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  Code,
  Copy,
  CheckCircle,
  Globe,
  Pulse,
  ArrowSquareOut,
  Info,
  Lightning,
  ShieldCheck,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const apiFetch = (path, init = {}) => {
  const token = (typeof window !== 'undefined' && localStorage.getItem('token')) || '';
  const headers = {
    ...(init.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
};

// ── Localised micro-dictionary (uk / en / bg) ──────────────────────────────
const T = {
  uk: {
    page_title:      'JS-трекер для зовнішнього сайту',
    page_subtitle:   'Цей скрипт треба вставити на bibi.cars. Він автоматично пінгує CRM подіями (cabinet_login, form_active, form_submitted, callback_request, session_end) і відображає онлайн-статус ліда чи клієнта в Customer 360.',
    loading:         'Завантаження…',
    section_install: 'Установка (1 рядок коду)',
    section_install_hint: 'Скопіюйте та вставте перед </body> на ВСІХ сторінках публічного сайту. Більше нічого робити не потрібно — решта подій спрацьовує автоматично.',
    section_identify: 'Прив\'язка відвідувача (опційно)',
    section_identify_hint: 'Якщо відвідувач уже авторизований або заповнив форму, передайте phone/email — CRM зв\'яже подію з конкретним лідом/клієнтом.',
    section_manual:  'Ручні події',
    section_manual_hint: 'Викликайте window.bibiTracker.track() щоразу, коли треба зафіксувати дію (напр. "Замовити дзвінок").',
    section_endpoints: 'Кінцеві точки API',
    section_events:  'Типи подій, що відстежуються',
    section_test:    'Перевірка',
    section_test_hint: 'Відправити тестову подію прямо звідси, щоб переконатися, що ingest працює.',
    test_btn:        'Відправити тестову подію',
    test_phone:      'Телефон для прив\'язки',
    test_event:      'Тип події',
    test_sending:    'Надсилаю…',
    test_ok:         'Подія прийнята. Перевірте Customer 360.',
    test_err:        'Помилка ingest: ',
    copy:            'Копіювати',
    copied:          'Скопійовано',
    notes:           'Нотатки',
    tracker_js:      'Сирий JS-трекер',
    open_tracker:    'Відкрити tracker.js',
    api_key:         'Публічний API-ключ',
    api_key_hint:    'Цей ключ вшитий у <script>. Сам по собі він не дає доступу до CRM — лише до ingest endpoint.',
  },
  en: {
    page_title:      'JS-tracker for the public site',
    page_subtitle:   'Paste this snippet on bibi.cars to make the CRM receive real-time activity events (cabinet_login, form_active, form_submitted, callback_request, session_end). Lead/Customer 360 will then show the live online-status badge.',
    loading:         'Loading…',
    section_install: 'Installation (one-line snippet)',
    section_install_hint: 'Copy and paste before </body> on EVERY page of the public website. No further setup is required — the rest is automatic.',
    section_identify: 'Bind visitor to a known person (optional)',
    section_identify_hint: 'When the visitor is logged in or has filled the contact form, pass phone/email so the CRM can link the events to a specific lead/customer.',
    section_manual:  'Manual events',
    section_manual_hint: 'Call window.bibiTracker.track() whenever you need to record an action (e.g. "Request a call").',
    section_endpoints: 'API endpoints',
    section_events:  'Tracked event types',
    section_test:    'Live test',
    section_test_hint: 'Fire a test event right from here to verify the ingest pipeline.',
    test_btn:        'Send test event',
    test_phone:      'Phone to bind to',
    test_event:      'Event type',
    test_sending:    'Sending…',
    test_ok:         'Event accepted. Open Customer 360 to verify.',
    test_err:        'Ingest error: ',
    copy:            'Copy',
    copied:          'Copied',
    notes:           'Notes',
    tracker_js:      'Raw tracker source',
    open_tracker:    'Open tracker.js',
    api_key:         'Public API key',
    api_key_hint:    'This key is embedded in the <script> tag. By itself it grants ingest access only — no CRM data is exposed.',
  },
  bg: {
    page_title:      'JS-тракер за външния сайт',
    page_subtitle:   'Поставете този скрипт на bibi.cars. Той автоматично изпраща събития (cabinet_login, form_active, form_submitted, callback_request, session_end) към CRM и онлайн-статусът се появява в Customer 360.',
    loading:         'Зареждане…',
    section_install: 'Инсталация (един ред код)',
    section_install_hint: 'Копирайте и поставете преди </body> на ВСИЧКИ страници от публичния сайт.',
    section_identify: 'Свързване на посетител (опционално)',
    section_identify_hint: 'Когато посетителят е логнат или вече е попълнил форма, подайте phone/email, за да свърже CRM събитията с конкретен клиент.',
    section_manual:  'Ръчни събития',
    section_manual_hint: 'Извикайте window.bibiTracker.track() при нужда (напр. "Поискай обаждане").',
    section_endpoints: 'API endpoint-и',
    section_events:  'Видове проследявани събития',
    section_test:    'Тест на живо',
    section_test_hint: 'Изпратете тестово събитие, за да проверите потока.',
    test_btn:        'Изпрати тестово събитие',
    test_phone:      'Телефон за свързване',
    test_event:      'Тип събитие',
    test_sending:    'Изпраща се…',
    test_ok:         'Събитието е прието. Отворете Customer 360.',
    test_err:        'Грешка: ',
    copy:            'Копирай',
    copied:          'Копирано',
    notes:           'Бележки',
    tracker_js:      'Сурс на tracker.js',
    open_tracker:    'Отвори tracker.js',
    api_key:         'Публичен API-ключ',
    api_key_hint:    'Този ключ е вграден в <script>. Сам по себе си дава достъп само до ingest endpoint.',
  },
};

const useT = () => {
  const { lang } = useLang() || { lang: 'uk' };
  const dict = T[lang] || T.uk;
  return (k) => dict[k] || T.uk[k] || k;
};

// ─── Small UI primitives ───────────────────────────────────────────────────

const CopyButton = ({ value, label, copied, onCopy, testId }) => (
  <button
    type="button"
    onClick={() => onCopy(value)}
    data-testid={testId}
    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-zinc-200 bg-white hover:bg-zinc-50 hover:border-zinc-300 active:bg-zinc-100 transition-colors"
  >
    {copied ? (
      <><CheckCircle size={14} weight="fill" className="text-emerald-500" /> {label.copied}</>
    ) : (
      <><Copy size={14} /> {label.copy}</>
    )}
  </button>
);

const CodeBlock = ({ code, lang = 'html', label, testId, onCopy, copied }) => (
  <div className="relative rounded-xl border border-zinc-200 bg-zinc-950 overflow-hidden" data-testid={`${testId}-block`}>
    <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800">
      <span className="text-[11px] uppercase tracking-wider font-bold text-zinc-400">{lang}</span>
      <CopyButton value={code} label={label} copied={copied} onCopy={onCopy} testId={`${testId}-copy`} />
    </div>
    <pre className="overflow-x-auto px-4 py-3 text-[12.5px] leading-relaxed text-zinc-100 font-mono whitespace-pre">
      {code}
    </pre>
  </div>
);

const Section = ({ icon: Icon, title, subtitle, children }) => (
  <section className="bg-white border border-zinc-200 rounded-2xl p-5 sm:p-6 shadow-sm">
    <header className="mb-4 flex items-start gap-3">
      <span className="inline-flex w-9 h-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 shrink-0">
        <Icon size={18} weight="duotone" />
      </span>
      <div>
        <h2 className="text-base font-semibold text-zinc-900">{title}</h2>
        {subtitle && <p className="text-sm text-zinc-500 mt-0.5">{subtitle}</p>}
      </div>
    </header>
    {children}
  </section>
);

// ─── Main page ─────────────────────────────────────────────────────────────

export default function AdminSiteTrackerPage() {
  const t = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedKey, setCopiedKey] = useState(null);
  const [testPhone, setTestPhone] = useState('');
  const [testEvent, setTestEvent] = useState('form_submitted');
  const [testSending, setTestSending] = useState(false);

  const labelL = useMemo(() => ({ copy: t('copy'), copied: t('copied') }), [t]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/site-activity/setup');
      const json = await res.json();
      if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
      setData(json);
    } catch (err) {
      toast.error(err?.message || 'Failed to load setup docs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCopy = useCallback(async (value, key) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey((cur) => (cur === key ? null : cur)), 1500);
      toast.success(t('copied'));
    } catch {
      toast.error('Clipboard unavailable');
    }
  }, [t]);

  const sendTestEvent = useCallback(async () => {
    if (!data) return;
    setTestSending(true);
    try {
      const res = await fetch(data.ingest_url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          [data.api_key_header]: data.api_key_value,
        },
        body: JSON.stringify({
          event_type: testEvent,
          phone: testPhone || undefined,
          session_id: `admin-test-${Date.now()}`,
          user_agent: navigator.userAgent,
        }),
      });
      const json = await res.json();
      if (!res.ok || json.success === false) throw new Error(json?.detail || `HTTP ${res.status}`);
      const matched = json.matched ? ` → matched ${json.target?.kind} ${json.target?.name}` : ' (no match — visitor anonymous)';
      toast.success(`${t('test_ok')}${matched}`);
    } catch (err) {
      toast.error(`${t('test_err')}${err?.message || err}`);
    } finally {
      setTestSending(false);
    }
  }, [data, testEvent, testPhone, t]);

  if (loading || !data) {
    return (
      <div className="space-y-6" data-testid="admin-site-tracker-loading">
        <div className="h-32 bg-zinc-100 rounded-2xl animate-pulse" />
        <div className="h-64 bg-zinc-100 rounded-2xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admin-site-tracker-page">
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <header className="bg-gradient-to-br from-indigo-50 via-white to-white border border-indigo-100 rounded-2xl p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <span className="inline-flex w-12 h-12 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600 shrink-0">
            <Pulse size={24} weight="duotone" />
          </span>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-2xl font-semibold text-zinc-900" data-testid="page-title">
              {t('page_title')}
            </h1>
            <p className="text-sm text-zinc-600 mt-1 max-w-3xl">
              {t('page_subtitle')}
            </p>
            <a
              href={data.tracker_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 mt-3 text-xs font-medium text-indigo-600 hover:text-indigo-700"
              data-testid="tracker-js-link"
            >
              <ArrowSquareOut size={14} /> {t('open_tracker')}
            </a>
          </div>
        </div>
      </header>

      {/* ── 1) Install snippet ───────────────────────────────────────── */}
      <Section icon={Code} title={`1. ${t('section_install')}`} subtitle={t('section_install_hint')}>
        <CodeBlock
          code={data.snippet}
          lang="HTML"
          testId="snippet"
          label={labelL}
          copied={copiedKey === 'snippet'}
          onCopy={(v) => handleCopy(v, 'snippet')}
        />
      </Section>

      {/* ── 2) Identify visitor ──────────────────────────────────────── */}
      <Section icon={ShieldCheck} title={`2. ${t('section_identify')}`} subtitle={t('section_identify_hint')}>
        <CodeBlock
          code={data.identify_example}
          lang="HTML"
          testId="identify"
          label={labelL}
          copied={copiedKey === 'identify'}
          onCopy={(v) => handleCopy(v, 'identify')}
        />
      </Section>

      {/* ── 3) Manual event API ──────────────────────────────────────── */}
      <Section icon={Lightning} title={`3. ${t('section_manual')}`} subtitle={t('section_manual_hint')}>
        <CodeBlock
          code={data.manual_event_example}
          lang="HTML"
          testId="manual"
          label={labelL}
          copied={copiedKey === 'manual'}
          onCopy={(v) => handleCopy(v, 'manual')}
        />
      </Section>

      {/* ── 4) Endpoints + API key ───────────────────────────────────── */}
      <Section icon={Globe} title={t('section_endpoints')}>
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3">
            <p className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-1">POST · ingest</p>
            <code className="text-[12px] font-mono text-zinc-800 break-all">{data.ingest_url}</code>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3">
            <p className="text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-1">GET · tracker.js</p>
            <code className="text-[12px] font-mono text-zinc-800 break-all">{data.tracker_url}</code>
          </div>
        </div>
        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 flex items-start gap-3">
          <Info size={18} className="text-amber-600 shrink-0 mt-0.5" weight="duotone" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-amber-800">{t('api_key')} · {data.api_key_header}</p>
            <code className="text-[12px] font-mono text-amber-900 break-all" data-testid="api-key-value">{data.api_key_value}</code>
            <p className="text-[11px] text-amber-700 mt-1">{t('api_key_hint')}</p>
          </div>
        </div>
      </Section>

      {/* ── 5) Valid events ──────────────────────────────────────────── */}
      <Section icon={Pulse} title={t('section_events')}>
        <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2" data-testid="events-list">
          {(data.valid_events || []).map((ev) => (
            <li
              key={ev}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-zinc-200 bg-white text-sm font-mono"
              data-testid={`event-${ev}`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {ev}
            </li>
          ))}
        </ul>
      </Section>

      {/* ── 6) Live test ─────────────────────────────────────────────── */}
      <Section icon={Lightning} title={t('section_test')} subtitle={t('section_test_hint')}>
        <div className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <div>
            <label htmlFor="tracker-test-phone" className="block text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-1">{t('test_phone')}</label>
            <input
              id="tracker-test-phone"
              type="text"
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
              placeholder="+359888123456"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
              data-testid="test-phone-input"
            />
          </div>
          <div>
            <label htmlFor="tracker-test-event" className="block text-[11px] uppercase tracking-wider font-bold text-zinc-500 mb-1">{t('test_event')}</label>
            <select
              id="tracker-test-event"
              value={testEvent}
              onChange={(e) => setTestEvent(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
              data-testid="test-event-select"
            >
              {(data.valid_events || []).map((ev) => (
                <option key={ev} value={ev}>{ev}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={sendTestEvent}
            disabled={testSending}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            data-testid="test-send-button"
          >
            {testSending ? <Pulse size={16} className="animate-pulse" /> : <Lightning size={16} weight="fill" />}
            {testSending ? t('test_sending') : t('test_btn')}
          </button>
        </div>
      </Section>

      {/* ── 7) Notes ─────────────────────────────────────────────────── */}
      <Section icon={Info} title={t('notes')}>
        <ul className="space-y-2 text-sm text-zinc-700" data-testid="notes-list">
          {(data.notes || []).map((note, i) => (
            <li key={i} className="flex gap-2 leading-relaxed">
              <span className="text-indigo-400 shrink-0">›</span>
              <span>{note}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
