"""
PHASE SECURITY — Wave S3.3 — Security headers (global) + CSP (Report-Only).

Approved rollout:
  • A safe set of headers is ENFORCED globally on every response.
  • CSP ships in **Report-Only** first (HTML responses only) so it cannot break
    the React app / Stripe / PDF preview / File Manager — violations are POSTed
    to `/api/security/csp-report` (stored 30 days) to inform a later strict CSP.
  • HSTS is intentionally NOT set here (enabled only after the prod cut-over to
    bibicars.org over HTTPS).
  • Private API responses (staff/customer/extension tiers) get `Cache-Control:
    no-store` so authenticated payloads are never cached by shared proxies.

All helpers are pure → unit-testable without a running server.
"""
from __future__ import annotations

from typing import Dict

CSP_REPORT_PATH = "/api/security/csp-report"

# ── enforced on EVERY response (safe, non-breaking) ───────────────────────
STATIC_SECURITY_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), usb=(), payment=()",
}

# ── CSP target policy — shipped Report-Only (HTML only) ───────────────────
# Third-party origins the storefront/cabinet legitimately uses are allowlisted
# (Stripe + Google sign-in). 'unsafe-inline' is permitted for STYLES only
# (Tailwind/React inline styles); scripts are NOT given unsafe-inline so the
# reports reveal exactly what must be nonced before we enforce.
_CSP_REPORT_ONLY = "; ".join([
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'self'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    "script-src 'self' https://js.stripe.com https://accounts.google.com "
    "https://apis.google.com https://www.googletagmanager.com",
    "connect-src 'self' https://api.stripe.com https://*.stripe.com "
    "https://accounts.google.com https://www.google-analytics.com",
    "frame-src 'self' https://js.stripe.com https://hooks.stripe.com "
    "https://checkout.stripe.com https://accounts.google.com",
    "worker-src 'self' blob:",
    "form-action 'self'",
    "report-uri " + CSP_REPORT_PATH,
])


def csp_report_only_value() -> str:
    return _CSP_REPORT_ONLY


def is_html_response(content_type: str) -> bool:
    """True when the response is an HTML document (CSP applies to these)."""
    return "text/html" in (content_type or "").lower()
