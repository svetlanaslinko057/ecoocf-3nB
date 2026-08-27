"""
app.services.call_intelligence
==============================

Call Intelligence pipeline (Jul 12, 2026 · BIBI Cars).

Flow
----
  Ringostat webhook → ringostat_calls (with recording_url) → this service:

     1. transcribe(audio_url) → call_transcripts   (Whisper / gpt-4o-transcribe)
     2. analyze(transcript, ctx) → call_intelligence  (gpt-4o structured JSON)
     3. optional auto-create task from `next_actions`
     4. mark ringostat_calls.intelligence_status = "ready"

The service is **provider-agnostic**: the OpenAI SDK is imported lazily so
the module can be imported even in test contexts where the SDK / API key
are absent (`process_call` will then return a structured error instead
of crashing on import).

All heavy work happens inside `process_call(call_id)`.  Callers should
schedule this via `asyncio.create_task(...)` — the fetch-recording worker
already does that at the bottom of `server.fetch_recording_url`.

Collections written
-------------------
  * `call_transcripts`   — one doc per call (fullText + segments + language)
  * `call_intelligence`  — one doc per call (summary + structured fields)
  * `ringostat_calls`    — status flags + short mirror of intelligence
                           (`summary`, `next_action`, `sentiment`,
                           `purchase_intent`) for quick list rendering.

Env
---
  * OPENAI_API_KEY                        — required
  * CALL_INTELLIGENCE_TRANSCRIBE_MODEL    — default `gpt-4o-transcribe`
  * CALL_INTELLIGENCE_ANALYZE_MODEL       — default `gpt-4o`
  * CALL_INTELLIGENCE_AUTO_CREATE_TASK    — default `true`
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("bibi.call_intelligence")


# ─────────────────────────── PROMPT ──────────────────────────────────
# We keep the analysis prompt at module scope so it is trivially unit-testable
# and reviewable.  The model is instructed to return a strict JSON envelope;
# unknown values must be nulled out (never fabricated).

ANALYZE_SYSTEM_PROMPT = """You are a Sales Call Intelligence analyst for BIBI Cars,
a company that imports pre-owned cars from the USA and Korea to Bulgaria.

You will receive a call transcript in Bulgarian, English, Russian or
Ukrainian. Your task is to extract structured facts about the conversation
that a sales manager or supervisor needs to see AT A GLANCE, without
reading the full transcript.

RULES:
  * Return ONLY valid JSON. No prose, no code fences.
  * Every string field must be short and human-readable (max ~200 chars).
  * If a fact is not stated in the transcript, use null (or an empty list).
    Do NOT invent details, budgets or names.
  * `summary` must be 2–4 sentences describing what happened in the call.
  * `next_actions` is a list — each item is a concrete follow-up
    (e.g. "Send 3 BMW X5 options by Friday"). Include a `due_date` in
    ISO-8601 (YYYY-MM-DD) when the transcript mentions a deadline.
  * `sentiment` ∈ {"positive","neutral","negative","mixed"}.
  * `purchase_intent` ∈ {"low","medium","high","very_high"}.
  * `deal_probability` ∈ {"low","medium","high"} — your own estimate.
  * `language` — the ISO-639-1 code of the transcript language.

