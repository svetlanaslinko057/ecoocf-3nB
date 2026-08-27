import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Phone, EnvelopeSimple, MapPin, Clock, ArrowUpRight,
  CopySimple, CheckCircle, Plus,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { useSeo } from "@/lib/seo";
import { useInquiry } from "@/context/InquiryContext";
import { useLang } from "@/i18n";
import { usePublicContacts } from "@/lib/usePublicContacts";
import "./eco-contacts.css";

/* ───────────────────────────────────────────────────────────────────────── */

const T = {
  uk: {
    seoTitle: "Контакти",
    seoDesc: "Зв’яжіться з ECO.NOVA — відділи, локації, робочий графік та прямі канали для оперативної комунікації.",
    channels: [
      { label: "Телефон",  value: "+380 66 788 04 45", sub: "Пн–Пт · 9:00–18:00", href: "tel:+380667880445", copy: "+380667880445" },
      { label: "Email",    value: "Econova2013@ukr.net", sub: "Відповідь у робочий час — до 30 хвилин",  href: "mailto:Econova2013@ukr.net",  copy: "Econova2013@ukr.net" },
    ],
    locations: [
      { eye: "Офіс", name: "Баранівка · Місце провадження діяльності", addr: "вул. Івана Франка, 104А, м. Баранівка, Звягельський р-н, Житомирська обл.", hours: "Пн–Пт · 9:00–18:00", phone: "+380 66 788 04 45" },
    ],
    faq: [
      { q: "Як швидко ви відповідаєте на звернення?", a: "У робочий час — до 30 хвилин. Повний прорахунок із документацією — впродовж 24 годин після збору вихідних даних." },
      { q: "Чи працюєте по всій Україні?", a: "Так, власний автопарк + партнерська мережа покривають усі області материкової частини України. Плечеві регіони — за окремими узгодженнями." },
      { q: "Чи потрібно готувати документи самому?", a: "Ні — ми самі оформлюємо пакет: акти приймання-передавання, транспортні накладні, супровідні документи та єдину звітність в Міндовкілля." },
      { q: "Мінімальний обсяг партії?", a: "Для разового вивезення від 200 кг. Для постійних клієнтів — без обмежень, за графіком накопичення." },
      { q: "Приймаєте радіоактивні відходи?", a: "Ні. Радіоактивні відходи (категорія D) — єдина група, з якою ми не працюємо. Свій бриф рекомендуємо передавати ДП «Радон»." },
    ],
    crumbHome: "Головна", crumbContacts: "Контакти", title: "Контакти",
    leadPre: "Напишіть на одну з адрес безпосереднього відділу або залиште заявку — менеджер відповість",
    leadStrong: " впродовж 30 хвилин", leadPost: " у робочий час, з повним прорахунком та пакетом документів — впродовж 24 годин.",
    liveOn: "Менеджер на лінії · Київ", liveOff: "Поза графіком · Київ",
    directChannels: "Прямі канали",
    copied: "Скопійовано", copy: "Копіювати", copyToast: "Скопійовано",
    quickRequest: "Швидка заявка", panelH: "Отримайте прорахунок за 24 години",
    panelP: "Надішліть опис відходу, обсяг та локацію. Ми підберемо код, порахуємо вартість і відправимо договір на електронний підпис.",
    leaveRequest: "Залишити заявку",
    panelList: ["Безкоштовна консультація", "Рекомендований код відходу", "Договір із вказаною ціною — без прихованих платежів"],
    locationsH: "Наші локації", faqH: "Часті питання",
    marquee: ["Ліцензія", "ADR-транспорт", "24/7"],
    ctaH: "Готові почати?",
    ctaP: "Спочатку — безкоштовний прорахунок вартості утилізації за вашими даними. Без реєстрації та без зобов’язань — просто щоб ви розуміли бюджет.",
    ctaCalc: "Розрахувати", ctaCreate: "Створити заявку", locale: "uk-UA",
  },
  en: {
    seoTitle: "Contacts",
    seoDesc: "Get in touch with ECO.NOVA — departments, locations, working hours and direct channels for fast communication.",
    channels: [
      { label: "Phone",      value: "+380 66 788 04 45", sub: "Mon–Fri · 9:00–18:00",          href: "tel:+380667880445", copy: "+380667880445" },
      { label: "Email",      value: "Econova2013@ukr.net", sub: "Reply within working hours — up to 30 min", href: "mailto:Econova2013@ukr.net",  copy: "Econova2013@ukr.net" },
    ],
    locations: [
      { eye: "Office", name: "Baranivka · Place of business", addr: "104A Ivana Franka St., Baranivka, Zviahel district, Zhytomyr region", hours: "Mon–Fri · 9:00–18:00", phone: "+380 66 788 04 45" },
    ],
    faq: [
      { q: "How fast do you respond to inquiries?", a: "Within working hours — up to 30 minutes. A full estimate with documentation — within 24 hours after the input data is gathered." },
      { q: "Do you operate across all of Ukraine?", a: "Yes, our own fleet + partner network cover all regions of mainland Ukraine. Remote regions — by separate arrangement." },
      { q: "Do I need to prepare the documents myself?", a: "No — we prepare the package ourselves: acceptance-transfer acts, transport waybills, accompanying documents and unified reporting to the Ministry of Ecology." },
      { q: "Minimum batch volume?", a: "From 200 kg for a one-off collection. For regular clients — no limits, on an accumulation schedule." },
      { q: "Do you accept radioactive waste?", a: "No. Radioactive waste (category D) is the only group we don't handle. We recommend referring it to the state enterprise “Radon”." },
    ],
    crumbHome: "Home", crumbContacts: "Contacts", title: "Contacts",
    leadPre: "Write to a specific department's address or leave a request — a manager will reply",
    leadStrong: " within 30 minutes", leadPost: " during working hours, with a full estimate and document package — within 24 hours.",
    liveOn: "Manager online · Kyiv", liveOff: "Off hours · Kyiv",
    directChannels: "Direct channels",
    copied: "Copied", copy: "Copy", copyToast: "Copied",
    quickRequest: "Quick request", panelH: "Get an estimate within 24 hours",
    panelP: "Send a waste description, volume and location. We'll pick the code, calculate the cost and send the contract for e-signature.",
    leaveRequest: "Leave a request",
    panelList: ["Free consultation", "Recommended waste code", "Contract with a fixed price — no hidden fees"],
    locationsH: "Our locations", faqH: "Frequently asked",
    marquee: ["Licensed", "ADR transport", "24/7"],
    ctaH: "Ready to start?",
    ctaP: "First — a free disposal cost estimate based on your data. No registration and no obligations — just so you understand the budget.",
    ctaCalc: "Calculate", ctaCreate: "Create a request", locale: "en-US",
  },
};

