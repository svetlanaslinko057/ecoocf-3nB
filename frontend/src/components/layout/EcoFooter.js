import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Phone, Mail, MapPin, Clock, ArrowUpRight, ArrowRight,
  Linkedin, Facebook, Instagram, Send, Youtube, Twitter, Globe,
  Loader2, Check,
} from "lucide-react";
import { FooterAPI } from "@/lib/api";
import { useLang } from "@/i18n";
import { usePublicContacts } from "@/lib/usePublicContacts";

/* ── Ukrainian fallback (also the base merged with admin-managed config) ── */
const UK_FALLBACK = {
  brand: {
    name: "ECO", accentChar: ".",
    tagline:
      "Ліцензований оператор поводження з небезпечними відходами. Прозора B2B-система утилізації по всій Україні.",
    wordmark: "ECO", showWordmark: true,
  },
  cta: {
    enabled: true,
    primaryLabel: "Розрахувати вартість", primaryHref: "/calculator",
    secondaryLabel: "Створити заявку", secondaryHref: "/contacts",
  },
  columns: [
    { title: "Сайт", links: [
      { label: "Головна", href: "/" },
      { label: "Каталог відходів", href: "/waste" },
      { label: "Калькулятор", href: "/calculator" },
      { label: "Блог", href: "/blog" },
      { label: "Контакти", href: "/contacts" },
    ] },
    { title: "Знання", links: [
      { label: "Блог · усі статті", href: "/blog" },
      { label: "Новини галузі", href: "/blog?category=news" },
      { label: "Регулювання та закони", href: "/blog?category=regulation" },
      { label: "Гайди та інструкції", href: "/blog?category=guides" },
      { label: "Кейси з практики", href: "/blog?category=cases" },
    ] },
  ],
  contacts: {
    title: "Контакти",
    phone: "+380 66 788 04 45", phoneHref: "tel:+380667880445",
    phone2: "", phone2Href: "",
    email: "Econova2013@ukr.net", email2: "",
    address: "Україна, Житомирська обл., Звягельський р-н, м. Баранівка, вул. Івана Франка, 104А",
    hours: "Пн–Пт, 9:00–18:00",
    clientLoginLabel: "Вхід для клієнтів", clientLoginHref: "/client/login",
  },
  company: { legalName: "ЕКО-НОВА", edrpou: "", registration: "" },
  newsletter: {
    enabled: true, title: "Розсилка",
    description: "Новини законодавства та поради з поводження з відходами — раз на місяць.",
    placeholder: "Ваш email", buttonLabel: "Підписатися",
    successText: "Дякуємо! Ви підписані на розсилку.",
  },
  socials: [],
  badges: ["Ліцензія Мінекології", "Акти 1–4 клас", "ADR-транспорт"],
  bottomLinks: [
    { label: "Умови використання", href: "/terms" },
    { label: "Політика конфіденційності", href: "/privacy" },
    { label: "Політика Cookies", href: "/cookies" },
  ],
  copyright: "ECO.NOVA — ліцензована утилізація небезпечних відходів 1–4 класів за кодами нацкласифікатора. Усі права захищені",
};

