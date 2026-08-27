/**
 * AdminSystemSettingsPage — «Система»  (Wave 23: i18n + mobile-adaptive).
 *
 * Now fully localised in uk / en / bg (Russian intentionally absent — that's
 * the CRM-wide policy). Layout is mobile-first: the header switches to
 * column on <sm, integration cards stack to one column, the code block
 * scrolls horizontally, and the whole page never overflows the viewport.
 *
 * Backend remained unchanged:
 *   GET   /api/admin/system/settings
 *   PATCH /api/admin/system/settings
 *   POST  /api/admin/system/settings/jwt/rotate
 *   GET   /api/v1/site-activity/setup
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  Globe, Plug, ShieldCheck, Plus, X, ArrowsClockwise, Copy, Warning,
  CheckCircle, SignOut, FloppyDisk, CaretDown, CaretRight, Code,
  Browser, PhoneCall, CreditCard, PaperPlaneTilt, Info,
} from '@phosphor-icons/react';
import { useAuth } from '../../App';
import { useLang } from '../../i18n';
import HelpTooltip from '../../components/ui/HelpTooltip';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const apiFetch = (path, init = {}) => {
  const token = (typeof window !== 'undefined' && localStorage.getItem('token')) || '';
  const headers = {
    ...(init.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
};

// ─────────────────────────────────────────────────────────────────────────────
// Localisation (uk / en / bg)                                                  ─
// ─────────────────────────────────────────────────────────────────────────────
const T = {
  uk: {
    pageTitle:        'Сайт та інтеграції',
    pageSubtitle:     'Тут налаштовується головна адреса сайту, копіюються посилання для зовнішніх сервісів (Ringostat, Stripe, Resend) і керується безпека сесій. Зміни застосовуються миттєво — рестарт не потрібен.',
    pageTooltip:      'Єдиний майданчик для конфігурації публічного сайту та зовнішніх інтеграцій. Не плутайте з пунктом меню «System» — той блок керує внутрішніми параметрами CRM (модулі, права, кеші).',
    btnSaving:        'Збереження…',
    btnSave:          'Зберегти зміни',
    btnSaved:         'Все збережено',
    btnSaveDisabled:  'Лише Master Admin може редагувати ці налаштування',
    // Block 1 — Domain
    blockDomain:      'Домен сайту',
    blockDomainHint:  'Адреса, на якій працює CRM. Від неї будуються посилання в листах, договорах та інтеграціях.',
    blockDomainTip:   'Це канонічна URL, яку отримують клієнти у листах, договорах і SMS. Якщо змінити домен — оновіть DNS-записи й SSL-сертифікат до збереження.',
    fieldMainAddress: 'Основна адреса',
    fieldExample:     'Приклад: https://bibi.cars (без слеша в кінці).',
    allowSubdomains:  'Дозволити піддомени',
    allowSubdomainsHint:'Увімкніть, якщо у вас є admin.bibi.cars, app.bibi.cars чи інші піддомени.',
    // Block 2 — Integrations
    blockIntegrations:'Інтеграційні посилання',
    blockIntegrationsHint:'Скопіюйте ці URL у відповідні дашборди (Ringostat, Stripe, Resend), щоб сервіси відправляли події до CRM.',
    blockIntegrationsTip:'Це webhook-адреси, на які зовнішні сервіси будуть надсилати події (нові дзвінки, успішні оплати, статуси email). Без них Customer 360 не побачить активності з телефонії та платежів.',
    cardRingostat:    'Ringostat (телефонія)',
    cardRingostatHint:'Вставте в розділ «Webhooks» у кабінеті Ringostat.',
    cardStripe:       'Stripe (оплати)',
    cardStripeHint:   'Вставте в Stripe Dashboard → Developers → Webhooks.',
    cardResend:       'Resend (e-mail)',
    cardResendHint:   'Вставте в Resend → Webhooks для статусів доставки.',
    cardSiteOrigin:   'Адреса сайту',
    cardSiteOriginHint:'Канонічна URL — використовується в листах та договорах.',
    cardSiteTracker:  'Скрипт для сайту',
    cardSiteTrackerHint:'Передайте цей фрагмент розробнику сайту bibi.cars — він вставить його перед закриваючим </body> на кожній сторінці. Завдяки цьому в Customer 360 і Lead 360 з\u2019являється вкладка «Активність».',
    placeholderDomain:'— спочатку вкажіть домен сайту вище —',
    placeholderUrl:   '— спочатку вкажіть домен —',
    copy:             'Копіювати',
    copied:           'Готово',
    // Block 3 — Security
    blockSecurity:    'Безпека сесій',
    blockSecurityHint:'Аварійна кнопка: миттєво вийти з усіх активних користувацьких сесій. Використовуйте лише за підозри на витік паролів.',
    blockSecurityTip: 'Натискання генерує новий JWT-секрет на сервері: всі поточні токени стають недійсними, і кожен користувач муситиме увійти знову. Потрібен одноразовий рестарт backend.',
    securityWarningStrong:'Зверніть увагу:',
    securityWarning:  'після натискання кнопки усі співробітники (і ви теж) автоматично вийдуть із системи. Знадобиться повторний вхід та одноразовий перезапуск сервера.',
    btnTerminateAll:  'Завершити всі активні сесії',
    confirmTerminate: 'Завершити всі активні сесії?\n\nУсіх користувачів (і вас зокрема) буде розлогінено. Робіть це лише при підозрі на витік ключів.',
    toastTerminated:  'Всі сесії завершено. Потрібен перезапуск backend.',
    // Block 4 — Advanced
    blockAdvanced:    'Розширені налаштування',
    blockAdvancedHint:'Технічні параметри для devops-команди. Звичайному адміністратору не потрібні.',
    blockAdvancedTip: 'CORS allowlist потрібен, якщо CRM API викликається з додаткових доменів (staging-середовища, preview-гілки, партнерські віджети). Помилка тут проявляється як «Cross-Origin» в консолі браузера.',
    advancedToggle:   'CORS allowlist (для додаткових доменів)',
    advancedDescr:    'Додаткові домени, з яких браузер може звертатись до CRM API: preview-гілки, staging-середовища, партнерські віджети тощо. Основний домен (вище) додається автоматично.',
    advancedEmpty:    'Додаткових доменів немає.',
    advancedPlaceholder:'https://staging.bibi.cars',
    advancedAdd:      'Додати',
    envBaseline:      '.env baseline (read-only)',
    subdomainRegex:   'Derived subdomain regex',
    // Toasts
    toastLoadFail:    'Не вдалося завантажити: ',
    toastSaved:       'Збережено · інтеграційні посилання оновлено',
    toastSaveFail:    'Помилка: ',
    toastDuplicate:   'Цей домен уже у списку',
    toastDelete:      'Видалити',
    footerUpdated:    'Останнє оновлення:',
    footerBy:         'unknown',
  },
  en: {
    pageTitle:        'Site & Integrations',
    pageSubtitle:     'Configure the main site URL, copy integration endpoints (Ringostat, Stripe, Resend) and manage session security. Changes apply instantly — no restart required.',
    pageTooltip:      'Single place to configure the public website and external integrations. Not to be confused with the «System» menu entry — that one manages internal CRM parameters (modules, permissions, caches).',
    btnSaving:        'Saving…',
    btnSave:          'Save changes',
    btnSaved:         'All saved',
    btnSaveDisabled:  'Only Master Admin can edit these settings',
    blockDomain:      'Site domain',
    blockDomainHint:  'The address where the CRM lives. It powers the URLs used in emails, contracts and integrations.',
    blockDomainTip:   'This is the canonical URL customers receive in emails, contracts and SMS. If you change it — update DNS records and the SSL certificate before saving.',
    fieldMainAddress: 'Main address',
    fieldExample:     'Example: https://bibi.cars (no trailing slash).',
    allowSubdomains:  'Allow subdomains',
    allowSubdomainsHint:'Enable if you also use admin.bibi.cars, app.bibi.cars or other subdomains.',
    blockIntegrations:'Integration endpoints',
    blockIntegrationsHint:'Paste these URLs into the corresponding dashboards (Ringostat, Stripe, Resend) so they push events to the CRM.',
    blockIntegrationsTip:'These webhook URLs receive events from external services (new calls, successful payments, email delivery status). Without them, Customer 360 will not see telephony and payment activity.',
    cardRingostat:    'Ringostat (telephony)',
    cardRingostatHint:'Paste into the Ringostat dashboard → Webhooks section.',
    cardStripe:       'Stripe (payments)',
    cardStripeHint:   'Paste into Stripe Dashboard → Developers → Webhooks.',
    cardResend:       'Resend (e-mail)',
    cardResendHint:   'Paste into Resend → Webhooks for delivery status updates.',
    cardSiteOrigin:   'Site URL',
    cardSiteOriginHint:'Canonical URL — used inside emails and contracts.',
    cardSiteTracker:  'Site script',
    cardSiteTrackerHint:'Hand this snippet to the bibi.cars web developer — it must be placed before the closing </body> on every page. After that, the «Activity» tab in Customer 360 and Lead 360 starts receiving events.',
    placeholderDomain:'— set the site domain above first —',
    placeholderUrl:   '— set the domain first —',
    copy:             'Copy',
    copied:           'Copied',
    blockSecurity:    'Session security',
    blockSecurityHint:'Emergency button: log every active user out instantly. Use only when a credential leak is suspected.',
    blockSecurityTip: 'Pressing this generates a fresh JWT secret on the server: every existing token becomes invalid and every user must sign in again. A one-off backend restart is required.',
    securityWarningStrong:'Heads up:',
    securityWarning:  'after the button is pressed every staff member (and you too) will be signed out automatically. A re-login and a one-off server restart will be required.',
    btnTerminateAll:  'Terminate all active sessions',
    confirmTerminate: 'Terminate all active sessions?\n\nEvery user (including yourself) will be logged out. Use only when a key leak is suspected.',
    toastTerminated:  'All sessions terminated. Backend restart required.',
    blockAdvanced:    'Advanced settings',
    blockAdvancedHint:'Technical knobs for the DevOps team. Regular admins don\u2019t need to touch them.',
    blockAdvancedTip: 'The CORS allowlist is required when the CRM API is called from additional domains (staging environments, preview branches, partner widgets). A misconfiguration surfaces as a «Cross-Origin» error in the browser console.',
    advancedToggle:   'CORS allowlist (extra domains)',
    advancedDescr:    'Extra domains from which the browser can call the CRM API: preview branches, staging environments, partner widgets, and so on. The main domain (above) is added automatically.',
    advancedEmpty:    'No extra domains configured.',
    advancedPlaceholder:'https://staging.bibi.cars',
    advancedAdd:      'Add',
    envBaseline:      '.env baseline (read-only)',
    subdomainRegex:   'Derived subdomain regex',
    toastLoadFail:    'Failed to load: ',
    toastSaved:       'Saved · integration links refreshed',
    toastSaveFail:    'Error: ',
    toastDuplicate:   'This domain is already on the list',
    toastDelete:      'Delete',
    footerUpdated:    'Last update:',
    footerBy:         'unknown',
  },
  bg: {
    pageTitle:        'Сайт и интеграции',
    pageSubtitle:     'Тук се конфигурира основният URL на сайта, копират се връзките за външни услуги (Ringostat, Stripe, Resend) и се управлява сигурността на сесиите. Промените се прилагат веднага — не е нужен рестарт.',
    pageTooltip:      'Единно място за конфигуриране на публичния сайт и външните интеграции. Не бъркайте с менюто «System» — този раздел управлява вътрешни параметри на CRM (модули, права, кешове).',
    btnSaving:        'Запазване…',
    btnSave:          'Запази промените',
    btnSaved:         'Всичко запазено',
    btnSaveDisabled:  'Само Master Admin може да редактира тези настройки',
    blockDomain:      'Домейн на сайта',
    blockDomainHint:  'Адресът, на който работи CRM. От него се изграждат връзките в писма, договори и интеграции.',
    blockDomainTip:   'Това е каноничният URL, който клиентите получават в писма, договори и SMS. Ако го промените — обновете DNS записите и SSL сертификата преди да запазите.',
    fieldMainAddress: 'Основен адрес',
    fieldExample:     'Пример: https://bibi.cars (без наклонена черта в края).',
    allowSubdomains:  'Разреши поддомейни',
    allowSubdomainsHint:'Включете, ако имате admin.bibi.cars, app.bibi.cars или други поддомейни.',
    blockIntegrations:'Интеграционни връзки',
    blockIntegrationsHint:'Поставете тези URL-и в съответните табла (Ringostat, Stripe, Resend), за да изпращат събития към CRM.',
    blockIntegrationsTip:'Това са webhook адреси, на които външните услуги ще изпращат събития (нови обаждания, успешни плащания, статуси на доставка на писма). Без тях Customer 360 няма да вижда активността от телефония и плащания.',
    cardRingostat:    'Ringostat (телефония)',
    cardRingostatHint:'Поставете в Ringostat кабинета → секция «Webhooks».',
    cardStripe:       'Stripe (плащания)',
    cardStripeHint:   'Поставете в Stripe Dashboard → Developers → Webhooks.',
    cardResend:       'Resend (e-mail)',
    cardResendHint:   'Поставете в Resend → Webhooks за статуси на доставка.',
    cardSiteOrigin:   'URL на сайта',
    cardSiteOriginHint:'Каноничен URL — използва се в писма и договори.',
    cardSiteTracker:  'Скрипт за сайта',
    cardSiteTrackerHint:'Предайте този фрагмент на разработчика на bibi.cars — той трябва да го постави преди затварящия </body> на всяка страница. След това разделът «Активност» в Customer 360 и Lead 360 започва да получава събития.',
    placeholderDomain:'— първо посочете домейна по-горе —',
    placeholderUrl:   '— първо посочете домейн —',
    copy:             'Копирай',
    copied:           'Копирано',
    blockSecurity:    'Сигурност на сесиите',
    blockSecurityHint:'Аварийно копче: незабавно излизане от всички активни сесии. Използвайте само при съмнения за компрометирани пароли.',
    blockSecurityTip: 'Натискането генерира нов JWT секрет на сървъра: всички текущи токени стават невалидни и всеки потребител ще трябва да влезе отново. Необходим е еднократен рестарт на backend.',
    securityWarningStrong:'Внимание:',
    securityWarning:  'след натискане всички служители (вкл. вие) автоматично ще бъдат отписани. Ще е необходимо повторно влизане и еднократен рестарт на сървъра.',
    btnTerminateAll:  'Прекрати всички активни сесии',
    confirmTerminate: 'Прекратяване на всички активни сесии?\n\nВсички потребители (включително вие) ще бъдат отписани. Използвайте само при съмнения за изтичане на ключове.',
    toastTerminated:  'Всички сесии са прекратени. Необходим е рестарт на backend.',
    blockAdvanced:    'Разширени настройки',
    blockAdvancedHint:'Технически параметри за DevOps екипа. Не са нужни на обикновения администратор.',
    blockAdvancedTip: 'CORS allowlist е необходим, когато CRM API се извиква от допълнителни домейни (staging среди, preview-разклонения, партньорски виджети). Грешка тук се проявява като «Cross-Origin» в конзолата на браузъра.',
    advancedToggle:   'CORS allowlist (допълнителни домейни)',
    advancedDescr:    'Допълнителни домейни, от които браузърът може да обръща към CRM API: preview-разклонения, staging среди, партньорски виджети и т.н. Основният домейн (по-горе) се добавя автоматично.',
    advancedEmpty:    'Няма допълнителни домейни.',
    advancedPlaceholder:'https://staging.bibi.cars',
    advancedAdd:      'Добави',
    envBaseline:      '.env baseline (read-only)',
    subdomainRegex:   'Derived subdomain regex',
    toastLoadFail:    'Грешка при зареждане: ',
    toastSaved:       'Запазено · интеграционните връзки са обновени',
    toastSaveFail:    'Грешка: ',
    toastDuplicate:   'Този домейн вече е в списъка',
    toastDelete:      'Изтрий',
    footerUpdated:    'Последно обновление:',
    footerBy:         'unknown',
  },
};

const useTr = () => {
  const { lang } = useLang() || { lang: 'uk' };
  const dict = T[lang] || T.uk;
  return (k) => dict[k] ?? T.uk[k] ?? k;
};

// ─────────────────────────────────────────────────────────────────────────────
// Re-usable UI primitives                                                      ─
// ─────────────────────────────────────────────────────────────────────────────

const Section = ({ icon: Icon, title, hint, tooltip, children, testId }) => (
  <section
    className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5 lg:p-6 space-y-4"
    data-testid={testId}
  >
    <header className="flex items-start gap-3">
      {Icon ? (
        <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
          <Icon size={18} weight="duotone" className="text-indigo-600" />
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        {tooltip ? (
          <HelpTooltip text={tooltip} side="top" align="start">
            <h3
              className="inline text-[15px] font-semibold tracking-tight text-[#18181B] leading-tight cursor-help underline decoration-dotted decoration-1 decoration-[#A1A1AA] underline-offset-4"
              data-testid={`section-tip-${testId}`}
            >
              {title}
            </h3>
          </HelpTooltip>
        ) : (
          <h3 className="text-[15px] font-semibold tracking-tight text-[#18181B] leading-tight">
            {title}
          </h3>
        )}
        {hint ? (
          <p className="text-[12.5px] text-[#71717A] mt-1 leading-relaxed break-words">{hint}</p>
        ) : null}
      </div>
    </header>
    {children}
  </section>
);

const TextField = ({ label, value, onChange, placeholder, hint, testid, ...rest }) => (
  <label className="block">
    {label ? (
      <span className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">
        {label}
      </span>
    ) : null}
    <input
      type="text"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full h-10 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
      data-testid={testid}
      {...rest}
    />
    {hint ? (
      <p className="text-[11.5px] text-[#71717A] mt-1.5 leading-snug">{hint}</p>
    ) : null}
  </label>
);

const IntegrationCard = ({ icon: Icon, name, description, url, testid, t }) => {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    if (!url) return;
    navigator.clipboard?.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div
      className="rounded-xl border border-[#E4E4E7] bg-white p-4 hover:border-indigo-200 hover:shadow-sm transition-all"
      data-testid={`integration-card-${testid}`}
    >
      <div className="flex items-start gap-3 mb-3">
        <span className="inline-flex w-9 h-9 items-center justify-center rounded-lg bg-zinc-100 text-zinc-700 shrink-0">
          <Icon size={16} weight="duotone" />
        </span>
        <div className="flex-1 min-w-0">
          <h4 className="text-[13.5px] font-semibold text-[#18181B] leading-tight">{name}</h4>
          {description ? (
            <p className="text-[11.5px] text-[#71717A] mt-0.5 leading-snug break-words">{description}</p>
          ) : null}
        </div>
      </div>
      <div className="flex items-stretch gap-2">
        <div className="flex-1 min-w-0 h-10 px-3 rounded-lg border border-[#E4E4E7] bg-[#FAFAFA] text-[12px] sm:text-[12.5px] text-[#52525B] font-mono flex items-center truncate">
          {url || <span className="italic text-[#A1A1AA] truncate">{t('placeholderUrl')}</span>}
        </div>
        <button
          type="button"
          onClick={copy}
          disabled={!url}
          className="h-10 px-2.5 sm:px-3 rounded-lg bg-white border border-[#E4E4E7] text-[#18181B] text-[12px] font-semibold hover:border-indigo-400 hover:text-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-1.5 shrink-0"
          data-testid={`integration-copy-${testid}`}
        >
          {copied ? (
            <>
              <CheckCircle size={13} weight="bold" className="text-emerald-500" />
              <span className="hidden sm:inline">{t('copied')}</span>
            </>
          ) : (
            <>
              <Copy size={13} weight="bold" />
              <span className="hidden sm:inline">{t('copy')}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

const ScriptSnippetCard = ({ snippet, testid, t }) => {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    if (!snippet) return;
    navigator.clipboard?.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div
      className="rounded-xl border border-[#E4E4E7] bg-white p-4 sm:col-span-2"
      data-testid={`integration-card-${testid}`}
    >
      <div className="flex items-start gap-3 mb-3">
        <span className="inline-flex w-9 h-9 items-center justify-center rounded-lg bg-zinc-100 text-zinc-700 shrink-0">
          <Code size={16} weight="duotone" />
        </span>
        <div className="flex-1 min-w-0">
          <h4 className="text-[13.5px] font-semibold text-[#18181B] leading-tight">{t('cardSiteTracker')}</h4>
          <p className="text-[11.5px] text-[#71717A] mt-0.5 leading-snug break-words">{t('cardSiteTrackerHint')}</p>
        </div>
      </div>
      <div className="rounded-xl border border-[#E4E4E7] bg-zinc-950 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800 gap-2">
          <span className="text-[10.5px] uppercase tracking-wider font-bold text-zinc-400">HTML</span>
          <button
            type="button"
            onClick={copy}
            disabled={!snippet}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold rounded-md border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-100 disabled:opacity-50 shrink-0"
            data-testid={`integration-copy-${testid}`}
          >
            {copied ? (
              <><CheckCircle size={12} weight="fill" className="text-emerald-400" /> {t('copied')}</>
            ) : (
              <><Copy size={12} weight="bold" /> {t('copy')}</>
            )}
          </button>
        </div>
        <pre className="overflow-x-auto px-4 py-3 text-[11.5px] sm:text-[12px] leading-relaxed text-zinc-100 font-mono whitespace-pre">{snippet || `<!-- ${t('placeholderDomain')} -->`}</pre>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Page                                                                        ─
// ─────────────────────────────────────────────────────────────────────────────

const AdminSystemSettingsPage = () => {
  const t = useTr();
  const { user } = useAuth() || {};
  const role = ((user || {}).role || '').toLowerCase();
  // Backend MASTER_ROLES = {admin, owner, master_admin}
  const isMasterAdmin = ['admin', 'owner', 'master_admin'].includes(role);

  const [data, setData] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [newOrigin, setNewOrigin] = useState('');
  const [trackerSetup, setTrackerSetup] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch('/api/admin/system/settings');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setData(j);
      setDraft(j.settings);
    } catch (e) {
      toast.error(`Load failed: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTrackerSnippet = useCallback(async () => {
    try {
      const r = await apiFetch('/api/v1/site-activity/setup');
      if (!r.ok) return;
      const j = await r.json();
      setTrackerSetup(j);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { load(); loadTrackerSnippet(); }, [load, loadTrackerSnippet]);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const r = await apiFetch('/api/admin/system/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          production_domain:  draft.production_domain,
          cors_origins:       draft.cors_origins || [],
          cors_origin_regex:  draft.cors_origin_regex,
          allow_subdomains:   draft.allow_subdomains,
        }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const j = await r.json();
      setData(j);
      setDraft(j.settings);
      toast.success(t('toastSaved'));
    } catch (e) {
      toast.error(`${t('toastSaveFail')}${e.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const addOrigin = () => {
    const o = (newOrigin || '').trim().replace(/\/$/, '');
    if (!o) return;
    if ((draft.cors_origins || []).includes(o)) {
      toast.message(t('toastDuplicate'));
      setNewOrigin('');
      return;
    }
    setDraft({ ...draft, cors_origins: [...(draft.cors_origins || []), o] });
    setNewOrigin('');
  };

  const removeOrigin = (o) =>
    setDraft({ ...draft, cors_origins: (draft.cors_origins || []).filter((x) => x !== o) });

  const rotateJwt = async () => {
    if (rotating) return;
    if (!window.confirm(t('confirmTerminate'))) return;
    setRotating(true);
    try {
      const r = await apiFetch('/api/admin/system/settings/jwt/rotate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true }),
      });
      const j = await r.json();
      if (!r.ok || !j.success) throw new Error(j.detail || `HTTP ${r.status}`);
      toast.success(t('toastTerminated'));
    } catch (e) {
      toast.error(`${t('toastSaveFail')}${e.message || e}`);
    } finally {
      setRotating(false);
    }
  };

  const dirty = useMemo(() => {
    if (!draft || !data?.settings) return false;
    return JSON.stringify(draft) !== JSON.stringify(data.settings);
  }, [draft, data]);

  const computed = data?.computed || {};
  const env = data?.env_baseline || {};
  const snippet = trackerSetup?.snippet;

  if (loading || !draft) {
    return (
      <div className="space-y-6" data-testid="admin-system-loading">
        <div className="h-24 bg-zinc-100 rounded-2xl animate-pulse" />
        <div className="h-48 bg-zinc-100 rounded-2xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-5 sm:space-y-6 w-full max-w-full overflow-hidden" data-testid="admin-system-page">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="bg-gradient-to-br from-indigo-50 via-white to-white border border-indigo-100 rounded-2xl p-4 sm:p-5 lg:p-6 shadow-sm">
        {/* Mobile: column stack — Desktop: icon | text | button row */}
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          {/* Title row: icon + text always inline, button below on mobile */}
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <span className="inline-flex w-11 h-11 sm:w-12 sm:h-12 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600 shrink-0">
              <Globe size={20} weight="duotone" />
            </span>
            <div className="min-w-0 flex-1">
              <HelpTooltip text={t('pageTooltip')} side="bottom" align="start">
                <h1
                  className="inline text-[19px] sm:text-[20px] lg:text-[22px] font-semibold tracking-tight text-[#18181B] leading-tight cursor-help underline decoration-dotted decoration-1 decoration-[#A1A1AA] underline-offset-4"
                  data-testid="page-title"
                >
                  {t('pageTitle')}
                </h1>
              </HelpTooltip>
              <p className="text-[12.5px] sm:text-[13px] text-[#71717A] mt-1 leading-relaxed break-words">
                {t('pageSubtitle')}
              </p>
            </div>
          </div>
          <button
            onClick={save}
            disabled={saving || !dirty || !isMasterAdmin}
            title={!isMasterAdmin ? t('btnSaveDisabled') : ''}
            className="inline-flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white text-[13px] font-semibold focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0 w-full sm:w-auto"
            data-testid="btn-save-settings"
          >
            {saving ? <ArrowsClockwise size={14} weight="bold" className="animate-spin" /> : <FloppyDisk size={14} weight="bold" />}
            {saving ? t('btnSaving') : dirty ? t('btnSave') : t('btnSaved')}
          </button>
        </div>
      </header>

      {/* ── Block 1 · Domain ───────────────────────────────────────── */}
      <Section icon={Browser} title={t('blockDomain')} hint={t('blockDomainHint')} tooltip={t('blockDomainTip')} testId="section-domain">
        <TextField
          label={t('fieldMainAddress')}
          value={draft.production_domain}
          onChange={(v) => setDraft({ ...draft, production_domain: v })}
          placeholder="https://bibi.cars"
          hint={t('fieldExample')}
          testid="input-production-domain"
        />
        <label className="flex items-start gap-3 cursor-pointer select-none pt-1">
          <input
            type="checkbox"
            checked={draft.allow_subdomains === true}
            onChange={(e) => setDraft({ ...draft, allow_subdomains: e.target.checked })}
            className="w-4 h-4 mt-0.5 accent-indigo-600 cursor-pointer shrink-0"
            data-testid="input-allow-subdomains"
          />
          <div className="flex-1 min-w-0">
            <span className="block text-[13px] font-medium text-[#18181B]">
              {t('allowSubdomains')}
            </span>
            <span className="block text-[11.5px] text-[#71717A] mt-0.5 leading-snug break-words">
              {t('allowSubdomainsHint')}
            </span>
          </div>
        </label>
      </Section>

      {/* ── Block 2 · Integrations ─────────────────────────────────── */}
      <Section icon={Plug} title={t('blockIntegrations')} hint={t('blockIntegrationsHint')} tooltip={t('blockIntegrationsTip')} testId="section-integrations">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <IntegrationCard t={t} icon={PhoneCall}      name={t('cardRingostat')}  description={t('cardRingostatHint')}  url={computed.ringostat_webhook_url} testid="ringostat" />
          <IntegrationCard t={t} icon={CreditCard}     name={t('cardStripe')}     description={t('cardStripeHint')}     url={computed.stripe_webhook_url}    testid="stripe" />
          <IntegrationCard t={t} icon={PaperPlaneTilt} name={t('cardResend')}     description={t('cardResendHint')}     url={computed.resend_webhook_url}    testid="resend" />
          <IntegrationCard t={t} icon={Globe}          name={t('cardSiteOrigin')} description={t('cardSiteOriginHint')} url={computed.site_origin}           testid="site-origin" />
          <ScriptSnippetCard t={t} snippet={snippet} testid="site-tracker-snippet" />
        </div>
      </Section>

      {/* ── Block 3 · Security ─────────────────────────────────────── */}
      <Section icon={ShieldCheck} title={t('blockSecurity')} hint={t('blockSecurityHint')} tooltip={t('blockSecurityTip')} testId="section-security">
        <div className="px-3 py-3 rounded-lg bg-amber-50 border border-amber-200 text-[12px] text-amber-900 flex items-start gap-2">
          <Warning size={16} weight="duotone" className="text-amber-700 shrink-0 mt-0.5" />
          <div className="min-w-0 leading-snug break-words">
            <strong>{t('securityWarningStrong')}</strong> {t('securityWarning')}
          </div>
        </div>
        <button
          onClick={rotateJwt}
          disabled={rotating}
          className="inline-flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-white border border-amber-300 text-amber-900 text-[13px] font-semibold hover:bg-amber-50 hover:border-amber-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors w-full sm:w-auto"
          data-testid="btn-rotate-jwt"
        >
          {rotating ? <ArrowsClockwise size={14} weight="bold" className="animate-spin" /> : <SignOut size={14} weight="bold" />}
          {t('btnTerminateAll')}
        </button>
      </Section>

      {/* ── Block 4 · Advanced (master_admin only) ─────────────────── */}
      {isMasterAdmin ? (
        <Section icon={Info} title={t('blockAdvanced')} hint={t('blockAdvancedHint')} tooltip={t('blockAdvancedTip')} testId="section-advanced">
          <button
            type="button"
            onClick={() => setAdvancedOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-zinc-600 hover:text-zinc-900"
            data-testid="btn-toggle-advanced"
          >
            {advancedOpen ? <CaretDown size={12} weight="bold" /> : <CaretRight size={12} weight="bold" />}
            {t('advancedToggle')}
          </button>

          {advancedOpen ? (
            <div className="space-y-3 pt-2" data-testid="advanced-content">
              <p className="text-[11.5px] text-[#71717A] leading-relaxed break-words">
                {t('advancedDescr')}
              </p>

              <div className="space-y-2">
                {(draft.cors_origins || []).map((o) => (
                  <div
                    key={o}
                    className="flex items-center justify-between gap-2 h-10 px-3 rounded-lg border border-[#E4E4E7] bg-[#FAFAFA]"
                    data-testid={`cors-row-${o}`}
                  >
                    <span className="text-[12.5px] text-[#18181B] font-mono truncate">{o}</span>
                    <button
                      type="button"
                      onClick={() => removeOrigin(o)}
                      className="w-6 h-6 rounded-md hover:bg-white border border-transparent hover:border-[#E4E4E7] text-[#71717A] hover:text-red-600 inline-flex items-center justify-center transition-colors shrink-0"
                      aria-label={t('toastDelete')}
                    >
                      <X size={12} weight="bold" />
                    </button>
                  </div>
                ))}
                {(draft.cors_origins || []).length === 0 ? (
                  <p className="text-[12px] text-[#A1A1AA] italic">{t('advancedEmpty')}</p>
                ) : null}
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-1">
                <input
                  type="text"
                  value={newOrigin}
                  onChange={(e) => setNewOrigin(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addOrigin(); } }}
                  placeholder={t('advancedPlaceholder')}
                  className="flex-1 h-10 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[12.5px] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 font-mono"
                  data-testid="input-new-origin"
                />
                <button
                  type="button"
                  onClick={addOrigin}
                  disabled={!newOrigin.trim()}
                  className="h-10 px-3 rounded-lg bg-white border border-[#E4E4E7] text-[#18181B] text-[12px] font-semibold hover:border-indigo-400 hover:text-indigo-600 disabled:opacity-50 inline-flex items-center justify-center gap-1.5 transition-colors shrink-0"
                  data-testid="btn-add-origin"
                >
                  <Plus size={12} weight="bold" />
                  {t('advancedAdd')}
                </button>
              </div>

              {(env.cors_origins?.length > 0 || env.cors_origin_regex) ? (
                <div className="mt-3 pt-3 border-t border-[#F4F4F5]">
                  <p className="text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-2">
                    {t('envBaseline')}
                  </p>
                  <div className="space-y-1">
                    {(env.cors_origins || []).map((o) => (
                      <code key={`env-${o}`} className="block text-[11.5px] text-[#52525B] font-mono break-all">{o}</code>
                    ))}
                    {env.cors_origin_regex ? (
                      <code className="block text-[11.5px] text-[#52525B] font-mono break-all">regex: {env.cors_origin_regex}</code>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {draft.cors_origin_regex ? (
                <div className="px-3 py-2 rounded-lg bg-[#FAFAFA] border border-[#E4E4E7]">
                  <span className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-0.5">
                    {t('subdomainRegex')}
                  </span>
                  <code className="text-[11.5px] text-[#52525B] break-all">{draft.cors_origin_regex}</code>
                </div>
              ) : null}
            </div>
          ) : null}
        </Section>
      ) : null}

      {data?.settings?.updated_at ? (
        <p className="text-[11.5px] text-[#A1A1AA] text-center break-words px-2">
          {t('footerUpdated')} {new Date(data.settings.updated_at).toLocaleString()} ·{' '}
          <span className="font-mono">{data.settings.updated_by || t('footerBy')}</span>
        </p>
      ) : null}
    </div>
  );
};

export default AdminSystemSettingsPage;
