import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useSeo } from "@/lib/seo";
import { useLang } from "@/i18n";
import { iconByName, categoryLabel, codesWord } from "@/lib/wasteMeta";
import { mediaUrl } from "@/lib/api";
import EcoCanvas from "@/components/layout/EcoCanvas";
import "./eco-cine.css";

gsap.registerPlugin(ScrollTrigger);
/* Mobile browsers fire resize when the URL bar collapses/expands — refreshing
   pinned ScrollTriggers mid-pin makes the hero jump/hang. Ignore those
   height-only resizes on touch devices (width/orientation changes still
   refresh normally). */
ScrollTrigger.config({ ignoreMobileResize: true });

const API_URL = process.env.REACT_APP_BACKEND_URL || "";

/* True for iPads / Android tablets / touch laptops in touch mode. Width alone
   is NOT enough: an 11–13" iPad is wider than 768px but must scroll natively —
   Lenis smooth-wheel fights the touch scroll and makes pinned scenes lag. */
const isTouchDevice = () =>
  typeof window !== "undefined" &&
  (window.matchMedia("(pointer: coarse)").matches ||
    (navigator.maxTouchPoints || 0) > 0 ||
    "ontouchstart" in window);

/* Real ECO.NOVA photography — licensed hazardous-waste utilization plant */
const IMG = {
  s0: "/media/sorting.jpg",             // workers sorting on conveyor (dynamic, wide)
  s1: "/media/handling.jpg",            // PPE crew + forklift handling big-bags
  s2: "/media/interior-1.jpg",          // facility interior, processing scale
  collect: "/media/loading.jpg",        // certified big-bag loading
  route: "/media/logistics.jpg",        // forklift loading onto transport
  transport: "/media/shipment-1.jpg",   // shipment / dispatch
  photo: "/media/utilization-powder.jpg", // utilization output (neutralised material)
  cta: "/media/facility.jpg",           // facility exterior
  opsBg: "/media/facility.jpg",         // operations band background
};

/* Real ECO.NOVA promo footage (own facility) */
const VIDEO = {
  heroLoop: "/media/hero-loop.mp4",     // muted aerial loop of the plant
  heroPoster: "/media/hero-poster.jpg",
  promo: "/media/promo.mp4",            // full company film
  promoPoster: "/media/promo-poster.jpg",
};

/* Real production gallery — how the company actually works */
const GALLERY = [
  { img: "/media/facility.jpg", key: "g_facility" },
  { img: "/media/sorting.jpg", key: "g_sorting" },
  { img: "/media/grinding.jpg", key: "g_grinding" },
  { img: "/media/utilization-powder.jpg", key: "g_util" },
  { img: "/media/furnace.jpg", key: "g_furnace" },
  { img: "/media/handling.jpg", key: "g_handling" },
  { img: "/media/shipment-2.jpg", key: "g_shipment" },
  { img: "/media/interior-2.jpg", key: "g_equipment" },
];

