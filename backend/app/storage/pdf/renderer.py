"""PdfRenderer abstraction.

WeasyPrint is the primary renderer right now, but contracts/acts/invoices
will soon need richer features (electronic signatures, QR codes, stamps,
specific government templates). Keeping renderers behind an interface
lets us drop in a different engine (or a hybrid) without touching the
router / repository layers.

Templates are loaded from ``app/storage/pdf/templates/`` via Jinja2.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _fmt_money(v: Any, cur: str = "UAH") -> str:
    try:
        n = float(v or 0)
    except Exception:
        return f"— {cur}"
    return f"{n:,.2f}".replace(",", " ") + f" {cur}"


def _fmt_date(v: Any) -> str:
    if not v:
        return "—"
    if isinstance(v, datetime):
        return v.strftime("%d.%m.%Y")
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.strftime("%d.%m.%Y")
    except Exception:
        return str(v)


def _build_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters["money"] = _fmt_money
    env.filters["date_ua"] = _fmt_date
    return env


_env: Optional[Environment] = None


def _env_get() -> Environment:
    global _env
    if _env is None:
        _env = _build_env()
    return _env


class PdfRenderer(ABC):
    name: str = "abstract"

    @abstractmethod
    def render(self, template_name: str, context: Dict[str, Any]) -> bytes:
        """Render ``template_name`` with ``context`` to PDF bytes."""


class WeasyRenderer(PdfRenderer):
    name = "weasyprint"

    def render(self, template_name: str, context: Dict[str, Any]) -> bytes:
        from weasyprint import HTML  # imported lazily — heavy native deps
        tmpl = _env_get().get_template(template_name)
        html = tmpl.render(**context)
        return HTML(string=html).write_pdf()


_default: Optional[PdfRenderer] = None


def get_default_renderer() -> PdfRenderer:
    global _default
    if _default is None:
        _default = WeasyRenderer()
    return _default


def render_pdf(template_name: str, context: Dict[str, Any], *, renderer: Optional[PdfRenderer] = None) -> bytes:
    return (renderer or get_default_renderer()).render(template_name, context)
