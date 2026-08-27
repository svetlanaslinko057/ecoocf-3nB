import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cookie } from "lucide-react";
import { PublicAPI } from "@/lib/clientApi";
import { useLang } from "@/i18n";
import "./eco-cookie.css";

const STORAGE_KEY = "eco_cookie_consent";

const T = {
  uk: {
    fallbackTitle: "Ми цінуємо вашу приватність",
    fallbackBody:
      "Ми використовуємо необхідні файли cookie для коректної роботи сайту, а також аналітичні cookie — щоб покращувати сервіс.",
    acceptAll: "Прийняти всі",
    acceptNecessary: "Лише необхідні",
    more: "Політика Cookies",
  },
  en: {
    fallbackTitle: "We value your privacy",
    fallbackBody:
      "We use essential cookies to keep the site working, plus analytics cookies to improve the service.",
    acceptAll: "Accept all",
    acceptNecessary: "Only necessary",
    more: "Cookies Policy",
  },
};

/**
 * Compact cookie-consent card (bottom-left) with a cookie icon.
 * Copy (title/body, per language) is admin-managed: Admin CRM → Site → Info →
 * Cookie Banner (`/api/site-info` → `cookie_banner`), incl. on/off switch.
 */
export default function CookieConsent() {
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  const [cfg, setCfg] = useState(null);
  const [visible, setVisible] = useState(false);
  const [anim, setAnim] = useState(false);

  useEffect(() => {
    // Already decided?
    let decided = false;
    try {
      decided = !!localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      decided = false;
    }
    if (decided) return;

    let alive = true;
    PublicAPI.siteInfo()
      .then((d) => {
        if (!alive) return;
        const cb = d?.cookie_banner || {};
        if (cb.enabled === false) return; // admin disabled the banner
        setCfg(cb);
        setVisible(true);
        requestAnimationFrame(() => alive && setAnim(true));
      })
      .catch(() => {
        // network fail → still show a minimal banner (consent is required)
        if (!alive) return;
        setCfg({});
        setVisible(true);
        requestAnimationFrame(() => alive && setAnim(true));
      });
    return () => { alive = false; };
  }, []);

  const decide = (choice) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ choice, ts: Date.now() }));
    } catch (e) { /* ignore */ }
    setAnim(false);
    setTimeout(() => setVisible(false), 260);
  };

  if (!visible) return null;

  const title = (lang === "en" ? cfg?.title_en : cfg?.title_uk) || L.fallbackTitle;
  const body = (lang === "en" ? cfg?.body_en : cfg?.body_uk) || L.fallbackBody;

  return (
    <div className={`cookie ${anim ? "is-in" : ""}`} role="dialog" aria-live="polite" aria-label={title} data-testid="cookie-consent">
      <div className="cookie__head">
        <span className="cookie__icon" aria-hidden="true"><Cookie /></span>
        <h3 className="cookie__title">{title}</h3>
      </div>
      <p className="cookie__body">{body}</p>
      <Link to="/cookies" className="cookie__more" data-testid="cookie-policy-link">{L.more}</Link>
      <div className="cookie__actions">
        <button type="button" className="cookie__btn cookie__btn--primary" onClick={() => decide("all")} data-testid="cookie-accept-all">
          {L.acceptAll}
        </button>
        <button type="button" className="cookie__btn cookie__btn--ghost" onClick={() => decide("necessary")} data-testid="cookie-accept-necessary">
          {L.acceptNecessary}
        </button>
      </div>
    </div>
  );
}
