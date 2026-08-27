import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import { CalendarBlank, Clock } from "@phosphor-icons/react";
import { useLang } from "@/i18n";
import "./eco-blog.css";

const API = process.env.REACT_APP_BACKEND_URL || "";

const CATEGORY_LABELS = {
  uk: { all: "Усі", news: "Новини", regulation: "Регулювання", guides: "Гайди", cases: "Кейси", ecology: "Екологія", industry: "Галузь" },
  en: { all: "All", news: "News", regulation: "Regulation", guides: "Guides", cases: "Cases", ecology: "Ecology", industry: "Industry" },
};

const UI = {
  uk: {
    title: "Блог · ECO.NOVA Utilization Platform", crumbHome: "Головна", crumbBlog: "Блог", h1: "Блог",
    sub: "Інсайти про відповідальне поводження з відходами, аналіз законодавства, гайди для бізнесу та реальні кейси з практики ECO.NOVA. Знання, що допомагають закривати цикл — від утворення відходу до його утилізації.",
    loadError: "Не вдалося завантажити статті.", errorLbl: "Помилка",
    emptyH: "Поки що тут порожньо", emptyP: "Перші статті з’являться зовсім скоро. Зазирніть пізніше або переключіть категорію.",
    noTitle: "Без заголовку", min: "хв", locale: "uk-UA",
  },
  en: {
    title: "Blog · ECO.NOVA Utilization Platform", crumbHome: "Home", crumbBlog: "Blog", h1: "Blog",
    sub: "Insights on responsible waste handling, legislation analysis, business guides and real cases from ECO practice. Knowledge that helps close the loop — from waste generation to its disposal.",
    loadError: "Failed to load articles.", errorLbl: "Error",
    emptyH: "It's empty here for now", emptyP: "The first articles will appear very soon. Check back later or switch the category.",
    noTitle: "Untitled", min: "min", locale: "en-US",
  },
};

const FALLBACK_COVER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 500'>" +
      "<defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>" +
      "<stop offset='0' stop-color='%234a5e2a'/><stop offset='1' stop-color='%23253318'/></linearGradient></defs>" +
      "<rect width='800' height='500' fill='url(%23g)'/>" +
      "<text x='50%' y='50%' fill='%23f1ecd8' font-family='Archivo' font-weight='800' font-size='44' text-anchor='middle' dominant-baseline='middle'>ECO · BLOG</text>" +
      "</svg>",
  );

function fmtDate(iso, locale) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  } catch {
    return "";
  }
}

