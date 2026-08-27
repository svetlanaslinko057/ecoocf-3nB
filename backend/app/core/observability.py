"""
app.core.observability — Wave 3 / Phase B3 operational hardening
==================================================================

Minimal, additive observability layer. Built per stakeholder directive
2026-05-24:

  > "Без этого любой production через полгода умирает молча."
  > Sentry / uptime / Mongo slow query log / parser failure alerts.

DESIGN INVARIANTS
-----------------
1. ZERO impact when disabled. All hooks short-circuit if the relevant
   env var is unset.
2. NEVER raises. Observability that crashes the host is worse than no
   observability at all — every helper here is wrapped in try/except.
3. NO new heavy dependencies. We use the optional `sentry-sdk` if
   already installed, otherwise we fall back to structured logger output
   that any log aggregator can pick up.
4. NEVER PII. The events / slow-query buffers store no email, no name,
   no IP, no full URL with query params. VIN is the closest thing to
   user-identifying data, and only the last 6 chars are stored.
5. Bounded memory. All in-process buffers are RingBuffers — bounded
   capacity, oldest entries fall off automatically.

PUBLIC SURFACE
--------------
- init_observability(app)                         — call once from startup
- report_error(err, *, context: dict | None=None) — wrap any unexpected exception
- record_slow_query(coll, op, duration_ms, …)     — Mongo slow query event
- record_parser_failure(parser, target, err)      — auction-source parser failure
- record_event(event_name, props=None)            — privacy-respecting user observation
- get_health_snapshot()                           — read-only state for /api/system/health
- get_recent_errors()                             — read-only ring buffer for /api/_internal/issues
- get_event_summary()                             — aggregated user-observation counters

This module is consumed by:
  - server.py startup (init_observability + new endpoints — see below)
  - bitmotors_scraper.py / westmotors / lemon (record_parser_failure)
  - app/core/db_runtime.py if/when we wrap motor ops (record_slow_query)
"""
from __future__ import annotations

import logging
import os
import time
import threading
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("bibi.observability")

# ── Tunables (all env-driven, all optional) ──────────────────────────────
SLOW_QUERY_MS = int(os.environ.get("BIBI_SLOW_QUERY_MS", "300"))
ERROR_BUFFER  = int(os.environ.get("BIBI_ERROR_BUFFER", "200"))
SLOW_BUFFER   = int(os.environ.get("BIBI_SLOW_BUFFER",  "200"))
EVENT_BUFFER  = int(os.environ.get("BIBI_EVENT_BUFFER", "1000"))
PARSER_BUFFER = int(os.environ.get("BIBI_PARSER_BUFFER", "200"))
ALLOWED_EVENTS = {
    # ── User-observation whitelist (privacy-respecting catalogue events)
    "catalog_filter_changed",   # filter usage
    "catalog_filter_reset",
    "catalog_search_abandoned", # user typed but didn't pick a result
    "catalog_search_submitted",
    "catalog_show_more",
    "catalog_sort_changed",
    "detail_view",              # most viewed cars
    "detail_bounce",             # user opened detail, left within 3s
    "vin_check_submitted",
    "vin_check_no_result",
    "calculator_used",
    "contact_us_clicked",
    "consultation_requested",
}

# ── Sentry integration (optional) ────────────────────────────────────────
_sentry_enabled = False
try:
    SENTRY_DSN = (os.environ.get("SENTRY_DSN") or "").strip()
    if SENTRY_DSN:
        import sentry_sdk  # noqa: F401  (sdk is already a transitive dep)
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=os.environ.get("BIBI_ENV", "production"),
            release=os.environ.get("BIBI_RELEASE", "v3.2.1-wave3-freeze"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.0")),
            send_default_pii=False,
        )
        _sentry_enabled = True
        logger.info("[observability] Sentry initialised — DSN active")
except Exception as e:   # noqa: BLE001 — observability MUST NOT crash boot
    logger.warning(f"[observability] Sentry init skipped: {e}")
    _sentry_enabled = False


# ─────────────────────────────────────────────────────────────────────────
# In-process ring buffers (bounded, thread-safe)
# ─────────────────────────────────────────────────────────────────────────
_lock = threading.RLock()
_errors:    Deque[Dict[str, Any]] = deque(maxlen=ERROR_BUFFER)
_slow:      Deque[Dict[str, Any]] = deque(maxlen=SLOW_BUFFER)
_parserfx:  Deque[Dict[str, Any]] = deque(maxlen=PARSER_BUFFER)
_events:    Deque[Dict[str, Any]] = deque(maxlen=EVENT_BUFFER)

# Aggregated counters (cheap, read-only by /admin endpoint)
_event_counts:   Counter = Counter()
_error_counts:   Counter = Counter()  # by exc type
_parser_counts:  Counter = Counter()  # by parser
_filter_counts:  Counter = Counter()  # which filters are actually used
_view_counts:    Counter = Counter()  # most-viewed cars (last 1000 unique VIN suffixes)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_vin(v: Optional[str]) -> Optional[str]:
    """Keep only last 6 chars of VIN for privacy."""
    if not v or not isinstance(v, str):
        return None
    v = v.strip().upper()
    if len(v) <= 6:
        return v
    return "…" + v[-6:]


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────
def init_observability(app=None) -> None:
    """Idempotent boot hook. Called from server.py startup."""
    logger.info(
        f"[observability] ready · sentry={_sentry_enabled} "
        f"slow_query_ms={SLOW_QUERY_MS} buffers="
        f"err{ERROR_BUFFER}/slow{SLOW_BUFFER}/event{EVENT_BUFFER}"
    )