function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const root = ref.current;
    if (!root || typeof IntersectionObserver === "undefined") return undefined;
    const items = root.querySelectorAll(".ec-reveal, .ec__h");
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.18, rootMargin: "0px 0px -8% 0px" });
    items.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}

function LiveStatus({ L }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);
  const kyiv = useMemo(() => {
    try {
      const dt = new Intl.DateTimeFormat(L.locale, { timeZone: "Europe/Kyiv", hour: "2-digit", minute: "2-digit", hour12: false }).format(now);
      const hourStr = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Kyiv", hour: "2-digit", hour12: false }).format(now);
      const h = parseInt(hourStr, 10);
      const weekday = now.toLocaleDateString("en-GB", { timeZone: "Europe/Kyiv", weekday: "short" }).toLowerCase();
      const isWeekend = weekday === "sat" || weekday === "sun";
      const open = !isWeekend && h >= 9 && h < 18;
      return { dt, open };
    } catch { return { dt: "—", open: true }; }
  }, [now, L.locale]);
  return (
    <div className={`ec__status ${kyiv.open ? "" : "is-off"}`} data-testid="contacts-live-status">
      <span className="ec__status-dot" />
      <span className="ec__status-label">{kyiv.open ? L.liveOn : L.liveOff}</span>
      <span className="ec__status-time">{kyiv.dt}</span>
    </div>
  );
}

