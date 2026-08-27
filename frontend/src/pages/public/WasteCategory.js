import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronRight, ArrowLeft } from "lucide-react";
import { WasteAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useLang } from "@/i18n";
import { iconByName, categoryLabel } from "@/lib/wasteMeta";
import { mediaUrl } from "@/lib/api";
import "./eco-pages.css";

const T = {
  uk: {
    directory: "Довідник",
    catFallback: "Категорія відходів",
    seoDescPre: "Утилізація: ", seoDescPost: ". Коди, клас небезпеки, ціни та умови.",
    seoSuffix: " — утилізація",
    inCategory: "кодів у категорії",
    haz: "Небезпечні *", nonHaz: "Ненебезпечні",
    loading: "Завантаження…",
    priceFrom: "від", unitSep: "грн/",
    allCategories: "До всіх категорій",
  },
  en: {
    directory: "Directory",
    catFallback: "Waste category",
    seoDescPre: "Disposal: ", seoDescPost: ". Codes, hazard class, prices and conditions.",
    seoSuffix: " — disposal",
    inCategory: "codes in the category",
    haz: "Hazardous *", nonHaz: "Non-hazardous",
    loading: "Loading…",
    priceFrom: "from", unitSep: "UAH/",
    allCategories: "To all categories",
  },
};

export default function WasteCategory() {
  const { key } = useParams();
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  const [codes, setCodes] = useState([]);
  const [cat, setCat] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    Promise.all([
      WasteAPI.codes({ category: key, limit: 200 }),
      WasteAPI.categories(),
    ]).then(([cd, ct]) => {
      setCodes(cd.items || []);
      setCat((ct.categories || []).find((c) => c.key === key) || null);
    }).finally(() => setLoading(false));
  }, [key]);
  const catLabel = (cat ? categoryLabel(cat, lang) : "") || key;
  useSeo(
    cat ? `${catLabel}${L.seoSuffix}` : L.catFallback,
    cat ? `${L.seoDescPre}${catLabel}${L.seoDescPost}` : ""
  );
  const Icon = iconByName(cat?.icon);
  const cover = mediaUrl(cat?.image_url);
  const desc = cat ? (lang === "en" ? (cat.desc_en || cat.desc_uk) : (cat.desc_uk || cat.desc_en)) : "";
  return (
    <div className="epage" data-testid="waste-category-page">
      <section className="epage-hero">
        <div className="epage-hero__inner">
          <nav className="ecrumb">
            <Link to="/waste">{L.directory}</Link>
            <ChevronRight />
            <span className="ecrumb__current">{catLabel}</span>
          </nav>
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            {cover ? (
              <span
                aria-hidden="true"
                style={{ width: 84, height: 84, borderRadius: 18, backgroundImage: `url(${cover})`, backgroundSize: "cover", backgroundPosition: "center", flexShrink: 0, border: "1px solid var(--eco-line)" }}
              />
            ) : (
              <span className="ecard__icon" style={{ marginBottom: 0, width: 60, height: 60 }}><Icon /></span>
            )}
            <div>
              <h1 className="epage__title" style={{ fontSize: "clamp(34px, 5vw, 64px)" }}>{catLabel}</h1>
              <p className="erow__name" style={{ marginTop: 8 }}>{codes.length} {L.inCategory}</p>
            </div>
          </div>
          {desc ? (
            <p className="epage__lead" data-testid="category-description" style={{ marginTop: 18, maxWidth: 760 }}>{desc}</p>
          ) : null}
        </div>
      </section>

      <section className="epage-sec">
        <div style={{ display: "grid", gap: 12 }}>
          {loading && <div className="estate">{L.loading}</div>}
          {codes.map((c) => (
            <Link key={c.code} to={`/waste-code/${c.slug}`} data-testid="category-code-row" className="erow">
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <span className="erow__code">{c.code}</span>
                  <span className={`epill ${c.hazardous ? "epill--haz" : "epill--ok"}`}>{c.hazardous ? L.haz : L.nonHaz}</span>
                </div>
                <div className="erow__name" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</div>
              </div>
              <div className="erow__meta">
                {c.price_from != null && <span style={{ fontSize: 13 }}>{L.priceFrom} {c.price_from} {L.unitSep}{c.price_unit}</span>}
                <ChevronRight className="erow__arrow" />
              </div>
            </Link>
          ))}
        </div>
        <div style={{ marginTop: 36 }}>
          <Link to="/waste" className="ebtn ebtn--ghost" data-cursor><ArrowLeft /> {L.allCategories}</Link>
        </div>
      </section>
    </div>
  );
}
