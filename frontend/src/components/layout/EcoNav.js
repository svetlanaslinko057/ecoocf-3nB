import React, { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Phone, User, ChevronDown, LogOut, ClipboardList, UserCircle, LayoutGrid, ArrowUpRight } from "lucide-react";
import { useClientAuth } from "@/context/ClientAuthContext";
import { useInquiry } from "@/context/InquiryContext";
import { useLang } from "@/i18n";
import { usePublicContacts } from "@/lib/usePublicContacts";

/* ── Bilingual copy (UA / EN) ─────────────────────────────────────────── */
const T = {
  uk: {
    nav: [
      { label: "Головна", to: "/" },
      { label: "Каталог відходів", to: "/waste" },
      { label: "Калькулятор", to: "/calculator" },
      { label: "Блог", to: "/blog" },
      { label: "Контакти", to: "/contacts" },
    ],
    menu: "Меню",
    close: "Закрити",
    openMenu: "Відкрити меню",
    closeMenu: "Закрити меню",
    callback: "Замовити дзвінок",
    home: "ECO.NOVA — головна",
    cabinet: "Особистий кабінет",
    myRequests: "Мої заявки",
    profile: "Профіль",
    logout: "Вийти",
    client: "Клієнт",
    clientLogin: "Вхід для клієнтів",
    navEyebrow: "Навігація",
    mainNav: "Головна навігація",
    cabinetLink: "Кабінет",
    authLink: "Авторизація",
    langLabel: "Мова",
    tagline: "Чисте довкілля починається з відповідальної утилізації.",
  },
  en: {
    nav: [
      { label: "Home", to: "/" },
      { label: "Waste catalog", to: "/waste" },
      { label: "Calculator", to: "/calculator" },
      { label: "Blog", to: "/blog" },
      { label: "Contacts", to: "/contacts" },
    ],
    menu: "Menu",
    close: "Close",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    callback: "Request a call",
    home: "ECO.NOVA — home",
    cabinet: "Client cabinet",
    myRequests: "My requests",
    profile: "Profile",
    logout: "Sign out",
    client: "Client",
    clientLogin: "Client sign-in",
    navEyebrow: "Navigation",
    mainNav: "Main navigation",
    cabinetLink: "Cabinet",
    authLink: "Sign in",
    langLabel: "Language",
    tagline: "A clean environment starts with responsible recycling.",
  },
};

const PHONE_DISPLAY_FALLBACK = "+380 66 788 04 45";
const EMAIL_FALLBACK = "Econova2013@ukr.net";

function initials(name, email) {
  const base = (name || email || "К").trim();
  const parts = base.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase();
}

/* 8-point asterisk that rotates when the menu opens (Farm-Minerals style) */
function AsteriskIcon() {
  return (
    <svg className="econav__trigger-ast" viewBox="0 0 24 24" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <line x1="12" y1="3" x2="12" y2="21" />
        <line x1="3" y1="12" x2="21" y2="12" />
        <line x1="5.6" y1="5.6" x2="18.4" y2="18.4" />
        <line x1="18.4" y1="5.6" x2="5.6" y2="18.4" />
      </g>
    </svg>
  );
}

/* small 4-point asterisk revealed to the left of a hovered menu item */
function MenuAsterisk() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <g fill="currentColor">
        <path d="M12 2c.6 3.2 1 3.6 4.2 4.2C13 6.8 12.6 7.2 12 10.4 11.4 7.2 11 6.8 7.8 6.2 11 5.6 11.4 5.2 12 2Z" />
        <path d="M12 13.6c.6 3.2 1 3.6 4.2 4.2C13 18.4 12.6 18.8 12 22c-.6-3.2-1-3.6-4.2-4.2 3.2-.6 3.6-1 4.2-4.2Z" />
        <path d="M2 12c3.2-.6 3.6-1 4.2-4.2C6.8 11 7.2 11.4 10.4 12 7.2 12.6 6.8 13 6.2 16.2 5.6 13 5.2 12.6 2 12Z" />
        <path d="M13.6 12c3.2-.6 3.6-1 4.2-4.2.6 3.2 1 3.6 4.2 4.2-3.2.6-3.6 1-4.2 4.2-.6-3.2-1-3.6-4.2-4.2Z" />
      </g>
    </svg>
  );
}