function TitleSpread({ text }) {
  const chars = Array.from(text);
  return (
    <h1 className="ec__h ec-reveal-title">
      {chars.map((ch, i) => (
        <span key={`${ch}-${i}`} className={ch === " " ? "is-space" : ""} style={{ transitionDelay: `${0.06 * i + 0.1}s` }}>
          {ch === " " ? "\u00A0" : ch}
        </span>
      ))}
    </h1>
  );
}

function ChannelRow({ ch, L }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async (e) => {
    e.preventDefault();
    try {
      await navigator.clipboard.writeText(ch.copy);
      setCopied(true);
      toast.success(`${L.copyToast}: ${ch.copy}`);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      window.location.href = ch.href;
    }
  };
  return (
    <a href={ch.href} onClick={onCopy} className={`ec__ch ${copied ? "copied" : ""}`} data-cursor data-testid={`contact-channel-${ch.label.toLowerCase()}`}>
      <div className="ec__ch-label">{ch.label}</div>
      <div>
        <div className="ec__ch-val">{ch.value}</div>
        <div className="ec__ch-sub">{ch.sub}</div>
      </div>
      <div className="ec__ch-cta">
        {copied ? <><CheckCircle weight="fill" size={14}/> {L.copied}</> : <><CopySimple weight="regular" size={14}/> {L.copy} <ArrowUpRight weight="bold" size={12}/></>}
      </div>
    </a>
  );
}

function FaqItem({ q, a, idx, open, setOpen }) {
  const isOpen = open === idx;
  return (
    <li className={`ec__faq-item ${isOpen ? "is-open" : ""}`} data-testid={`faq-item-${idx}`}>
      <button type="button" className="ec__faq-q" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? -1 : idx)}>
        <span>{q}</span>
        <span className="ec__faq-q-ico"><Plus weight="bold" size={14}/></span>
      </button>
      <div className="ec__faq-a" style={{ maxHeight: isOpen ? 500 : 0 }}>
        <div className="ec__faq-a-inner">{a}</div>
      </div>
    </li>
  );
}

