import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PublicAPI } from "@/lib/clientApi";
import { useLang } from "@/i18n";
import { useSeo } from "@/lib/seo";
import "./eco-legal.css";

const NAV = {
  uk: [
    { key: "privacy", label: "Політика конфіденційності", href: "/privacy" },
    { key: "terms", label: "Умови використання", href: "/terms" },
    { key: "cookies", label: "Політика Cookies", href: "/cookies" },
  ],
  en: [
    { key: "privacy", label: "Privacy Policy", href: "/privacy" },
    { key: "terms", label: "Terms of Use", href: "/terms" },
    { key: "cookies", label: "Cookies Policy", href: "/cookies" },
  ],
};

const T = {
  uk: { eyebrow: "ECO · Правова інформація", home: "Головна", loading: "Завантаження…", err: "Не вдалося завантажити документ." },
  en: { eyebrow: "ECO · Legal", home: "Home", loading: "Loading…", err: "Failed to load the document." },
};

export default function LegalPage({ docKey }) {
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  const nav = NAV[lang] || NAV.uk;
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr("");
    PublicAPI.policy(docKey, lang)
      .then((d) => { if (alive) setDoc(d); })
      .catch(() => { if (alive) setErr(L.err); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [docKey, lang]); // eslint-disable-line react-hooks/exhaustive-deps

  const title = doc?.title || nav.find((n) => n.key === docKey)?.label || "";
  useSeo(`${title} — ECO.NOVA`, title);

  return (
    <div className="legal" data-testid={`legal-${docKey}`}>
      <div className="legal__wrap">
        <nav className="legal__crumbs" aria-label="breadcrumb">
          <Link to="/">{L.home}</Link>
          <span>/</span>
          <span>{title}</span>
        </nav>

        <header className="legal__head">
          <p className="legal__eyebrow">{L.eyebrow}</p>
          <h1 className="legal__title">{title}</h1>
        </header>

        <div className="legal__grid">
          <aside className="legal__aside">
            <ul>
              {nav.map((n) => (
                <li key={n.key}>
                  <Link to={n.href} className={n.key === docKey ? "is-active" : ""} data-testid={`legal-nav-${n.key}`}>
                    {n.label}
                  </Link>
                </li>
              ))}
            </ul>
          </aside>

          <article className="legal__body">
            {loading && <p className="legal__muted">{L.loading}</p>}
            {!loading && err && <p className="legal__err">{err}</p>}
            {!loading && !err && (
              <div className="legal__prose" dangerouslySetInnerHTML={{ __html: doc?.content || "" }} />
            )}
          </article>
        </div>
      </div>
    </div>
  );
}