function stripHtml(s) {
  if (!s) return "";
  return s.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function BlogCard({ post, variant = "tile", L, cat }) {
  const cls = `ebcard ebcard--${variant}`;
  const cover = post.cover_image_url
    ? (post.cover_image_url.startsWith("http") ? post.cover_image_url : `${API}${post.cover_image_url}`)
    : FALLBACK_COVER;
  const title = post.title || L.noTitle;
  const excerpt = stripHtml(post.excerpt) || stripHtml(post.body).slice(0, 160);
  const catLabel = cat[post.category] || post.category;
  const meta = (
    <div className="ebcard__meta">
      <time><CalendarBlank weight="regular" size={14}/>{fmtDate(post.published_at || post.created_at, L.locale)}</time>
      <span><Clock weight="regular" size={14}/> {post.read_time_minutes || 1} {L.min}</span>
    </div>
  );
  if (variant === "featured") {
    return (
      <Link to={`/blog/${post.slug}`} className={cls} data-testid={`blog-card-${post.slug}`}>
        <div className="ebcard__media"><img src={cover} alt={title} loading="lazy" /></div>
        <span className="ebcard__chip">{catLabel}</span>
        <div className="ebcard__title-wrap">
          <h2 className="ebcard__title">{title}</h2>
          {excerpt && <p className="ebcard__excerpt">{excerpt}</p>}
          {meta}
        </div>
      </Link>
    );
  }
  if (variant === "mini") {
    return (
      <Link to={`/blog/${post.slug}`} className={cls} data-testid={`blog-card-${post.slug}`}>
        <div className="ebcard__body">
          <span className="ebcard__chip">{catLabel}</span>
          <div className="ebcard__title-wrap">
            <h3 className="ebcard__title">{title}</h3>
            {excerpt && <p className="ebcard__excerpt">{excerpt}</p>}
          </div>
          {meta}
        </div>
        <div className="ebcard__media"><img src={cover} alt={title} loading="lazy" /></div>
      </Link>
    );
  }
  return (
    <Link to={`/blog/${post.slug}`} className={cls} data-testid={`blog-card-${post.slug}`}>
      <div className="ebcard__media"><img src={cover} alt={title} loading="lazy" /></div>
      <div className="ebcard__body">
        <span className="ebcard__chip">{catLabel}</span>
        <h3 className="ebcard__title">{title}</h3>
        {excerpt && <p className="ebcard__excerpt">{excerpt}</p>}
        {meta}
      </div>
    </Link>
  );
}

export default function BlogIndex() {
  const { lang } = useLang();
  const L = UI[lang] || UI.uk;
  const cat = CATEGORY_LABELS[lang] || CATEGORY_LABELS.uk;
  const [params, setParams] = useSearchParams();
  const currentCategory = params.get("category") || "all";
  const [items, setItems] = useState([]);
  const [cats, setCats] = useState(["all"]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true); setError(null);
    const url = `${API}/api/public/blog/articles?lang=${lang}&category=${currentCategory}&limit=50`;
    axios.get(url).then((r) => {
      if (!mounted) return;
      setItems(Array.isArray(r.data?.items) ? r.data.items : []);
      const backendCats = Array.isArray(r.data?.categories) ? r.data.categories : [];
      setCats(["all", ...backendCats]);
      setLoading(false);
    }).catch((e) => {
      if (!mounted) return;
      setError(e?.message || L.loadError);
      setLoading(false);
    });
    return () => { mounted = false; };
  }, [currentCategory, lang]); // eslint-disable-line react-hooks/exhaustive-deps

  const setCategory = (c) => {
    if (c === "all") { params.delete("category"); setParams(params); }
    else { params.set("category", c); setParams(params); }
  };

  const featured = items[0] || null;
  const stacked = items.slice(1, 3);
  const tiles = items.slice(3);
  const hasAny = !loading && items.length > 0;

  useEffect(() => { document.title = L.title; }, [L.title]);

  return (
    <main className="ebpage" data-testid="blog-index">
      <div className="ebpage__inner">
        <nav className="ebpage__crumbs" aria-label="breadcrumb">
          <Link to="/">{L.crumbHome}</Link>
          <i aria-hidden="true" />
          <strong>{L.crumbBlog}</strong>
        </nav>
        <h1 className="ebpage__h1">{L.h1}</h1>
        <p className="ebpage__sub">{L.sub}</p>

        <div className="ebpage__filters" data-testid="blog-filters">
          {cats.map((c) => (
            <button
              key={c}
              type="button"
              className={`ebpage__filter ${currentCategory === c ? "is-active" : ""}`}
              onClick={() => setCategory(c)}
              data-testid={`blog-filter-${c}`}
            >
              {cat[c] || c}
            </button>
          ))}
        </div>

        {loading && (
          <div className="ebpage__grid">
            <div className="ebskeleton ebskeleton--featured" />
            <div className="ebpage__stack">
              <div className="ebskeleton ebskeleton--mini" />
              <div className="ebskeleton ebskeleton--mini" />
            </div>
          </div>
        )}

        {!loading && error && (
          <div className="ebpage__empty">
            <strong>{L.errorLbl}</strong>
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && !hasAny && (
          <div className="ebpage__empty" data-testid="blog-empty">
            <strong>{L.emptyH}</strong>
            <p>{L.emptyP}</p>
          </div>
        )}

        {hasAny && (
          <>
            <div className="ebpage__grid">
              {featured && <BlogCard post={featured} variant="featured" L={L} cat={cat} />}
              <div className="ebpage__stack">
                {stacked.map((p) => <BlogCard key={p.id} post={p} variant="mini" L={L} cat={cat} />)}
                {stacked.length === 0 && <div className="ebskeleton ebskeleton--mini" style={{ opacity: 0.3 }} />}
              </div>
            </div>
            {tiles.length > 0 && (
              <div className="ebgrid">
                {tiles.map((p) => <BlogCard key={p.id} post={p} variant="tile" L={L} cat={cat} />)}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
