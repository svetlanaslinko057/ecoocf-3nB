import React, { useCallback, useEffect, useRef, useState } from "react";
import { Phone } from "lucide-react";
import { PublicAPI } from "@/lib/clientApi";
import { useLang } from "@/i18n";
import { validatePhone, validateEmail } from "@/lib/validators";
import PhoneField from "@/components/PhoneField";
import CompanyAutocomplete from "@/components/CompanyAutocomplete";
import "./InquiryModal.css";

const T = {
  uk: {
    titles: { callback: "Замовити дзвінок", inquiry: "Залишити звернення", request: "Заявка на утилізацію" },
    defaultTitle: "Звернення",
    eyebrow: "ECO · Звернення",
    sub: "Залиште контакти — менеджер передзвонить протягом робочого дня та підготує комерційну пропозицію.",
    name: "Ім'я *", phone: "Телефон *", email: "Email", company: "Компанія / заклад", message: "Повідомлення",
    nameReq: "Вкажіть ваше ім'я",
    phoneHint: "Україна або міжнародний формат: +380 67 123 45 67",
    companyPh: "Почніть вводити назву — підкажемо з реєстру",
    errSend: "Не вдалося надіслати. Спробуйте ще раз або зателефонуйте нам.",
    sending: "Надсилання…", send: "Надіслати звернення",
    close: "Закрити", thanks: "Дякуємо!",
    doneSub: "Ваше звернення прийнято. Менеджер зв'яжеться з вами найближчим часом.",
    codePrefix: "Код відходу: ",
    fab: "Замовити дзвінок",
  },
  en: {
    titles: { callback: "Request a call", inquiry: "Leave an inquiry", request: "Disposal request" },
    defaultTitle: "Inquiry",
    eyebrow: "ECO · Inquiry",
    sub: "Leave your contacts — a manager will call back within a business day and prepare a commercial offer.",
    name: "Name *", phone: "Phone *", email: "Email", company: "Company / facility", message: "Message",
    nameReq: "Enter your name",
    phoneHint: "Ukraine or international format: +380 67 123 45 67",
    companyPh: "Start typing a name — we'll suggest from the registry",
    errSend: "Failed to send. Please try again or call us.",
    sending: "Sending…", send: "Send inquiry",
    close: "Close", thanks: "Thank you!",
    doneSub: "Your inquiry has been received. A manager will contact you shortly.",
    codePrefix: "Waste code: ",
    fab: "Request a call",
  },
};

/* Open-state card max height (px) — mirrored in CSS (.inqm-inner max-height). */
const maxH = () => Math.min(Math.round(window.innerHeight * 0.82), 660);

/**
 * InquiryModal — morphing launcher.
 *
 * The floating «Замовити дзвінок» button IS the modal: on open the round FAB
 * itself grows into the inquiry card (width/height/radius/color morph, content
 * fades in); on close it shrinks back into the icon-only button.
 */
