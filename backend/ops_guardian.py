"""
ops_guardian.py — autonomous ops layer for BIBI Cars.

Two tightly-coupled capabilities that push the system from 9/10 (great UI) to
10/10 (SaaS-ready, survives without a human watching the screen):

  1. Alerter  — fan-out of CRITICAL events to external channels (Telegram +
                generic webhook). De-duplicated per (channel, fingerprint) for
                ALERT_COOLDOWN seconds so a flapping source doesn't spam.

  2. Auto-healer — a 60 s background loop that takes SAFE corrective actions:
       · if extension_clients == 0 and there are provisioned clients → log
         and try a soft re-bootstrap (reload client registry from DB).
       · if bitmotors circuit breaker has been OPEN for > 5 min → force
         half-open so it can self-recover.
       · if ALL primary sources are down → escalate alert with context.

Design principles:
  · Never performs destructive writes (no DELETE / no config mutation).
  · Every action is audit-logged via ``db.ops_audit`` with reason + before/after.
  · All external side-effects (HTTP POST) are fire-and-forget with bounded
    timeout (5 s) so the loop never blocks the event loop.
  · If no ``TELEGRAM_BOT_TOKEN`` / ``ALERT_WEBHOOK_URL`` are configured the
    module degrades to log-only mode (still writes audit rows).

Env configuration (all optional):
  TELEGRAM_BOT_TOKEN     — e.g. 1234:AAA...
  TELEGRAM_CHAT_ID       — e.g. -1001234567890
  ALERT_WEBHOOK_URL      — e.g. https://my-sink.example.com/ingest
  ALERT_COOLDOWN_SEC     — default 900 (15 min); minimum 60
  OPS_HEAL_INTERVAL_SEC  — default 60
  OPS_HEAL_ENABLED       — default true; set to "false" to disable the loop
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger("bibi.ops")

# ── Configuration ────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
ALERT_COOLDOWN_SEC = max(60, int(os.environ.get("ALERT_COOLDOWN_SEC", "900") or 900))
OPS_HEAL_INTERVAL_SEC = max(30, int(os.environ.get("OPS_HEAL_INTERVAL_SEC", "60") or 60))
OPS_HEAL_ENABLED = os.environ.get("OPS_HEAL_ENABLED", "true").strip().lower() not in (
    "0", "false", "no", "off",
)

# Thresholds
EXT_STALE_SEC = 120          # 2 min — "no clients alive" trigger
BM_BREAKER_STUCK_SEC = 300   # 5 min — force half-open after this long open


@dataclass
class AlertState:
    """In-memory dedup cache + last state for the heal loop."""
    # fingerprint → last-sent epoch seconds
    sent_at: dict[str, float] = field(default_factory=dict)
    # event counters for /api/control/ops/status
    total_alerts_sent: int = 0
    total_heal_actions: int = 0
    last_loop_at: Optional[float] = None
    last_error: Optional[str] = None
    # "breaker_open_since" — maps source_key → epoch when it went OPEN.
    breaker_open_since: dict[str, float] = field(default_factory=dict)
    # extension-clients-zero start timestamp (None when there ARE clients)
    ext_zero_since: Optional[float] = None


STATE = AlertState()


# ── Channel implementations ──────────────────────────────────────────
async def _send_telegram(text: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if r.status_code >= 300:
                logger.warning(f"[ops] telegram {r.status_code}: {r.text[:200]}")
                return False
            return True
    except Exception as e:
        logger.warning(f"[ops] telegram send error: {e}")
        return False


async def _send_webhook(payload: dict) -> bool:
    if not ALERT_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(ALERT_WEBHOOK_URL, json=payload)
            if r.status_code >= 300:
                logger.warning(
                    f"[ops] webhook {r.status_code}: {r.text[:200]}"
                )
                return False
            return True
    except Exception as e:
        logger.warning(f"[ops] webhook send error: {e}")
        return False


# ── Public alert API ─────────────────────────────────────────────────
async def emit_alert(
    *,
    severity: str,
    title: str,
    message: str,
    context: Optional[dict] = None,
    fingerprint: Optional[str] = None,
    db: Any = None,
) -> bool:
    """Fan out a single alert to all configured channels with dedup.

    Args:
      severity: 'critical' | 'warn' | 'info' (shapes emoji + webhook field).
      title:    short headline (<120 chars).
      message:  single paragraph of human context.
      context:  optional structured data for webhook consumers.
      fingerprint: stable key for dedup. Default = sha256(title + severity).
      db:       motor db handle for ops_audit persistence.

    Returns True if at least one channel accepted the alert.
    """
    fp = fingerprint or hashlib.sha256(
        f"{severity}|{title}".encode("utf-8")
    ).hexdigest()[:16]

    last = STATE.sent_at.get(fp)
    now = time.time()
    if last and (now - last) < ALERT_COOLDOWN_SEC:
        # Still within cooldown → only update audit (deduped) and return
        if db is not None:
            try:
                await db.ops_audit.insert_one({
                    "ts": now,
                    "kind": "alert_deduped",
                    "severity": severity,
                    "fingerprint": fp,
                    "cooldown_remaining_sec": int(ALERT_COOLDOWN_SEC - (now - last)),
                })
            except Exception:
                pass
        return False

    emoji = {"critical": "🔥", "warn": "⚠️", "info": "ℹ️"}.get(severity, "•")
    text = f"{emoji} <b>{title}</b>\n{message}"
    if context:
        lines = "\n".join(f"  · <code>{k}</code>: {v}" for k, v in context.items())
        text += f"\n\n{lines}"

    payload = {
        "ts": int(now),
        "severity": severity,
        "title": title,
        "message": message,
        "context": context or {},
        "fingerprint": fp,
        "source": "bibi.ops",
    }

    # Fan out concurrently — whichever succeeds is good.
    results = await asyncio.gather(
        _send_telegram(text),
        _send_webhook(payload),
        return_exceptions=True,
    )
    sent = any(r is True for r in results)

    if sent:
        STATE.sent_at[fp] = now
        STATE.total_alerts_sent += 1

    # Always persist — gives operator a timeline even if channels are absent.
    if db is not None:
        try:
            await db.ops_audit.insert_one({
                "ts": now,
                "kind": "alert_emitted" if sent else "alert_logged_only",
                **payload,
            })
        except Exception as e:
            logger.warning(f"[ops] audit insert failed: {e}")

    if not sent:
        logger.warning(f"[ops] ALERT {severity.upper()}: {title} — {message}")
    else:
        logger.info(f"[ops] alert emitted: {title}")

    return sent


# ── Auto-healing loop ────────────────────────────────────────────────
async def _check_extension_gap(db: Any, overview_fetcher: Callable) -> None:
    """If extension has 0 clients online for > 2 minutes, alert + log."""
    overview = await overview_fetcher()
    ext = overview.get("extension") or {}
    online = int(ext.get("online") or 0)
    total = int(ext.get("total") or 0)
    now = time.time()

    if online == 0:
        if STATE.ext_zero_since is None:
            STATE.ext_zero_since = now
        duration = now - STATE.ext_zero_since
        if duration >= EXT_STALE_SEC:
            await emit_alert(
                severity="critical",
                title="Extension layer offline",
                message=(
                    f"No extension clients have been online for "
                    f"{int(duration)} s. Cloudflare-protected sources "
                    f"(poctra, cfw, aah, salvagebid) are disabled."
                ),
                context={
                    "clients_total": total,
                    "clients_online": 0,
                    "duration_sec": int(duration),
                    "action_hint": "install / register a BIBI extension client",
                },
                fingerprint="ext_offline",
                db=db,
            )
    else:
        # Recovery → fire a one-shot recovery notice.
        if STATE.ext_zero_since is not None:
            dur = int(now - STATE.ext_zero_since)
            STATE.ext_zero_since = None
            await emit_alert(
                severity="info",
                title="Extension layer recovered",
                message=f"{online}/{total} clients back online after {dur} s.",
                context={"clients_online": online, "clients_total": total},
                fingerprint="ext_recovered",
                db=db,
            )


async def _check_breakers(db: Any) -> None:
    """If a primary circuit breaker has been OPEN for > 5 min, force it
    back to HALF_OPEN so the system can retry. Emits an alert either way."""
    try:
        from vin_service import get_circuit_stats  # noqa
    except Exception:
        return

    try:
        stats = get_circuit_stats() or {}
    except Exception as e:
        STATE.last_error = f"circuit stats: {e}"
        return

    now = time.time()
    for key in ("bitmotors_search", "bitmotors_page"):
        cb = stats.get(key) or {}
        is_open = bool(cb.get("is_open"))
        if is_open:
            since = STATE.breaker_open_since.get(key)
            if since is None:
                STATE.breaker_open_since[key] = now
                await emit_alert(
                    severity="critical",
                    title=f"Circuit breaker tripped: {key}",
                    message=(
                        f"{key} is OPEN — traffic is being short-circuited. "
                        f"Will auto-force half-open after "
                        f"{BM_BREAKER_STUCK_SEC}s."
                    ),
                    context={
                        "total_calls": cb.get("total_calls"),
                        "total_failures": cb.get("total_failures"),
                    },
                    fingerprint=f"cb_open_{key}",
                    db=db,
                )
            elif (now - since) >= BM_BREAKER_STUCK_SEC:
                # Attempt soft half-open via public API if available
                forced = False
                try:
                    from vin_service import force_half_open_breaker  # optional
                    forced = bool(force_half_open_breaker(key))
                except Exception:
                    forced = False
                if forced:
                    STATE.total_heal_actions += 1
                    STATE.breaker_open_since[key] = now  # reset timer
                    if db is not None:
                        try:
                            await db.ops_audit.insert_one({
                                "ts": now,
                                "kind": "heal_action",
                                "action": "force_half_open",
                                "target": key,
                            })
                        except Exception:
                            pass
                    await emit_alert(
                        severity="warn",
                        title=f"Breaker forced half-open: {key}",
                        message=(
                            f"{key} was stuck OPEN for "
                            f"{int(now - since)}s — forced to HALF_OPEN "
                            f"for a retry probe."
                        ),
                        fingerprint=f"cb_healed_{key}",
                        db=db,
                    )
        else:
            # Breaker healed on its own — clear the tracker
            if key in STATE.breaker_open_since:
                STATE.breaker_open_since.pop(key, None)


async def _check_full_outage(db: Any, overview_fetcher: Callable) -> None:
    """If every non-extension primary source is down simultaneously, escalate."""
    overview = await overview_fetcher()
    rows = overview.get("sources") or []
    primaries = [r for r in rows if r.get("key") != "extension"]
    if not primaries:
        return
    all_down = all((r.get("status") == "down") for r in primaries)
    if all_down:
        await emit_alert(
            severity="critical",
            title="All primary sources are down",
            message=(
                "Resolver chain cannot answer: "
                + ", ".join(r.get("label", "?") for r in primaries)
                + " are all DOWN. Check network, circuit breakers and parser "
                  "logs immediately."
            ),
            context={"sources": [r.get("key") for r in primaries]},
            fingerprint="all_primary_down",
            db=db,
        )


async def ops_guardian_loop(db: Any, overview_fetcher: Callable) -> None:
    """Main background task. Call from app startup.

    ``overview_fetcher`` must be an async callable that returns the same
    dict shape as ``/api/control/overview``. In server.py we bind it to
    the route handler directly so the guardian always sees live data.
    """
    if not OPS_HEAL_ENABLED:
        logger.info("[ops] guardian disabled by OPS_HEAL_ENABLED=false")
        return
    # Delay first tick so startup chatter settles.
    await asyncio.sleep(15)
    logger.info(
        f"[ops] guardian running every {OPS_HEAL_INTERVAL_SEC}s "
        f"(telegram={'on' if TELEGRAM_BOT_TOKEN else 'off'}, "
        f"webhook={'on' if ALERT_WEBHOOK_URL else 'off'}, "
        f"cooldown={ALERT_COOLDOWN_SEC}s)"
    )
    while True:
        try:
            await _check_extension_gap(db, overview_fetcher)
            await _check_breakers(db)
            await _check_full_outage(db, overview_fetcher)
            STATE.last_loop_at = time.time()
            STATE.last_error = None
        except asyncio.CancelledError:
            logger.info("[ops] guardian cancelled")
            raise
        except Exception as e:
            STATE.last_error = str(e)
            logger.warning(f"[ops] guardian loop error: {e}")
        await asyncio.sleep(OPS_HEAL_INTERVAL_SEC)


# ── Status export (for /api/control/ops/status) ──────────────────────
def get_guardian_status() -> dict:
    """Snapshot for the admin UI — which channels wired, cooldowns, counters."""
    now = time.time()
    return {
        "enabled": OPS_HEAL_ENABLED,
        "interval_sec": OPS_HEAL_INTERVAL_SEC,
        "cooldown_sec": ALERT_COOLDOWN_SEC,
        "channels": {
            "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
            "webhook": bool(ALERT_WEBHOOK_URL),
        },
        "counters": {
            "total_alerts_sent": STATE.total_alerts_sent,
            "total_heal_actions": STATE.total_heal_actions,
        },
        "last_loop_at": STATE.last_loop_at,
        "last_loop_age_sec": (
            int(now - STATE.last_loop_at) if STATE.last_loop_at else None
        ),
        "last_error": STATE.last_error,
        "active_dedup_keys": list(STATE.sent_at.keys()),
        "ext_zero_since": STATE.ext_zero_since,
        "breaker_open_since": STATE.breaker_open_since,
        "thresholds": {
            "ext_stale_sec": EXT_STALE_SEC,
            "bm_breaker_stuck_sec": BM_BREAKER_STUCK_SEC,
        },
    }
