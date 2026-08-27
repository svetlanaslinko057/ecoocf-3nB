import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Search } from "lucide-react";
import { WasteAPI } from "@/lib/api";
import { useSeo } from "@/lib/seo";
import { useLang } from "@/i18n";
import { iconByName, categoryLabel, codesWord } from "@/lib/wasteMeta";
import { mediaUrl } from "@/lib/api";
import { Checkbox } from "@/components/ui/checkbox";
import "./eco-pages.css";

const T = {
  uk: {
    seoTitle: "Довідник відходів",
    seoDesc: "Національний перелік відходів: коди, категорії, клас небезпеки, ціни та умови утилізації.",
    eyebrow: "Довідник відходів",
    title: "Каталог кодів відходів",
    lead: "Знайдіть свій відхід за назвою або кодом — або оберіть категорію зі списку.",
    searchPh: "Назва або код, напр. 20 01 21 або батарейки",
    hazOnly: "Лише небезпечні",
    haz: "Небезпечні *", nonHaz: "Ненебезпечні",
    searching: "Пошук…", notFound: "Нічого не знайдено.",
    codes: "кодів",
  },
  en: {
    seoTitle: "Waste directory",
    seoDesc: "National waste list: codes, categories, hazard class, prices and disposal conditions.",
    eyebrow: "Waste directory",
    title: "Waste code catalog",
    lead: "Find your waste by name or code — or pick a category from the list.",
    searchPh: "Name or code, e.g. 20 01 21 or batteries",
    hazOnly: "Hazardous only",
    haz: "Hazardous *", nonHaz: "Non-hazardous",
    searching: "Searching…", notFound: "Nothing found.",
    codes: "codes",
  },
};

export default function WasteDirectory() {
  const { lang } = useLang();
  const L = T[lang] || T.uk;
  useSeo(L.seoTitle, L.seoDesc);
  const [cats, setCats] = useState([]);
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [hazOnly, setHazOnly] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => { WasteAPI.categories().then((r) => setCats(r.categories || [])); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      if (!q.trim() && !hazOnly) { setItems([]); return; }
      setLoading(true);
      WasteAPI.codes({ q: q.trim() || undefined, hazardous: hazOnly || undefined, limit: 100 })
        .then((r) => setItems(r.items || [])).finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q, hazOnly]);

  const showList = useMemo(() => q.trim() || hazOnly, [q, hazOnly]);
  return (
    <div className="epage" data-testid="waste-directory-page">
      <section className="epage-hero">
        <div className="epage-hero__inner">
          <div className="epage__eyebrow"><i />{L.eyebrow}</div>
          <h1 className="epage__title">{L.title}</h1>
          <p className="epage__lead">{L.lead}</p>
        </div>
      </section>

      <section className="epage-sec">
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
          <div className="einput-wrap" style={{ flex: 1, minWidth: 260 }}>
            <Search />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={L.searchPh} data-testid="directory-search-input" className="einput einput--search" />
          </div>
          <label className="etoggle-row" style={{ cursor: "pointer", width: "auto" }}>
            <Checkbox checked={hazOnly} onCheckedChange={(v) => setHazOnly(!!v)} data-testid="directory-hazardous-checkbox" />
            <span className="etoggle-row__label" style={{ gap: 0 }}>{L.hazOnly}</span>
          </label>
        </div>

        {showList ? (
          <div style={{ marginTop: 28, display: "grid", gap: 12 }}>
            {loading && <div className="estate">{L.searching}</div>}
            {!loading && items.length === 0 && <div className="estate">{L.notFound}</div>}
            {items.map((c) => (
              <Link key={c.code} to={`/waste-code/${c.slug}`} data-testid="directory-code-row" className="erow">
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                    <span className="erow__code">{c.code}</span>
                    <span className={`epill ${c.hazardous ? "epill--haz" : "epill--ok"}`}>{c.hazardous ? L.haz : L.nonHaz}</span>
                  </div>
                  <div className="erow__name" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</div>
                </div>
                <ChevronRight className="erow__arrow" />
              </Link>
            ))}
          </div>
        ) : (
          <div className="egrid etiles" style={{ marginTop: 32 }}>
            {cats.map((c) => {
              const Icon = iconByName(c.icon);
              const cover = mediaUrl(c.image_url);
              return (
                <Link key={c.key} to={`/waste/category/${c.key}`} data-testid={`directory-category-${c.key}`} className="etile">
                  {cover ? (
                    <span className="etile__cover" style={{ backgroundImage: `url(${cover})` }} aria-hidden="true" />
                  ) : null}
                  <span className="ecard__icon" style={{ marginBottom: 0 }}><Icon /></span>
                  <div className="etile__title">{categoryLabel(c, lang)}</div>
                  <div className="etile__count">{c.count} {codesWord(c.count, lang)}</div>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