/* ── Bilingual copy (UA / EN) ─────────────────────────────────────────── */
const T = {
  uk: {
    seoTitle: "Безпечна утилізація небезпечних відходів для бізнесу • ECO.NOVA",
    seoDesc: "Ліцензований оператор. Класифікація, вивезення, утилізація та документи (акти, договори) для небезпечних відходів 1–4 класу. 80+ кодів, по всій Україні.",
    eyebrow: "Ліцензований оператор · Небезпечні відходи",
    h1: ["Чисте довкілля", "починається з", "відповідальної", "утилізації."],
    sub: "Класифікація, вивезення, утилізація та повний документальний супровід небезпечних відходів — в одній прозорій B2B-системі.",
    ctaCalc: "Розрахувати вартість",
    ctaCatalog: "Каталог відходів",
    ctaRequest: "Створити заявку",
    scene1H: "Класифікація. Збір. Транспортування.",
    scene1Label: "Кожен код — окремий ліцензійний сценарій",
    scene2H: "Прозорість на кожному етапі.",
    scene2Label: "Документи, акти та фотозвіти у захищеному кабінеті",
    railLabel: "Зроблено надійно",
    scrollHint: "Прокрутіть",
    trust: ["Ліцензія Мінекології", "Акти 1–4 клас", "ADR-транспорт", "24 області", "80+ кодів"],
    act1Kicker: "01 — Класифікація",
    act1H: ["Код. Ризик.", "Ліцензія. Рішення."],
    act1Lead: "Система визначає тип відходу, перевіряє ліцензійний допуск і формує правильний сценарій обробки — від класу небезпеки до акта утилізації.",
    codesHead: ["Код", "Тип відходу", "Клас", "Статус"],
    accepted: "Приймаємо",
    fullCatalog: "Повний довідник відходів →",
    codes: [
      { code: "18 01 03*", type: "Медичні відходи", cls: "Клас 1" },
      { code: "20 01 21*", type: "Люмінесцентні лампи", cls: "Клас 2" },
      { code: "16 06 01*", type: "Свинцеві акумулятори", cls: "Клас 1" },
      { code: "13 02 05*", type: "Відпрацьовані оливи", cls: "Клас 2" },
    ],
    act2Kicker: "02 — Операції",
    act2H: ["Процес під", "повним контролем."],
    ops: [
      { n: "01", t: "Збір", d: "Маркування, сертифікована тара та безпечне накопичення на об’єкті.", img: IMG.collect },
      { n: "02", t: "Маршрут", d: "Оптимальний логістичний план і графік вивезення по регіону.", img: IMG.route },
      { n: "03", t: "Транспорт", d: "ADR-транспорт із дозволами на перевезення небезпечних вантажів.", img: IMG.transport },
      { n: "04", t: "Фотофіксація", d: "Фото- та вагова фіксація на кожному етапі — у вашому кабінеті.", img: IMG.photo },
    ],
    manifestoEst: "ECO® Utilization Platform · Україна · Est. 2026",
    manifestoH: ["Іти далі за очікуване —", "наше покликання.", "Справжня сталість", "вимагає творчості,", "вирівняної зі суворими", "принципами та найвищими", "галузевими стандартами."],
    cells: [
      { t: "Класифікуємо", d: "431 код. 13 категорій. Ліцензії — у матриці прийому." },
      { t: "Вивозимо", d: "ADR-флот, маршрутизація та фотофіксація на кожному об’єкті." },
      { t: "Закриваємо", d: "Акт утилізації, екологічний звіт та архів у кабінеті клієнта." },
    ],
    // ── Rules (horizontal-scroll manifesto) ──
    rulesKicker: "Наші принципи",
    rulesH: "Правила, за якими ми працюємо.",
    rulesLead: "П’ять простих принципів, які роблять кожне вивезення прозорим, безпечним і законним — від приймання до акту утилізації.",
    rulesStat1: "5 принципів",
    rulesStat2: "Кожен крок задокументовано",
    rulesFoot: "Стандарт ECO.NOVA",
    rulesCta: "Дивитись",
    rulesBackdrop: "PRINCIPLES",
    rulesHint: "Прокрутіть →",
    rules: [
      { no: "01", t: "Ліцензія",        d: "Дозволи Мінекології на всі 1–4 класи небезпеки. 431 код у матриці — з правовою підставою за кожним рухом." },
      { no: "02", t: "Прозорість",      d: "Фотофіксація, GPS-маршрут і вага на кожній точці. Всі документи — у вашому кабінеті в real-time." },
      { no: "03", t: "Безпека",         d: "ADR-транспорт, сертифікована тара, навчений персонал у ЗІЗ. Нуль інцидентів — робочий стандарт, не гасло." },
      { no: "04", t: "Закритий цикл",   d: "Акт утилізації, еко-звіт, архів версій у кабінеті. Ланцюг замикається юридично й фізично." },
      { no: "05", t: "Циркулярність",   d: "Максимум переробки, мінімум полігону. Ваша ESG-звітність — на нашій відповідальності." },
    ],
    act4Kicker: "04 — Ліцензії",
    act4H: ["Наші", "ліцензії."],
    act4Lead: "Кожен рух відходів — з правовою підставою. Повний набір дозволів Мінекології, ISO та ADR — оновлені та завжди актуальні.",
    licensesBg: "ЛІЦЕНЗІЇ",
    licenses: [
      { no: "01", t: "Ліцензія Мінекології", d: "Поводження з небезпечними відходами · класи I–IV", img: "/media/licenses/license-01.svg" },
      { no: "02", t: "Сертифікат ISO 14001", d: "Система екологічного менеджменту · TÜV NORD", img: "/media/licenses/license-02.svg" },
      { no: "03", t: "Дозвіл на викиди", d: "Державна екоінспекція · граничні норми", img: "/media/licenses/license-03.svg" },
      { no: "04", t: "Сертифікат ADR/RID", d: "Перевезення небезпечних вантажів · класи 1–9", img: "/media/licenses/license-04.svg" },
    ],
    docs: [
      { t: "Договір", d: "Умови, обсяги, графік та відповідальність сторін." },
      { t: "Рахунок", d: "Прозоре ціноутворення за кодами відходів." },
      { t: "Акт", d: "Акт приймання-передачі та утилізації відходу." },
      { t: "Сертифікат", d: "Підтвердження знешкодження й екологічної звітності." },
    ],
    ctaKicker: "06 — Почнімо",
    ctaH: ["Готові розпочати", "відповідальну утилізацію?"],
    ctaSub: "Оберіть код відходу, вкажіть обсяг — і отримайте прозорий розрахунок із повним документальним супроводом.",
    // ── Video showcase ──
    videoKicker: "Реальне виробництво",
    videoH: ["Подивіться, як", "працює ECO.NOVA."],
    videoLead: "Власний ліцензований комплекс: приймання, сортування, переробка та термічне знешкодження небезпечних відходів — знято на нашому майданчику.",
    videoPlay: "Дивитися фільм",
    videoFacts: [
      { k: "431", v: "кодів у нацпереліку" },
      { k: "1–4", v: "класи небезпеки" },
      { k: "24", v: "області покриття" },
    ],
    // ── Production gallery ──
    galleryKicker: "03 — Виробництво",
    galleryH: ["Власний ліцензований", "комплекс утилізації."],
    galleryLead: "Кожен кадр знято на нашому виробництві. Так виглядає повний цикл поводження з небезпечними відходами на практиці — від приймання до безпечної утилізації.",
    gallery: {
      g_facility: { t: "Виробничий комплекс", d: "Ліцензований майданчик утилізації" },
      g_sorting: { t: "Сортування", d: "Розділення та ідентифікація фракцій" },
      g_grinding: { t: "Механічна переробка", d: "Подрібнення й підготовка сировини" },
      g_util: { t: "Знешкодження", d: "Перетворення відходу на інертний продукт" },
      g_furnace: { t: "Термічна обробка", d: "Високотемпературне знешкодження" },
      g_handling: { t: "Безпечне поводження", d: "ЗІЗ та контроль на кожному кроці" },
      g_shipment: { t: "Відвантаження", d: "Тарування, зважування, логістика" },
      g_equipment: { t: "Промислові лінії", d: "Обладнання для переробки" },
    },
    // ── Client access / how to start ──
    accessKicker: "05 — Ваш кабінет",
    accessH: ["Прозорість —", "у вашому кабінеті."],
    accessLead: "Клієнти працюють у захищеному онлайн-кабінеті: заявки, договори, акти, рахунки та статус кожного вивезення — цілодобово.",
    accessSteps: [
      { n: "01", t: "Реєстрація та вхід", d: "Створюєте акаунт компанії або входите через Google — доступ лише для бізнесу." },
      { n: "02", t: "Заявка на вивезення", d: "Обираєте код відходу, обсяг та об’єкт — система формує розрахунок." },
      { n: "03", t: "Договір і графік", d: "Електронний підпис договору та узгодження дати вивезення." },
      { n: "04", t: "Контроль і документи", d: "Фотозвіти, акти утилізації та історія — усе в кабінеті." },
    ],
    accessCtaClient: "Увійти в кабінет клієнта",
    accessCtaRequest: "Замовити дзвінок",
    accessNote: "Робочий доступ для операторів і менеджерів — через окремий вхід /admin.",
  },
  en: {
    seoTitle: "Safe hazardous-waste disposal for business • ECO.NOVA",
    seoDesc: "Licensed operator. Classification, collection, disposal and documents (acts, contracts) for class 1–4 hazardous waste. 80+ codes, across Ukraine.",
    eyebrow: "Licensed operator · Hazardous waste",
    h1: ["A clean environment", "begins with", "responsible", "recycling."],
    sub: "Classification, collection, disposal and full documentary support of hazardous waste — in one transparent B2B system.",
    ctaCalc: "Calculate the cost",
    ctaCatalog: "Waste catalog",
    ctaRequest: "Create a request",
    scene1H: "Classification. Collection. Transport.",
    scene1Label: "Each code is its own licensed scenario",
    scene2H: "Transparency at every step.",
    scene2Label: "Documents, acts and photo reports in a secure cabinet",
    railLabel: "Built reliably",
    scrollHint: "Scroll",
    trust: ["Ministry of Ecology licence", "Class 1–4 acts", "ADR transport", "24 regions", "80+ codes"],
    act1Kicker: "01 — Classification",
    act1H: ["Code. Risk.", "Licence. Decision."],
    act1Lead: "The system identifies the waste type, checks licence clearance and builds the right handling scenario — from hazard class to the disposal act.",
    codesHead: ["Code", "Waste type", "Class", "Status"],
    accepted: "Accepted",
    fullCatalog: "Full waste directory →",
    codes: [
      { code: "18 01 03*", type: "Medical waste", cls: "Class 1" },
      { code: "20 01 21*", type: "Fluorescent lamps", cls: "Class 2" },
      { code: "16 06 01*", type: "Lead batteries", cls: "Class 1" },
      { code: "13 02 05*", type: "Used oils", cls: "Class 2" },
    ],
    act2Kicker: "02 — Operations",
    act2H: ["A process under", "full control."],
    ops: [
      { n: "01", t: "Collection", d: "Labelling, certified containers and safe on-site accumulation.", img: IMG.collect },
      { n: "02", t: "Route", d: "An optimal logistics plan and regional collection schedule.", img: IMG.route },
      { n: "03", t: "Transport", d: "ADR transport with permits for hazardous-cargo carriage.", img: IMG.transport },
      { n: "04", t: "Photo log", d: "Photo and weight logging at every stage — in your cabinet.", img: IMG.photo },
    ],
    manifestoEst: "ECO® Utilization Platform · Ukraine · Est. 2026",
    manifestoH: ["Going beyond the expected —", "that is our calling.", "True sustainability", "demands creativity,", "aligned with strict", "principles and the highest", "industry standards."],
    cells: [
      { t: "We classify", d: "431 codes. 13 categories. Licences — in the acceptance matrix." },
      { t: "We collect", d: "ADR fleet, routing and photo logging at every site." },
      { t: "We close out", d: "Disposal act, eco report and archive in the client cabinet." },
    ],
    // ── Rules (horizontal-scroll manifesto) ──
    rulesKicker: "Our principles",
    rulesH: "The rules we work by.",
    rulesLead: "Five simple principles that make every collection transparent, safe and lawful — from acceptance to the disposal act.",
    rulesStat1: "5 principles",
    rulesStat2: "Every step is documented",
    rulesFoot: "ECO.NOVA standard",
    rulesCta: "View",
    rulesBackdrop: "PRINCIPLES",
    rulesHint: "Scroll →",
    rules: [
      { no: "01", t: "Licence",     d: "Ministry of Ecology permits for all hazard classes 1–4. 431 codes in the acceptance matrix — every move has legal grounds." },
      { no: "02", t: "Transparency", d: "Photo evidence, GPS route and weight at every checkpoint. All documents — in your cabinet in real-time." },
      { no: "03", t: "Safety",      d: "ADR transport, certified containers, PPE-trained crew. Zero incidents — a working standard, not a slogan." },
      { no: "04", t: "Closed loop", d: "Disposal act, eco report and version archive in your cabinet. The chain closes legally and physically." },
      { no: "05", t: "Circular",    d: "Maximum recycling, minimum landfill. Your ESG reporting — on our responsibility." },
    ],
    act4Kicker: "04 — Licenses",
    act4H: ["Our", "licenses."],
    act4Lead: "Every movement of waste, backed by paperwork. A complete stack of Ministry-of-Environment, ISO and ADR permits — kept current, never expired.",
    licensesBg: "LICENSES",
    licenses: [
      { no: "01", t: "Ministry-of-Environment Permit", d: "Hazardous-waste management · classes I–IV", img: "/media/licenses/license-01.svg" },
      { no: "02", t: "ISO 14001 Certificate", d: "Environmental management system · TÜV NORD", img: "/media/licenses/license-02.svg" },
      { no: "03", t: "Emission Permit", d: "State Environmental Inspectorate · limit values", img: "/media/licenses/license-03.svg" },
      { no: "04", t: "ADR/RID Certificate", d: "Transport of dangerous goods · classes 1–9", img: "/media/licenses/license-04.svg" },
    ],
    docs: [
      { t: "Contract", d: "Terms, volumes, schedule and the parties' responsibilities." },
      { t: "Invoice", d: "Transparent pricing by waste codes." },
      { t: "Act", d: "Acceptance-transfer and waste-disposal act." },
      { t: "Certificate", d: "Confirmation of neutralisation and eco reporting." },
    ],
    ctaKicker: "06 — Let's start",
    ctaH: ["Ready to start", "responsible recycling?"],
    ctaSub: "Pick a waste code, enter the volume — and get a transparent estimate with full documentary support.",
    // ── Video showcase ──
    videoKicker: "Real operations",
    videoH: ["See how", "ECO.NOVA works."],
    videoLead: "Our own licensed plant: intake, sorting, processing and thermal neutralisation of hazardous waste — filmed on site.",
    videoPlay: "Watch the film",
    videoFacts: [
      { k: "431", v: "codes in the register" },
      { k: "1–4", v: "hazard classes" },
      { k: "24", v: "regions covered" },
    ],
    // ── Production gallery ──
    galleryKicker: "03 — Production",
    galleryH: ["Our own licensed", "utilization facility."],
    galleryLead: "Every frame is shot at our own facility. This is what a full hazardous-waste handling cycle looks like in practice — from intake to safe utilization.",
    gallery: {
      g_facility: { t: "Production site", d: "Licensed utilization facility" },
      g_sorting: { t: "Sorting", d: "Separation and identification of fractions" },
      g_grinding: { t: "Mechanical processing", d: "Shredding and feedstock prep" },
      g_util: { t: "Neutralisation", d: "Turning waste into inert product" },
      g_furnace: { t: "Thermal treatment", d: "High-temperature neutralisation" },
      g_handling: { t: "Safe handling", d: "PPE and control at every step" },
      g_shipment: { t: "Dispatch", d: "Packing, weighing, logistics" },
      g_equipment: { t: "Industrial lines", d: "Processing equipment" },
    },
    // ── Client access / how to start ──
    accessKicker: "05 — Your cabinet",
    accessH: ["Transparency —", "in your cabinet."],
    accessLead: "Clients work in a secure online cabinet: requests, contracts, acts, invoices and the status of every collection — around the clock.",
    accessSteps: [
      { n: "01", t: "Sign up & log in", d: "Create a company account or sign in with Google — business access only." },
      { n: "02", t: "Collection request", d: "Choose a waste code, volume and site — the system builds an estimate." },
      { n: "03", t: "Contract & schedule", d: "E-sign the contract and agree the collection date." },
      { n: "04", t: "Control & documents", d: "Photo reports, disposal acts and history — all in the cabinet." },
    ],
    accessCtaClient: "Enter the client cabinet",
    accessCtaRequest: "Request a call",
    accessNote: "Operator & manager access is via a separate /admin login.",
  },
};

