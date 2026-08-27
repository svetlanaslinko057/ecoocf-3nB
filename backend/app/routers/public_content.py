"""Public content router — Phase D1.

Endpoints (`/api/content`):

    GET /page?path=/services/battery&lang=uk   published page (blocks tree)
    GET /pages?lang=uk&kind=service            published pages listing (SEO)
    GET /faq?group=warranty&lang=uk            published FAQ items
    GET /faq?page_path=/waste&lang=uk

Only `status == "published"` content is exposed. This is what the client-side
react renderer + the prerender engine call to hydrate a page's body.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.content.service import ContentPageService, FAQService

router = APIRouter(prefix="/api/content", tags=["public-content"])


def _db():
    from app.core.db_runtime import get_db
    return get_db()


@router.get("/page")
async def get_public_page(path: str = Query(...), lang: str = Query("uk")) -> Dict[str, Any]:
    page = await ContentPageService(_db()).get_public(path, lang)
    if not page:
        raise HTTPException(status_code=404, detail="page not published")
    # Strip sensitive audit metadata before public exposure
    for k in ("created_by", "updated_by", "published_by", "reviewer_id", "ai_status", "human_review_required", "reviewed_at"):
        page.pop(k, None)
    return {"page": page}


@router.get("/pages")
async def list_public_pages(lang: str = Query("uk"),
                             kind: Optional[str] = Query(None),
                             limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    svc = ContentPageService(_db())
    items = await svc.list_pages(status="published", kind=kind, lang=lang, limit=limit)
    # Publicly expose only what's needed for indexing/nav
    out = []
    for p in items:
        out.append({
            "id": p.get("id"),
            "path": p.get("path"),
            "lang": p.get("lang"),
            "slug": p.get("slug"),
            "kind": p.get("kind"),
            "title": p.get("title"),
            "summary": p.get("summary"),
            "seo": p.get("seo"),
            "cms": p.get("cms"),
            "updated_at": p.get("updated_at"),
            "published_at": p.get("published_at"),
        })
    return {"items": out, "count": len(out)}


@router.get("/faq")
async def list_public_faq(group: Optional[str] = Query(None),
                          page_path: Optional[str] = Query(None),
                          lang: str = Query("uk"),
                          limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    svc = FAQService(_db())
    items = await svc.list(group=group, page_path=page_path, lang=lang,
                            published_only=True, limit=limit)
    # public payload: strip audit
    out = []
    for f in items:
        out.append({
            "id": f.get("id"),
            "question": f.get("question"),
            "answer": f.get("answer"),
            "group": f.get("group"),
            "page_path": f.get("page_path"),
            "lang": f.get("lang"),
            "order": f.get("order"),
            "tags": f.get("tags"),
        })
    return {"items": out, "count": len(out)}
