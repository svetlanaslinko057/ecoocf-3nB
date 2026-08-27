"""
openai_usage — record + aggregate OpenAI spend for the Call Intelligence surface
==================================================================================

Wave 2A-CI/2 (Jul 13, 2026) — real-money awareness. Every OpenAI call the CRM
issues (Whisper/gpt-4o-transcribe for audio, gpt-4o for analysis) is charged
by tokens or by audio minutes; without visibility the operator has no idea
how much a busy Ringostat day costs.

This module gives us:

    • :data:`PRICING`           canonical USD price table (per 1M tokens / per minute)
    • :func:`price_chat`        USD cost from prompt/completion token counts
    • :func:`price_audio`       USD cost from audio seconds
    • :func:`record_usage`      persist one usage event into ``openai_usage`` (best-effort)
    • :func:`usage_rollup`      aggregate day / 7d / 30d / 90d / all-time

The ``openai_usage`` collection schema (denormalised so ONE endpoint can read it
without joins)::

    {
      "_id":        uuid4 str,
      "ts":         datetime (UTC),                 # when the API call resolved
      "kind":       "chat" | "transcribe",          # coarse pipeline stage
      "endpoint":   "chat.completions" | "audio.transcriptions",
      "model":      "gpt-4o" | "gpt-4o-transcribe" | ...,
      "call_id":    str | None,                     # bridge to ringostat_calls
      "manager_id": str | None,
      # For chat calls:
      "prompt_tokens":     int | None,
      "completion_tokens": int | None,
      "total_tokens":      int | None,
      # For transcription calls:
      "audio_seconds":     float | None,
      # Money (USD) — always populated when we can compute it
      "cost_usd":          float,
      "pricing_source":    "table:v1"               # so future updates don't rewrite history
    }

The service is deliberately *fire-and-forget*: `record_usage` never raises,
so a Mongo hiccup can never break a real user-facing call to the OpenAI
pipeline.  Errors are logged and swallowed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("bibi.openai_usage")

# ─────────────────────────────────────────────────────────────────────
# PRICING TABLE  (USD — as of Jul 2026, per OpenAI's public list)
#
# Chat/completion models are priced per 1M tokens split by prompt vs completion.
# Audio models are priced per **minute** of input audio, regardless of language.
#
# When a model isn't listed we fall back to the ``_default_*`` entry so we never
# under-report spend — operators can update this table in one place without
# touching call-sites.  Old rows keep their historical ``cost_usd`` because we
# persist the number at record time (not compute on read).
# ─────────────────────────────────────────────────────────────────────

# ¤ per 1M tokens (USD)
CHAT_PRICING: Dict[str, Dict[str, float]] = {
    # gpt-4o family
    "gpt-4o":                {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-05-13":     {"input": 5.00, "output": 15.00},
    "gpt-4o-2024-08-06":     {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-11-20":     {"input": 2.50, "output": 10.00},
    # gpt-4o-mini family
    "gpt-4o-mini":           {"input": 0.150, "output": 0.600},
    "gpt-4o-mini-2024-07-18":{"input": 0.150, "output": 0.600},
    # gpt-4-turbo (legacy)
    "gpt-4-turbo":           {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-2024-04-09":{"input": 10.00, "output": 30.00},
    # gpt-3.5-turbo (legacy)
    "gpt-3.5-turbo":         {"input": 0.500, "output": 1.500},
    # gpt-4.1 family (Apr 2025)
    "gpt-4.1":               {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini":          {"input": 0.400, "output": 1.600},
    "gpt-4.1-nano":          {"input": 0.100, "output": 0.400},
    # o1 / reasoning
    "o1":                    {"input": 15.00, "output": 60.00},
    "o1-mini":               {"input": 3.00, "output": 12.00},
    # sensible default for unknown chat models — mirrors gpt-4o so we never
    # silently under-report a new model.
    "_default":              {"input": 2.50, "output": 10.00},
}

# ¤ per minute of audio (USD)
AUDIO_PRICING: Dict[str, float] = {
    "whisper-1":                0.006,
    "gpt-4o-transcribe":        0.006,
    "gpt-4o-mini-transcribe":   0.003,
    "_default":                 0.006,
}

PRICING_VERSION = "table:v1"


def _chat_rate(model: str) -> Dict[str, float]:
    return CHAT_PRICING.get(model) or CHAT_PRICING["_default"]


def _audio_rate(model: str) -> float:
    return AUDIO_PRICING.get(model, AUDIO_PRICING["_default"])


def price_chat(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return USD spend for one chat completion. Never raises."""
    try:
        rate = _chat_rate(model or "")
        pt = max(0, int(prompt_tokens or 0))
        ct = max(0, int(completion_tokens or 0))
        return round(pt / 1_000_000 * rate["input"] + ct / 1_000_000 * rate["output"], 6)
    except Exception:  # noqa: BLE001 — defensive: bad inputs never propagate
        return 0.0