/* word/line split helpers (own splitter — no extra deps) */
const Word = ({ children }) => (
  <span className="word"><span>{children}</span></span>
);
const Line = ({ text }) => (
  <span style={{ display: "block" }}>
    {text.split(" ").map((w, i) => <Word key={i}>{w}</Word>)}
  </span>
);
const Words = ({ text }) => text.split(" ").map((w, i) => <Word key={i}>{w}</Word>);

/* ── Unique, hand-drawn SVG icons for each rule (Licence 01 → Circular 05) ── */
const RuleIcon = ({ no }) => {
  const c = "currentColor";
  const sw = 1.6;
  const shared = {
    viewBox: "0 0 32 32",
    width: 22,
    height: 22,
    fill: "none",
    stroke: c,
    strokeWidth: sw,
    strokeLinecap: "round",
    strokeLinejoin: "round",
  };
  switch (parseInt(no, 10)) {
    case 1: // Licence — certificate with rosette & ribbon
      return (
        <svg {...shared}>
          <rect x="6" y="4" width="20" height="18" rx="2" />
          <path d="M10 10h8M10 14h6" />
          <circle cx="21" cy="22" r="4.2" />
          <path d="M18.7 25.2l-1 4 3.3-1.8 3.3 1.8-1-4" />
        </svg>
      );
    case 2: // Transparency — eye with iris
      return (
        <svg {...shared}>
          <path d="M2.5 16C6 9 10.5 6 16 6s10 3 13.5 10c-3.5 7-8 10-13.5 10S6 23 2.5 16z" />
          <circle cx="16" cy="16" r="3.2" />
          <circle cx="14.8" cy="14.8" r="0.7" fill={c} stroke="none" />
        </svg>
      );
    case 3: // Safety — shield with checkmark
      return (
        <svg {...shared}>
          <path d="M16 3l11 4v9c0 6.5-4.6 11.5-11 13-6.4-1.5-11-6.5-11-13V7l11-4z" />
          <path d="M11 16l3.4 3.4L21 12.8" />
        </svg>
      );
    case 4: // Closed loop — two arrows forming a closed loop
      return (
        <svg {...shared}>
          <path d="M6 12a10 10 0 0 1 17-3" />
          <path d="M19 5v5h5" />
          <path d="M26 20a10 10 0 0 1-17 3" />
          <path d="M13 27v-5H8" />
        </svg>
      );
    case 5: // Circular — recycle triangle with three arrows
      return (
        <svg {...shared}>
          <path d="M16 6l4 6h-8l4-6z" />
          <path d="M11.5 13l-5.5 9h6" />
          <path d="M20.5 13l5.5 9h-6" />
          <path d="M9.5 22l1 3 3-1" />
          <path d="M22.5 22l-1 3-3-1" />
          <path d="M16 14v-2" />
        </svg>
      );
    default:
      return (
        <svg {...shared}>
          <circle cx="16" cy="16" r="10" />
        </svg>
      );
  }
};