JSON schema:
{
  "summary": string,
  "language": string,
  "customer_intent": string | null,
  "budget": string | null,
  "country": string | null,
  "vehicle_preferences": [string, ...],
  "objections": [string, ...],
  "agreements": [string, ...],
  "next_actions": [
     { "action": string, "due_date": string | null, "owner": "manager" | "customer" | null }
  ],
  "risks": [string, ...],
  "sentiment": "positive" | "neutral" | "negative" | "mixed",
  "purchase_intent": "low" | "medium" | "high" | "very_high",
  "deal_probability": "low" | "medium" | "high",
  "confidence": number  // 0..1 — your confidence in the extracted facts
}
"""


# ─────────────────────────── OPENAI CLIENT ───────────────────────────

async def _load_openai_doc() -> Optional[Dict[str, Any]]:
    """Fetch the whole `integration_configs.openai` doc (credentials + settings).

    Returns ``None`` if the DB is not accessible or the provider row is missing.
    """
    try:
        from app.core.db_runtime import get_db  # local import — avoids cycles
        db = get_db()
        if db is None:
            return None
        return await db.integration_configs.find_one({"provider": "openai"})
    except Exception as e:  # noqa: BLE001 — DB may not be up in unit tests
        logger.debug("[call-intel] db integration lookup failed: %s", e)
        return None


async def _load_key_from_db() -> Optional[str]:
    """Prefer the OpenAI key persisted through the admin Integrations UI.

    The admin panel writes to ``integration_configs.openai.credentials.apiKey``
    via ``PATCH /api/admin/integrations/openai``.  When present (and not the
    masked placeholder), it takes precedence over the ``OPENAI_API_KEY``
    environment variable so operators can rotate keys without a redeploy.
    """
    doc = await _load_openai_doc()
    if not doc:
        return None
    creds = doc.get("credentials") or {}
    raw = (creds.get("apiKey") or "").strip()
    # The GET surface returns "…lastEight" masked strings; never treat
    # those as a real key.
    if raw and not raw.startswith("…") and len(raw) > 20:
        return raw
    return None


async def resolve_api_key() -> Optional[str]:
    """Return the LLM key, preferring admin-configured OpenAI → env OPENAI → Emergent.

    Order:
      1. OpenAI key persisted via Admin → Integrations → OpenAI (production).
      2. ``OPENAI_API_KEY`` environment variable.
      3. ``EMERGENT_LLM_KEY`` (MR Gate) — used for now; routes through the
         Emergent gateway which supports Whisper STT and gpt-4o chat.
    """
    return (
        (await _load_key_from_db())
        or (os.environ.get("OPENAI_API_KEY") or "").strip()
        or (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
        or None
    )


def _is_emergent_key(key: Optional[str]) -> bool:
    return bool(key) and key.strip().startswith("sk-emergent-")


# ─── Language / model resolution ────────────────────────────────────
# Whisper / gpt-4o-transcribe support automatic language detection when
# no `language` hint is passed. Passing an ISO-639-1 hint dramatically
# improves accuracy for short utterances or noisy audio — which is
# BIBI's typical use case (calls in Bulgarian and English mostly, with
# occasional Russian / Ukrainian). The admin can pin the expected
# language via the Integrations page; "auto" leaves detection to the model.

_SUPPORTED_LANGUAGES: set[str] = {"en", "bg", "ru", "uk", "de", "es", "fr", "it", "pl", "ro", "tr"}


async def _load_settings_from_db() -> Dict[str, Any]:
    doc = await _load_openai_doc()
    if not doc:
        return {}
    return dict(doc.get("settings") or {})


async def resolve_transcribe_language() -> Optional[str]:
    """Read the desired Whisper language hint from DB → env → None (auto)."""
    settings = await _load_settings_from_db()
    lang = (settings.get("transcribeLanguage") or "").strip().lower()
    if not lang:
        lang = (os.environ.get("CALL_INTELLIGENCE_TRANSCRIBE_LANGUAGE") or "").strip().lower()
    if lang in ("", "auto"):
        return None
    if lang in _SUPPORTED_LANGUAGES:
        return lang
    return None


async def resolve_transcribe_model() -> str:
    """DB → env → default ``gpt-4o-transcribe``."""
    settings = await _load_settings_from_db()
    model = (settings.get("transcribeModel") or "").strip()
    if model:
        return model
    return os.environ.get("CALL_INTELLIGENCE_TRANSCRIBE_MODEL", "gpt-4o-transcribe")


async def resolve_analyze_model() -> str:
    """DB → env → default ``gpt-4o``."""
    settings = await _load_settings_from_db()
    model = (settings.get("model") or settings.get("analyzeModel") or "").strip()
    if model:
        return model
    return os.environ.get("CALL_INTELLIGENCE_ANALYZE_MODEL", "gpt-4o")


def _api_key() -> Optional[str]:
    """Sync helper — env only (kept for legacy call sites that can't await).

    Prefer :func:`resolve_api_key` inside coroutines.
    """
    return (os.environ.get("OPENAI_API_KEY") or "").strip() or None


def _transcribe_model() -> str:
    """Sync fallback — env only (used by /intelligence/config for a cheap read).

    Coroutines should prefer :func:`resolve_transcribe_model`, which also
    consults the DB-persisted admin setting.
    """
    return os.environ.get("CALL_INTELLIGENCE_TRANSCRIBE_MODEL", "gpt-4o-transcribe")


def _analyze_model() -> str:
    """Sync fallback — env only (see :func:`resolve_analyze_model`)."""
    return os.environ.get("CALL_INTELLIGENCE_ANALYZE_MODEL", "gpt-4o")


def _auto_create_task_enabled() -> bool:
    v = (os.environ.get("CALL_INTELLIGENCE_AUTO_CREATE_TASK") or "").strip().lower()
    return v in {"", "1", "true", "yes", "on"}  # default TRUE


class CallIntelligenceError(RuntimeError):
    """Raised when the pipeline cannot complete (missing key, HTTP error…)."""


# ─────────────────────────── TRANSCRIBE ──────────────────────────────

async def _download_audio(url: str, max_bytes: int = 60 * 1024 * 1024) -> str:
    """Stream-download the recording to a temp .mp3 file. Returns the local path.

    Ringostat recordings are typically 1–5MB for <20-minute calls, so we cap
    at 60MB defensively (OpenAI limit is 25MB — we validate below).
    """
    # Use httpx.AsyncClient with streaming to keep memory footprint tiny
    # (this matters — the container has a 2GB cgroup cap).
    fd, path = tempfile.mkstemp(prefix="bibi_call_", suffix=".mp3")
    os.close(fd)
    written = 0
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    raise CallIntelligenceError(
                        f"recording download failed: HTTP {resp.status_code}"
                    )
                with open(path, "wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                        fh.write(chunk)
                        written += len(chunk)
                        if written > max_bytes:
                            raise CallIntelligenceError(
                                f"recording too large (> {max_bytes} bytes)"
                            )
    except CallIntelligenceError:
        try: os.unlink(path)
        except Exception: pass
        raise
    except Exception as e:
        try: os.unlink(path)
        except Exception: pass
        raise CallIntelligenceError(f"recording download error: {e}") from e
    return path


async def transcribe(audio_url: str, *, hint_language: Optional[str] = None) -> Dict[str, Any]:
    """Download `audio_url` and transcribe it via OpenAI.

    Returns a dict::

        {
          "full_text": "...",
          "language":  "bg" | "en" | ...,
          "duration":  float | None,
          "model":     "gpt-4o-transcribe",
          "segments":  [ {"start": .., "end": .., "text": ..}, ... ] | []
        }

    Raises `CallIntelligenceError` on any failure (missing key, HTTP error,
    invalid audio).
    """
    key = await resolve_api_key()
    if not key:
        raise CallIntelligenceError("Ключ LLM не налаштовано (додайте OpenAI у Admin → Integrations, або EMERGENT_LLM_KEY у backend/.env)")

    path = await _download_audio(audio_url)
    try:
        size = os.path.getsize(path)
        if size > 25 * 1024 * 1024:
            # OpenAI /audio/transcriptions caps at 25MB.
            raise CallIntelligenceError(f"recording exceeds 25MB API limit ({size} bytes)")

        # ── Emergent (MR Gate) path — Whisper via the Emergent gateway ──────
        if _is_emergent_key(key):
            from emergentintegrations.llm.openai.speech_to_text import OpenAISpeechToText  # noqa: WPS433
            model = "whisper-1"  # only model the Emergent STT bridge exposes
            stt = OpenAISpeechToText(api_key=key)
            with open(path, "rb") as fh:
                resp = await stt.transcribe(
                    file=fh,
                    model=model,
                    response_format="verbose_json",
                    language=hint_language or None,
                )
            if hasattr(resp, "model_dump"):
                data = resp.model_dump()
            elif isinstance(resp, dict):
                data = resp
            else:
                data = {"text": getattr(resp, "text", str(resp)),
                        "language": getattr(resp, "language", None),
                        "duration": getattr(resp, "duration", None),
                        "segments": getattr(resp, "segments", None)}
        else:
            # ── Direct OpenAI path (production key configured in admin/env) ──
            model = await resolve_transcribe_model()
            from openai import AsyncOpenAI  # noqa: WPS433
            client = AsyncOpenAI(api_key=key)
            with open(path, "rb") as fh:
                fmt = "verbose_json" if model.startswith("whisper") else "json"
                kwargs = dict(model=model, file=fh, response_format=fmt)
                if hint_language:
                    kwargs["language"] = hint_language
                resp = await client.audio.transcriptions.create(**kwargs)
            if hasattr(resp, "model_dump"):
                data = resp.model_dump()
            elif isinstance(resp, dict):
                data = resp
            else:
                data = {"text": str(resp)}

        return {
            "full_text": (data.get("text") or "").strip(),
            "language": data.get("language"),
            "duration": data.get("duration"),
            "model": model,
            "segments": data.get("segments") or [],
        }
    finally:
        try: os.unlink(path)
        except Exception: pass


async def _record_transcribe_usage(
    db,
    *,
    model: str,
    duration: Optional[float],
    call_id: Optional[str],
    manager_id: Optional[str],
) -> None:
    """Best-effort side-effect: persist a usage row so operators can see
    real-money spend on the Call Intelligence dashboard. Never raises."""
    if db is None:
        return
    try:
        from app.services import openai_usage as _usage  # noqa: WPS433
        await _usage.record_usage(
            db,
            kind="transcribe",
            endpoint="audio.transcriptions",
            model=model,
            call_id=call_id,
            manager_id=manager_id,
            audio_seconds=float(duration) if duration else 0.0,
        )
    except Exception:  # noqa: BLE001
        pass


async def _record_chat_usage(
    db,
    *,
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    call_id: Optional[str],
    manager_id: Optional[str],
) -> None:
    """Best-effort persist of a chat.completions usage row. Never raises."""
    if db is None:
        return
    try:
        from app.services import openai_usage as _usage  # noqa: WPS433
        await _usage.record_usage(
            db,
            kind="chat",
            endpoint="chat.completions",
            model=model,
            call_id=call_id,
            manager_id=manager_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception:  # noqa: BLE001
        pass


# ─────────────────────────── ANALYZE ─────────────────────────────────

async def analyze(
    transcript_text: str,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send transcript through gpt-4o for structured Call Intelligence.

    `context` is a dict with keys like `manager_name`, `lead_name`,
    `previous_summary`, `vehicle_of_interest` — all optional. They are
    embedded as a short prefix message so the model can disambiguate names.

    Returns the parsed JSON envelope (see `ANALYZE_SYSTEM_PROMPT`) plus
    `raw` and `model` keys.
    """
    key = await resolve_api_key()
    if not key:
        raise CallIntelligenceError("Ключ LLM не налаштовано (додайте OpenAI у Admin → Integrations, або EMERGENT_LLM_KEY у backend/.env)")

    model = await resolve_analyze_model()
    ctx_lines: List[str] = []
    if context:
        for k, v in context.items():
            if v:
                ctx_lines.append(f"- {k}: {v}")
    context_block = ("Call context (do NOT invent — only for name disambiguation):\n"
                     + "\n".join(ctx_lines) + "\n\n") if ctx_lines else ""

    user_msg = context_block + "Transcript:\n\"\"\"\n" + transcript_text.strip() + "\n\"\"\"" \
               + "\n\nReturn ONLY a valid JSON object, no markdown, no code fences."

    prompt_tokens = None
    completion_tokens = None

    if _is_emergent_key(key):
        # ── Emergent (MR Gate) path — gpt-4o via the Emergent gateway ───────
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433
        chat = LlmChat(
            api_key=key,
            session_id=f"call-intel-{uuid.uuid4()}",
            system_message=ANALYZE_SYSTEM_PROMPT,
        ).with_model("openai", model)
        raw = await chat.send_message(UserMessage(text=user_msg))
        raw = raw if isinstance(raw, str) else str(raw)
    else:
        # ── Direct OpenAI path (production key) ─────────────────────────────
        from openai import AsyncOpenAI  # noqa: WPS433
        client = AsyncOpenAI(api_key=key)
        resp = await client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        _usage_obj = getattr(resp, "usage", None)
        try:
            if _usage_obj is not None:
                prompt_tokens = int(getattr(_usage_obj, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(_usage_obj, "completion_tokens", 0) or 0)
        except Exception:  # noqa: BLE001
            prompt_tokens = None
            completion_tokens = None

    # Strip markdown code fences if the model wrapped the JSON.
    raw = (raw or "{}").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw.lstrip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()
    # As a last resort, slice from the first '{' to the last '}'.
    if not raw.startswith("{"):
        i, j = raw.find("{"), raw.rfind("}")
        if i != -1 and j != -1 and j > i:
            raw = raw[i:j + 1]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise CallIntelligenceError(f"gpt returned non-JSON: {e} · raw={raw[:200]!r}")

    # Defensive defaults so downstream renders never KeyError.
    parsed.setdefault("summary", "")
    parsed.setdefault("language", None)
    parsed.setdefault("customer_intent", None)
    parsed.setdefault("budget", None)
    parsed.setdefault("country", None)
    parsed.setdefault("vehicle_preferences", [])
    parsed.setdefault("objections", [])
    parsed.setdefault("agreements", [])
    parsed.setdefault("next_actions", [])
    parsed.setdefault("risks", [])
    parsed.setdefault("sentiment", "neutral")
    parsed.setdefault("purchase_intent", "low")
    parsed.setdefault("deal_probability", "low")
    parsed.setdefault("confidence", 0.0)
    parsed["model"] = model
    parsed["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    # Attach raw usage (tokens) so the orchestrator can log spend.
    # We use double-underscore keys so downstream serializers ignore them
    # if they filter meta.
    parsed["__usage__"] = {
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    return parsed


# ─────────────────────────── ORCHESTRATOR ────────────────────────────

async def _build_context(db, call: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort context builder from the call → lead/staff."""
    ctx: Dict[str, Any] = {}
    try:
        if call.get("lead_id"):
            lead = await db.leads.find_one({"_id": call["lead_id"]})
            if lead:
                ctx["lead_name"] = lead.get("name") or lead.get("fullName")
                ctx["lead_phone"] = lead.get("phone")
                ctx["lead_stage"] = lead.get("stage")
                if lead.get("carOfInterest"):
                    ctx["vehicle_of_interest"] = lead["carOfInterest"]
    except Exception:  # noqa: BLE001 — context is best-effort
        pass
    try:
        if call.get("manager_id"):
            mgr = await db.staff.find_one({"id": call["manager_id"]}) or \
                  await db.staff.find_one({"_id": call["manager_id"]})
            if mgr:
                ctx["manager_name"] = mgr.get("name") or mgr.get("fullName")
    except Exception:
        pass
    return ctx


async def _auto_create_task_from_ci(
    db, call: Dict[str, Any], intelligence: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Create a follow-up task from the first `next_actions[]` entry with
    owner="manager" (or unknown). Idempotent by (call_id, source=ai_call_ci).
    """
    if not _auto_create_task_enabled():
        return None
    actions = intelligence.get("next_actions") or []
    action = None
    for a in actions:
        if not isinstance(a, dict):
            continue
        owner = (a.get("owner") or "").lower()
        if owner in ("manager", "", None) and a.get("action"):
            action = a
            break
    if not action:
        return None

    existing = await db.tasks.find_one({
        "call_id": call.get("call_id") or call.get("_id"),
        "source":  "ai_call_ci",
    })
    if existing:
        return existing  # idempotent

    due_iso = action.get("due_date")
    try:
        due_at = datetime.fromisoformat(due_iso).replace(tzinfo=timezone.utc) \
            if due_iso else datetime.now(timezone.utc) + timedelta(days=2)
    except Exception:
        due_at = datetime.now(timezone.utc) + timedelta(days=2)

    now = datetime.now(timezone.utc)
    task_doc = {
        "_id": str(uuid.uuid4()),
        "id":  str(uuid.uuid4()),
        "type": "follow_up",
        "source": "ai_call_ci",
        "title": action["action"][:200],
        "description": intelligence.get("summary") or "",
        "call_id": call.get("call_id") or call.get("_id"),
        "lead_id": call.get("lead_id"),
        "deal_id": call.get("deal_id"),
        "customer_id": call.get("customer_id"),
        "assignee_id": call.get("manager_id"),
        "assigneeId":  call.get("manager_id"),  # camelCase mirror (Wave 8+ readers)
        "leadId":      call.get("lead_id"),
        "customerId":  call.get("customer_id"),
        "priority": "high" if (intelligence.get("purchase_intent") in ("high", "very_high")) else "medium",
        "status": "pending",
        "due_at":   due_at,
        "dueDate":  due_at,        # camelCase mirror
        "deadline": due_at,
        "created_at": now,
        "updated_at": now,
    }
    await db.tasks.insert_one(task_doc)
    logger.info(
        "[call-intel] auto-created follow-up task %s for call %s (action=%r due=%s)",
        task_doc["_id"], call.get("call_id"), action["action"][:60], due_at.isoformat(),
    )
    return task_doc


async def process_call(db, call_id: str, *, force: bool = False) -> Dict[str, Any]:
    """End-to-end pipeline for a single call.

    Idempotent: if `call_intelligence` already exists for this call and
    `force=False`, the existing document is returned as-is.

    Returns::

        {
          "success":       bool,
          "call_id":       str,
          "transcript":    { fullText, language, duration, ... },
          "intelligence":  { summary, ... },
          "task_created":  { id, title, due_at } | None,
          "error":         str | None,
        }
    """
    now = datetime.now(timezone.utc)
    call = await db.ringostat_calls.find_one({"call_id": call_id}) or \
           await db.ringostat_calls.find_one({"_id": call_id})
    if not call:
        return {"success": False, "call_id": call_id, "error": "call not found"}

    if not force:
        existing_ci = await db.call_intelligence.find_one({"call_id": call_id})
        if existing_ci and existing_ci.get("summary"):
            existing_tr = await db.call_transcripts.find_one({"call_id": call_id})
            return {
                "success": True,
                "call_id": call_id,
                "transcript": existing_tr,
                "intelligence": existing_ci,
                "task_created": None,
                "cached": True,
            }

    recording_url = call.get("recording_url")
    if not recording_url:
        await db.ringostat_calls.update_one(
            {"call_id": call_id},
            {"$set": {"intelligence_status": "no_recording", "intelligence_updated_at": now}},
        )
        return {"success": False, "call_id": call_id, "error": "no recording_url"}

    # Mark as running so the UI can show a spinner.
    await db.ringostat_calls.update_one(
        {"call_id": call_id},
        {"$set": {
            "transcription_status": "running",
            "intelligence_status":  "pending",
            "intelligence_updated_at": now,
        }},
    )

    # ── Step 1: transcribe
    try:
        # Resolve the operator-configured language hint (BG / EN / RU / UK /
        # auto) once per call — passing an ISO-639-1 code to Whisper markedly
        # improves accuracy for BIBI's typical calls (Bulgarian ↔ English).
        hint_language = await resolve_transcribe_language()
        tr = await transcribe(recording_url, hint_language=hint_language)
    except CallIntelligenceError as e:
        logger.warning("[call-intel] transcribe failed for %s: %s", call_id, e)
        await db.ringostat_calls.update_one(
            {"call_id": call_id},
            {"$set": {
                "transcription_status": "failed",
                "intelligence_status":  "failed",
                "intelligence_error":   str(e),
                "intelligence_updated_at": datetime.now(timezone.utc),
            }},
        )
        return {"success": False, "call_id": call_id, "error": str(e)}

    # Check if transcript already exists to avoid _id collision on replace
    existing_tr = await db.call_transcripts.find_one({"call_id": call_id})
    tr_doc = {
        "call_id":    call_id,
        "language":   tr.get("language"),
        "full_text":  tr.get("full_text") or "",
        "segments":   tr.get("segments") or [],
        "duration":   tr.get("duration"),
        "model":      tr.get("model"),
        "created_at": datetime.now(timezone.utc),
    }
    if not existing_tr:
        tr_doc["_id"] = str(uuid.uuid4())
    await db.call_transcripts.replace_one({"call_id": call_id}, tr_doc, upsert=True)
    # ─ Wave 2A-CI/2: persist USD spend for the transcription call so the
    # dashboard "OpenAI usage" panel reflects real money out the door.
    await _record_transcribe_usage(
        db,
        model=tr.get("model") or "",
        duration=tr.get("duration"),
        call_id=call_id,
        manager_id=call.get("manager_id"),
    )
    await db.ringostat_calls.update_one(
        {"call_id": call_id},
        {"$set": {
            "transcription_status": "ready",
            "transcript_language":  tr.get("language"),
            "transcript_preview":   (tr.get("full_text") or "")[:280],
        }},
    )

    if not tr_doc["full_text"]:
        await db.ringostat_calls.update_one(
            {"call_id": call_id},
            {"$set": {"intelligence_status": "empty_transcript"}},
        )
        return {"success": False, "call_id": call_id, "error": "empty transcript",
                "transcript": tr_doc}

    # ── Step 2: analyze
    context = await _build_context(db, call)
    try:
        ci = await analyze(tr_doc["full_text"], context=context)
    except CallIntelligenceError as e:
        logger.warning("[call-intel] analyze failed for %s: %s", call_id, e)
        await db.ringostat_calls.update_one(
            {"call_id": call_id},
            {"$set": {
                "intelligence_status": "analyze_failed",
                "intelligence_error":  str(e),
                "intelligence_updated_at": datetime.now(timezone.utc),
            }},
        )
        return {"success": False, "call_id": call_id, "error": str(e),
                "transcript": tr_doc}

    # Check if intelligence already exists to avoid _id collision on replace
    existing_ci = await db.call_intelligence.find_one({"call_id": call_id})
    ci_doc = {
        "call_id":     call_id,
        "lead_id":     call.get("lead_id"),
        "customer_id": call.get("customer_id"),
        "manager_id":  call.get("manager_id"),
        "created_at":  datetime.now(timezone.utc),
        **ci,
    }
    if not existing_ci:
        ci_doc["_id"] = str(uuid.uuid4())
    # Extract & drop the private usage side-channel before persisting so the
    # DB doc stays a public shape. Then record spend in openai_usage.
    _chat_usage = ci_doc.pop("__usage__", None) or {}
    ci.pop("__usage__", None)
    await db.call_intelligence.replace_one({"call_id": call_id}, ci_doc, upsert=True)
    await _record_chat_usage(
        db,
        model=ci.get("model") or "",
        prompt_tokens=_chat_usage.get("prompt_tokens"),
        completion_tokens=_chat_usage.get("completion_tokens"),
        call_id=call_id,
        manager_id=call.get("manager_id"),
    )

    # Mirror short summary onto the call row itself for fast list rendering
    # (avoids joining call_intelligence on every list request).
    await db.ringostat_calls.update_one(
        {"call_id": call_id},
        {"$set": {
            "intelligence_status":  "ready",
            "intelligence_updated_at": datetime.now(timezone.utc),
            "ai_summary":           ci.get("summary") or "",
            "ai_sentiment":         ci.get("sentiment"),
            "ai_purchase_intent":   ci.get("purchase_intent"),
            "ai_next_action":       (ci.get("next_actions") or [{}])[0].get("action")
                                    if ci.get("next_actions") else None,
        }},
    )

    # ── Step 3: auto-create follow-up task (opt-in via env, default ON)
    task_created = await _auto_create_task_from_ci(db, call, ci)

    # ── Step 4 (Wave 2B): drop a `call_analysis_completed` event onto the
    #    customer timeline so Customer 360 Timeline shows every AI analysis
    #    inline with orders/deposits/comments. Best-effort — never fails
    #    the request.
    try:
        cust_id = call.get("customer_id") or call.get("customerId")
        if cust_id:
            from app.services import customer_timeline as _tl
            summary = (ci.get("summary") or "").strip()
            body_txt = summary[:280] + ("…" if len(summary) > 280 else "")
            await _tl.record_event(
                customer_id=str(cust_id),
                kind="call_analysis_completed",
                title=f"Call analysed by AI · {ci.get('sentiment') or '?'} · {ci.get('purchase_intent') or '?'}",
                body=body_txt or None,
                ref={"collection": "call_intelligence", "id": call_id,
                     "url": f"/admin/call-intelligence?call_id={call_id}"},
                actor=None,
                meta={
                    "call_id":          call_id,
                    "manager_id":       call.get("manager_id"),
                    "sentiment":        ci.get("sentiment"),
                    "purchase_intent":  ci.get("purchase_intent"),
                    "deal_probability": ci.get("deal_probability"),
                    "confidence":       ci.get("confidence"),
                    "language":         ci.get("language"),
                    "next_action":      (ci.get("next_actions") or [{}])[0].get("action")
                                        if ci.get("next_actions") else None,
                },
            )
    except Exception as _tl_err:  # noqa: BLE001
        logger.warning("[call-intel] timeline log failed for %s: %s", call_id, _tl_err)

    return {
        "success": True,
        "call_id": call_id,
        "transcript": tr_doc,
        "intelligence": ci_doc,
        "task_created": task_created,
    }


# ─────────────────────────── STATS ───────────────────────────────────

async def manager_stats(db, *, manager_id: Optional[str] = None,
                        days: int = 30) -> Dict[str, Any]:
    """Aggregate coaching / deal-risk metrics for a manager (or the whole team)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    match: Dict[str, Any] = {"created_at": {"$gte": since}}
    if manager_id:
        match["manager_id"] = manager_id

    pipeline: List[Dict[str, Any]] = [
        {"$match": match},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "positive": {"$sum": {"$cond": [{"$eq": ["$sentiment", "positive"]}, 1, 0]}},
            "negative": {"$sum": {"$cond": [{"$eq": ["$sentiment", "negative"]}, 1, 0]}},
            "high_intent": {"$sum": {"$cond": [
                {"$in": ["$purchase_intent", ["high", "very_high"]]}, 1, 0
            ]}},
            "with_next_action": {"$sum": {"$cond": [
                {"$gt": [{"$size": {"$ifNull": ["$next_actions", []]}}, 0]}, 1, 0
            ]}},
            "without_next_action": {"$sum": {"$cond": [
                {"$eq": [{"$size": {"$ifNull": ["$next_actions", []]}}, 0]}, 1, 0
            ]}},
            "objection_price": {"$sum": {"$cond": [
                {"$regexMatch": {
                    "input": {"$reduce": {
                        "input": {"$ifNull": ["$objections", []]},
                        "initialValue": "",
                        "in": {"$concat": ["$$value", " ", {"$toString": "$$this"}]},
                    }},
                    "regex": "(?i)price|цена|budget|бюджет|скъп|дорого",
                }}, 1, 0
            ]}},
        }},
    ]
    agg = await db.call_intelligence.aggregate(pipeline).to_list(length=1)
    row = agg[0] if agg else {}
    total = int(row.get("total") or 0)
    return {
        "manager_id": manager_id,
        "days": days,
        "total_calls_with_ci": total,
        "positive": int(row.get("positive") or 0),
        "negative": int(row.get("negative") or 0),
        "high_intent": int(row.get("high_intent") or 0),
        "with_next_action": int(row.get("with_next_action") or 0),
        "without_next_action": int(row.get("without_next_action") or 0),
        "objection_price": int(row.get("objection_price") or 0),
        "next_action_coverage": round(
            (int(row.get("with_next_action") or 0) / total) if total else 0.0, 3
        ),
    }


# ─────────────────────────── RECENT LIST ─────────────────────────────

async def recent_analyzed_calls(
    db,
    *,
    manager_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Return the last ``limit`` calls that have a stored intelligence doc.

    Each item is a compact projection meant for admin lists — enough to
    render a row with sentiment/intent/language chips + a transcript
    preview + a link to the deep-drawer, without any extra round-trips.

    Filter by ``manager_id`` when a specific manager's coaching feed is
    requested; pass ``None`` for the team-wide view.
    """
    match: Dict[str, Any] = {}
    if manager_id:
        match["manager_id"] = manager_id
    cursor = db.call_intelligence.find(
        match,
        {
            "_id": 0,
            "call_id": 1,
            "manager_id": 1,
            "lead_id": 1,
            "customer_id": 1,
            "summary": 1,
            "language": 1,
            "sentiment": 1,
            "purchase_intent": 1,
            "deal_probability": 1,
            "next_actions": 1,
            "objections": 1,
            "risks": 1,
            "created_at": 1,
            "model": 1,
        },
    ).sort("created_at", -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))

    # Best-effort enrich each row with a transcript preview & call metadata
    # (direction, duration, manager name) — bulk-fetch to keep it cheap.
    call_ids = [it["call_id"] for it in items if it.get("call_id")]
    calls_by_id: Dict[str, Dict[str, Any]] = {}
    transcripts_by_id: Dict[str, Dict[str, Any]] = {}
    if call_ids:
        calls_cursor = db.ringostat_calls.find(
            {"call_id": {"$in": call_ids}},
            {
                "_id": 0,
                "call_id": 1,
                "direction": 1,
                "duration": 1,
                "started_at": 1,
                "startedAt": 1,
                "manager_id": 1,
                "manager_name": 1,
                "recording_url": 1,
                "transcript_preview": 1,
            },
        )
        async for c in calls_cursor:
            calls_by_id[c["call_id"]] = c
        transcripts_cursor = db.call_transcripts.find(
            {"call_id": {"$in": call_ids}},
            {"_id": 0, "call_id": 1, "full_text": 1, "language": 1},
        )
        async for t in transcripts_cursor:
            transcripts_by_id[t["call_id"]] = t

    out: List[Dict[str, Any]] = []
    for it in items:
        call = calls_by_id.get(it.get("call_id") or "") or {}
        tr = transcripts_by_id.get(it.get("call_id") or "") or {}
        preview = (tr.get("full_text") or call.get("transcript_preview") or "")[:220]
        out.append({
            "call_id":         it.get("call_id"),
            "manager_id":      it.get("manager_id"),
            "lead_id":         it.get("lead_id"),
            "customer_id":     it.get("customer_id"),
            "summary":         it.get("summary") or "",
            "language":        it.get("language") or tr.get("language"),
            "sentiment":       it.get("sentiment"),
            "purchase_intent": it.get("purchase_intent"),
            "deal_probability": it.get("deal_probability"),
            "next_action":     ((it.get("next_actions") or [{}])[0].get("action")
                                if it.get("next_actions") else None),
            "objections_count": len(it.get("objections") or []),
            "risks_count":     len(it.get("risks") or []),
            "created_at":      it.get("created_at").isoformat() if isinstance(it.get("created_at"), datetime) else it.get("created_at"),
            "direction":       call.get("direction"),
            "duration":        call.get("duration"),
            "started_at":      call.get("startedAt") or call.get("started_at"),
            "manager_name":    call.get("manager_name"),
            "recording_available": bool(call.get("recording_url")),
            "transcript_preview": preview,
        })
    return out