def price_audio(model: str, audio_seconds: float) -> float:
    """Return USD spend for one transcription. Never raises."""
    try:
        rate = _audio_rate(model or "")
        secs = max(0.0, float(audio_seconds or 0.0))
        return round((secs / 60.0) * rate, 6)
    except Exception:  # noqa: BLE001
        return 0.0


# ─────────────────────────────────────────────────────────────────────
# RECORD
# ─────────────────────────────────────────────────────────────────────

async def record_usage(
    db,
    *,
    kind: str,                         # "chat" | "transcribe"
    endpoint: str,                     # e.g. "chat.completions"
    model: str,
    call_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    audio_seconds: Optional[float] = None,
    cost_usd: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Persist one usage event. Never raises."""
    try:
        if cost_usd is None:
            if kind == "chat":
                cost_usd = price_chat(model, prompt_tokens or 0, completion_tokens or 0)
            elif kind == "transcribe":
                cost_usd = price_audio(model, audio_seconds or 0)
            else:
                cost_usd = 0.0

        doc = {
            "_id":               str(uuid.uuid4()),
            "ts":                datetime.now(timezone.utc),
            "kind":              kind,
            "endpoint":          endpoint,
            "model":             model,
            "call_id":           call_id,
            "manager_id":        manager_id,
            "prompt_tokens":     int(prompt_tokens) if prompt_tokens is not None else None,
            "completion_tokens": int(completion_tokens) if completion_tokens is not None else None,
            "total_tokens":      (int(prompt_tokens or 0) + int(completion_tokens or 0))
                                 if (prompt_tokens is not None or completion_tokens is not None) else None,
            "audio_seconds":     float(audio_seconds) if audio_seconds is not None else None,
            "cost_usd":          float(cost_usd or 0.0),
            "pricing_source":    PRICING_VERSION,
        }
        await db.openai_usage.insert_one(doc)
        return doc
    except Exception as e:  # noqa: BLE001 — fire-and-forget
        logger.warning("[openai_usage] record failed (kind=%s model=%s): %s", kind, model, e)
        return None


# ─────────────────────────────────────────────────────────────────────
# AGGREGATE
# ─────────────────────────────────────────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def _sum_in_window(db, *, since: datetime) -> Dict[str, Any]:
    """Return {requests, cost_usd, tokens_in, tokens_out, audio_seconds} for
    events with ``ts >= since``. Robust to an empty collection."""
    try:
        pipeline = [
            {"$match": {"ts": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "requests":       {"$sum": 1},
                "cost_usd":       {"$sum": "$cost_usd"},
                "tokens_in":      {"$sum": {"$ifNull": ["$prompt_tokens", 0]}},
                "tokens_out":     {"$sum": {"$ifNull": ["$completion_tokens", 0]}},
                "audio_seconds":  {"$sum": {"$ifNull": ["$audio_seconds", 0]}},
            }},
        ]
        cursor = db.openai_usage.aggregate(pipeline)
        docs = await cursor.to_list(length=1)
        if not docs:
            return {"requests": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "audio_seconds": 0.0}
        d = docs[0]
        return {
            "requests":      int(d.get("requests", 0)),
            "cost_usd":      round(float(d.get("cost_usd", 0.0)), 4),
            "tokens_in":     int(d.get("tokens_in", 0)),
            "tokens_out":    int(d.get("tokens_out", 0)),
            "audio_seconds": round(float(d.get("audio_seconds", 0.0)), 2),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("[openai_usage] rollup failed: %s", e)
        return {"requests": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "audio_seconds": 0.0}


async def _breakdown_by_model(db, *, since: datetime, limit: int = 8) -> list:
    """Per-model cost breakdown for the ``since`` window."""
    try:
        pipeline = [
            {"$match": {"ts": {"$gte": since}}},
            {"$group": {
                "_id":       "$model",
                "requests":  {"$sum": 1},
                "cost_usd":  {"$sum": "$cost_usd"},
                "kind":      {"$first": "$kind"},
            }},
            {"$sort": {"cost_usd": -1}},
            {"$limit": limit},
        ]
        docs = await db.openai_usage.aggregate(pipeline).to_list(length=limit)
        return [
            {
                "model":    d.get("_id") or "?",
                "kind":     d.get("kind"),
                "requests": int(d.get("requests", 0)),
                "cost_usd": round(float(d.get("cost_usd", 0.0)), 4),
            }
            for d in docs
        ]
    except Exception as e:  # noqa: BLE001
        logger.warning("[openai_usage] breakdown failed: %s", e)
        return []


async def _last_events(db, *, limit: int = 5) -> list:
    """Return the most recent N events for a tail-view."""
    try:
        cursor = db.openai_usage.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
        rows = await cursor.to_list(length=limit)
        for r in rows:
            if isinstance(r.get("ts"), datetime):
                r["ts"] = _iso(r["ts"])
        return rows
    except Exception as e:  # noqa: BLE001
        logger.warning("[openai_usage] last events failed: %s", e)
        return []


async def usage_rollup(db) -> Dict[str, Any]:
    """Aggregate OpenAI spend across canonical windows.

    Returns a dict shaped for the frontend Usage widget::

        {
          "today":     { requests, cost_usd, tokens_in, tokens_out, audio_seconds },
          "week":      { ... },      # rolling 7-day
          "month":     { ... },      # rolling 30-day
          "quarter":   { ... },      # rolling 90-day
          "all_time":  { ... },
          "by_model":  [ { model, requests, cost_usd, kind }, ... ],  # top-8 30-day
          "recent":    [ { ts, model, kind, cost_usd, ... }, ... ],   # last 5 events
          "pricing":   { chat: {...}, audio: {...} },                 # for tooltip
          "currency":  "USD",
          "version":   "table:v1"
        }
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start    = now - timedelta(days=7)
    month_start   = now - timedelta(days=30)
    quarter_start = now - timedelta(days=90)
    epoch_start   = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Run window rollups sequentially — Mongo aggregations are cheap on
    # openai_usage (< 1 doc per call), no need to fan-out.
    today   = await _sum_in_window(db, since=today_start)
    week    = await _sum_in_window(db, since=week_start)
    month   = await _sum_in_window(db, since=month_start)
    quarter = await _sum_in_window(db, since=quarter_start)
    total   = await _sum_in_window(db, since=epoch_start)

    by_model = await _breakdown_by_model(db, since=month_start, limit=8)
    recent   = await _last_events(db, limit=5)

    return {
        "today":    today,
        "week":     week,
        "month":    month,
        "quarter":  quarter,
        "all_time": total,
        "by_model": by_model,
        "recent":   recent,
        "pricing":  {"chat": CHAT_PRICING, "audio": AUDIO_PRICING},
        "currency": "USD",
        "version":  PRICING_VERSION,
        "as_of":    _iso(now),
    }