export default function Contacts() {
  const { lang } = useLang();
  const { contacts: pub } = usePublicContacts();
  const L = T[lang] || T.uk;
  useSeo(L.seoTitle, L.seoDesc);
  const revealRef = useReveal();
  const inquiry = useInquiry();
  const [openFaq, setOpenFaq] = useState(0);

  // Override the primary phone/email channels with the admin-managed contacts.
  const channels = useMemo(() => {
    const phones = pub.phones || [];
    const emails = pub.emails || [];
    const tel = (v) => `tel:${(v || "").replace(/[^\d+]/g, "")}`;
    let pi = 0, ei = 0;
    return (L.channels || []).map((c) => {
      const isPhone = /tel:/.test(c.href || "");
      const isEmail = /mailto:/.test(c.href || "");
      if (isPhone && phones[pi]) {
        const v = phones[pi++].value;
        return { ...c, value: v, href: tel(v), copy: v.replace(/[^\d+]/g, "") };
      }
      if (isEmail && emails[ei]) {
        const v = emails[ei++].value;
        return { ...c, value: v, href: `mailto:${v}`, copy: v };
      }
      return c;
    });
  }, [L, pub]);

  useEffect(() => {
    const t = window.setTimeout(() => {
      document.querySelectorAll(".ec__h").forEach((h) => h.classList.add("is-in"));
    }, 60);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <main className="ec" ref={revealRef} data-testid="contacts-page">
      {/* 1. Hero */}
      <section className="ec__hero">
        <nav className="ec__crumbs" aria-label="breadcrumb">
          <Link to="/">{L.crumbHome}</Link><i/><strong>{L.crumbContacts}</strong>
        </nav>
        <TitleSpread text={L.title} />
        <div className="ec__leadrow ec-reveal">
          <p className="ec__lead">
            {L.leadPre}<strong>{L.leadStrong}</strong>{L.leadPost}
          </p>
          <LiveStatus L={L} />
        </div>
      </section>

      {/* 2. Channels + Aside CTA */}
      <section className="ec__split">
        <div className="ec__chs ec-reveal">
          <div className="ec__sec-title"><i/>{L.directChannels}</div>
          {channels.map((ch) => <ChannelRow key={ch.label} ch={ch} L={L} />)}
        </div>
        <aside className="ec__aside ec-reveal">
          <div className="ec__panel">
            <div className="ec__panel-eyebrow">{L.quickRequest}</div>
            <h3 className="ec__panel-h">{L.panelH}</h3>
            <p className="ec__panel-p">{L.panelP}</p>
            <button type="button" className="ec__panel-btn" onClick={() => inquiry?.open?.()} data-cursor data-testid="contacts-quick-request">
              <Phone weight="fill" size={14}/> {L.leaveRequest}
            </button>
            <ul className="ec__panel-list">
              {L.panelList.map((li) => <li key={li}>{li}</li>)}
            </ul>
          </div>
        </aside>
      </section>

      {/* 3. Locations (single compact 3-chip row) */}
      <section className="ec__locs">
        <h2 className="ec__locs-h ec-reveal">{L.locationsH}</h2>
        <div className="ec__locs-chips">
          {L.locations.map((l) => (
            <article key={l.name} className="ec__chip ec-reveal" data-testid={`loc-${l.eye.toLowerCase()}`}>
              <span className="ec__chip-pin"><MapPin weight="fill" size={14}/></span>
              <div className="ec__chip-body">
                <div className="ec__chip-eye">{l.eye}</div>
                <div className="ec__chip-name">{l.name}</div>
                <div className="ec__chip-addr">{l.addr}</div>
              </div>
              <div className="ec__chip-meta">
                <span title="Hours"><Clock weight="regular" size={12}/> {l.hours}</span>
                <a href={`tel:${l.phone.replace(/\s+/g, "")}`} title="Phone"><Phone weight="regular" size={12}/> {l.phone}</a>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* 4. FAQ */}
      <section className="ec__faq">
        <div className="ec__faq-grid ec-reveal">
          <h2 className="ec__faq-h">{L.faqH}</h2>
          <ul className="ec__faq-list">
            {L.faq.map((f, i) => <FaqItem key={f.q} q={f.q} a={f.a} idx={i} open={openFaq} setOpen={setOpenFaq} />)}
          </ul>
        </div>
      </section>

      {/* 5. Marquee */}
      <section className="ec__marq" aria-hidden="true">
        <div className="ec__marq-track">
          {Array.from({ length: 3 }).map((_, k) => (
            <span key={k}>
              {L.marquee.map((m, mi) => (
                <React.Fragment key={mi}>{m} <i/> </React.Fragment>
              ))}
            </span>
          ))}
        </div>
      </section>

      {/* 6. Final CTA */}
      <section className="ec__cta">
        <div className="ec__cta-inner ec-reveal">
          <div>
            <h2 className="ec__cta-h">{L.ctaH}</h2>
            <p className="ec__cta-p">{L.ctaP}</p>
          </div>
          <div className="ec__cta-actions">
            <Link to="/calculator" className="ec__btn ec__btn--ghost" data-cursor>{L.ctaCalc} <ArrowUpRight weight="bold" size={14}/></Link>
            <button type="button" className="ec__btn ec__btn--primary" onClick={() => inquiry?.open?.()} data-cursor data-testid="contacts-final-cta">
              {L.ctaCreate} <ArrowUpRight weight="bold" size={14}/>
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
