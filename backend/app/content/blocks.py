"""Block registry — Phase D1.

Each block type has a name, an allow-list of fields, per-field validators and
an HTML renderer used by the prerender engine (bots see full HTML in first
byte). Client-side React renders the same block tree via `BlockRenderer`.

Only 12 types ship in D1 (see plan.md). Adding a new type = single entry here
+ matching React component; no other change needed on backend or admin UI.
"""
from __future__ import annotations

import html
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Field validators — cheap, non-recursive, safe to call in a request handler.
# ---------------------------------------------------------------------------

def _s(v, maxlen: int = 5000) -> str:
    if v is None:
        return ""
    s = str(v)
    return s[:maxlen]


def _b(v) -> bool:
    return bool(v) if v is not None else False


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _list_of_dicts(v) -> List[Dict[str, Any]]:
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


_URL_RE = re.compile(r"^(https?://|/)[^\s]+$")


def _url(v) -> str:
    s = _s(v, 2000)
    if not s:
        return ""
    return s if _URL_RE.match(s) else ""


# ---------------------------------------------------------------------------
# HTML helpers (mirror app.seo.prerender._h for XSS-safety on public HTML)
# ---------------------------------------------------------------------------

def _h(v: Any) -> str:
    return html.escape(str(v), quote=True) if v is not None else ""