/* ── English fallback ──────────────────────────────────────────────────── */
const EN_FALLBACK = {
  brand: {
    name: "ECO", accentChar: ".",
    tagline:
      "Licensed hazardous-waste management operator. A transparent B2B recycling system across Ukraine.",
    wordmark: "ECO", showWordmark: true,
  },
  cta: {
    enabled: true,
    primaryLabel: "Calculate the cost", primaryHref: "/calculator",
    secondaryLabel: "Create a request", secondaryHref: "/contacts",
  },
  columns: [
    { title: "Site", links: [
      { label: "Home", href: "/" },
      { label: "Waste catalog", href: "/waste" },
      { label: "Calculator", href: "/calculator" },
      { label: "Blog", href: "/blog" },
      { label: "Contacts", href: "/contacts" },
    ] },
    { title: "Knowledge", links: [
      { label: "Blog · all articles", href: "/blog" },
      { label: "Industry news", href: "/blog?category=news" },
      { label: "Regulations & laws", href: "/blog?category=regulation" },
      { label: "Guides & instructions", href: "/blog?category=guides" },
      { label: "Case studies", href: "/blog?category=cases" },
    ] },
  ],
  contacts: {
    title: "Contacts",
    phone: "+380 66 788 04 45", phoneHref: "tel:+380667880445",
    phone2: "", phone2Href: "",
    email: "Econova2013@ukr.net", email2: "",
    address: "104A Ivana Franka St., Baranivka, Zviahel district, Zhytomyr region, Ukraine",
    hours: "Mon–Fri, 9:00–18:00",
    clientLoginLabel: "Client sign-in", clientLoginHref: "/client/login",
  },
  company: { legalName: "ECO-NOVA", edrpou: "", registration: "" },
  newsletter: {
    enabled: true, title: "Newsletter",
    description: "Legislation news and waste-handling tips — once a month.",
    placeholder: "Your email", buttonLabel: "Subscribe",
    successText: "Thank you! You are subscribed.",
  },
  socials: [],
  badges: ["Ministry of Ecology licence", "Class 1–4 acts", "ADR transport"],
  bottomLinks: [
    { label: "Terms of Use", href: "/terms" },
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Cookies Policy", href: "/cookies" },
  ],
  copyright: "ECO.NOVA — licensed utilization of class 1–4 hazardous waste under national classifier codes. All rights reserved",
};

const MSG = {
  uk: {
    badEmail: "Вкажіть коректний email",
    thanks: "Дякуємо! Ви підписані.",
    failed: "Не вдалося підписатися. Спробуйте пізніше.",
    emailAria: "Email для розсилки",
    edrpou: "ЄДРПОУ",
  },
  en: {
    badEmail: "Enter a valid email",
    thanks: "Thank you! You are subscribed.",
    failed: "Subscription failed. Please try again later.",
    emailAria: "Newsletter email",
    edrpou: "Reg. No.",
  },
};

const SOCIAL_ICONS = {
  linkedin: Linkedin, facebook: Facebook, instagram: Instagram,
  telegram: Send, youtube: Youtube, twitter: Twitter, x: Twitter,
};

const isExternal = (href = "") => /^https?:\/\//i.test(href) || href.startsWith("mailto:") || href.startsWith("tel:");

function FootLink({ href = "/", children, className, ...rest }) {
  if (isExternal(href)) {
    return (
      <a href={href} className={className} target={href.startsWith("http") ? "_blank" : undefined}
         rel="noreferrer" {...rest}>{children}</a>
    );
  }
  return <Link to={href || "/"} className={className} {...rest}>{children}</Link>;
}

function Newsletter({ cfg, lang }) {
  const m = MSG[lang] || MSG.uk;
  const [email, setEmail] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | done | error
  const [msg, setMsg] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (state === "loading") return;
    const value = email.trim();
    if (!value || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)) {
      setState("error"); setMsg(m.badEmail); return;
    }
    setState("loading"); setMsg("");
    try {
      await FooterAPI.subscribe(value, "footer");
      setState("done"); setEmail("");
      setMsg(cfg.successText || m.thanks);
    } catch (err) {
      setState("error");
      setMsg(err?.response?.data?.detail || m.failed);
    }
  };

  return (
    <form className="ecofoot__news" onSubmit={submit} data-testid="footer-newsletter">
      <div className="ecofoot__news-row">
        <input
          type="email"
          className="ecofoot__news-input"
          placeholder={cfg.placeholder || "email"}
          value={email}
          onChange={(e) => { setEmail(e.target.value); if (state !== "idle") setState("idle"); }}
          aria-label={m.emailAria}
          data-testid="footer-newsletter-input"
        />
        <button
          type="submit"
          className="ecofoot__news-btn"
          disabled={state === "loading"}
          aria-label={cfg.buttonLabel || "Subscribe"}
          data-testid="footer-newsletter-submit"
        >
          {state === "loading" ? <Loader2 className="ecofoot__spin" size={18} />
            : state === "done" ? <Check size={18} />
            : <Send size={18} />}
        </button>
      </div>
      {msg && (
        <p className={`ecofoot__news-msg ${state === "error" ? "is-error" : "is-ok"}`} data-testid="footer-newsletter-msg">
          {msg}
        </p>
      )}
    </form>
  );
}

