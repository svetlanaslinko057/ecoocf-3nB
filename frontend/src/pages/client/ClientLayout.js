import React, { useState, useEffect, Suspense } from "react";
import { NavLink, Outlet, useNavigate, Link } from "react-router-dom";
import { useClientAuth } from "@/context/ClientAuthContext";
import RouteFallback from "@/components/RouteFallback";
import { useClientCopy } from "./clientCopy";
import { useLang } from "@/i18n";
import { ClientAPI } from "@/lib/clientApi";
import "./client.css";

function initials(name, email) {
  const base = (name || email || "K").trim();
  const parts = base.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase();
}

function LangToggle() {
  const { lang, changeLang } = useLang();
  return (
    <div className="cl-lang" role="group" aria-label="Language" data-testid="client-lang-switch">
      {[{ code: "uk", label: "UA" }, { code: "en", label: "EN" }].map((c) => (
        <button
          key={c.code}
          type="button"
          className={`cl-lang__btn ${lang === c.code ? "is-active" : ""}`}
          onClick={() => changeLang(c.code)}
          data-testid={`client-lang-${c.code}`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}

export default function ClientLayout() {
  const { customer, loading, logout } = useClientAuth();
  const { L } = useClientCopy();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!customer) return;
    let alive = true;
    const load = () => ClientAPI.notificationsUnread().then((r) => { if (alive) setUnread(r.unread || 0); }).catch(() => {});
    load();
    const t = setInterval(load, 30000);
    return () => { alive = false; clearInterval(t); };
  }, [customer]);

  const NAV = [
    { to: "/client", label: L.navOverview, end: true },
    { to: "/client/requests", label: L.navRequests },
    { to: "/client/contracts", label: L.navContracts || "Договори" },
    { to: "/client/contract-flow", label: "Договори на підпис" },
    { to: "/client/invoices", label: L.navInvoices },
    { to: "/client/messages", label: L.navMessages, badge: unread },
    { to: "/client/documents", label: L.navDocuments },
    { to: "/client/profile", label: L.navProfile },
  ];

  useEffect(() => {
    if (!loading && !customer) {
      navigate("/client/login", { replace: true });
    }
  }, [loading, customer, navigate]);

  if (loading) {
    return (
      <div className="eco-client cl-loading" data-testid="client-loading">
        <div className="cl-spinner" />
      </div>
    );
  }
  if (!customer) {
    return null;
  }

  const doLogout = () => {
    logout();
    navigate("/", { replace: true });
  };

  return (
    <div className="eco-client cl-shell" data-testid="client-shell">
      <aside className={`cl-side ${open ? "is-open" : ""}`}>
        <Link to="/" className="cl-brand">ECO<i>.</i><b>NOVA</b></Link>
        <nav className="cl-nav">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => `cl-nav__link ${isActive ? "is-active" : ""}`}
              onClick={() => setOpen(false)}
              data-testid={`client-nav-${n.to}`}
            >
              {n.label}
              {n.badge > 0 && (
                <span className="cl-nav__badge" data-testid="client-nav-badge">{n.badge > 9 ? "9+" : n.badge}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <button className="cl-logout" onClick={doLogout} data-testid="client-logout">{L.logout}</button>
      </aside>

      <div className="cl-main">
        <header className="cl-top">
          <button className="cl-burger" onClick={() => setOpen((v) => !v)} aria-label={L.menu}>
            <span /><span /><span />
          </button>
          <div className="cl-top__spacer" />
          <LangToggle />
          <div className="cl-user" data-testid="client-user">
            <div className="cl-avatar" aria-hidden="true">{initials(customer.name, customer.email)}</div>
            <div className="cl-user__meta">
              <span className="cl-user__name">{customer.name || customer.email}</span>
              {customer.company_name && <span className="cl-user__org">{customer.company_name}</span>}
            </div>
          </div>
        </header>
        <main className="cl-content">
          <Suspense fallback={<RouteFallback />}><Outlet /></Suspense>
        </main>
      </div>
    </div>
  );
}