export default function Home() {
  const root = useRef(null);
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  // Tracks whether the cinematic timeline has already been built once, so we
  // can tell a genuine language *switch* apart from the very first mount and
  // reset the scroll position cleanly before rebuilding the pinned scenes.
  const cineBuiltRef = useRef(false);
  const [partners, setPartners] = useState(null);
  const [reviews, setReviews] = useState(null);
  const [hero, setHero] = useState(null);
  const [certificates, setCertificates] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [ruleIdx, setRuleIdx] = useState(0);
  const licensesRef = useRef(null);
  const licensesTrackRef = useRef(null);
  const licensesBgRef = useRef(null);
  const heroCountRef = useRef(null);
  const heroVideoRef = useRef(null);
  /* Bumped whenever the viewport crosses a layout breakpoint (768 / 900px) —
     forces the cinematic timeline to tear down and rebuild so pinned triggers
     always match the CSS layout that is actually on screen (fixes "hanging"
     sliders after window resize / iPad rotation). */
  const [vpKey, setVpKey] = useState(0);

  useSeo(L.seoTitle, L.seoDesc);

  /* ── Managed catalog categories (top quick-links under the hero) ───────── */
  useEffect(() => {
    let alive = true;
    axios
      .get(`${API_URL}/api/waste/categories`, { params: { accepted: true } })
      .then((r) => { if (alive) setCatalog(r.data?.categories || []); })
      .catch(() => { if (alive) setCatalog([]); });
    return () => { alive = false; };
  }, []);

  /* ── Rebuild pinned scenes when crossing responsive breakpoints ────────── */
  useEffect(() => {
    const queries = ["(max-width: 768px)", "(max-width: 900px)"].map((q) =>
      window.matchMedia(q)
    );
    const onChange = () => setVpKey((v) => v + 1);
    queries.forEach((q) =>
      q.addEventListener ? q.addEventListener("change", onChange) : q.addListener(onChange)
    );
    return () =>
      queries.forEach((q) =>
        q.removeEventListener ? q.removeEventListener("change", onChange) : q.removeListener(onChange)
      );
  }, []);

  /* ── Hero video: bullet-proof autoplay across browsers ───────────────────
     React does not render the `muted` attribute into the DOM, and Safari /
     Brave / low-power modes can refuse the initial autoplay. We force the
     muted+playsinline attributes imperatively and retry play() on
     loadeddata / visibility / the first user gesture. If the source truly
     cannot be decoded we hide the <video> so the still photo behind it shows
     — the hero never renders a black box. */
  useEffect(() => {
    const v = heroVideoRef.current;
    if (!v) return undefined;
    let disposed = false;

    v.defaultMuted = true;
    v.muted = true;
    v.setAttribute("muted", "");
    v.playsInline = true;
    v.setAttribute("playsinline", "");
    v.setAttribute("webkit-playsinline", "");

    const isHidden = () => {
      try { return window.getComputedStyle(v).display === "none"; } catch { return false; }
    };
    const tryPlay = () => {
      if (disposed || v.error || isHidden() || !v.paused) return;
      const p = v.play();
      if (p && typeof p.catch === "function") p.catch(() => {});
    };

    const onLoaded = () => tryPlay();
    const onVisible = () => { if (!document.hidden) tryPlay(); };
    const gestures = ["pointerdown", "touchstart", "keydown", "wheel", "scroll"];
    const onGesture = () => tryPlay();

    v.addEventListener("loadeddata", onLoaded);
    v.addEventListener("canplay", onLoaded);
    document.addEventListener("visibilitychange", onVisible);
    gestures.forEach((e) => window.addEventListener(e, onGesture, { passive: true }));

    const onError = () => { try { v.style.display = "none"; } catch {} };
    v.addEventListener("error", onError);
    // The decode error may have fired BEFORE this effect attached listeners —
    // apply the still-photo fallback synchronously in that case.
    if (v.error) onError();

    // kick it off (covers the normal path where autoplay is simply allowed)
    tryPlay();
    const lateKick = setTimeout(tryPlay, 800);

    return () => {
      disposed = true;
      clearTimeout(lateKick);
      v.removeEventListener("loadeddata", onLoaded);
      v.removeEventListener("canplay", onLoaded);
      v.removeEventListener("error", onError);
      document.removeEventListener("visibilitychange", onVisible);
      gestures.forEach((e) => window.removeEventListener(e, onGesture));
    };
  }, [vpKey]);

  /* ── Licenses / certificates (admin-managed via site-info) ──────────────
     When the admin has configured certificates we render those; otherwise we
     fall back to the built-in static defaults so the section is never empty. */
  const licLang = lang === "en" ? "en" : "uk";
  const mediaUrl = (u) => (u && String(u).startsWith("/api") ? `${API_URL}${u}` : u);
  const certItems = (certificates?.items || []).filter((c) => c && c.enabled !== false);
  const useCerts = certificates?.enabled !== false && certItems.length > 0;
  const licenseCards = useCerts
    ? certItems.map((c, i) => ({
        no: c.no || String(i + 1).padStart(2, "0"),
        t: (licLang === "en" ? c.title_en : c.title_uk) || c.title_uk || c.title_en || "",
        d: (licLang === "en" ? c.desc_en : c.desc_uk) || c.desc_uk || c.desc_en || "",
        img: mediaUrl(c.image_url) || "/media/licenses/license-01.svg",
        file: mediaUrl(c.file_url) || "",
        issuer: (licLang === "en" ? c.issuer_en : c.issuer_uk) || "",
        number: c.number || "",
        issued: c.issued || "",
        validUntil: c.valid_until || "",
      }))
    : (L.licenses || []).map((lic) => ({ ...lic, t: lic.t, d: lic.d }));
  const licLead =
    (useCerts && (licLang === "en" ? certificates?.subtitle_en : certificates?.subtitle_uk)) ||
    L.act4Lead;

  /* Fetch admin-managed partners (public site-info) */
  useEffect(() => {
    let alive = true;
    axios
      .get(`${API_URL}/api/site-info`)
      .then((r) => {
        if (!alive) return;
        setPartners(r.data?.partners || null);
        setReviews(r.data?.reviews || null);
        setHero(r.data?.hero || null);
        setCertificates(r.data?.certificates || null);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  /* Cinematic scroll-reveal for the Friends & Reviews section headers.
     The marquee tracks themselves auto-scroll via CSS; here we just lift the
     kicker / title / subtitle into view to match the site's motion language. */
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = window.matchMedia("(max-width: 768px)").matches;
    const rootEl = root.current;
    if (!rootEl) return undefined;
    if (reduce || isMobile) return undefined;

    const sections = Array.from(
      rootEl.querySelectorAll('[data-testid="home-partners"], [data-testid="home-reviews"]'),
    );
    if (!sections.length) return undefined;

    const ctx = gsap.context(() => {
      sections.forEach((section) => {
        const head = section.querySelector(".cine-act__head");
        if (head) {
          gsap.from(head.children, {
            y: 42,
            opacity: 0,
            duration: 0.9,
            ease: "power3.out",
            stagger: 0.12,
            scrollTrigger: { trigger: section, start: "top 82%", once: true },
          });
        }
      });
    }, root);
    ScrollTrigger.refresh();
    return () => ctx.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partners, reviews, vpKey]);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = window.matchMedia("(max-width: 768px)").matches;
    // Mobile now runs the SAME in-place cross-fade hero as desktop (slides
    // replace each other while the block is pinned). Only prefers-reduced-motion
    // falls back to the static, no-animation layout.
    const canAnimate = !reduce;

    if (!canAnimate) {
      // On phones / reduced-motion we do NOT run the cinematic timeline.
      // Make absolutely sure nothing is left hidden: the `.cine--enhanced`
      // class drives `[data-reveal] { opacity: 0 }`, and a previous
      // (wider-width) render or a language switch could have left GSAP inline
      // styles behind. Strip them so every block is visible immediately.
      const rootEl = root.current;
      if (rootEl) {
        rootEl.classList.remove("cine--enhanced");
        rootEl.querySelectorAll(
          '[data-reveal], [data-reveal-group] > *, .word > span, [data-cap]'
        ).forEach((el) => {
          el.style.opacity = "";
          el.style.transform = "";
          el.style.visibility = "";
        });
      }
      const sections = Array.from(rootEl?.querySelectorAll("[data-theme]") || []);
      const apply = () => {
        const line = 70;
        let theme = "dark";
        for (const s of sections) {
          const r = s.getBoundingClientRect();
          if (r.top <= line && r.bottom > line) { theme = s.dataset.theme || "light"; break; }
        }
        document.documentElement.dataset.navTheme = theme;
      };
      apply();
      window.addEventListener("scroll", apply, { passive: true });
      window.addEventListener("resize", apply);
      return () => {
        window.removeEventListener("scroll", apply);
        window.removeEventListener("resize", apply);
        document.documentElement.removeAttribute("data-nav-theme");
      };
    }

    root.current?.classList.add("cine--enhanced");
    document.documentElement.dataset.navTheme = "dark";

    // When the visitor switches language mid-page the whole cinematic timeline
    // is torn down and rebuilt. Rebuilding pinned ScrollTriggers while the page
    // is scrolled leaves the stacking hero scenes in a broken, overlapping
    // state with oversized pin-spacers ("huge paddings"). Snap back to the top
    // first so every pin is measured from a clean origin.
    if (cineBuiltRef.current) {
      try {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
        ScrollTrigger.clearScrollMemory();
      } catch {}
    }

    // Smooth-scroll (Lenis) only on non-touch desktop. On touch devices
    // (phones AND tablets/iPads — regardless of width) native scroll drives
    // ScrollTrigger — Lenis smooth-touch fights the browser and makes the
    // pinned hero feel laggy / "hang".
    let lenis = null;
    let raf = null;
    if (!isMobile && !isTouchDevice()) {
      lenis = new Lenis({ duration: 1.2, lerp: 0.09, smoothWheel: true, wheelMultiplier: 0.95 });
      // Force Lenis to the very top so its internal target matches the DOM.
      try { lenis.scrollTo(0, { immediate: true, force: true }); } catch {}
      lenis.on("scroll", ScrollTrigger.update);
      raf = (t) => lenis.raf(t * 1000);
      gsap.ticker.add(raf);
      gsap.ticker.lagSmoothing(0);
    }

    const ctx = gsap.context((self) => {
      const q = gsap.utils.selector(root);

      gsap.set(q('[data-cap] [data-reveal]'), { y: 24, opacity: 0 });
      gsap.set(q('.cine-act [data-reveal]'), { y: 34, opacity: 0 });
      gsap.utils.toArray(q('[data-reveal-group]')).forEach((g) =>
        gsap.set(g.children, { y: 34, opacity: 0 })
      );
      const cap0Spans = Array.from(q('[data-cap="0"] .word > span'));
      const restSpans = Array.from(q('.word > span')).filter((s) => !cap0Spans.includes(s));
      cap0Spans.forEach((s) => {
        const h = s.offsetHeight || 100;
        gsap.set(s, { y: h * 1.15 });
      });
      gsap.set(restSpans, { yPercent: 115 });

      gsap.to(cap0Spans, {
        y: 0, duration: 1.05, stagger: 0.05, ease: "power4.out", delay: 0.2,
      });
      gsap.to(q('[data-cap="0"] [data-reveal]'), {
        y: 0, opacity: 1, duration: 0.85, stagger: 0.1, ease: "power3.out", delay: 0.5,
      });

      const hero = q(".cine-hero")[0];
      const scene0 = q('[data-scene="0"]')[0];
      const scene1 = q('[data-scene="1"]')[0];
      const scene2 = q('[data-scene="2"]')[0];
      const m0 = q('[data-scene="0"] .cine-scene__img')[0];
      const m1 = q('[data-scene="1"] .cine-scene__img')[0];
      const m2 = q('[data-scene="2"] .cine-scene__img')[0];

      /* Explicit initial state for the stacking scenes. GSAP doesn't
         inherit CSS transforms, so we set them here to guarantee the
         "card sits below the fold" starting point. Use `immediateRender`
         via fromTo() below to force the initial matrix on paint. */

      const master = gsap.timeline({
        scrollTrigger: {
          trigger: hero,
          start: "top top",
          end: () => "+=" + window.innerHeight * 6.5,
          pin: true,
          scrub: 1,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            const el = heroCountRef.current;
            if (!el) return;
            const p = self.progress;
            const idx = p < 0.24 ? 1 : p < 0.56 ? 2 : 3;
            if (el.dataset.idx !== String(idx)) {
              el.dataset.idx = String(idx);
              el.textContent = String(idx).padStart(2, "0");
              el.classList.remove("is-tick");
              void el.offsetWidth; // restart the pop animation
              el.classList.add("is-tick");
            }
          },
        },
        defaults: { immediateRender: false },
      });

      /* Explicit initial state for the stacking scenes. GSAP doesn't
         inherit CSS transforms, so we set them here to guarantee the
         "card sits below the fold" starting point. */
      gsap.set([scene1, scene2], {
        yPercent: 100,
        scale: 1.02,
        borderRadius: 32,
        transformOrigin: "50% 0%",
        force3D: true,
      });

      /* ── LEOLEO-STYLE STACKING CARDS (subtle) ────────────────────────────
         The next scene slides up from below with a modest border-radius
         that shrinks to zero as it covers the previous one. The previous
         scene gets a very light "stacked" treatment (tiny scale-down,
         faint dim) — only really visible on reverse-scroll. Values are
         intentionally understated to keep the hero feeling calm rather
         than gimmicky. */

      /* ambient parallax on scene-0 hero image throughout act 1 */
      master.to(m0, { scale: 1.14, duration: 4.2, ease: "none" }, 0);

      /* ── SCENE 0 → SCENE 1 (t = 0.9 … 2.4) ── */
      master.to(q('[data-cap="0"]'), { opacity: 0, y: -40, duration: 0.6, ease: "power2.in", immediateRender: false }, 0.9);

      master.fromTo(scene1,
        { yPercent: 100, scale: 1.02, borderRadius: 32 },
        {
          yPercent: 0,
          scale: 1,
          borderRadius: 0,
          ease: "power3.out",
          duration: 1.5,
          immediateRender: true,
        }, 0.9);
      master.fromTo(m1, { scale: 1.18 }, { scale: 1.04, duration: 3.0, ease: "none" }, 0.9);
      master.fromTo(q('[data-cap="1"] .word > span'),
        { yPercent: 115 },
        { yPercent: 0, duration: 0.7, stagger: 0.03, ease: "power4.out" }, 1.6);
      master.to(q('[data-cap="1"] [data-reveal]'), { opacity: 1, y: 0, duration: 0.5 }, 1.8);

      /* Scene 0 receives a barely-there "stacked" state after being
         covered — a whisper of scale + dim, no filter blur. */
      master.to(scene0, {
        scale: 0.97,
        yPercent: -1.5,
        borderRadius: 18,
        opacity: 0.85,
        ease: "power1.out",
        duration: 0.4,
      }, 2.45);

      /* ── SCENE 1 → SCENE 2 (t = 2.6 … 4.1) ── */
      master.to(q('[data-cap="1"] .word > span'), { yPercent: -115, duration: 0.55, stagger: 0.02, ease: "power3.in" }, 2.6);
      master.to(q('[data-cap="1"] [data-reveal]'), { opacity: 0, duration: 0.35 }, 2.6);

      master.fromTo(scene2,
        { yPercent: 100, scale: 1.02, borderRadius: 32 },
        {
          yPercent: 0,
          scale: 1,
          borderRadius: 0,
          ease: "power3.out",
          duration: 1.5,
          immediateRender: true,
        }, 2.7);
      master.fromTo(m2, { scale: 1.18 }, { scale: 1.04, duration: 3.0, ease: "none" }, 2.7);
      master.fromTo(q('[data-cap="2"] .word > span'),
        { yPercent: 115 },
        { yPercent: 0, duration: 0.7, stagger: 0.03, ease: "power4.out" }, 3.4);
      master.to(q('[data-cap="2"] [data-reveal]'), { opacity: 1, y: 0, duration: 0.5 }, 3.6);

      /* Same subtle stacked state for scene 1 once scene 2 covers it. */
      master.to(scene1, {
        scale: 0.97,
        yPercent: -1.5,
        borderRadius: 18,
        opacity: 0.85,
        ease: "power1.out",
        duration: 0.4,
      }, 4.25);

      master.to({}, { duration: 0.9 }, 4.4);

      const fill = q(".cine-rail__fill")[0];
      if (fill) master.fromTo(fill, { scaleY: 0 }, { scaleY: 1, ease: "none", duration: master.duration() }, 0);

      gsap.utils.toArray(q(".reveal-words")).forEach((h) => {
        gsap.to(h.querySelectorAll(".word > span"), {
          yPercent: 0, duration: 0.95, stagger: 0.04, ease: "power4.out",
          scrollTrigger: { trigger: h, start: "top 86%" },
        });
      });
      gsap.utils.toArray(q(".cine-act [data-reveal]")).forEach((el) => {
        gsap.to(el, { y: 0, opacity: 1, duration: 0.9, ease: "power3.out", scrollTrigger: { trigger: el, start: "top 90%" } });
      });
      gsap.utils.toArray(q("[data-reveal-group]")).forEach((g) => {
        gsap.to(g.children, { y: 0, opacity: 1, duration: 0.8, stagger: 0.08, ease: "power3.out", scrollTrigger: { trigger: g, start: "top 86%" } });
      });

      gsap.utils.toArray(q("[data-parallax]")).forEach((el) => {
        const sp = parseFloat(el.dataset.parallax) || 0.2;
        gsap.fromTo(el, { yPercent: -sp * 14 }, {
          yPercent: sp * 14, ease: "none",
          scrollTrigger: { trigger: el.closest("section"), start: "top bottom", end: "bottom top", scrub: true },
        });
      });

      /* ── RULES · classic grid, no scroll animation (per user request) ── */

      /* ── LICENSES · Buzzworthy-style pinned horizontal scroll ────────
         The <section> is pinned as long as the horizontal track has
         off-screen content; foreground cards translate on X, background
         "LICENSES" word does a colour drift + slow x-parallax so it feels
         alive without competing with the cards. */
      const licSec = licensesRef.current;
      const licTrack = licensesTrackRef.current;
      const licBg = licensesBgRef.current;
      /* Only run the pinned horizontal scroll on desktop. On phones/tablets
         the section falls back to a native side-scroll row (see CSS
         @media max-width:900px) — pinning there clips cards & captions. */
      if (licSec && licTrack && window.innerWidth > 900) {
        const measure = () => Math.max(0, licTrack.scrollWidth - window.innerWidth);
        ScrollTrigger.create({
          trigger: licSec,
          start: "top top",
          end: () => "+=" + measure(),
          pin: true,
          scrub: 0.8,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          animation: gsap.timeline()
            .to(licTrack, { x: () => -measure(), ease: "none" }, 0)
            .fromTo(licBg,
              { xPercent: 6, color: "#e6ecdd" },
              { xPercent: -14, color: "#2f5d3d", ease: "none" }, 0),
        });
      }

      gsap.utils.toArray(q("[data-theme]")).forEach((sec) => {
        ScrollTrigger.create({
          trigger: sec, start: "top 64", end: "bottom 64",
          onToggle: (s) => { if (s.isActive) document.documentElement.dataset.navTheme = sec.dataset.theme; },
        });
      });

      ScrollTrigger.refresh();
    }, root);

    // Mark the timeline as built so subsequent language switches know to reset
    // the scroll position before rebuilding.
    cineBuiltRef.current = true;

    // Robust re-measure: pin-spacer heights depend on the final laid-out
    // content, which for a language switch changes AFTER React commits the new
    // text and AFTER webfonts settle. A single refresh can therefore capture
    // stale heights (the "big paddings that fix themselves on hard refresh"
    // bug). We refresh across several settle points instead.
    const refreshHandles = [];
    const doRefresh = () => { try { ScrollTrigger.refresh(); } catch {} };
    const onLoad = () => doRefresh();
    window.addEventListener("load", onLoad);
    // next paint + one more frame
    requestAnimationFrame(() => requestAnimationFrame(doRefresh));
    // webfonts (heading metrics shift once the display font loads)
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(doRefresh).catch(() => {});
    }
    // safety timers for slow layout / late images
    [200, 600, 1200].forEach((ms) => refreshHandles.push(setTimeout(doRefresh, ms)));

    return () => {
      refreshHandles.forEach((h) => clearTimeout(h));
      window.removeEventListener("load", onLoad);
      ctx.revert();
      if (raf) gsap.ticker.remove(raf);
      if (lenis) lenis.destroy();
      root.current?.classList.remove("cine--enhanced");
      document.documentElement.removeAttribute("data-nav-theme");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, vpKey]);

  /* ── Friends / partners (admin-managed logo marquee) ──────────────────── */
  const isUk = lang === "uk";
  const partnerItems = (partners?.items || []).filter((p) => p && p.enabled !== false);
  const showPartners = (partners?.enabled !== false) && partnerItems.length > 0;
  const pTitle =
    (isUk ? partners?.title_uk : partners?.title_en) ||
    partners?.title_en || partners?.title_uk ||
    (isUk ? "Наші френди" : "Our friends");
  const pSub = (isUk ? partners?.subtitle_uk : partners?.subtitle_en) || "";
  const pKicker = isUk ? "Френди" : "Friends";

  /* ── Reviews (admin-managed testimonials marquee) ─────────────────────── */
  const reviewItems = (reviews?.items || []).filter((r) => r && r.enabled !== false);
  const showReviews = (reviews?.enabled !== false) && reviewItems.length > 0;
  const rTitle =
    (isUk ? reviews?.title_uk : reviews?.title_en) ||
    reviews?.title_en || reviews?.title_uk ||
    (isUk ? "Що кажуть наші клієнти" : "What our clients say");
  const rSub = (isUk ? reviews?.subtitle_uk : reviews?.subtitle_en) || "";
  const rKicker = isUk ? "Відгуки" : "Reviews";

  return (
    <div className="cine" ref={root} data-testid="home-page">
      <EcoCanvas />

      {/* ═══ ACT 1 — PINNED HERO (cross-fade scenes) ═══ */}
      <section className="cine-hero" data-theme="dark">
        <div className="cine-hero__stage">
          {/* scene 0 */}
          <div className="cine-scene" data-scene="0">
            <div className="cine-scene__media">
              <div className="cine-scene__img" style={{ backgroundImage: `url(${IMG.s0})` }} />
              <video
                ref={heroVideoRef}
                className="cine-scene__video"
                src={VIDEO.heroLoop}
                poster={VIDEO.heroPoster}
                autoPlay muted loop playsInline preload="auto"
                aria-hidden="true"
              />
            </div>
            <div className="cine-cap" data-cap="0">
              <div className="cine-cap__inner">
                <div className="cine-eyebrow" data-reveal><i />{L.eyebrow}</div>
                <h1 className="cine-h1">
                  {L.h1.map((ln, i) => <Line key={i} text={ln} />)}
                </h1>
                <p className="cine-sub" data-reveal>{L.sub}</p>
                <div className="cine-hero__cta" data-reveal>
                  <Link to="/calculator" className="cbtn cbtn--leaf cbtn--hero-main" data-cursor>{L.ctaCalc}</Link>
                </div>
              </div>
            </div>
          </div>

          {/* scene 1 */}
          <div className="cine-scene" data-scene="1">
            <div className="cine-scene__media"><div className="cine-scene__img" style={{ backgroundImage: `url(${hero?.scene2_image || IMG.s1})` }} /></div>
            <div className="cine-cap" data-cap="1">
              <div className="cine-cap__inner">
                <h2 className="cine-statement"><Words text={L.scene1H} /></h2>
                <p className="cine-scene__label" data-reveal>{L.scene1Label}</p>
              </div>
            </div>
          </div>

          {/* scene 2 */}
          <div className="cine-scene" data-scene="2">
            <div className="cine-scene__media"><div className="cine-scene__img" style={{ backgroundImage: `url(${hero?.scene3_image || IMG.s2})` }} /></div>
            <div className="cine-cap" data-cap="2">
              <div className="cine-cap__inner">
                <h2 className="cine-statement"><Words text={L.scene2H} /></h2>
                <p className="cine-scene__label" data-reveal>{L.scene2Label}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="cine-rail">
          <div className="cine-rail__track"><div className="cine-rail__fill" /></div>
          <span className="cine-rail__label">{L.railLabel}</span>
        </div>
        <div className="cine-count" aria-hidden="true" data-testid="hero-count">
          <span className="cine-count__cur" ref={heroCountRef} data-idx="1">01</span>
          <span className="cine-count__sep">/</span>
          <span className="cine-count__tot">03</span>
        </div>
        <div className="cine-scrollhint" aria-hidden="true"><span>{L.scrollHint}</span></div>
      </section>

      {/* trust strip */}
      <div className="cine-trust">
        {L.trust.map((t, i, a) => (
          <React.Fragment key={t}><span>{t}</span>{i < a.length - 1 && <i />}</React.Fragment>
        ))}
      </div>

      {/* ═══ CATALOG QUICK-LINKS — managed from CRM Content Center ═══ */}
      {catalog.length > 0 ? (
        <section className="cine-catalog" data-theme="light" data-testid="home-catalog">
          <div className="cine-catalog__head">
            <div className="cine-kicker"><i />{lang === "en" ? "Waste catalog" : "Каталог відходів"}</div>
            <h2 className="cine-catalog__title">
              {lang === "en" ? "What we accept for disposal" : "Що ми приймаємо на утилізацію"}
            </h2>
            <p className="cine-catalog__lead">
              {lang === "en"
                ? "Pick a category to see codes, hazard class and pricing."
                : "Оберіть категорію — коди, клас небезпеки та ціни."}
            </p>
          </div>
          <div className="cine-catalog__grid">
            {catalog.slice(0, 8).map((c) => {
              const Icon = iconByName(c.icon);
              const cover = mediaUrl(c.image_url);
              return (
                <Link
                  key={c.key}
                  to={`/waste/category/${c.key}`}
                  className="cine-cat"
                  data-testid={`home-catalog-${c.key}`}
                  data-cursor
                >
                  <span className="cine-cat__ico">
                    {cover ? <img src={cover} alt="" /> : <Icon />}
                  </span>
                  <span className="cine-cat__body">
                    <span className="cine-cat__name">{categoryLabel(c, lang)}</span>
                    <span className="cine-cat__count">{c.count} {codesWord(c.count, lang)}</span>
                  </span>
                </Link>
              );
            })}
          </div>
          <div className="cine-catalog__more">
            <Link to="/waste" className="cbtn cbtn--ghost" data-cursor>
              {lang === "en" ? "View full catalog" : "Переглянути весь каталог"}
            </Link>
          </div>
        </section>
      ) : null}

      {/* ═══ ACT 2 — CLASSIFICATION (editorial data-table) ═══ */}
      <section className="cine-act cine-class" data-theme="light">
        <div className="cine-act__head">
          <div className="cine-kicker" data-reveal><i />{L.act1Kicker}</div>
          <h2 className="cine-h2 reveal-words">
            {L.act1H.map((ln, i) => <Line key={i} text={ln} />)}
          </h2>
          <p className="cine-lead" data-reveal>{L.act1Lead}</p>
        </div>
        <div className="codes" data-reveal-group>
          <div className="codes__head"><span>{L.codesHead[0]}</span><span>{L.codesHead[1]}</span><span>{L.codesHead[2]}</span><span>{L.codesHead[3]}</span></div>
          {L.codes.map((c) => (
            <div className="codes__row" key={c.code}>
              <span className="codes__code">{c.code}</span>
              <span className="codes__type">{c.type}</span>
              <span className="codes__cls">{c.cls}</span>
              <span className="codes__status"><i />{L.accepted}</span>
            </div>
          ))}
        </div>
        <Link to="/waste" className="cine-link" data-cursor>{L.fullCatalog}</Link>
      </section>

      {/* ═══ ACT 3 — OPERATIONS (dark band + photo planes) ═══ */}
      <section className="cine-act cine-ops" data-theme="dark">
        <div className="cine-ops__bg"><div className="cine-ops__bg-img" data-parallax="0.18" style={{ backgroundImage: `url(${IMG.opsBg})` }} /></div>
        <div className="cine-act__head">
          <div className="cine-kicker cine-kicker--light" data-reveal><i />{L.act2Kicker}</div>
          <h2 className="cine-h2 cine-h2--light reveal-words">
            {L.act2H.map((ln, i) => <Line key={i} text={ln} />)}
          </h2>
        </div>
        <div className="ops-steps" data-reveal-group>
          {L.ops.map((s) => (
            <div className="ops-step" key={s.n}>
              <div className="ops-step__media"><div className="ops-step__img" data-parallax="0.12" style={{ backgroundImage: `url(${s.img})` }} /></div>
              <div className="ops-step__n">{s.n}</div>
              <h3 className="ops-step__t">{s.t}</h3>
              <p className="ops-step__d">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ ACT 3.5 — PRODUCTION GALLERY (real facility photos) ═══ */}
      <section className="cine-act cine-gallery" data-theme="light" data-testid="home-gallery">
        <div className="cine-act__head">
          <div className="cine-kicker" data-reveal><i />{L.galleryKicker}</div>
          <h2 className="cine-h2 reveal-words">
            {L.galleryH.map((ln, i) => <Line key={i} text={ln} />)}
          </h2>
          <p className="cine-lead" data-reveal>{L.galleryLead}</p>
        </div>
        <div className="gallery-grid" data-reveal-group>
          {GALLERY.map((g, i) => {
            const meta = (L.gallery && L.gallery[g.key]) || {};
            return (
              <figure className={`gallery-cell gallery-cell--${i}`} key={g.key} data-cursor>
                <div className="gallery-cell__img" style={{ backgroundImage: `url(${g.img})` }} />
                <figcaption className="gallery-cell__cap">
                  <span className="gallery-cell__t">{meta.t}</span>
                  <span className="gallery-cell__d">{meta.d}</span>
                </figcaption>
              </figure>
            );
          })}
        </div>
      </section>

      {/* ═══ ACT 4 — PRINCIPLES (interactive vertical accordion — distinct from the licenses horizontal scroll) ═══ */}
      <section className="cine-act cine-rules" data-theme="light" data-testid="home-rules">
        <div className="rules-wrap">
          {/* header on top (not a side column) */}
          <div className="rules-head">
            <div className="cine-kicker" data-reveal><i />{L.rulesKicker}</div>
            <h2 className="rules-head__h reveal-words"><Words text={L.rulesH} /></h2>
            <p className="rules-head__lead" data-reveal>{L.rulesLead}</p>
          </div>

          {/* vertical expanding accordion */}
          <div className="rules-acc" data-reveal-group>
            {L.rules.map((r, i) => (
              <div
                className={`rule-item${i === ruleIdx ? " is-open" : ""}`}
                key={r.no}
                data-testid={`rule-slide-${i}`}
                role="button"
                tabIndex={0}
                aria-expanded={i === ruleIdx}
                onClick={() => setRuleIdx((cur) => (cur === i ? -1 : i))}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setRuleIdx((cur) => (cur === i ? -1 : i));
                  }
                }}
              >
                <span className="rule-item__no">{r.no}</span>
                <span className="rule-item__icon" aria-hidden><RuleIcon no={r.no} /></span>
                <div className="rule-item__body">
                  <h3 className="rule-item__title">{r.t}</h3>
                  <div className="rule-item__panel">
                    <p className="rule-item__desc">{r.d}</p>
                    <Link to="/waste" className="rule-item__link" data-cursor>
                      {L.rulesCta}<span aria-hidden>→</span>
                    </Link>
                  </div>
                </div>
                <span className="rule-item__chev" aria-hidden />
              </div>
            ))}
          </div>

          {/* footer stat */}
          <div className="rules-foot">
            <span className="rules-foot__badge" aria-hidden>{L.rules.length}</span>
            <div className="rules-foot__txt">
              <strong>{L.rulesStat1}</strong>
              <span>{L.rulesStat2}</span>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ ACT 5 — LICENSES (pinned horizontal scroll · big BG text + async cards) ═══ */}
      <section className="cine-act cine-licenses" data-theme="light" data-testid="home-licenses" ref={licensesRef}>
        <div className="licenses-pin">
          {/* Background "LICENSES" word – huge, colour drifts on scroll */}
          <div className="licenses-bg" aria-hidden="true">
            <span className="licenses-bg__word" ref={licensesBgRef}>{L.licensesBg}</span>
          </div>

          {/* Optional intro strip that hovers above the scroll track */}
          <div className="licenses-head">
            <div className="cine-kicker" data-reveal><i />{L.act4Kicker}</div>
            <h2 className="licenses-head__h reveal-words">
              {L.act4H.map((ln, i) => <Line key={i} text={ln} />)}
            </h2>
            <p className="licenses-head__lead" data-reveal>{licLead}</p>
          </div>

          {/* Foreground horizontal track */}
          <div className="licenses-track" ref={licensesTrackRef}>
            {(licenseCards || []).map((lic, i) => {
              const Card = (
                <>
                  <div className="license-card__num">{lic.no}</div>
                  <div className="license-card__frame">
                    <img
                      className="license-card__img"
                      src={lic.img}
                      alt={lic.t}
                      loading="lazy"
                      draggable="false"
                    />
                    {lic.file ? (
                      <span className="license-card__view" aria-hidden="true">
                        {licLang === "en" ? "View document" : "Переглянути документ"}
                      </span>
                    ) : null}
                  </div>
                  <figcaption className="license-card__cap">
                    <span className="license-card__t">{lic.t}</span>
                    <span className="license-card__d">{lic.d}</span>
                    {(lic.number || lic.issuer || lic.issued || lic.validUntil) ? (
                      <span className="license-card__meta">
                        {lic.number ? <b>{lic.number}</b> : null}
                        {lic.issuer ? <span>{lic.issuer}</span> : null}
                        {lic.issued ? (
                          <span>
                            {(licLang === "en" ? "Issued: " : "Видано: ") + lic.issued}
                            {lic.validUntil ? (licLang === "en" ? ` · valid until ${lic.validUntil}` : ` · діє до ${lic.validUntil}`) : ""}
                          </span>
                        ) : null}
                      </span>
                    ) : null}
                  </figcaption>
                </>
              );
              return lic.file ? (
                <a
                  key={lic.no || i}
                  href={lic.file}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`license-card license-card--link license-card--o${i % 4}`}
                  data-testid={`license-card-${i}`}
                  style={{ "--i": i }}
                >
                  {Card}
                </a>
              ) : (
                <figure
                  key={lic.no || i}
                  className={`license-card license-card--o${i % 4}`}
                  data-testid={`license-card-${i}`}
                  style={{ "--i": i }}
                >
                  {Card}
                </figure>
              );
            })}
            <span className="licenses-track__spacer" aria-hidden="true" />
          </div>
        </div>
      </section>

      {/* ═══ CLIENT ACCESS / HOW TO START (authorization flow) ═══ */}
      <section className="cine-act cine-access" data-theme="light" data-testid="home-access">
        <div className="cine-act__head">
          <div className="cine-kicker" data-reveal><i />{L.accessKicker}</div>
          <h2 className="cine-h2 reveal-words">
            {L.accessH.map((ln, i) => <Line key={i} text={ln} />)}
          </h2>
          <p className="cine-lead" data-reveal>{L.accessLead}</p>
        </div>
        <div className="access-flow">
          <div className="access-steps" data-reveal-group>
            {L.accessSteps.map((s) => (
              <div className="access-step" key={s.n}>
                <div className="access-step__n">{s.n}</div>
                <div className="access-step__body">
                  <h3 className="access-step__t">{s.t}</h3>
                  <p className="access-step__d">{s.d}</p>
                </div>
              </div>
            ))}
          </div>
          <aside className="access-card" data-reveal>
            <div className="access-card__media" style={{ backgroundImage: `url(${IMG.s2})` }} />
            <div className="access-card__body">
              <div className="access-card__badge"><i />ECO.NOVA · B2B</div>
              <div className="access-card__btns">
                <Link to="/client/login" className="cbtn cbtn--leaf" data-cursor>{L.accessCtaClient}</Link>
                <Link to="/contacts" className="cbtn cbtn--ghost" data-cursor>{L.accessCtaRequest}</Link>
              </div>
              <p className="access-card__note">{L.accessNote}</p>
            </div>
          </aside>
        </div>
      </section>

      {/* ═══ FRIENDS — admin-managed logos, STATIC (non-scrolling) grid ═══ */}
      {showPartners && (
        <section className="cine-act cine-friends" data-theme="light" data-testid="home-partners">
          <div className="cine-act__head">
            <div className="cine-kicker"><i />{pKicker}</div>
            <h2 className="cine-h2">{pTitle}</h2>
            {pSub && <p className="cine-lead">{pSub}</p>}
          </div>

          <div className="friends-marquee friends-static" data-testid="friends-marquee">
            <div className="friends-track">
              {partnerItems.map((p, i) => {
                const name = (isUk ? p.name_uk : p.name_en) || p.name_en || p.name_uk || "";
                const logo = p.logo_url
                  ? (/^https?:\/\//i.test(p.logo_url) ? p.logo_url : `${API_URL}${p.logo_url}`)
                  : "";
                const hasLink = p.link && /^https?:\/\//i.test(p.link);
                const inner = logo
                  ? <img className="friend__logo" src={logo} alt={name || "partner"} loading="lazy" />
                  : <span className="friend__word">{name}</span>;
                return hasLink ? (
                  <a
                    key={p.id || i}
                    href={p.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="friend"
                    data-cursor
                    data-testid={`partner-card-${i}`}
                  >
                    {inner}
                  </a>
                ) : (
                  <span
                    key={p.id || i}
                    className="friend"
                    data-testid={`partner-card-${i}`}
                  >
                    {inner}
                  </span>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ═══ REVIEWS — admin-managed testimonials marquee ═══ */}
      {showReviews && (
        <section className="cine-act cine-reviews" data-theme="light" data-testid="home-reviews">
          <div className="cine-act__head">
            <div className="cine-kicker"><i />{rKicker}</div>
            <h2 className="cine-h2">{rTitle}</h2>
            {rSub && <p className="cine-lead">{rSub}</p>}
          </div>

          <div className="reviews-marquee" data-testid="reviews-marquee">
            <div className="reviews-track">
              {[...reviewItems, ...reviewItems].map((rv, i) => {
                const orig = i < reviewItems.length;
                const name = (isUk ? rv.name_uk : rv.name) || rv.name || rv.name_uk || "";
                const role = (isUk ? rv.role_uk : rv.role_en) || rv.role_en || rv.role_uk || "";
                const text = (isUk ? rv.text_uk : rv.text_en) || rv.text_en || rv.text_uk || "";
                const avatar = rv.image_url
                  ? (/^https?:\/\//i.test(rv.image_url) ? rv.image_url : `${API_URL}${rv.image_url}`)
                  : "";
                const rating = Math.max(0, Math.min(5, Number(rv.rating) || 0));
                const filled = Math.round(rating);
                const initials = (name || "?").trim().charAt(0).toUpperCase();
                return (
                  <article
                    key={`${rv.id || i}-${orig ? "a" : "b"}`}
                    className="rev-card"
                    data-testid={orig ? `review-card-${i}` : undefined}
                    aria-hidden={orig ? undefined : "true"}
                  >
                    <div className="rev-card__top">
                      <span className="rev__dots" aria-hidden="true">
                        {[0, 1, 2, 3, 4].map((n) => (
                          <i key={n} className={n < filled ? "on" : ""} />
                        ))}
                      </span>
                      <span className="rev__score">{rating.toFixed(1)}<em> / 5</em></span>
                    </div>
                    <p className="rev-card__text">{text}</p>
                    <div className="rev-card__who">
                      {avatar ? (
                        <img className="rev-card__ava" src={avatar} alt={name} loading="lazy" />
                      ) : (
                        <span className="rev-card__ava rev-card__ava--i" aria-hidden="true">{initials}</span>
                      )}
                      <span className="rev-card__meta">
                        <span className="rev-card__name">{name}</span>
                        {role && <span className="rev-card__role">{role}</span>}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>
      )}


      {/* ═══ ACT 6 — CTA ═══ */}
      <section className="cine-act cine-cta" data-theme="dark">
        <div className="cine-cta__bg"><div className="cine-cta__bg-img" data-parallax="0.16" style={{ backgroundImage: `url(${IMG.cta})` }} /></div>
        <div className="cine-cta__inner">
          <div className="cine-kicker cine-kicker--light" data-reveal><i />{L.ctaKicker}</div>
          <h2 className="cine-cta__title reveal-words">
            {L.ctaH.map((ln, i) => <Line key={i} text={ln} />)}
          </h2>
          <p className="cine-cta__sub" data-reveal>{L.ctaSub}</p>
          <div className="cine-cta__btns" data-reveal>
            <Link to="/calculator" className="cbtn cbtn--leaf" data-cursor>{L.ctaCalc}</Link>
            <Link to="/contacts" className="cbtn cbtn--dark-ghost" data-cursor>{L.ctaRequest}</Link>
            <Link to="/waste" className="cbtn cbtn--dark-ghost" data-cursor>{L.ctaCatalog}</Link>
          </div>
        </div>
      </section>
    </div>
  );
}