"""
PHASE SECURITY — Wave S3.2 — Rate limiting (in-memory, slowapi/limits engine).

A single HTTP edge that throttles abusive traffic on sensitive routes BEFORE
the access-control gate / business logic runs. Only the explicitly-listed
routes below are limited; everything else (including the extension HMAC tier
and internal server-to-server calls) is left untouched by design.

Design decisions (approved):
  • client key  → X-Forwarded-For (first hop) → X-Real-IP → client.host
  • on breach   → HTTP 429 JSON {detail, retry_after} + standard headers
  • whitelist   → /api/ext/*, /api/vesselfinder/* and any unlisted route
  • engine      → limits.MovingWindowRateLimiter + MemoryStorage (per worker)

`classify_rate_rule(method, path)` is pure (no I/O) → trivially unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Pattern, Set, Tuple

from limits import RateLimitItem, RateLimitItemPerMinute
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

# ── engine (process-local; backend runs a single uvicorn worker) ──────────
_storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(_storage)


@dataclass(frozen=True)
class _Rule:
    methods: Set[str]
    pattern: Pattern
    item: RateLimitItem
    name: str


def _r(methods: str, pattern: str, amount: int, per_minutes: int, name: str) -> _Rule:
    return _Rule(
        methods={m.strip().upper() for m in methods.split(",")},
        pattern=re.compile(pattern),
        item=RateLimitItemPerMinute(amount, per_minutes),
        name=name,
    )


# ── rule table (FIRST match wins; order specific → generic) ───────────────
# Tier 1 — critical auth (brute-force / OTP guessing / enumeration of creds)
# Tier 2 — resource-heavy (CPU / network / disk)
# Tier 3 — business-entity creation (spam / abuse)
# Tier 4 — soft anti-enumeration on single-entity reads (post-IDOR hardening)
RULES: List[_Rule] = [
    # ── Tier 1 ────────────────────────────────────────────────────────────
    _r("POST", r"/api/auth/login", 5, 1, "auth-login"),
    _r("POST", r"/api/customer-auth/login", 5, 1, "customer-login"),
    _r("POST", r"/api/auth/2fa/verify", 5, 1, "twofa-verify"),
    _r("POST", r"/api/auth/email-otp/(request|verify)", 5, 1, "email-otp"),
    _r("POST", r"/api/customer-auth/(register|verify-email|resend-email-code)", 5, 1, "customer-otp"),
    _r("POST", r"/api/customer-auth/(forgot-password|reset-password)", 3, 15, "password-reset"),

    # ── Tier 2 ────────────────────────────────────────────────────────────
    _r("GET,POST", r"/api/(vin|vin-price|vin-resolver|vin-unified)(/.*)?", 30, 1, "vin-search"),
    _r("GET", r"/api/v2/search(/.*)?", 30, 1, "vin-search"),
    _r("GET,POST", r"/api/calculator/(calculate|quote|calculate-with-visibility)(/.*)?", 30, 1, "calculator"),
    _r("POST", r"/api/invoices/[^/]+/(contract|invoice-pdf)", 20, 1, "doc-generate"),
    # upload endpoints (customer folder uploads + admin image uploads)
    _r("POST", r"/api/customers/[^/]+/folders/[^/]+/upload", 20, 1, "upload"),
    _r("POST", r"/api/admin/site-info/upload-[a-z-]+", 20, 1, "upload"),
    _r("POST", r"/api/admin/blog/upload-image", 20, 1, "upload"),

    # ── Tier 3 ────────────────────────────────────────────────────────────
    _r("POST", r"/api/customers", 10, 1, "customer-create"),
    _r("POST", r"/api/leads", 20, 1, "lead-create"),
    _r("POST", r"/api/(quick-leads|public/leads|leads/consultation)(/.*)?", 20, 1, "lead-create"),
    _r("POST", r"/api/deals", 20, 1, "deal-create"),
    _r("POST", r"/api/invoices/(create|create-from-package)", 20, 1, "invoice-create"),

    # ── Tier 4 — single-entity reads (anti-enumeration) ───────────────────
    _r("GET", r"/api/customers/[^/]+", 120, 1, "entity-read"),
    _r("GET", r"/api/leads/[^/]+", 120, 1, "entity-read"),
    _r("GET", r"/api/deals/[^/]+", 120, 1, "entity-read"),
    _r("GET", r"/api/invoices/[^/]+", 120, 1, "entity-read"),
]

# Never rate-limit these (extension HMAC tier + server-to-server). Matched
# routes are already opt-in above, but this is a belt-and-braces guard so a
# future rule can't accidentally throttle the extension/worker plane.
_WHITELIST: Pattern = re.compile(r"/api/(ext|vesselfinder)(/.*)?")


def _norm(path: str) -> str:
    p = path or "/"
    if len(p) > 1 and p.endswith("/"):
        p = p.rstrip("/") or "/"
    return p


def classify_rate_rule(method: str, path: str) -> Optional[_Rule]:
    """Return the first matching rule for (method, path), or None (unlimited)."""
    p = _norm(path)
    if _WHITELIST.fullmatch(p):
        return None
    m = (method or "").upper()
    for rule in RULES:
        if m in rule.methods and rule.pattern.fullmatch(p):
            return rule
    return None


def client_ip(request) -> str:
    """Resolve the real client IP behind the Kubernetes Ingress / proxy.

    Order: X-Forwarded-For (left-most) → X-Real-IP → socket peer.
    """
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xri = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
    if xri:
        return xri.strip()
    try:
        return request.client.host or "unknown"
    except Exception:
        return "unknown"


def check_and_consume(method: str, path: str, ip: str) -> Tuple[bool, Optional[_Rule], int, int]:
    """Apply the matching rule.

    Returns (allowed, rule, remaining, reset_after_seconds).
    If no rule matches, returns (True, None, -1, 0).
    """
    rule = classify_rate_rule(method, path)
    if rule is None:
        return True, None, -1, 0

    identifiers = (rule.name, ip)
    allowed = _limiter.hit(rule.item, *identifiers)
    reset_ts, remaining = _limiter.get_window_stats(rule.item, *identifiers)
    import time as _time
    reset_after = max(0, int(reset_ts - _time.time()))
    return allowed, rule, max(0, remaining), reset_after
