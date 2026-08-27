/**
 * AdminSeoSettingsPage — SEO control panel (master-admin only).
 *
 * Sibling of AdminSystemSettingsPage. Mirrors its visual language so the
 * two settings hubs feel like one product. Reads/writes:
 *
 *   GET   /api/admin/seo/settings
 *   PATCH /api/admin/seo/settings
 *
 * Public ``/api/seo/runtime-config`` returns the same data minus internal
 * flags — the frontend's <SeoRuntimeInjector/> reads it at bootstrap and
 * mounts GA4/Google Ads/Facebook pixel scripts on the fly.
 */
import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { toast } from 'sonner';
import {
  Funnel,
  ChartLine,
  Megaphone,
  Globe,
  Robot,
  ShieldCheck,
  Copy,
  CheckCircle,
  Warning,
  FloppyDisk,
  LinkSimple,
  Eye,
  MagnifyingGlass,
  Buildings,
  Certificate,
} from '@phosphor-icons/react';
import { useLang } from '../../i18n';
import HelpTooltip from '../../components/ui/HelpTooltip';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const apiFetch = (path, init = {}) => {
  const token = (typeof window !== 'undefined' && (localStorage.getItem('eco_token') || localStorage.getItem('token'))) || '';
  const headers = {
    ...(init.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
};

// ─── Mini translation table (en/bg/uk) — only the strings we use here.
//    Matches the existing /admin language set so the page slots in cleanly.
const T = {
  en: {
    page_title:        'SEO Settings',
    page_subtitle:     'Manage Google Search Console verification, Google Analytics 4, Google Ads, Facebook Pixel and site identity overrides. All changes propagate to the public site instantly — no rebuild required.',
    page_tooltip:      'Central SEO hub: search-engine verification, analytics, Google Ads conversions, default meta tags and crawler rules. Changes apply to the live site instantly — no rebuild.',
    loading:           'Loading…',
    save:              'Save changes',
    saving:            'Saving…',
    saved:             'SEO settings saved — propagating to all sessions now.',
    discard:           'Discard',
    unsaved:           'Unsaved changes',
    copied:            'Copied',
    copy:              'Copy',
    preview:           'Preview',
    section_verify:    'Search-engine verification',
    section_verify_hint: 'Paste the verification tokens issued by each console. The full <meta> tag is also accepted — we extract the value automatically.',
    section_verify_tip:  'Proves to Google, Bing and Yandex that you own this site, which unlocks their webmaster tools (indexing, search analytics, sitemaps). Paste the token each console gives you — done once.',
    google_verify:     'Google Search Console',
    google_verify_hint:'Open Search Console → Settings → Ownership verification → HTML tag. Copy the value of the content="…" attribute, or paste the whole tag.',
    bing_verify:       'Bing Webmaster Tools',
    bing_verify_hint:  'Open Bing Webmaster Tools → Verify Ownership → HTML Meta Tag.',
    yandex_verify:     'Yandex Webmaster',
    yandex_verify_hint:'Open Yandex Webmaster → Owner verification → Meta tag.',
    section_analytics: 'Analytics',
    section_analytics_hint:'These tags are injected at runtime — page-view and conversion events are tracked across all public pages.',
    section_analytics_tip:'Measures traffic and conversions. GA4 tracks visitor behaviour; the Facebook Pixel attributes ad-driven actions. Powers marketing reports and ad retargeting.',
    ga4_id:            'GA4 Measurement ID',
    ga4_id_hint:       'Format: G-XXXXXXXXXX (find it in Google Analytics → Admin → Data Streams).',
    fbpx_id:           'Facebook Pixel ID',
    fbpx_id_hint:      '8-20 digit Pixel ID. Leave empty to disable Facebook tracking.',
    section_ads:       'Google Ads',
    section_ads_hint:  'Conversion ID + per-event labels for your campaigns. Labels come from Google Ads → Tools → Conversions → Tag setup.',
    section_ads_tip:   'Sends conversions back to Google Ads so it can optimise campaigns and measure ROI for each event (lead, VIN search, calculator, signed contract).',
    ads_id:            'Conversion ID',
    ads_id_hint:       'Format: AW-XXXXXXXXX',
    ads_send_pv:       'Send page-view conversions',
    ads_labels:        'Conversion labels',
    label_lead:        'Lead submitted',
    label_vin:         'VIN searched',
    label_calc:        'Calculator used',
    label_contract:    'Contract signed',
    section_identity:  'Site identity (fallbacks)',
    section_identity_hint:'These values appear on pages that have not declared their own SEO. Per-page useSeo() calls always override them.',
    section_identity_tip:'Default title, description and image used in search results and social shares for pages that do not declare their own SEO.',
    default_title:     'Default title',
    default_description:'Default description',
    default_keywords:  'Default keywords',
    default_og_image:  'Default Open Graph image URL',
    section_crawlers:  'Crawler directives',
    section_crawlers_hint:'Control which automated agents may access the site.',
    section_crawlers_tip:'Controls which automated bots may crawl the site — for example, block AI-training crawlers from scraping your catalog and blog.',
    block_ai:          'Block AI training crawlers',
    block_ai_hint:     'When enabled, robots.txt blocks GPTBot, Anthropic, Claude-Web and CCBot from training on your catalog & blog content.',
    last_update:       'Last update',
    by:                'by',
    runtime_endpoint:  'Public runtime endpoint',
    runtime_endpoint_hint:'The frontend reads this to load GA / Ads / Pixel scripts. Test it from your browser:',
    runtime_endpoint_tip:'Read-only endpoint the public site calls on load to fetch these settings. Open it to confirm your GA / Ads / Pixel config is live.',
    section_domain:    'Domain & environment',
    section_domain_hint:'The public domain used for every canonical, sitemap, hreflang and JSON-LD URL. Change it here when the real domain goes live — no redeploy.',
    section_domain_tip: 'Single source of truth for the site origin. Empty = use the server default (preview). Environment controls indexing: only “production” is indexable; preview/stage/test emit noindex + robots Disallow.',
    f_public_origin:   'Public domain (origin)',
    f_public_origin_hint:'e.g. https://eco-nova.ua — no trailing slash. Empty = server default.',
    f_environment:     'Environment',
    f_environment_hint:'auto detects from host. Only “production” lets Google index the site.',
    f_indexnow:        'IndexNow key',
    f_indexnow_hint:   'Optional. Enables instant URL submission to Bing/Yandex via IndexNow.',
    f_gtm:             'Google Tag Manager ID',
    f_gtm_hint:        'Format: GTM-XXXXXXX. Optional container for tags.',
    section_company:   'Company & E-E-A-T',
    section_company_tip:'Real, verifiable company facts. These feed the Organization / LocalBusiness structured data (schema.org) that proves to Google you are a genuine business. Use REAL data only — never placeholders.',
    section_company_hint:'Real, verifiable data only — it powers your Organization / LocalBusiness rich results. Empty fields are simply omitted.',
    f_company_name:    'Brand name',
    f_legal_name:      'Legal name',
    f_edrpou:          'EDRPOU / VAT',
    f_license_number:  'Waste-handling license №',
    f_license_name:    'License name',
    f_company_email:   'Public email',
    f_company_phones:  'Phones (comma-separated)',
    f_company_street:  'Street address',
    f_company_city:    'City',
    f_company_region:  'Region / oblast',
    f_company_postal:  'Postal code',
    f_company_country: 'Country (ISO)',
    f_company_lat:     'Latitude',
    f_company_lng:     'Longitude',
    f_founding_date:   'Founding date',
    f_opening_hours:   'Opening hours',
    f_price_range:     'Price range',
    f_same_as:         'Social / sameAs URLs',
    f_same_as_hint:    'One per line or comma-separated (Facebook, LinkedIn, etc.).',
    f_company_description:'Short company description',
  },
  bg: {
    page_title:        'SEO настройки',
    page_subtitle:     'Управление на верификация Google Search Console, Google Analytics 4, Google Ads, Facebook Pixel и фалбек идентичност на сайта. Промените се прилагат веднага — без рестарт.',
    page_tooltip:      'Централен SEO център: верификация в търсачки, аналитика, Google Ads конверсии, мета тагове по подразбиране и правила за краулери. Промените се прилагат веднага.',
    loading:           'Зарежда…',
    save:              'Запази промените',
    saving:            'Записва…',
    saved:             'SEO настройките са запазени — прилагат се за всички сесии.',
    discard:           'Откажи',
    unsaved:           'Незапазени промени',
    copied:            'Копирано',
    copy:              'Копирай',
    preview:           'Преглед',
    section_verify:    'Верификация в търсачки',
    section_verify_hint:'Поставете верификационните токени от всеки конзолен екран. Може и целия <meta> таг — стойността се извлича автоматично.',
    section_verify_tip:'Доказва пред Google, Bing и Yandex, че сайтът е ваш, което отключва инструментите им за уебмастъри (индексиране, search analytics, sitemaps). Поставете токена от всяка конзола — еднократно.',
    google_verify:     'Google Search Console',
    google_verify_hint:'Search Console → Settings → Ownership verification → HTML tag. Копирайте съдържанието на content="…" или целия таг.',
    bing_verify:       'Bing Webmaster Tools',
    bing_verify_hint:  'Bing Webmaster Tools → Verify Ownership → HTML Meta Tag.',
    yandex_verify:     'Яндекс Уебмастър',
    yandex_verify_hint:'Yandex Webmaster → Owner verification → Meta tag.',
    section_analytics: 'Аналитика',
    section_analytics_hint:'Таговете се инжектират по време на изпълнение — събитията за page view и конверсии се проследяват на всички публични страници.',
    section_analytics_tip:'Измерва трафик и конверсии. GA4 проследява поведението на посетителите; Facebook Pixel приписва действията от реклами. Захранва маркетинг отчетите и ретаргетинга.',
    ga4_id:            'GA4 Measurement ID',
    ga4_id_hint:       'Формат: G-XXXXXXXXXX (намерете в Google Analytics → Admin → Data Streams).',
    fbpx_id:           'Facebook Pixel ID',
    fbpx_id_hint:      '8-20 цифрен Pixel ID. Празно — изключва Facebook tracking.',
    section_ads:       'Google Ads',
    section_ads_hint:  'Conversion ID + етикети за събития за вашите кампании.',
    section_ads_tip:   'Изпраща конверсии обратно към Google Ads, за да оптимизира кампаниите и да измерва ROI за всяко събитие (лид, VIN търсене, калкулатор, подписан договор).',
    ads_id:            'Conversion ID',
    ads_id_hint:       'Формат: AW-XXXXXXXXX',
    ads_send_pv:       'Изпращай page-view конверсии',
    ads_labels:        'Етикети за конверсии',
    label_lead:        'Изпратен лид',
    label_vin:         'Търсене на VIN',
    label_calc:        'Използван калкулатор',
    label_contract:    'Подписан договор',
    section_identity:  'Идентичност на сайта (фалбек)',
    section_identity_hint:'Тези стойности се показват на страници без собствени SEO декларации. useSeo() винаги ги презаписва.',
    section_identity_tip:'Заглавие, описание и изображение по подразбиране за резултатите в търсачки и споделяне в социални мрежи за страници без собствено SEO.',
    default_title:     'Заглавие по подразбиране',
    default_description:'Описание по подразбиране',
    default_keywords:  'Ключови думи по подразбиране',
    default_og_image:  'OG image URL по подразбиране',
    section_crawlers:  'Директиви за краулери',
    section_crawlers_hint:'Контрол кои автоматизирани агенти могат да достъпват сайта.',
    section_crawlers_tip:'Контролира кои автоматизирани ботове могат да обхождат сайта — напр. блокиране на AI-training краулери да извличат каталога и блога.',
    block_ai:          'Блокирай AI training краулери',
    block_ai_hint:     'Когато е активно, robots.txt блокира GPTBot, Anthropic, Claude-Web и CCBot.',
    last_update:       'Последна промяна',
    by:                'от',
    runtime_endpoint:  'Публичен runtime ендпойнт',
    runtime_endpoint_hint:'Фронтендът чете това, за да зареди GA / Ads / Pixel. Тествайте от браузъра:',
    runtime_endpoint_tip:'Само за четене ендпойнт, който публичният сайт извиква при зареждане, за да вземе тези настройки. Отворете го, за да проверите дали GA / Ads / Pixel са активни.',
  },
  uk: {
    page_title:        'SEO налаштування',
    page_subtitle:     'Керування верифікацією Google Search Console, Google Analytics 4, Google Ads, Facebook Pixel та фолбеком ідентичності сайту. Зміни застосовуються миттєво — без ребілду.',
    page_tooltip:      'Центральний SEO-хаб: верифікація в пошукових системах, аналітика, конверсії Google Ads, типові мета-теги та правила для краулерів. Зміни застосовуються миттєво.',
    loading:           'Завантаження…',
    save:              'Зберегти зміни',
    saving:            'Збереження…',
    saved:             'SEO налаштування збережено — поширюються на всі сесії.',
    discard:           'Скасувати',
    unsaved:           'Незбережені зміни',
    copied:            'Скопійовано',
    copy:              'Копіювати',
    preview:           'Перегляд',
    section_verify:    'Верифікація в пошукових системах',
    section_verify_hint:'Вставте верифікаційні токени з кожної консолі. Можна весь <meta> тег — значення вилучається автоматично.',
    section_verify_tip:'Підтверджує Google, Bing і Yandex, що сайт належить вам, що відкриває їхні інструменти для вебмайстрів (індексація, search analytics, sitemaps). Вставте токен з кожної консолі — одноразово.',
    google_verify:     'Google Search Console',
    google_verify_hint:'Search Console → Settings → Ownership verification → HTML tag. Скопіюйте значення content="…" або весь тег.',
    bing_verify:       'Bing Webmaster Tools',
    bing_verify_hint:  'Bing Webmaster Tools → Verify Ownership → HTML Meta Tag.',
    yandex_verify:     'Яндекс Вебмастер',
    yandex_verify_hint:'Yandex Webmaster → Owner verification → Meta tag.',
    section_analytics: 'Аналітика',
    section_analytics_hint:'Теги ін’єктуються під час виконання — події page view та конверсій трекаються на всіх публічних сторінках.',
    section_analytics_tip:'Вимірює трафік і конверсії. GA4 відстежує поведінку відвідувачів; Facebook Pixel приписує дії з реклами. Живить маркетингові звіти та ретаргетинг.',
    ga4_id:            'GA4 Measurement ID',
    ga4_id_hint:       'Формат: G-XXXXXXXXXX (знайдіть у Google Analytics → Admin → Data Streams).',
    fbpx_id:           'Facebook Pixel ID',
    fbpx_id_hint:      '8-20 цифровий Pixel ID. Порожньо — вимикає Facebook tracking.',
    section_ads:       'Google Ads',
    section_ads_hint:  'Conversion ID + мітки подій для ваших кампаній.',
    section_ads_tip:   'Надсилає конверсії назад у Google Ads, щоб оптимізувати кампанії та вимірювати ROI для кожної події (лід, пошук VIN, калькулятор, підписаний договір).',
    ads_id:            'Conversion ID',
    ads_id_hint:       'Формат: AW-XXXXXXXXX',
    ads_send_pv:       'Надсилати page-view конверсії',
    ads_labels:        'Мітки конверсій',
    label_lead:        'Лід надіслано',
    label_vin:         'Пошук VIN',
    label_calc:        'Використано калькулятор',
    label_contract:    'Підписано договір',
    section_identity:  'Ідентичність сайту (фолбек)',
    section_identity_hint:'Ці значення показуються на сторінках без власних SEO декларацій. useSeo() завжди їх перезаписує.',
    section_identity_tip:'Заголовок, опис та зображення за замовчуванням для результатів пошуку та поширення в соцмережах для сторінок без власного SEO.',
    default_title:     'Заголовок за замовчуванням',
    default_description:'Опис за замовчуванням',
    default_keywords:  'Ключові слова за замовчуванням',
    default_og_image:  'OG image URL за замовчуванням',
    section_crawlers:  'Директиви для краулерів',
    section_crawlers_hint:'Контроль, які автоматизовані агенти можуть отримати доступ до сайту.',
    section_crawlers_tip:'Керує тим, які автоматизовані боти можуть сканувати сайт — напр., блокування AI-training краулерів від збору каталогу та блогу.',
    block_ai:          'Блокувати AI training краулерів',
    block_ai_hint:     'Якщо активно, robots.txt блокує GPTBot, Anthropic, Claude-Web та CCBot.',
    last_update:       'Остання зміна',
    by:                'від',
    runtime_endpoint:  'Публічний runtime ендпойнт',
    runtime_endpoint_hint:'Фронтенд читає це, щоб завантажити GA / Ads / Pixel. Перевірте з браузера:',
    runtime_endpoint_tip:'Лише для читання ендпойнт, який публічний сайт викликає під час завантаження, щоб отримати ці налаштування. Відкрийте його, щоб перевірити, що GA / Ads / Pixel активні.',
    section_domain:    'Домен і середовище',
    section_domain_hint:'Публічний домен для всіх canonical, sitemap, hreflang і JSON-LD. Впишіть реальний домен, коли він буде готовий — без ребілду.',
    section_domain_tip: 'Єдине джерело істини для домену сайту. Порожньо = серверний дефолт (прев’ю). Середовище керує індексацією: лише «production» індексується; preview/stage/test дають noindex + robots Disallow.',
    f_public_origin:   'Публічний домен (origin)',
    f_public_origin_hint:'напр. https://eco-nova.ua — без слешу в кінці. Порожньо = серверний дефолт.',
    f_environment:     'Середовище',
    f_environment_hint:'auto визначає з хоста. Лише «production» дозволяє індексацію Google.',
    f_indexnow:        'Ключ IndexNow',
    f_indexnow_hint:   'Опційно. Вмикає миттєве надсилання URL у Bing/Yandex через IndexNow.',
    f_gtm:             'ID Google Tag Manager',
    f_gtm_hint:        'Формат: GTM-XXXXXXX. Опційний контейнер тегів.',
    section_company:   'Компанія та E-E-A-T',
    section_company_tip:'Реальні, перевірні дані компанії. Вони живлять структуровані дані Organization / LocalBusiness (schema.org), що доводять Google, що ви — справжній бізнес. Лише РЕАЛЬНІ дані — жодних заглушок.',
    section_company_hint:'Лише реальні перевірні дані — вони живлять rich results Organization / LocalBusiness. Порожні поля просто не виводяться.',
    f_company_name:    'Назва бренду',
    f_legal_name:      'Юридична назва',
    f_edrpou:          'ЄДРПОУ / ПДВ',
    f_license_number:  '№ ліцензії на поводження з відходами',
    f_license_name:    'Назва ліцензії',
    f_company_email:   'Публічний email',
    f_company_phones:  'Телефони (через кому)',
    f_company_street:  'Адреса (вулиця)',
    f_company_city:    'Місто',
    f_company_region:  'Область / регіон',
    f_company_postal:  'Поштовий індекс',
    f_company_country: 'Країна (ISO)',
    f_company_lat:     'Широта',
    f_company_lng:     'Довгота',
    f_founding_date:   'Дата заснування',
    f_opening_hours:   'Години роботи',
    f_price_range:     'Ціновий діапазон',
    f_same_as:         'Соцмережі / sameAs URL',
    f_same_as_hint:    'По одному в рядку або через кому (Facebook, LinkedIn тощо).',
    f_company_description:'Короткий опис компанії',
  },
};

// ─── Shared visual primitives (mirror AdminSystemSettingsPage so the two
//    settings hubs read as one coherent product) ───────────────────────────
const Section = ({ icon: Icon, title, hint, tooltip, children }) => (
  <div className="bg-white border border-[#E4E4E7] rounded-2xl p-4 sm:p-5 space-y-4">
    <div className="flex items-start gap-3">
      {Icon ? (
        <div className="w-9 h-9 rounded-xl bg-[#FAFAFA] border border-[#E4E4E7] flex items-center justify-center shrink-0">
          <Icon size={16} weight="duotone" className="text-[#18181B]" />
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        {tooltip ? (
          <HelpTooltip text={tooltip} side="top" align="start">
            <h3 className="inline text-[14px] font-bold tracking-tight text-[#18181B] leading-tight cursor-help underline decoration-dotted decoration-1 decoration-[#A1A1AA] underline-offset-4">
              {title}
            </h3>
          </HelpTooltip>
        ) : (
          <h3 className="text-[14px] font-bold tracking-tight text-[#18181B] leading-tight">{title}</h3>
        )}
        {hint ? <p className="text-[12px] text-[#71717A] mt-0.5 leading-snug">{hint}</p> : null}
      </div>
    </div>
    {children}
  </div>
);

const Field = ({ label, value, onChange, placeholder, hint, mono, error, ...rest }) => (
  <label className="block">
    {label ? (
      <span className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">{label}</span>
    ) : null}
    <input
      type="text"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full h-10 px-3 rounded-lg border text-[13px] focus:outline-none transition ${
        error
          ? 'border-red-300 bg-red-50 focus:border-red-400'
          : 'border-[#E4E4E7] bg-white focus:border-[#18181B]'
      } ${mono ? 'font-mono' : ''}`}
      {...rest}
    />
    {hint ? <p className="text-[11px] text-[#71717A] mt-1.5 leading-snug">{hint}</p> : null}
    {error ? <p className="text-[11px] text-red-600 mt-1.5 leading-snug">{error}</p> : null}
  </label>
);

const TextArea = ({ label, value, onChange, placeholder, hint, rows = 3, max }) => (
  <label className="block">
    {label ? (
      <span className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">{label}</span>
    ) : null}
    <textarea
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full px-3 py-2 rounded-lg border border-[#E4E4E7] bg-white text-[13px] focus:outline-none focus:border-[#18181B] resize-y"
    />
    <div className="flex items-center justify-between mt-1.5">
      {hint ? <p className="text-[11px] text-[#71717A] leading-snug flex-1">{hint}</p> : <span />}
      {max ? (
        <span className={`text-[10px] tabular-nums ml-2 shrink-0 ${(value?.length || 0) > max ? 'text-red-600 font-semibold' : 'text-[#A1A1AA]'}`}>
          {(value || '').length}/{max}
        </span>
      ) : null}
    </div>
  </label>
);

const Toggle = ({ label, hint, checked, onChange }) => (
  <label className="flex items-start gap-3 cursor-pointer select-none">
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 mt-0.5 rounded-full border transition ${
        checked ? 'bg-[#18181B] border-[#18181B]' : 'bg-[#E4E4E7] border-[#E4E4E7]'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white shadow transition transform ${
          checked ? 'translate-x-4' : 'translate-x-0.5'
        } mt-[1px]`}
      />
    </button>
    <div className="min-w-0">
      <div className="text-[13px] font-medium text-[#18181B]">{label}</div>
      {hint ? <div className="text-[11px] text-[#71717A] mt-0.5 leading-snug">{hint}</div> : null}
    </div>
  </label>
);

const AdminSeoSettingsPage = () => {
  const { lang } = useLang();
  const t = useMemo(() => ({ ...T.en, ...(T[lang] || {}) }), [lang]);

  const [data,     setData]     = useState(null);
  const [draft,    setDraft]    = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [saving,   setSaving]   = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await apiFetch('/api/admin/seo/settings');
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

  useEffect(() => { load(); }, [load]);

  const dirty = useMemo(
    () => draft && data && JSON.stringify(draft) !== JSON.stringify(data.settings),
    [draft, data],
  );

  const setField = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  const setLabel = (k, v) =>
    setDraft((d) => ({
      ...d,
      google_ads_conversion_labels: { ...(d.google_ads_conversion_labels || {}), [k]: v },
    }));

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const r = await apiFetch('/api/admin/seo/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`);
      setData({ ...data, settings: j.settings });
      setDraft(j.settings);
      toast.success(t.saved);
    } catch (e) {
      toast.error(`${e.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  const copyUrl = (path) => {
    const full = `${BACKEND_URL || window.location.origin}${path}`;
    navigator.clipboard?.writeText(full).then(
      () => toast.success(t.copied),
      () => toast.error('Copy failed'),
    );
  };

  if (loading || !draft) {
    return (
      <div className="space-y-6">
        <div className="text-center text-[#71717A] py-10">{t.loading}</div>
      </div>
    );
  }

  const runtimeUrl = `${BACKEND_URL || window.location.origin}/api/seo/runtime-config`;

  return (
    <div className="space-y-6" data-testid="admin-seo-settings-page">
      {/* ─── Header (matches Sales / Contract360 pattern) ─────────── */}
      <div className="flex items-start gap-3 flex-wrap">
        <div className="w-10 h-10 rounded-xl bg-[#18181B] text-white flex items-center justify-center shrink-0">
          <MagnifyingGlass size={18} weight="bold" />
        </div>
        <div className="flex-1 min-w-0">
          <HelpTooltip text={t.page_tooltip} side="bottom" align="start">
            <h1
              className="inline text-[17px] sm:text-[19px] font-semibold tracking-tight text-[#18181B] leading-tight cursor-help underline decoration-dotted decoration-1 decoration-[#A1A1AA] underline-offset-4"
              data-testid="seo-settings-title"
            >
              {t.page_title}
            </h1>
          </HelpTooltip>
          <p className="mt-1 text-[12.5px] sm:text-[13px] text-[#71717A] leading-relaxed max-w-3xl">
            {t.page_subtitle}
          </p>
          {data?.settings?.updated_at ? (
            <div className="text-[11px] text-[#A1A1AA] mt-2 flex items-center gap-1.5">
              <CheckCircle size={11} weight="bold" className="text-emerald-500" />
              {t.last_update}: {new Date(data.settings.updated_at).toLocaleString()}
              {data.settings.updated_by ? ` · ${t.by} ${data.settings.updated_by}` : ''}
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {dirty ? (
            <>
              <span className="hidden md:inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-md">
                <Warning size={11} weight="fill" /> {t.unsaved}
              </span>
              <button
                onClick={() => setDraft(data.settings)}
                className="h-9 px-3 rounded-xl border border-[#E4E4E7] text-[12.5px] font-semibold text-[#52525B] hover:bg-[#FAFAFA] transition-colors"
                data-testid="seo-discard"
              >
                {t.discard}
              </button>
            </>
          ) : null}
          <button
            onClick={save}
            disabled={!dirty || saving}
            className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl bg-[#18181B] hover:bg-[#27272A] active:bg-black text-white text-[12.5px] font-semibold focus:outline-none focus-visible:ring-4 focus-visible:ring-black/15 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="seo-save"
          >
            <FloppyDisk size={13} weight="bold" />
            {saving ? t.saving : t.save}
          </button>
        </div>
      </div>

      {/* ─── 1. Domain & environment ──────────────────────────────── */}
      <Section icon={Globe} title={t.section_domain} hint={t.section_domain_hint} tooltip={t.section_domain_tip}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field
            label={t.f_public_origin}
            value={draft.public_origin}
            onChange={(v) => setField('public_origin', v)}
            placeholder="https://eco-nova.ua"
            hint={t.f_public_origin_hint}
            mono
            data-testid="seo-input-origin"
          />
          <label className="block">
            <span className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-1.5">{t.f_environment}</span>
            <select
              value={draft.seo_environment || 'auto'}
              onChange={(e) => setField('seo_environment', e.target.value)}
              className="w-full h-10 px-3 rounded-lg border border-[#E4E4E7] bg-white text-[13px] focus:outline-none focus:border-[#18181B]"
              data-testid="seo-input-environment"
            >
              <option value="auto">auto</option>
              <option value="production">production</option>
              <option value="preview">preview</option>
              <option value="stage">stage</option>
              <option value="test">test</option>
              <option value="dev">dev</option>
            </select>
            <p className="text-[11px] text-[#71717A] mt-1.5 leading-snug">{t.f_environment_hint}</p>
          </label>
          <Field
            label={t.f_gtm}
            value={draft.gtm_container_id}
            onChange={(v) => setField('gtm_container_id', v.toUpperCase())}
            placeholder="GTM-XXXXXXX"
            hint={t.f_gtm_hint}
            mono
            data-testid="seo-input-gtm"
          />
          <Field
            label={t.f_indexnow}
            value={draft.indexnow_key}
            onChange={(v) => setField('indexnow_key', v)}
            placeholder="a1b2c3…"
            hint={t.f_indexnow_hint}
            mono
            data-testid="seo-input-indexnow"
          />
        </div>
      </Section>

      {/* ─── 2. Company & E-E-A-T ──────────────────────────────────── */}
      <Section icon={Buildings} title={t.section_company} hint={t.section_company_hint} tooltip={t.section_company_tip}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label={t.f_company_name} value={draft.company_name} onChange={(v) => setField('company_name', v)} placeholder="ECO.NOVA" data-testid="seo-input-company-name" />
          <Field label={t.f_legal_name} value={draft.legal_name} onChange={(v) => setField('legal_name', v)} placeholder="ТОВ «ЕКО-НОВА»" data-testid="seo-input-legal-name" />
          <Field label={t.f_edrpou} value={draft.edrpou} onChange={(v) => setField('edrpou', v)} placeholder="12345678" mono />
          <Field label={t.f_founding_date} value={draft.founding_date} onChange={(v) => setField('founding_date', v)} placeholder="2019-03-01" mono />
          <Field label={t.f_license_number} value={draft.license_number} onChange={(v) => setField('license_number', v)} placeholder="UA-HW-…" mono data-testid="seo-input-license" />
          <Field label={t.f_license_name} value={draft.license_name} onChange={(v) => setField('license_name', v)} placeholder="Ліцензія на поводження з небезпечними відходами" />
          <Field label={t.f_company_email} value={draft.company_email} onChange={(v) => setField('company_email', v)} placeholder="info@eco-nova.ua" mono />
          <Field label={t.f_company_phones} value={draft.company_phones} onChange={(v) => setField('company_phones', v)} placeholder="+380 44 …, +380 67 …" />
          <Field label={t.f_company_street} value={draft.company_street} onChange={(v) => setField('company_street', v)} placeholder="вул. …" />
          <Field label={t.f_company_city} value={draft.company_city} onChange={(v) => setField('company_city', v)} placeholder="Київ" />
          <Field label={t.f_company_region} value={draft.company_region} onChange={(v) => setField('company_region', v)} placeholder="Київська обл." />
          <Field label={t.f_company_postal} value={draft.company_postal} onChange={(v) => setField('company_postal', v)} placeholder="01001" mono />
          <Field label={t.f_company_country} value={draft.company_country} onChange={(v) => setField('company_country', v.toUpperCase())} placeholder="UA" mono />
          <Field label={t.f_opening_hours} value={draft.opening_hours} onChange={(v) => setField('opening_hours', v)} placeholder="Mo-Fr 09:00-18:00" mono />
          <Field label={t.f_company_lat} value={draft.company_lat} onChange={(v) => setField('company_lat', v)} placeholder="50.4501" mono />
          <Field label={t.f_company_lng} value={draft.company_lng} onChange={(v) => setField('company_lng', v)} placeholder="30.5234" mono />
        </div>
        <div className="mt-4 space-y-4">
          <TextArea label={t.f_same_as} value={draft.same_as} onChange={(v) => setField('same_as', v)} rows={2} hint={t.f_same_as_hint} />
          <TextArea label={t.f_company_description} value={draft.company_description} onChange={(v) => setField('company_description', v)} rows={2} max={600} />
        </div>
      </Section>

      {/* ─── 3. Verification ──────────────────────────────────────── */}
      <Section icon={ShieldCheck} title={t.section_verify} hint={t.section_verify_hint} tooltip={t.section_verify_tip}>
        <div className="grid grid-cols-1 gap-4">
          <Field
            label={t.google_verify}
            value={draft.google_site_verification}
            onChange={(v) => setField('google_site_verification', v)}
            placeholder='REPLACE_ME_GOOGLE_SEARCH_CONSOLE_TOKEN'
            hint={t.google_verify_hint}
            mono
            data-testid="seo-input-gsc"
          />
          <Field
            label={t.bing_verify}
            value={draft.bing_site_verification}
            onChange={(v) => setField('bing_site_verification', v)}
            placeholder='REPLACE_ME_BING_WEBMASTER_TOKEN'
            hint={t.bing_verify_hint}
            mono
            data-testid="seo-input-bing"
          />
          <Field
            label={t.yandex_verify}
            value={draft.yandex_site_verification}
            onChange={(v) => setField('yandex_site_verification', v)}
            placeholder='REPLACE_ME_YANDEX_WEBMASTER_TOKEN'
            hint={t.yandex_verify_hint}
            mono
            data-testid="seo-input-yandex"
          />
        </div>
      </Section>

      {/* ─── 2. Analytics ─────────────────────────────────────────── */}
      <Section icon={ChartLine} title={t.section_analytics} hint={t.section_analytics_hint} tooltip={t.section_analytics_tip}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field
            label={t.ga4_id}
            value={draft.ga4_measurement_id}
            onChange={(v) => setField('ga4_measurement_id', v.toUpperCase())}
            placeholder="G-XXXXXXXXXX"
            hint={t.ga4_id_hint}
            mono
            data-testid="seo-input-ga4"
          />
          <Field
            label={t.fbpx_id}
            value={draft.facebook_pixel_id}
            onChange={(v) => setField('facebook_pixel_id', v.replace(/[^\d]/g, ''))}
            placeholder="123456789012345"
            hint={t.fbpx_id_hint}
            mono
            data-testid="seo-input-fbpx"
          />
        </div>
      </Section>

      {/* ─── 3. Google Ads ────────────────────────────────────────── */}
      <Section icon={Megaphone} title={t.section_ads} hint={t.section_ads_hint} tooltip={t.section_ads_tip}>
        <div className="grid grid-cols-1 gap-4">
          <Field
            label={t.ads_id}
            value={draft.google_ads_conversion_id}
            onChange={(v) => setField('google_ads_conversion_id', v.toUpperCase())}
            placeholder="AW-XXXXXXXXX"
            hint={t.ads_id_hint}
            mono
            data-testid="seo-input-ads"
          />
          <Toggle
            label={t.ads_send_pv}
            checked={!!draft.google_ads_send_page_view}
            onChange={(v) => setField('google_ads_send_page_view', v)}
          />
          <div className="pt-2">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-[#71717A] mb-2.5">{t.ads_labels}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field
                label={t.label_lead}
                value={draft.google_ads_conversion_labels?.lead_submit}
                onChange={(v) => setLabel('lead_submit', v)}
                placeholder="abc123XyZ"
                mono
                data-testid="seo-label-lead"
              />
              <Field
                label={t.label_calc}
                value={draft.google_ads_conversion_labels?.calc_used}
                onChange={(v) => setLabel('calc_used', v)}
                placeholder="ghi789StU"
                mono
                data-testid="seo-label-calc"
              />
              <Field
                label={t.label_contract}
                value={draft.google_ads_conversion_labels?.contract_signed}
                onChange={(v) => setLabel('contract_signed', v)}
                placeholder="jkl012VwX"
                mono
                data-testid="seo-label-contract"
              />
            </div>
          </div>
        </div>
      </Section>

      {/* ─── 4. Site identity ─────────────────────────────────────── */}
      <Section icon={Globe} title={t.section_identity} hint={t.section_identity_hint}>
        <div className="space-y-4">
          <Field
            label={t.default_title}
            value={draft.default_title}
            onChange={(v) => setField('default_title', v)}
            placeholder="ECO.NOVA — …"
          />
          <TextArea
            label={t.default_description}
            value={draft.default_description}
            onChange={(v) => setField('default_description', v)}
            rows={3}
            max={320}
          />
          <TextArea
            label={t.default_keywords}
            value={draft.default_keywords}
            onChange={(v) => setField('default_keywords', v)}
            rows={2}
            max={500}
          />
          <Field
            label={t.default_og_image}
            value={draft.default_og_image}
            onChange={(v) => setField('default_og_image', v)}
            placeholder="/og-image.png  or  https://…"
            mono
          />
        </div>
      </Section>

      {/* ─── 5. Crawler directives ────────────────────────────────── */}
      <Section icon={Robot} title={t.section_crawlers} hint={t.section_crawlers_hint} tooltip={t.section_crawlers_tip}>
        <Toggle
          label={t.block_ai}
          hint={t.block_ai_hint}
          checked={!!draft.block_ai_crawlers}
          onChange={(v) => setField('block_ai_crawlers', v)}
        />
      </Section>

      {/* ─── 6. Runtime endpoint preview ──────────────────────────── */}
      <Section icon={LinkSimple} title={t.runtime_endpoint} hint={t.runtime_endpoint_hint} tooltip={t.runtime_endpoint_tip}>
        <div className="flex items-stretch gap-2">
          <code className="flex-1 min-w-0 px-3 h-10 rounded-lg border border-[#E4E4E7] bg-[#FAFAFA] text-[12px] font-mono text-[#3F3F46] truncate flex items-center">
            {runtimeUrl}
          </code>
          <button
            onClick={() => copyUrl('/api/seo/runtime-config')}
            className="h-10 px-3 rounded-lg border border-[#E4E4E7] text-[12px] font-semibold text-[#52525B] hover:bg-[#FAFAFA] inline-flex items-center gap-1"
            data-testid="seo-copy-runtime"
          >
            <Copy size={12} weight="bold" /> {t.copy}
          </button>
          <a
            href={runtimeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="h-10 px-3 rounded-lg border border-[#E4E4E7] text-[12px] font-semibold text-[#52525B] hover:bg-[#FAFAFA] inline-flex items-center gap-1"
            data-testid="seo-preview-runtime"
          >
            <Eye size={12} weight="bold" /> {t.preview}
          </a>
        </div>
      </Section>

      {/* Tail spacer */}
      <div className="h-2" />
    </div>
  );
};

export default AdminSeoSettingsPage;