def _clean_html(raw: str) -> str:
    """Minimal sanitiser for rich_text — strip `<script>`/`<style>` and event
    handlers. TipTap/ProseMirror on the admin side already produces safe HTML;
    this is a defence-in-depth pass on the render path."""
    if not raw:
        return ""
    s = str(raw)
    s = re.sub(r"<script[\s\S]*?</script>", "", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", "", s, flags=re.I)
    s = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", s, flags=re.I)
    s = re.sub(r"\son\w+\s*=\s*'[^']*'", "", s, flags=re.I)
    s = re.sub(r"javascript:", "", s, flags=re.I)
    return s


# ---------------------------------------------------------------------------
# Per-block normalisers
# ---------------------------------------------------------------------------

def _norm_hero(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "hero",
        "eyebrow": _s(d.get("eyebrow"), 200),
        "title": _s(d.get("title"), 300),
        "subtitle": _s(d.get("subtitle"), 800),
        "image_url": _url(d.get("image_url")),
        "image_alt": _s(d.get("image_alt"), 200),
        "cta_label": _s(d.get("cta_label"), 100),
        "cta_href": _url(d.get("cta_href")),
        "secondary_cta_label": _s(d.get("secondary_cta_label"), 100),
        "secondary_cta_href": _url(d.get("secondary_cta_href")),
        "variant": _s(d.get("variant") or "default", 30),
    }


def _norm_rich_text(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "rich_text",
        "html": _clean_html(d.get("html") or ""),
        "align": _s(d.get("align") or "left", 10),
    }


def _norm_image(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "image",
        "url": _url(d.get("url")),
        "alt": _s(d.get("alt"), 300),
        "caption": _s(d.get("caption"), 500),
        "width": _int(d.get("width")),
        "height": _int(d.get("height")),
        "focus_x": _int(d.get("focus_x"), 50),
        "focus_y": _int(d.get("focus_y"), 50),
        "link_href": _url(d.get("link_href")),
    }


def _norm_gallery(d: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    for it in _list_of_dicts(d.get("items"))[:24]:
        u = _url(it.get("url"))
        if u:
            items.append({
                "url": u,
                "alt": _s(it.get("alt"), 300),
                "caption": _s(it.get("caption"), 300),
            })
    return {
        "type": "gallery",
        "layout": _s(d.get("layout") or "grid", 20),
        "items": items,
    }


def _norm_quote(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "quote",
        "text": _s(d.get("text"), 2000),
        "author": _s(d.get("author"), 200),
        "role": _s(d.get("role"), 200),
        "avatar_url": _url(d.get("avatar_url")),
    }


def _norm_cta(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "cta",
        "title": _s(d.get("title"), 300),
        "description": _s(d.get("description"), 800),
        "button_label": _s(d.get("button_label"), 100),
        "button_href": _url(d.get("button_href")),
        "variant": _s(d.get("variant") or "primary", 30),
        "align": _s(d.get("align") or "center", 10),
    }


def _norm_faq(d: Dict[str, Any]) -> Dict[str, Any]:
    inline_items = []
    for it in _list_of_dicts(d.get("items"))[:50]:
        q = _s(it.get("question"), 400)
        a = _clean_html(it.get("answer") or "")
        if q and a:
            inline_items.append({"question": q, "answer": a})
    # If items are provided inline, we use those; otherwise the block can
    # reference `faq_group` and be resolved at render-time from faq_items.
    return {
        "type": "faq",
        "title": _s(d.get("title"), 300),
        "faq_group": _s(d.get("faq_group") or "", 100),
        "items": inline_items,
    }


def _norm_process(d: Dict[str, Any]) -> Dict[str, Any]:
    steps = []
    for st in _list_of_dicts(d.get("steps"))[:20]:
        steps.append({
            "title": _s(st.get("title"), 200),
            "description": _s(st.get("description"), 800),
            "icon": _s(st.get("icon"), 50),
        })
    return {
        "type": "process",
        "title": _s(d.get("title"), 300),
        "description": _s(d.get("description"), 800),
        "steps": steps,
    }


def _norm_cards(d: Dict[str, Any]) -> Dict[str, Any]:
    cards = []
    for c in _list_of_dicts(d.get("cards"))[:24]:
        cards.append({
            "title": _s(c.get("title"), 200),
            "description": _s(c.get("description"), 800),
            "icon": _s(c.get("icon"), 50),
            "image_url": _url(c.get("image_url")),
            "href": _url(c.get("href")),
        })
    return {
        "type": "cards",
        "title": _s(d.get("title"), 300),
        "description": _s(d.get("description"), 800),
        "columns": max(1, min(4, _int(d.get("columns"), 3))),
        "cards": cards,
    }


def _norm_stats(d: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    for it in _list_of_dicts(d.get("items"))[:8]:
        items.append({
            "value": _s(it.get("value"), 40),
            "label": _s(it.get("label"), 200),
            "suffix": _s(it.get("suffix"), 20),
        })
    return {
        "type": "stats",
        "title": _s(d.get("title"), 300),
        "items": items,
    }


def _norm_table(d: Dict[str, Any]) -> Dict[str, Any]:
    headers = [
        _s(h, 200) for h in (d.get("headers") if isinstance(d.get("headers"), list) else [])
    ][:12]
    rows = []
    for r in (d.get("rows") if isinstance(d.get("rows"), list) else [])[:200]:
        if isinstance(r, list):
            rows.append([_s(c, 500) for c in r][:12])
    return {
        "type": "table",
        "title": _s(d.get("title"), 300),
        "headers": headers,
        "rows": rows,
    }


def _norm_related_links(d: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    for it in _list_of_dicts(d.get("items"))[:24]:
        href = _url(it.get("href"))
        label = _s(it.get("label"), 200)
        if href and label:
            items.append({
                "href": href,
                "label": label,
                "description": _s(it.get("description"), 500),
                "icon": _s(it.get("icon"), 50),
            })
    return {
        "type": "related_links",
        "title": _s(d.get("title"), 300),
        "items": items,
    }


# ---------------------------------------------------------------------------
# HTML renderers (server-side, used by prerender for bots)
# ---------------------------------------------------------------------------

def _r_hero(b: Dict[str, Any]) -> str:
    parts = [f'<section class="cms-hero cms-hero--{_h(b.get("variant"))}">']
    if b.get("eyebrow"):
        parts.append(f'<div class="eyebrow">{_h(b["eyebrow"])}</div>')
    if b.get("title"):
        parts.append(f'<h1>{_h(b["title"])}</h1>')
    if b.get("subtitle"):
        parts.append(f'<p class="subtitle">{_h(b["subtitle"])}</p>')
    if b.get("cta_href"):
        parts.append(f'<p><a class="btn primary" href="{_h(b["cta_href"])}">{_h(b.get("cta_label") or "Learn more")}</a>')
        if b.get("secondary_cta_href"):
            parts.append(f' <a class="btn secondary" href="{_h(b["secondary_cta_href"])}">{_h(b.get("secondary_cta_label") or "")}</a>')
        parts.append('</p>')
    if b.get("image_url"):
        parts.append(f'<img src="{_h(b["image_url"])}" alt="{_h(b.get("image_alt") or b.get("title"))}" loading="eager" fetchpriority="high">')
    parts.append('</section>')
    return "".join(parts)


def _r_rich_text(b: Dict[str, Any]) -> str:
    align = _h(b.get("align") or "left")
    return f'<div class="cms-rich-text" style="text-align:{align}">{b.get("html") or ""}</div>'


def _r_image(b: Dict[str, Any]) -> str:
    if not b.get("url"):
        return ""
    inner = f'<img src="{_h(b["url"])}" alt="{_h(b.get("alt") or "")}" loading="lazy"'
    if b.get("width"):
        inner += f' width="{int(b["width"])}"'
    if b.get("height"):
        inner += f' height="{int(b["height"])}"'
    inner += '>'
    if b.get("link_href"):
        inner = f'<a href="{_h(b["link_href"])}">{inner}</a>'
    cap = f'<figcaption>{_h(b["caption"])}</figcaption>' if b.get("caption") else ""
    return f'<figure class="cms-image">{inner}{cap}</figure>'


def _r_gallery(b: Dict[str, Any]) -> str:
    items = "".join(
        f'<figure><img src="{_h(i["url"])}" alt="{_h(i.get("alt") or "")}" loading="lazy">'
        + (f'<figcaption>{_h(i["caption"])}</figcaption>' if i.get("caption") else "")
        + '</figure>'
        for i in b.get("items") or []
    )
    return f'<section class="cms-gallery cms-gallery--{_h(b.get("layout") or "grid")}">{items}</section>'


def _r_quote(b: Dict[str, Any]) -> str:
    if not b.get("text"):
        return ""
    parts = [f'<blockquote class="cms-quote"><p>{_h(b["text"])}</p>']
    if b.get("author") or b.get("role"):
        parts.append('<footer>')
        if b.get("author"):
            parts.append(f'<strong>{_h(b["author"])}</strong>')
        if b.get("role"):
            parts.append(f' <span>{_h(b["role"])}</span>')
        parts.append('</footer>')
    parts.append('</blockquote>')
    return "".join(parts)


def _r_cta(b: Dict[str, Any]) -> str:
    parts = [f'<section class="cms-cta cms-cta--{_h(b.get("variant"))}" style="text-align:{_h(b.get("align") or "center")}">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    if b.get("description"):
        parts.append(f'<p>{_h(b["description"])}</p>')
    if b.get("button_href"):
        parts.append(f'<a class="btn" href="{_h(b["button_href"])}">{_h(b.get("button_label") or "Contact")}</a>')
    parts.append('</section>')
    return "".join(parts)


def _r_faq(b: Dict[str, Any], resolver: Optional[Callable[[str], List[Dict[str, str]]]] = None) -> str:
    items = b.get("items") or []
    if not items and b.get("faq_group") and resolver:
        items = resolver(b["faq_group"]) or []
    if not items:
        return ""
    parts = ['<section class="cms-faq">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    for it in items:
        parts.append(
            f'<details><summary>{_h(it.get("question"))}</summary>'
            f'<div>{it.get("answer") or ""}</div></details>'
        )
    parts.append('</section>')
    return "".join(parts)


def _r_process(b: Dict[str, Any]) -> str:
    parts = ['<section class="cms-process">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    if b.get("description"):
        parts.append(f'<p>{_h(b["description"])}</p>')
    parts.append('<ol class="steps">')
    for st in b.get("steps") or []:
        parts.append('<li>')
        if st.get("title"):
            parts.append(f'<h3>{_h(st["title"])}</h3>')
        if st.get("description"):
            parts.append(f'<p>{_h(st["description"])}</p>')
        parts.append('</li>')
    parts.append('</ol></section>')
    return "".join(parts)


def _r_cards(b: Dict[str, Any]) -> str:
    parts = [f'<section class="cms-cards cms-cards--cols-{int(b.get("columns") or 3)}">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    if b.get("description"):
        parts.append(f'<p>{_h(b["description"])}</p>')
    parts.append('<div class="grid">')
    for c in b.get("cards") or []:
        parts.append('<article class="card">')
        if c.get("image_url"):
            parts.append(f'<img src="{_h(c["image_url"])}" alt="{_h(c.get("title") or "")}" loading="lazy">')
        if c.get("title"):
            title_html = _h(c["title"])
            if c.get("href"):
                title_html = f'<a href="{_h(c["href"])}">{title_html}</a>'
            parts.append(f'<h3>{title_html}</h3>')
        if c.get("description"):
            parts.append(f'<p>{_h(c["description"])}</p>')
        parts.append('</article>')
    parts.append('</div></section>')
    return "".join(parts)


def _r_stats(b: Dict[str, Any]) -> str:
    parts = ['<section class="cms-stats">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    parts.append('<div class="grid">')
    for it in b.get("items") or []:
        parts.append(
            f'<div class="stat"><strong class="value">{_h(it.get("value"))}{_h(it.get("suffix") or "")}</strong>'
            f'<span class="label">{_h(it.get("label"))}</span></div>'
        )
    parts.append('</div></section>')
    return "".join(parts)


def _r_table(b: Dict[str, Any]) -> str:
    parts = ['<section class="cms-table">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    parts.append('<table>')
    if b.get("headers"):
        parts.append('<thead><tr>' + "".join(f'<th>{_h(h)}</th>' for h in b["headers"]) + '</tr></thead>')
    parts.append('<tbody>')
    for r in b.get("rows") or []:
        parts.append('<tr>' + "".join(f'<td>{_h(c)}</td>' for c in r) + '</tr>')
    parts.append('</tbody></table></section>')
    return "".join(parts)


def _r_related_links(b: Dict[str, Any]) -> str:
    parts = ['<section class="cms-related">']
    if b.get("title"):
        parts.append(f'<h2>{_h(b["title"])}</h2>')
    parts.append('<ul>')
    for it in b.get("items") or []:
        parts.append(f'<li><a href="{_h(it["href"])}">{_h(it["label"])}</a>')
        if it.get("description"):
            parts.append(f' — <span>{_h(it["description"])}</span>')
        parts.append('</li>')
    parts.append('</ul></section>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

BlockNormaliser = Callable[[Dict[str, Any]], Dict[str, Any]]
BlockRenderer = Callable[[Dict[str, Any]], str]

BLOCK_REGISTRY: Dict[str, Tuple[BlockNormaliser, BlockRenderer]] = {
    "hero": (_norm_hero, _r_hero),
    "rich_text": (_norm_rich_text, _r_rich_text),
    "image": (_norm_image, _r_image),
    "gallery": (_norm_gallery, _r_gallery),
    "quote": (_norm_quote, _r_quote),
    "cta": (_norm_cta, _r_cta),
    "faq": (_norm_faq, _r_faq),
    "process": (_norm_process, _r_process),
    "cards": (_norm_cards, _r_cards),
    "stats": (_norm_stats, _r_stats),
    "table": (_norm_table, _r_table),
    "related_links": (_norm_related_links, _r_related_links),
}


def list_block_types() -> List[str]:
    return list(BLOCK_REGISTRY.keys())


def validate_blocks(raw_blocks: Any) -> List[Dict[str, Any]]:
    """Normalise/whitelist an incoming blocks[] array. Unknown block types
    are dropped silently to keep the admin form forgiving."""
    if not isinstance(raw_blocks, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, blk in enumerate(raw_blocks):
        if not isinstance(blk, dict):
            continue
        t = str(blk.get("type") or "").lower()
        norm, _renderer = BLOCK_REGISTRY.get(t, (None, None))
        if not norm:
            continue
        cleaned = norm(blk)
        cleaned["id"] = _s(blk.get("id") or f"blk_{i}", 60)
        out.append(cleaned)
    return out


def render_blocks_html(blocks: List[Dict[str, Any]], faq_resolver: Optional[Callable[[str], List[Dict[str, str]]]] = None) -> str:
    """Render a normalised block array to HTML string (used by prerender)."""
    if not blocks:
        return ""
    parts: List[str] = []
    for b in blocks:
        t = b.get("type")
        _, renderer = BLOCK_REGISTRY.get(t, (None, None))
        if not renderer:
            continue
        try:
            if t == "faq":
                parts.append(_r_faq(b, resolver=faq_resolver))
            else:
                parts.append(renderer(b))
        except Exception:
            # Never fail the whole page on one bad block.
            continue
    return "".join(parts)