export default function InquiryModal({ state, onClose, onToggle }) {
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  const { open, type, code, title } = state;
  const [form, setForm] = useState({ name: "", phone: "", email: "", company_name: "", company_edrpou: "", message: "" });
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const [fieldErr, setFieldErr] = useState({});
  // render → card content is mounted; morph → shell is expanded (CSS class)
  const [render, setRender] = useState(open);
  const [morph, setMorph] = useState(false);
  // lift → the idle FAB rises above the footer bottom bar so it never covers
  // the legal links / made-by credit when the user scrolls to the very bottom.
  const [lift, setLift] = useState(false);
  const shellRef = useRef(null);
  const innerRef = useRef(null);

  /* Keep the shell height in sync with the card content (measured, capped). */
  const syncHeight = useCallback(() => {
    const shell = shellRef.current;
    const inner = innerRef.current;
    if (!shell || !inner) return;
    shell.style.height = `${Math.min(inner.scrollHeight, maxH())}px`;
  }, []);

  /* Morph open / close. */
  useEffect(() => {
    let raf1, raf2, t;
    if (open) {
      setRender(true);
      // Двойной rAF: контент смонтирован и измерен ДО старта transition.
      raf1 = requestAnimationFrame(() => {
        raf2 = requestAnimationFrame(() => {
          setMorph(true);
          syncHeight();
        });
      });
    } else if (render) {
      setMorph(false);
      if (shellRef.current) shellRef.current.style.height = ""; // back to CSS 58px
      t = setTimeout(() => setRender(false), 460);
    }
    return () => {
      if (raf1) cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
      if (t) clearTimeout(t);
    };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Track content size while open (validation errors, success view, resize). */
  useEffect(() => {
    if (!render) return undefined;
    const inner = innerRef.current;
    let ro;
    if (inner && typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => { if (open) syncHeight(); });
      ro.observe(inner);
    }
    const onResize = () => { if (open) syncHeight(); };
    window.addEventListener("resize", onResize);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", onResize);
    };
  }, [render, open, syncHeight]);

  /* Escape closes. */
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  /* Lift the FAB above the footer bottom bar when it scrolls into view. */
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return undefined;
    let io = null;
    let raf = 0;
    const attach = () => {
      const el = document.querySelector(".ecofoot__bottom");
      if (!el) {
        raf = window.setTimeout(attach, 800); // footer may mount later
        return;
      }
      io = new IntersectionObserver(
        ([entry]) => setLift(!!entry?.isIntersecting),
        { threshold: 0 }
      );
      io.observe(el);
    };
    attach();
    return () => {
      if (io) io.disconnect();
      if (raf) clearTimeout(raf);
    };
  }, []);

  /* Reset form on every open. */
  useEffect(() => {
    if (open) {
      setDone(false);
      setErr("");
      setFieldErr({});
      setForm({ name: "", phone: "", email: "", company_name: "", company_edrpou: "", message: code ? `${L.codePrefix}${code}` : "" });
    }
  }, [open, code]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    setFieldErr((fe) => ({ ...fe, [k]: undefined }));
  };

  const validate = () => {
    const fe = {};
    if (!form.name.trim()) fe.name = L.nameReq;
    const ph = validatePhone(form.phone, lang);
    if (!ph.ok) fe.phone = ph.error;
    const em = validateEmail(form.email, { required: false, lang });
    if (!em.ok) fe.email = em.error;
    setFieldErr(fe);
    return Object.keys(fe).length === 0;
  };

  const blurEmail = () => {
    const em = validateEmail(form.email, { required: false, lang });
    setFieldErr((fe) => ({ ...fe, email: em.ok ? undefined : em.error }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    if (!validate()) return;
    setSending(true);
    try {
      await PublicAPI.inquiry({ ...form, type, waste_code: code || "" });
      setDone(true);
    } catch (e2) {
      const detail = e2?.response?.data?.detail;
      setErr(typeof detail === "string" ? detail : L.errSend);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <div
        className={`inqm-scrim ${morph ? "is-on" : ""}`}
        onClick={onClose}
        aria-hidden="true"
        data-testid="inquiry-scrim"
      />
      <div
        ref={shellRef}
        className={`inqm ${morph ? "is-open" : ""} ${lift && !morph ? "is-lift" : ""}`}
        role={open ? "dialog" : undefined}
        aria-modal={open ? "true" : undefined}
        data-testid={open ? "inquiry-modal" : "inquiry-launcher"}
      >
        {/* ── Closed face: icon-only FAB ─────────────────────────────── */}
        <button
          type="button"
          className="inqm-fab"
          onClick={() => (onToggle ? onToggle({ type: "callback", title: L.fab }) : undefined)}
          aria-label={L.fab}
          aria-expanded={open}
          tabIndex={morph ? -1 : 0}
          data-testid="floating-cta"
        >
          <Phone aria-hidden="true" />
        </button>

        {/* ── Open face: card content grows out of the button ─────────── */}
        {render && (
          <div className="inqm-inner" ref={innerRef} role="document">
            <button className="inq-close" onClick={onClose} aria-label={L.close} data-testid="inquiry-close">
              ×
            </button>
            {!done ? (
              <>
                <p className="inq-eyebrow">{L.eyebrow}</p>
                <h3 className="inq-title">{title || L.titles[type] || L.defaultTitle}</h3>
                <p className="inq-sub">{L.sub}</p>
                <form className="inq-form" onSubmit={submit} noValidate>
                  <label className="inq-field">
                    <span>{L.name}</span>
                    <input value={form.name} onChange={set("name")} data-testid="inq-name"
                      className={fieldErr.name ? "inq-input--err" : ""} />
                    {fieldErr.name && <em className="inq-fielderr" data-testid="inq-name-err">{fieldErr.name}</em>}
                  </label>
                  <label className="inq-field">
                    <span>{L.phone}</span>
                    <PhoneField
                      value={form.phone}
                      onChange={(v) => { setForm((f) => ({ ...f, phone: v })); setFieldErr((fe) => ({ ...fe, phone: undefined })); }}
                      invalid={!!fieldErr.phone}
                      international={lang === "en"}
                      testId="inq-phone"
                    />
                    {fieldErr.phone && <em className="inq-fielderr" data-testid="inq-phone-err">{fieldErr.phone}</em>}
                  </label>
                  <label className="inq-field">
                    <span>{L.email}</span>
                    <input value={form.email} onChange={set("email")} onBlur={blurEmail} data-testid="inq-email"
                      type="email" placeholder="name@company.ua"
                      className={fieldErr.email ? "inq-input--err" : ""} />
                    {fieldErr.email && <em className="inq-fielderr" data-testid="inq-email-err">{fieldErr.email}</em>}
                  </label>
                  <label className="inq-field">
                    <span>{L.company}</span>
                    <CompanyAutocomplete
                      value={form.company_name}
                      onChange={(v) => setForm((f) => ({ ...f, company_name: v, company_edrpou: "" }))}
                      onSelect={(it) => setForm((f) => ({ ...f, company_name: it.name, company_edrpou: it.edrpou || "" }))}
                      placeholder={L.companyPh}
                      testId="inq-company"
                      lang={lang}
                    />
                  </label>
                  <label className="inq-field inq-field--full">
                    <span>{L.message}</span>
                    <textarea rows={3} value={form.message} onChange={set("message")} data-testid="inq-message" />
                  </label>
                  {err && <p className="inq-err" data-testid="inq-form-err">{err}</p>}
                  <button type="submit" className="inq-submit" disabled={sending} data-testid="inq-submit">
                    {sending ? L.sending : L.send}
                  </button>
                </form>
              </>
            ) : (
              <div className="inq-done" data-testid="inquiry-success">
                <div className="inq-done__mark">✓</div>
                <h3 className="inq-title">{L.thanks}</h3>
                <p className="inq-sub">{L.doneSub}</p>
                <button className="inq-submit" onClick={onClose}>{L.close}</button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