/* Language switcher: on DESKTOP it lives in the header (two-pill UA|EN,
   original behaviour). On MOBILE the header one is hidden via CSS and the
   switcher inside the overlay menu footer (LangMenu) is shown instead. */
const LANG_CODES = [
  { code: "uk", label: "UA" },
  { code: "en", label: "EN" },
];

function HeaderLang({ lang, setLang }) {
  return (
    <div className="econav__lang" role="group" aria-label="Language" data-testid="nav-lang-switch">
      {LANG_CODES.map((c) => (
        <button
          key={c.code}
          type="button"
          onClick={() => setLang(c.code)}
          data-testid={`nav-lang-${c.code}`}
          aria-pressed={lang === c.code}
          className={`econav__lang-pill${lang === c.code ? " is-active" : ""}`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}

export default function EcoNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const navigate = useNavigate();
  const { customer, isAuthed, logout } = useClientAuth();
  const { openInquiry } = useInquiry();
  const { lang, changeLang } = useLang();
  const L = T[lang] || T.uk;
  const NAV = L.nav;
  const { primaryPhone, primaryEmail } = usePublicContacts();
  const PHONE_DISPLAY = (primaryPhone && primaryPhone.value) || PHONE_DISPLAY_FALLBACK;
  const PHONE_HREF = `tel:${PHONE_DISPLAY.replace(/[^\d+]/g, "")}`;
  const EMAIL = (primaryEmail && primaryEmail.value) || EMAIL_FALLBACK;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // deep-link: open the overlay menu when the URL hash is #menu
  useEffect(() => {
    const sync = () => setOpen(window.location.hash === "#menu");
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  // close overlay on Esc
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  // close profile dropdown on outside click / Esc
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onDoc = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [menuOpen]);

  const callback = () => openInquiry({ type: "callback", title: L.callback });

  const doLogout = () => {
    logout();
    setMenuOpen(false);
    navigate("/", { replace: true });
  };

  return (
    <>
      <header
        className={`econav ${scrolled ? "is-scrolled" : ""} ${open ? "is-menu-open" : ""}`}
        data-testid="public-header"
      >
        {/* ── LEFT: menu trigger ─────────────────────────────────────── */}
        <button
          type="button"
          className={`econav__trigger ${open ? "is-open" : ""}`}
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? L.closeMenu : L.openMenu}
          aria-expanded={open}
          aria-controls="eco-overlay-menu"
          data-testid="nav-menu-trigger"
          data-cursor
        >
          <span className="econav__trigger-icon"><AsteriskIcon /></span>
          <span className="econav__trigger-label">
            <span className="econav__trigger-word" data-text={open ? L.close : L.menu}>
              {open ? L.close : L.menu}
            </span>
          </span>
        </button>

        {/* ── CENTER: logo ───────────────────────────────────────────── */}
        <Link to="/" className="econav__logo" data-cursor aria-label={L.home} onClick={() => setOpen(false)}>
          <span className="econav__mark">ECO<i>.</i><b>NOVA</b></span>
          <span className="econav__sub">Utilization Platform</span>
        </Link>

        {/* ── RIGHT: actions ─────────────────────────────────────────── */}
        <div className="econav__actions">
          <HeaderLang lang={lang} setLang={changeLang} />

          <a href={PHONE_HREF} className="econav__phone" data-cursor aria-label={`${PHONE_DISPLAY}`}>
            <Phone /><span>{PHONE_DISPLAY}</span>
          </a>

          <button type="button" className="econav__cta" onClick={callback} data-cursor data-testid="nav-callback">
            {L.callback}
          </button>

          {isAuthed ? (
            <div className="econav__profile" ref={menuRef}>
              <button
                type="button"
                className="econav__profile-btn"
                onClick={() => setMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                data-testid="nav-profile-btn"
                data-cursor
              >
                <span className="econav__profile-ava">{initials(customer?.name, customer?.email)}</span>
                <ChevronDown style={{ width: 15, height: 15, opacity: 0.6 }} />
              </button>
              {menuOpen && (
                <div className="econav__menu" role="menu" data-testid="nav-profile-menu">
                  <div className="econav__menu-head">
                    <div className="econav__menu-name">{customer?.name || L.client}</div>
                    <div className="econav__menu-mail">{customer?.email}</div>
                  </div>
                  <Link to="/client" className="econav__menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    <LayoutGrid /> {L.cabinet}
                  </Link>
                  <Link to="/client/requests" className="econav__menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    <ClipboardList /> {L.myRequests}
                  </Link>
                  <Link to="/client/profile" className="econav__menu-item" role="menuitem" onClick={() => setMenuOpen(false)}>
                    <UserCircle /> {L.profile}
                  </Link>
                  <div className="econav__menu-sep" />
                  <button type="button" className="econav__menu-item econav__menu-item--danger" onClick={doLogout} role="menuitem" data-testid="nav-logout">
                    <LogOut /> {L.logout}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to="/client/login" className="econav__profile-btn" aria-label={L.clientLogin} data-testid="nav-client-login" data-cursor>
              <span className="econav__profile-ava econav__profile-ava--guest"><User /></span>
            </Link>
          )}
        </div>
      </header>

      {/* ── Full-screen overlay menu ─────────────────────────────────── */}
      <div id="eco-overlay-menu" className={`ecomenu ${open ? "is-open" : ""}`} aria-hidden={!open}>
        <div className="ecomenu__panel">
          <div className="ecomenu__panel-inner">
            <span className="ecomenu__line" aria-hidden="true" />
            <span className="ecomenu__eyebrow">{L.navEyebrow}</span>
            <nav className="ecomenu__links" aria-label={L.mainNav}>
              {NAV.map((n, i) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.to === "/"}
                  className={({ isActive }) => `ecomenu__link ${isActive ? "is-active" : ""}`}
                  style={{ transitionDelay: `${0.22 + i * 0.08}s` }}
                  onClick={() => setOpen(false)}
                  data-testid={`overlay-link-${i}`}
                >
                  <span className="ecomenu__ast" aria-hidden="true"><MenuAsterisk /></span>
                  <span className="ecomenu__txt">{n.label}</span>
                </NavLink>
              ))}
              <NavLink
                to={isAuthed ? "/client" : "/client/login"}
                className="ecomenu__link"
                style={{ transitionDelay: `${0.22 + NAV.length * 0.08}s` }}
                onClick={() => setOpen(false)}
                data-testid="overlay-link-cabinet"
              >
                <span className="ecomenu__ast" aria-hidden="true"><MenuAsterisk /></span>
                <span className="ecomenu__txt">{isAuthed ? L.cabinetLink : L.authLink}</span>
              </NavLink>
            </nav>

            <div className="ecomenu__foot">
              <div className="ecomenu__lang" role="group" aria-label={L.langLabel} data-testid="menu-lang-switch">
                <span className="ecomenu__lang-label">{L.langLabel}</span>
                <div className="ecomenu__lang-pills">
                  {LANG_CODES.map((c) => (
                    <button
                      key={c.code}
                      type="button"
                      className={`ecomenu__lang-pill${lang === c.code ? " is-active" : ""}`}
                      onClick={() => changeLang(c.code)}
                      aria-pressed={lang === c.code}
                      data-testid={`menu-lang-${c.code}`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
              <p className="ecomenu__tag">{L.tagline}</p>
              <div className="ecomenu__contacts">
                <a href={PHONE_HREF} onClick={() => setOpen(false)}>{PHONE_DISPLAY}</a>
                <a href={`mailto:${EMAIL}`} onClick={() => setOpen(false)}>{EMAIL}</a>
                <button
                  type="button"
                  className="ecomenu__cta"
                  onClick={() => { setOpen(false); callback(); }}
                  data-testid="overlay-callback"
                >
                  {L.callback} <ArrowUpRight size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* clickable scrim that reveals the page behind */}
        <button
          type="button"
          className="ecomenu__scrim"
          onClick={() => setOpen(false)}
          aria-label={L.closeMenu}
          tabIndex={open ? 0 : -1}
        >
          <span className="ecomenu__watermark" aria-hidden="true">ECO<i>.</i><b>NOVA</b></span>
        </button>
      </div>
    </>
  );
}
