"""Content Platform — Phase D1.

Provides a block-based CMS layered on top of the existing SEO Center. Every
public page (marketing site, waste directory, services, industries, blog,
landings) reads its body from `content_pages`; every waste code enriches its
detail view via the same block system.

Key principles
--------------
* **Versioned** — every write snapshots the previous state into
  `content_versions`; restore = clone → new draft.
* **Publish-gated** — only `status == "published"` bubbles up to public API,
  sitemap and prerender.
* **Cache-aware** — every write invalidates the prerender cache for the
  affected path.
* **AI-Guard-ready** — the model already carries `ai_status`,
  `human_review_required`, `reviewer_id`, `reviewed_at` so Phase D2 can wire
  the AI pipeline without a migration.
"""
from app.content.blocks import BLOCK_REGISTRY, validate_blocks  # noqa: F401
from app.content.service import (  # noqa: F401
    ContentPageService,
    ContentVersionService,
    MediaLibraryService,
    FAQService,
)