def report_error(err: BaseException, *, context: Optional[Dict[str, Any]] = None) -> None:
    """Best-effort: log + Sentry capture + ring buffer."""
    try:
        ctx = dict(context or {})
        ctx.setdefault("ts", _utcnow())
        ctx["error_type"] = type(err).__name__
        ctx["error_msg"]  = str(err)[:500]
        with _lock:
            _errors.append(ctx)
            _error_counts[ctx["error_type"]] += 1
        logger.error(f"[observability] {ctx['error_type']}: {ctx['error_msg']} ctx={context!r}")
        if _sentry_enabled:
            try:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    for k, v in (context or {}).items():
                        try:
                            scope.set_extra(k, v)
                        except Exception:   # noqa: BLE001
                            pass
                    sentry_sdk.capture_exception(err)
            except Exception:   # noqa: BLE001
                pass
    except Exception:   # noqa: BLE001 — observability MUST NOT crash callers
        pass


def record_slow_query(
    coll: str, op: str, duration_ms: float,
    query_preview: Optional[str] = None,
) -> None:
    """Log + buffer a Mongo operation that took > SLOW_QUERY_MS."""
    try:
        if duration_ms < SLOW_QUERY_MS:
            return
        entry = {
            "ts": _utcnow(),
            "coll": coll, "op": op,
            "duration_ms": round(duration_ms, 1),
            "query_preview": (query_preview or "")[:200],
        }
        with _lock:
            _slow.append(entry)
        logger.warning(
            f"[slow-query] {coll}.{op} {duration_ms:.0f}ms — {entry['query_preview']!r}"
        )
    except Exception:   # noqa: BLE001
        pass


def record_parser_failure(parser: str, target: Optional[str], err: BaseException) -> None:
    """Count + buffer a scraper / source-parser failure."""
    try:
        entry = {
            "ts": _utcnow(),
            "parser": parser,
            "target": (target or "")[:200],
            "error_type": type(err).__name__,
            "error_msg": str(err)[:300],
        }
        with _lock:
            _parserfx.append(entry)
            _parser_counts[parser] += 1
        logger.warning(f"[parser-fail] {parser} on {entry['target']!r}: {entry['error_type']}: {entry['error_msg']}")
        if _sentry_enabled:
            try:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("parser", parser)
                    scope.set_extra("target", target)
                    sentry_sdk.capture_exception(err)
            except Exception:   # noqa: BLE001
                pass
    except Exception:   # noqa: BLE001
        pass


def record_event(event_name: str, props: Optional[Dict[str, Any]] = None) -> bool:
    """Privacy-respecting user-observation event.

    Returns True if accepted, False if rejected (unknown event / bad input).
    Frontend sends these via POST /api/events/track.
    """
    try:
        if not event_name or event_name not in ALLOWED_EVENTS:
            return False
        props = props if isinstance(props, dict) else {}
        # Strip anything that smells like PII before we keep it.
        clean: Dict[str, Any] = {}
        for k, v in props.items():
            if k.lower() in {"email", "phone", "name", "ip", "address",
                             "password", "token", "session"}:
                continue
            if k.lower() == "vin":
                clean[k] = _redact_vin(v if isinstance(v, str) else None)
                continue
            # Truncate long strings to prevent log bombs.
            if isinstance(v, str) and len(v) > 200:
                v = v[:200]
            clean[k] = v
        entry = {"ts": _utcnow(), "event": event_name, "props": clean}
        with _lock:
            _events.append(entry)
            _event_counts[event_name] += 1
            # Aggregated breakdowns for the most useful events.
            if event_name == "catalog_filter_changed":
                f = clean.get("filter")
                if isinstance(f, str):
                    _filter_counts[f] += 1
            elif event_name == "detail_view":
                vin_red = clean.get("vin")
                if vin_red:
                    _view_counts[vin_red] += 1
        return True
    except Exception:   # noqa: BLE001
        return False


# ─────────────────────────────────────────────────────────────────────────
# Read-only accessors (consumed by /api/system/health + admin endpoints)
# ─────────────────────────────────────────────────────────────────────────
def get_health_snapshot() -> Dict[str, Any]:
    """Read-only operational fingerprint for /api/system/health."""
    with _lock:
        return {
            "sentry_enabled": _sentry_enabled,
            "slow_query_threshold_ms": SLOW_QUERY_MS,
            "errors_last_n":        len(_errors),
            "slow_queries_last_n":  len(_slow),
            "parser_failures_last_n": len(_parserfx),
            "events_last_n":        len(_events),
            "top_error_types": dict(_error_counts.most_common(5)),
            "top_parser_failures": dict(_parser_counts.most_common(5)),
        }


def get_recent_errors(limit: int = 50) -> List[Dict[str, Any]]:
    with _lock:
        return list(_errors)[-limit:]


def get_recent_slow_queries(limit: int = 50) -> List[Dict[str, Any]]:
    with _lock:
        return list(_slow)[-limit:]


def get_recent_parser_failures(limit: int = 50) -> List[Dict[str, Any]]:
    with _lock:
        return list(_parserfx)[-limit:]


def get_event_summary(top_n: int = 20) -> Dict[str, Any]:
    with _lock:
        return {
            "events_total":   sum(_event_counts.values()),
            "by_event":       dict(_event_counts.most_common(top_n)),
            "top_filters":    dict(_filter_counts.most_common(top_n)),
            "top_viewed_vin_suffixes": dict(_view_counts.most_common(top_n)),
            "buffer_size":    len(_events),
        }


__all__ = [
    "init_observability",
    "report_error",
    "record_slow_query",
    "record_parser_failure",
    "record_event",
    "get_health_snapshot",
    "get_recent_errors",
    "get_recent_slow_queries",
    "get_recent_parser_failures",
    "get_event_summary",
    "ALLOWED_EVENTS",
]