export default function EcoFooter() {
  const { lang } = useLang();
  const { contacts: pubContacts } = usePublicContacts();
  const base = lang === "en" ? EN_FALLBACK : UK_FALLBACK;
  const [cfg, setCfg] = useState(base);

  const load = useCallback(async () => {
    // Admin-managed footer config is Ukrainian; only merge it for the UK locale
    // so the English version stays fully translated.
    if (lang === "en") { setCfg(EN_FALLBACK); return; }
    setCfg(UK_FALLBACK);
    try {
      const res = await FooterAPI.getPublic();
      if (res?.footer) setCfg((prev) => ({ ...prev, ...res.footer }));
    } catch { /* keep fallback */ }
  }, [lang]);

  useEffect(() => { load(); }, [load]);

  const m = MSG[lang] || MSG.uk;
  const brand = cfg.brand || base.brand;
  const cta = cfg.cta || base.cta;
  const _baseContacts = cfg.contacts || base.contacts;
  const _phones = (pubContacts.phones || []);
  const _emails = (pubContacts.emails || []);
  const _tel = (v) => `tel:${(v || "").replace(/[^\d+]/g, "")}`;
  const contacts = {
    ..._baseContacts,
    phone: _phones[0]?.value || _baseContacts.phone,
    phoneHref: _phones[0]?.value ? _tel(_phones[0].value) : _baseContacts.phoneHref,
    phone2: _phones[1]?.value || "",
    phone2Href: _phones[1]?.value ? _tel(_phones[1].value) : "",
    email: _emails[0]?.value || _baseContacts.email,
    email2: _emails[1]?.value || _baseContacts.email2 || "",
    address: pubContacts.address || _baseContacts.address,
    hours: pubContacts.working_hours || _baseContacts.hours,
  };
  const newsletter = cfg.newsletter || base.newsletter;
  const socials = (cfg.socials || []).filter((s) => s && s.href);
  const badges = cfg.badges || [];
  const bottomLinks = cfg.bottomLinks || [];
  const columns = cfg.columns || [];
  const year = new Date().getFullYear();

  return (
    <footer className="ecofoot" data-testid="public-footer">
      <div className="ecofoot__inner">
        {/* ── Top: brand + grid ─────────────────────────────────────── */}
        <div className="ecofoot__top">
          <div className="ecofoot__brandcol">
            <div className="ecofoot__brand" data-testid="footer-brand">
              {brand.name}<i>{brand.accentChar}</i><b className="ecofoot__nova">NOVA</b>
            </div>
            <p className="ecofoot__tag">{brand.tagline}</p>
            {cta.enabled && (
              <div className="ecofoot__cta">
                {cta.primaryLabel && (
                  <FootLink href={cta.primaryHref} className="ecofoot__btn ecofoot__btn--primary" data-testid="footer-cta-primary">
                    {cta.primaryLabel} <ArrowRight size={16} />
                  </FootLink>
                )}
                {cta.secondaryLabel && (
                  <FootLink href={cta.secondaryHref} className="ecofoot__btn ecofoot__btn--ghost" data-testid="footer-cta-secondary">
                    {cta.secondaryLabel}
                  </FootLink>
                )}
              </div>
            )}

            {socials.length > 0 && (
              <div className="ecofoot__socials" data-testid="footer-socials">
                {socials.map((s, i) => {
                  const Icon = SOCIAL_ICONS[(s.network || "").toLowerCase()] || Globe;
                  return (
                    <a key={`${s.network}-${i}`} href={s.href} target="_blank" rel="noreferrer"
                       className="ecofoot__social" aria-label={s.label || s.network} title={s.label || s.network}>
                      <Icon size={18} />
                    </a>
                  );
                })}
              </div>
            )}
          </div>

          <div className="ecofoot__grid">
            {columns.map((c, ci) => (
              <div className="ecofoot__col" key={`${c.title}-${ci}`}>
                <h4>{c.title}</h4>
                <ul>
                  {(c.links || []).map((l, i) => (
                    <li key={`${l.label}-${i}`}>
                      <FootLink href={l.href}>{l.label}</FootLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}

            {/* Contacts column */}
            <div className="ecofoot__col ecofoot__col--contacts">
              <h4>{contacts.title || base.contacts.title}</h4>
              <ul className="ecofoot__contacts">
                {contacts.phone && (
                  <li><Phone size={15} /><a href={contacts.phoneHref || `tel:${contacts.phone}`}>{contacts.phone}</a></li>
                )}
                {contacts.phone2 && (
                  <li><Phone size={15} /><a href={contacts.phone2Href || `tel:${contacts.phone2}`}>{contacts.phone2}</a></li>
                )}
                {contacts.email && (
                  <li><Mail size={15} /><a href={`mailto:${contacts.email}`}>{contacts.email}</a></li>
                )}
                {contacts.email2 && (
                  <li><Mail size={15} /><a href={`mailto:${contacts.email2}`}>{contacts.email2}</a></li>
                )}
                {contacts.address && (
                  <li><MapPin size={15} /><span>{contacts.address}</span></li>
                )}
                {contacts.hours && (
                  <li><Clock size={15} /><span>{contacts.hours}</span></li>
                )}
              </ul>
              {contacts.clientLoginLabel && (
                <FootLink href={contacts.clientLoginHref || "/client/login"} className="ecofoot__clientlink" data-testid="footer-client-login">
                  {contacts.clientLoginLabel} <ArrowUpRight size={14} />
                </FootLink>
              )}
            </div>

            {/* Newsletter column */}
            {newsletter.enabled && (
              <div className="ecofoot__col ecofoot__col--news">
                <h4>{newsletter.title || base.newsletter.title}</h4>
                {newsletter.description && <p className="ecofoot__news-desc">{newsletter.description}</p>}
                <Newsletter cfg={newsletter} lang={lang} />
              </div>
            )}
          </div>
        </div>

        {/* ── Giant wordmark ────────────────────────────────────────── */}
        {brand.showWordmark && brand.wordmark && (
          <div className="ecofoot__wordmark" aria-hidden="true" data-testid="footer-wordmark">
            {brand.wordmark}<span>{brand.accentChar}</span>NOVA
          </div>
        )}

        {/* ── Bottom bar ────────────────────────────────────────────── */}
        <div className="ecofoot__bottom">
          <span className="ecofoot__copy">
            © {year} {cfg.copyright || base.copyright}
            {cfg.company?.legalName ? ` · ${cfg.company.legalName}` : ""}
            {cfg.company?.edrpou ? ` · ${m.edrpou} ${cfg.company.edrpou}` : ""}
          </span>

          {badges.length > 0 && (
            <div className="ecofoot__badges">
              {badges.map((b, i) => (
                <React.Fragment key={`${b}-${i}`}>
                  {i > 0 && <i />}
                  <span>{b}</span>
                </React.Fragment>
              ))}
            </div>
          )}

          {bottomLinks.length > 0 && (
            <div className="ecofoot__bottomlinks">
              {bottomLinks.map((l, i) => (
                <FootLink key={`${l.label}-${i}`} href={l.href}>{l.label}</FootLink>
              ))}
            </div>
          )}

          <a
            href="https://eva-x.cx"
            target="_blank"
            rel="noopener noreferrer"
            className="ecofoot__madeby"
            data-testid="footer-made-by"
          >
            {lang === "en" ? "Website made by" : "Вебсайт розроблено"} <b>EVA-X</b>
          </a>
        </div>
      </div>
    </footer>
  );
}
