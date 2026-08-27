import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import DOMPurify from "isomorphic-dompurify";
import {
  CalendarBlank, Clock, ArrowLeft, LinkSimple,
  TwitterLogo, FacebookLogo, LinkedinLogo, ArrowRight,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { useLang } from "@/i18n";
import "./eco-blog.css";

const API = process.env.REACT_APP_BACKEND_URL || "";

const CATEGORY_LABELS = {
  uk: { news: "Новини", regulation: "Регулювання", guides: "Гайди", cases: "Кейси", ecology: "Екологія", industry: "Галузь" },
  en: { news: "News", regulation: "Regulation", guides: "Guides", cases: "Cases", ecology: "Ecology", industry: "Industry" },
};

const UI = {
  uk: {
    crumbHome: "Головна", crumbBlog: "Блог", error: "Помилка", notFound: "Статтю не знайдено",
    errorHint: "Перевірте посилання або поверніться до списку статей.", allArticles: "Усі статті",
    min: "хв читання", inArticle: "У статті", copy: "Скопіювати",
    copied: "Посилання скопійовано", copyFail: "Не вдалося скопіювати",
    ctaH: "Готові закрити цикл утилізації?",
    ctaP: "Наша команда ECO допоможе підібрати правильний код, оформити пакет документів і безпечно вивезти небезпечні відходи.",
    calc: "Розрахувати вартість", contact: "Зв’язатися з нами", readNext: "Читати далі",
    titleSuffix: " · Блог ECO", locale: "uk-UA",
  },
  en: {
    crumbHome: "Home", crumbBlog: "Blog", error: "Error", notFound: "Article not found",
    errorHint: "Check the link or return to the article list.", allArticles: "All articles",
    min: "min read", inArticle: "In this article", copy: "Copy",
    copied: "Link copied", copyFail: "Couldn't copy",
    ctaH: "Ready to close the disposal loop?",
    ctaP: "Our ECO team will help pick the right code, prepare the document package and safely remove hazardous waste.",
    calc: "Calculate the cost", contact: "Contact us", readNext: "Read next",
    titleSuffix: " · ECO.NOVA Blog", locale: "en-US",
  },
};

const FALLBACK_COVER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 900'>" +
      "<defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>" +
      "<stop offset='0' stop-color='%234a5e2a'/><stop offset='1' stop-color='%23253318'/></linearGradient></defs>" +
      "<rect width='1600' height='900' fill='url(%23g)'/>" +
      "<text x='50%' y='50%' fill='%23f1ecd8' font-family='Archivo' font-weight='800' font-size='80' text-anchor='middle' dominant-baseline='middle'>ECO · BLOG</text>" +
      "</svg>",
  );

function fmtDate(iso, locale) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(locale, { day: "numeric", month: "long", year: "numeric" });
  } catch { return ""; }
}

function extractToc(html) {
  if (!html) return [];
  try {
    const wrap = document.createElement("div");
    wrap.innerHTML = html;
    const out = [];
    wrap.querySelectorAll("h2, h3").forEach((el, idx) => {
      let id = el.id;
      if (!id) { id = `sec-${idx}`; el.id = id; }
      out.push({ id, text: el.textContent || "", level: el.tagName === "H2" ? 2 : 3 });
    });
    return { items: out, html: wrap.innerHTML };
  } catch { return { items: [], html }; }
}

function RelatedCard({ post, cat, L }) {
  const cover = post.cover_image_url
    ? (post.cover_image_url.startsWith("http") ? post.cover_image_url : `${API}${post.cover_image_url}`)
    : FALLBACK_COVER;
  return (
    <Link to={`/blog/${post.slug}`} className="ebcard ebcard--tile" data-testid={`related-${post.slug}`}>
      <div className="ebcard__media"><img src={cover} alt={post.title} loading="lazy" /></div>
      <div className="ebcard__body">
        <span className="ebcard__chip">{cat[post.category] || post.category}</span>
        <h3 className="ebcard__title">{post.title}</h3>
        <div className="ebcard__meta">
          <time><CalendarBlank weight="regular" size={14}/>{fmtDate(post.published_at || post.created_at, L.locale)}</time>
          <span><Clock weight="regular" size={14}/> {post.read_time_minutes || 1} {L.min}</span>
        </div>
      </div>
    </Link>
  );
}

