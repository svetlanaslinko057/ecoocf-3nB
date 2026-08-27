"""Wave 5B-v2: PDF engine package.

Keeps the legacy ``/api/pdf/*`` URL surface intact while moving the
implementation behind a small ``PdfRenderer`` abstraction. Templates
are Jinja2 HTML files under ``templates/`` so design tweaks (logo,
colours, signatures, future QR/e-sign blocks) live outside Python code.

The original module-level helpers (``_render_contract_html`` etc.) used
by legacy imports remain available for unit tests — they now wrap the
Jinja2 renderer.
"""
from __future__ import annotations

from .renderer import (
    PdfRenderer,
    WeasyRenderer,
    get_default_renderer,
    render_pdf,
)
from .router import router

__all__ = [
    "PdfRenderer", "WeasyRenderer", "get_default_renderer",
    "render_pdf", "router",
]