export default function BlogArticle() {
  const { slug } = useParams();
  const { lang } = useLang();
  const L = UI[lang] || UI.uk;
  const cat = CATEGORY_LABELS[lang] || CATEGORY_LABELS.uk;
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const articleRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true); setError(null);
    axios.get(`${API}/api/public/blog/articles/${slug}?lang=${lang}`).then((r) => {
      if (!mounted) return;
      setData(r.data || null);
      setLoading(false);
    }).catch((e) => {
      if (!mounted) return;
      setError(e?.response?.status === 404 ? L.notFound : (e?.message || L.error));
      setLoading(false);
    });
    return () => { mounted = false; };
  }, [slug, lang]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (data?.title) document.title = `${data.title}${L.titleSuffix}`;
  }, [data, L.titleSuffix]);

  useEffect(() => {
    const update = () => {
      const el = articleRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const total = el.scrollHeight - window.innerHeight;
      const scrolled = Math.max(0, -rect.top);
      const pct = total > 0 ? Math.min(100, (scrolled / total) * 100) : 0;
      setProgress(pct);
    };
    window.addEventListener("scroll", update, { passive: true });
    update();
    return () => window.removeEventListener("scroll", update);
  }, [data]);

  const sanitized = useMemo(() => {
    if (!data?.body) return { items: [], html: "" };
    const clean = DOMPurify.sanitize(data.body, { ADD_ATTR: ["target", "rel"] });
    return extractToc(clean);
  }, [data]);

  const cover = data?.cover_image_url
    ? (data.cover_image_url.startsWith("http") ? data.cover_image_url : `${API}${data.cover_image_url}`)
    : FALLBACK_COVER;

  const fullUrl = typeof window !== "undefined" ? window.location.href : "";

  const copyLink = async () => {
    try { await navigator.clipboard.writeText(fullUrl); toast.success(L.copied); }
    catch { toast.error(L.copyFail); }
  };

  if (loading) {
    return (
      <main className="eapage"><div className="eapage__inner">
        <div className="ebskeleton" style={{ height: 28, width: 200, marginBottom: 22 }} />
        <div className="ebskeleton" style={{ height: 80, width: "80%", marginBottom: 22 }} />
        <div className="ebskeleton" style={{ height: 18, width: "60%", marginBottom: 80 }} />
        <div className="ebskeleton" style={{ aspectRatio: "16/9", marginBottom: 60 }} />
        <div className="ebskeleton" style={{ height: 320, maxWidth: 760 }} />
      </div></main>
    );
  }

  if (error) {
    return (
      <main className="eapage"><div className="eapage__inner">
        <nav className="eapage__crumbs"><Link to="/">{L.crumbHome}</Link><i/><Link to="/blog">{L.crumbBlog}</Link><i/><strong>{L.error}</strong></nav>
        <h1 className="eapage__title">{error}</h1>
        <p className="eapage__excerpt">{L.errorHint}</p>
        <button type="button" className="eapage__share-btn" onClick={() => navigate("/blog")} data-testid="back-to-blog">
          <ArrowLeft weight="bold" size={16}/> {L.allArticles}
        </button>
      </div></main>
    );
  }
  if (!data) return null;

  return (
    <main className="eapage" data-testid="blog-article" ref={articleRef}>
      <div className="eapage__progress" style={{ width: `${progress}%` }} />
      <div className="eapage__inner">
        <header className="eapage__header">
          <nav className="eapage__crumbs" aria-label="breadcrumb">
            <Link to="/">{L.crumbHome}</Link>
            <i aria-hidden="true" />
            <Link to="/blog">{L.crumbBlog}</Link>
            <i aria-hidden="true" />
            <strong>{cat[data.category] || data.category}</strong>
          </nav>
          <span className="eapage__chip">{cat[data.category] || data.category}</span>
          <h1 className="eapage__title">{data.title}</h1>
          {data.excerpt && <p className="eapage__excerpt">{data.excerpt}</p>}
          <div className="eapage__meta">
            <time><CalendarBlank weight="regular" size={15}/>{fmtDate(data.published_at || data.created_at, L.locale)}</time>
            <span><Clock weight="regular" size={15}/> {data.read_time_minutes || 1} {L.min}</span>
            {data.tags && data.tags.length > 0 && (
              <span className="eapage__tags">
                {data.tags.slice(0, 5).map((t) => (
                  <Link to={`/blog?tag=${encodeURIComponent(t)}`} key={t} className="eapage__tag">#{t}</Link>
                ))}
              </span>
            )}
          </div>
        </header>

        <figure className="eapage__cover"><img src={cover} alt={data.title} /></figure>

        <div className="eapage__layout">
          <article
            className="eapage__body"
            dangerouslySetInnerHTML={{ __html: sanitized.html }}
            data-testid="article-body"
          />
          <aside className="eapage__aside">
            {sanitized.items.length > 1 && (
              <div className="eapage__toc">
                <div className="eapage__toc-title">{L.inArticle}</div>
                {sanitized.items.map((s) => (
                  <a key={s.id} href={`#${s.id}`} style={{ paddingLeft: s.level === 3 ? 14 : 0, color: "var(--eco-ink)", textDecoration: "none" }}>
                    {s.text}
                  </a>
                ))}
              </div>
            )}
            <div className="eapage__share">
              <a className="eapage__share-btn" href={`https://twitter.com/intent/tweet?url=${encodeURIComponent(fullUrl)}&text=${encodeURIComponent(data.title)}`} target="_blank" rel="noreferrer"><TwitterLogo weight="regular" size={16}/> Twitter</a>
              <a className="eapage__share-btn" href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(fullUrl)}`} target="_blank" rel="noreferrer"><FacebookLogo weight="regular" size={16}/> Facebook</a>
              <a className="eapage__share-btn" href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(fullUrl)}`} target="_blank" rel="noreferrer"><LinkedinLogo weight="regular" size={16}/> LinkedIn</a>
              <button type="button" className="eapage__share-btn" onClick={copyLink}><LinkSimple weight="regular" size={16}/> {L.copy}</button>
            </div>
          </aside>
        </div>

        {/* CTA */}
        <section className="eapage__cta" data-testid="article-cta">
          <div>
            <h3 className="eapage__cta-h">{L.ctaH}</h3>
            <p className="eapage__cta-p">{L.ctaP}</p>
          </div>
          <div className="eapage__cta-actions">
            <Link to="/calculator" className="eapage__cta-btn eapage__cta-btn--primary">
              {L.calc} <ArrowRight weight="bold" size={16}/>
            </Link>
            <Link to="/contacts" className="eapage__cta-btn eapage__cta-btn--ghost">
              {L.contact}
            </Link>
          </div>
        </section>

        {/* Related */}
        {data.related && data.related.length > 0 && (
          <section className="eapage__related" data-testid="article-related">
            <h3 className="eapage__related-h">{L.readNext}</h3>
            <div className="eapage__related-grid">
              {data.related.slice(0, 3).map((r) => <RelatedCard key={r.id} post={r} cat={cat} L={L} />)}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
