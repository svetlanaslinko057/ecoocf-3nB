"""
BIBI Cars — Notification "central nervous system"
==================================================

Architecture (no-surprises version):

    business logic
         │
         │  bus.emit("order_started", {...ctx})
         ▼
    ┌────────────┐
    │  EventBus  │  (simple async fan-out, in-process)
    └─────┬──────┘
          │
          ▼
    NotificationService
          │
          │  1. load enabled rule for the event
          │  2. for each target (customer / manager / team_lead / master_admin):
          │       resolve recipient(s) → render template in recipient's language →
          │       dispatch via enabled channels
          │
    ┌─────┼──────┬───────────────────┐
    ▼     ▼      ▼                   ▼
  Email  In-App  (telegram, sms)  future stubs

Templates + rules live in Mongo so master_admin edits them from the UI.
Defaults are seeded in code on the first boot.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger("bibi.notifications")

# ── event catalogue ────────────────────────────────────────────────────
EVENT_INVOICE_SENT        = "invoice_sent"
EVENT_PAYMENT_CONFIRMED   = "payment_confirmed"
EVENT_ORDER_STARTED       = "order_started"
EVENT_ORDER_FINISHED      = "order_finished"
EVENT_PAYMENT_REMINDER    = "payment_reminder"
EVENT_PROVIDER_TIER_CHANGED = "provider_tier_changed"

ALL_EVENTS = [
    EVENT_INVOICE_SENT,
    EVENT_PAYMENT_CONFIRMED,
    EVENT_ORDER_STARTED,
    EVENT_ORDER_FINISHED,
    EVENT_PAYMENT_REMINDER,
    EVENT_PROVIDER_TIER_CHANGED,
]

EVENT_TITLES = {
    EVENT_INVOICE_SENT:      {"ua": "Надіслано рахунок",       "en": "Invoice sent",       "bg": "Изпратена фактура"},
    EVENT_PAYMENT_CONFIRMED: {"ua": "Оплату підтверджено",     "en": "Payment confirmed",  "bg": "Плащането е потвърдено"},
    EVENT_ORDER_STARTED:     {"ua": "Замовлення в роботі",     "en": "Order started",      "bg": "Поръчката е в процес"},
    EVENT_ORDER_FINISHED:    {"ua": "Замовлення завершено",    "en": "Order completed",    "bg": "Поръчката е приключена"},
    EVENT_PAYMENT_REMINDER:  {"ua": "Нагадування про оплату",  "en": "Payment reminder",   "bg": "Напомняне за плащане"},
    EVENT_PROVIDER_TIER_CHANGED: {"ua": "Зміна рівня виконавця", "en": "Provider tier changed", "bg": "Промяна на ниво на изпълнителя"},
}

AUDIENCES = ("customer", "manager", "team_lead", "master_admin")
CHANNELS  = ("email", "in_app", "sms")
LANGUAGES = ("ua", "en", "bg")

# ── simple async event bus ─────────────────────────────────────────────
class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {}

    def on(self, event: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    async def emit(self, event: str, payload: Dict[str, Any]) -> None:
        handlers = list(self._handlers.get(event, []))
        if not handlers:
            logger.debug("[bus] no handlers for %s", event)
            return
        for h in handlers:
            try:
                # fire-and-forget; any handler exception is isolated
                asyncio.create_task(_safe(h, event, payload))
            except RuntimeError:
                # no running loop -> run inline
                try:
                    await h(payload)
                except Exception:
                    logger.exception("[bus] handler for %s failed (sync path)", event)


async def _safe(handler, event: str, payload: Dict[str, Any]):
    try:
        await handler(payload)
    except Exception:
        logger.exception("[bus] handler for %s failed", event)


bus = EventBus()


# ── channels ───────────────────────────────────────────────────────────
# Resend transactional-email defaults.
#   • Resend API key resolution order (highest → lowest):
#       1. integration_configs.resend.credentials.apiKey  (admin UI, live)
#       2. RESEND_API_KEY env var
#       3. RESEND_API_KEY_FALLBACK env var (optional last-resort for fresh
#          deploys before the admin re-enters the key)
#     PHASE SECURITY S3.4 — the key is NO LONGER hardcoded in source. It lives
#     in the DB (integration_configs.resend) and/or the environment only.
#   • RESEND_DEFAULT_FROM — the production sender. The domain (bibicars.org) must
#     be verified in the Resend dashboard. Until it is verified, every send that
#     fails with a "domain not verified / invalid from" error is automatically
#     retried from RESEND_SANDBOX_FROM (onboarding@resend.dev) which Resend always
#     accepts — so verification emails are delivered immediately during rollout.
RESEND_API_KEY_FALLBACK = os.environ.get("RESEND_API_KEY_FALLBACK", "").strip()
RESEND_DEFAULT_FROM = "BIBI Cars <noreply@bibicars.eu>"
RESEND_SANDBOX_FROM = "BIBI Cars <onboarding@resend.dev>"


class EmailChannel:
    """Email dispatcher — три режима, выбор автоматический:

    1) **Resend** — если в env есть ``RESEND_API_KEY``. Самый простой production
       вариант: один HTTP-запрос на ``api.resend.com``. Поддерживает HTML+text.
    2) **SMTP** — если в БД ``integration_configs.email`` сохранён валидный
       блок ``credentials`` (``smtpHost`` + ``smtpLogin`` + ``smtpPassword``)
       и ``isEnabled=True``. Admin настраивает это через ``/admin/integrations``
       без рестарта.
    3) **dry_run** — если ни Resend, ни SMTP не настроены. Письма НЕ
       отправляются никуда; вместо этого они складываются в ``email_outbox``
       со статусом ``dry_run``, чтобы admin видел *что бы было отправлено*.

    Каждая попытка отправки (успешная или нет) пишется в ``email_outbox``
    через ``EmailOutboxRepository``.
    """

    def __init__(self, db):
        self.db = db
        from app.repositories import EmailOutboxRepository
        self._outbox_repo = EmailOutboxRepository(db)
        # Env-level Resend (legacy fallback). UI-level config из integration_configs.resend
        # имеет приоритет и резолвится лениво на каждом send() через _resolve_resend_cfg().
        # Hardcoded production fallback so transactional email keeps working
        # even on a fresh deploy where neither .env nor integration_configs
        # carry the key yet. Admin can always override via /admin/integrations
        # (integration_configs.resend) which has the highest priority.
        self.api_key = os.environ.get("RESEND_API_KEY") or RESEND_API_KEY_FALLBACK
        self.from_addr = os.environ.get("RESEND_FROM") or RESEND_DEFAULT_FROM
        self.reply_to = os.environ.get("RESEND_REPLY_TO")
        # Mode определяется лениво в момент send(), потому что и Resend, и SMTP
        # могут быть включены через UI после старта приложения.
        self.provider = "resend" if self.api_key else "auto"

    async def _resolve_resend_cfg(self) -> Optional[Dict[str, Any]]:
        """Читает live-конфиг Resend из БД (integration_configs.resend).

        Структура документа (как и у sms/email):
          {
            provider: "resend",
            isEnabled: true,
            credentials: { apiKey: "re_xxx" },
            settings: { from: "...", replyTo: "..." },
          }

        Возвращает dict с ключами api_key/from/reply_to ИЛИ None.

        Если в БД ничего не найдено, fallback на env (RESEND_API_KEY).
        Это даёт admin-у возможность настраивать Resend без рестарта,
        но не ломает старые деплои, у которых ключ в .env.
        """
        try:
            doc = (
                await self.db.integration_configs.find_one({"provider": "resend"})
                or await self.db.integration_configs.find_one({"_id": "resend"})
                or await self.db.integration_configs.find_one({"id": "resend"})
            )
            if doc and doc.get("isEnabled"):
                creds = doc.get("credentials") or {}
                settings = doc.get("settings") or {}
                api_key = (creds.get("apiKey") or creds.get("resendKey") or "").strip()
                if api_key:
                    return {
                        "api_key": api_key,
                        "from": (creds.get("from") or settings.get("from") or self.from_addr).strip(),
                        "reply_to": (creds.get("replyTo") or settings.get("replyTo") or self.reply_to or "").strip() or None,
                        "source": "db",
                    }
        except Exception as e:  # noqa: BLE001
            logger.warning("[email] resend db config load failed: %s", e)
        # env fallback
        if self.api_key:
            return {
                "api_key": self.api_key,
                "from": self.from_addr,
                "reply_to": self.reply_to,
                "source": "env",
            }
        return None

    async def _resolve_smtp_cfg(self) -> Optional[Dict[str, Any]]:
        """Читает live-конфиг email-интеграции из БД."""
        try:
            doc = (
                await self.db.integration_configs.find_one({"provider": "email"})
                or await self.db.integration_configs.find_one({"_id": "email"})
                or await self.db.integration_configs.find_one({"id": "email"})
            )
            if not doc or not doc.get("isEnabled"):
                return None
            creds = doc.get("credentials") or {}
            if not (creds.get("smtpHost") and creds.get("smtpLogin") and creds.get("smtpPassword")):
                return None
            return {
                "host":  creds["smtpHost"],
                "port":  int(creds.get("smtpPort") or 587),
                "login": creds["smtpLogin"],
                "pwd":   creds["smtpPassword"],
                "from":  creds.get("from") or doc.get("settings", {}).get("from") or self.from_addr,
                "use_ssl": bool(creds.get("smtpSecure") or False),
            }
        except Exception as e:  # noqa: BLE001
            logger.warning("[email] smtp config load failed: %s", e)
            return None

    async def send(self, *, to: str, subject: str, html: str, text: str = "",
                   event: str = "", context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        record = {
            "id": str(uuid.uuid4()),
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
            "event": event,
            "context": context or {},
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # ── Mock transport (TESTING ONLY) ──────────────────────────────
        # Proves the provider-adapter path end-to-end without real
        # credentials and WITHOUT touching the network. Enabled only when
        # EMAIL_MOCK_TRANSPORT is set (success|fail). Off in production.
        _mock = os.environ.get("EMAIL_MOCK_TRANSPORT", "").strip().lower()
        if _mock in ("1", "true", "success", "sent", "fail", "failed"):
            ok = _mock not in ("fail", "failed")
            record["provider"] = "mock"
            record["status"] = "sent" if ok else "failed"
            if ok:
                record["provider_response"] = {"id": f"mock_{uuid.uuid4().hex[:12]}"}
                record["provider_status"] = 200
            else:
                record["provider_status"] = 502
                record["provider_error"] = "Mock transport forced failure"
            try:
                await self._outbox_repo.record_email_send_attempt(record)
            except Exception:
                logger.exception("[email] outbox insert failed")
            return {"ok": ok, "mode": "mock", "id": record["id"],
                    "status": record["status"],
                    "provider_id": (record.get("provider_response") or {}).get("id"),
                    "error": record.get("provider_error")}

        # ── Resend (DB-config preferred, env fallback) ─────────────────
        resend_cfg = await self._resolve_resend_cfg()
        if resend_cfg:
            record["provider"] = "resend"
            record["provider_source"] = resend_cfg["source"]

            async def _resend_post(from_addr: str):
                """Single POST to Resend. Returns (status_code, body_dict)."""
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.resend.com/emails",
                        headers={
                            "Authorization": f"Bearer {resend_cfg['api_key']}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "from": from_addr,
                            "to": [to],
                            "subject": subject,
                            "html": html,
                            **({"text": text} if text else {}),
                            **({"reply_to": resend_cfg["reply_to"]} if resend_cfg["reply_to"] else {}),
                        },
                    )
                return resp.status_code, (resp.json() if resp.content else {})

            def _is_domain_error(status: int, body: Dict[str, Any]) -> bool:
                """True when Resend rejected the From because its domain is not
                yet verified (HTTP 403/422 with a domain/verify message)."""
                if status < 300:
                    return False
                msg = ((body or {}).get("message") or (body or {}).get("error") or "").lower()
                if status in (403, 422):
                    return ("domain" in msg) or ("not verified" in msg) or ("verify" in msg) or ("testing emails" in msg)
                return False

            try:
                status_code, body = await _resend_post(resend_cfg["from"])

                # Auto-fallback: domain (e.g. bibicars.org) still pending Resend
                # verification → retry from the always-allowed sandbox sender so
                # the email is actually delivered during rollout.
                if _is_domain_error(status_code, body) and RESEND_SANDBOX_FROM not in (resend_cfg["from"] or ""):
                    logger.warning(
                        "[email/resend] from=%s rejected (domain not verified) — retrying from %s",
                        resend_cfg["from"], RESEND_SANDBOX_FROM,
                    )
                    fb_status, fb_body = await _resend_post(RESEND_SANDBOX_FROM)
                    record["fallback_used"] = True
                    record["fallback_from"] = RESEND_SANDBOX_FROM
                    record["primary_from_error"] = (
                        (body or {}).get("message") or (body or {}).get("error") or f"HTTP {status_code}"
                    )
                    status_code, body = fb_status, fb_body

                record["status"] = "sent" if status_code < 300 else "failed"
                record["provider_response"] = body
                record["provider_status"] = status_code
                if status_code >= 300:
                    record["provider_error"] = (
                        (body or {}).get("message") or (body or {}).get("error") or f"HTTP {status_code}"
                    )
            except Exception as e:
                record["status"] = "failed"
                record["provider_error"] = str(e)
                logger.exception("[email/resend] send failed")

            try:
                await self._outbox_repo.record_email_send_attempt(record)
            except Exception:
                logger.exception("[email] outbox insert failed")
            return {"ok": record["status"] == "sent", "mode": "resend", "id": record["id"],
                    "status": record["status"],
                    "provider_id": (record.get("provider_response") or {}).get("id"),
                    "error": record.get("provider_error")}

        # ── SMTP (admin UI) ────────────────────────────────────────────
        smtp_cfg = await self._resolve_smtp_cfg()
        if smtp_cfg:
            record["provider"] = "smtp"
            try:
                import smtplib, ssl
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = smtp_cfg["from"]
                msg["To"] = to
                if text:
                    msg.attach(MIMEText(text, "plain", "utf-8"))
                msg.attach(MIMEText(html or text or "", "html", "utf-8"))
                # Run blocking smtplib in a thread.
                import asyncio as _asyncio
                def _smtp_send():
                    if smtp_cfg["use_ssl"] or smtp_cfg["port"] == 465:
                        srv = smtplib.SMTP_SSL(smtp_cfg["host"], smtp_cfg["port"], timeout=15,
                                               context=ssl.create_default_context())
                    else:
                        srv = smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=15)
                        srv.ehlo()
                        try:
                            srv.starttls(context=ssl.create_default_context())
                            srv.ehlo()
                        except Exception:
                            pass
                    try:
                        srv.login(smtp_cfg["login"], smtp_cfg["pwd"])
                        srv.sendmail(smtp_cfg["from"], [to], msg.as_string())
                    finally:
                        try: srv.quit()
                        except Exception: pass
                await _asyncio.to_thread(_smtp_send)
                record["status"] = "sent"
            except Exception as e:
                record["status"] = "failed"
                record["provider_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                logger.exception("[email/smtp] send failed")

            try:
                await self._outbox_repo.record_email_send_attempt(record)
            except Exception:
                logger.exception("[email] outbox insert failed")
            return {"ok": record["status"] == "sent", "mode": "smtp", "id": record["id"],
                    "status": record["status"], "error": record.get("provider_error")}

        # ── dry_run ────────────────────────────────────────────────────
        record["provider"] = "dry_run"
        record["status"] = "dry_run"
        logger.info("[email/dry_run] %s → %s | event=%s (no provider configured)", subject, to, event)
        await self._outbox_repo.record_email_send_dry_run(record)
        return {"ok": True, "mode": "dry_run", "id": record["id"], "status": "dry_run"}


class InAppChannel:
    """In-app notification = one document per recipient user in `notifications`."""

    def __init__(self, db, sio=None):
        self.db = db
        self.sio = sio

    async def send(self, *, user_id: str, title: str, message: str, event: str,
                   severity: str = "info", meta: Dict[str, Any] | None = None,
                   sound_key: Optional[str] = None) -> Dict[str, Any]:
        if not user_id:
            return {"ok": False, "error": "user_id required"}
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": f"notif_{int(datetime.now(timezone.utc).timestamp()*1000)}_{uuid.uuid4().hex[:6]}",
            "userId": user_id,
            "type": event,
            "event": event,
            "title": title,
            "message": message,
            "severity": severity,
            "meta": meta or {},
            "soundKey": sound_key or _default_sound(event),
            "read": False,
            "isRead": False,
            "created_at": now,
            "createdAt": now,
        }
        await self.db.notifications.insert_one(doc)
        doc.pop("_id", None)
        # Live push via socket.io (frontend uses /notifications room already)
        if self.sio:
            try:
                await self.sio.emit("notification", doc, namespace="/notifications")
            except Exception:
                logger.exception("[in_app] socket emit failed")
        return {"ok": True, "id": doc["id"]}


# ── SMS channel ─────────────────────────────────────────────────────────
class SmsChannel:
    """SMS dispatcher — TextBelt provider, **бесплатно по умолчанию**.

    Архитектура каналов та же, что у EmailChannel:

    1) **TextBelt FREE** — если admin ничего не ввёл, используем публичный
       ключ ``textbelt`` → 1 SMS в день с одного IP **без регистрации**.
       Достаточно для smoke-test'ов и редких критичных оповещений
       (например, `payment_reminder` мастер-админу).
    2) **TextBelt paid** — admin вводит свой ключ через
       ``/admin/integrations`` → ``sms``. Тогда канал работает без лимитов
       (~$0.01-0.10 за SMS в зависимости от страны). Регистрация на
       textbelt.com одна минута, без верификации компании.
    3) **dry_run** — если admin явно выключил SMS (`isEnabled: false`),
       сообщения никуда не уходят, только пишутся в `sms_outbox`.

    Каждая попытка отправки (успех/неудача) пишется в коллекцию
    ``sms_outbox`` — admin видит, что и куда уходило.
    """

    DEFAULT_TEXTBELT_KEY = "textbelt"  # public free key, 1 SMS/day/IP

    def __init__(self, db):
        self.db = db

    async def _resolve_cfg(self) -> Dict[str, Any]:
        """Читает live-конфиг sms-интеграции из БД. Возвращает dict с
        ключами provider/api_key/enabled/sender. Если запись не найдена —
        возвращает default (textbelt free)."""
        try:
            doc = (
                await self.db.integration_configs.find_one({"provider": "sms"})
                or await self.db.integration_configs.find_one({"_id": "sms"})
                or await self.db.integration_configs.find_one({"id": "sms"})
            ) or {}
        except Exception:
            doc = {}
        creds = doc.get("credentials") or {}
        settings = doc.get("settings") or {}
        # If admin explicitly disabled — dry_run.
        enabled = doc.get("isEnabled")
        if enabled is False:
            return {"provider": "dry_run", "api_key": "", "enabled": False, "sender": ""}
        # Provider can be "textbelt" only (for now). Future: nikita, sms.ru...
        provider = (creds.get("provider") or settings.get("provider") or "textbelt").lower()
        api_key = (creds.get("apiKey") or creds.get("textbeltKey") or "").strip()
        if not api_key:
            api_key = self.DEFAULT_TEXTBELT_KEY
        sender = (settings.get("sender") or creds.get("sender") or "BIBI Cars")[:11]
        return {"provider": provider, "api_key": api_key, "enabled": True, "sender": sender}

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        """E.164-ish нормализация: оставляем только цифры и ведущий «+»."""
        if not raw:
            return ""
        cleaned = "".join(ch for ch in str(raw) if ch.isdigit() or ch == "+")
        if cleaned and not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        return cleaned

    @staticmethod
    def _strip_html(html: str) -> str:
        """Простейший html→plain для SMS-длины. Без зависимостей."""
        if not html:
            return ""
        text = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def send(self, *, to: str, message: str, event: str = "",
                   context: Dict[str, Any] | None = None,
                   subject: str = "") -> Dict[str, Any]:
        phone = self._normalize_phone(to)
        cfg = await self._resolve_cfg()
        # Truncate to single-segment-friendly length (160 chars ASCII; here we go up to 320 — ~2 segments).
        body = (subject + ": " + message) if subject else message
        body = self._strip_html(body)
        if len(body) > 320:
            body = body[:317] + "..."

        record = {
            "id": str(uuid.uuid4()),
            "to": phone,
            "raw_to": to,
            "message": body,
            "event": event,
            "context": context or {},
            "provider": cfg["provider"],
            "sender": cfg["sender"],
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if not phone:
            record["status"] = "failed"
            record["provider_error"] = "Empty/invalid phone"
            await self._record(record)
            return {"ok": False, "mode": cfg["provider"], "id": record["id"], "error": "no_phone"}

        if not cfg["enabled"] or cfg["provider"] == "dry_run":
            record["status"] = "dry_run"
            record["provider"] = "dry_run"
            logger.info("[sms/dry_run] %s → %s | event=%s", body[:80], phone, event)
            await self._record(record)
            return {"ok": True, "mode": "dry_run", "id": record["id"]}

        # ── TextBelt ─────────────────────────────────────────────────
        if cfg["provider"] == "textbelt":
            try:
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.post(
                        "https://textbelt.com/text",
                        data={
                            "phone":   phone,
                            "message": body,
                            "key":     cfg["api_key"],
                            "sender":  cfg["sender"],
                        },
                    )
                payload = r.json() if r.content else {}
                ok = bool(payload.get("success"))
                record["status"] = "sent" if ok else "failed"
                record["provider_response"] = payload
                record["provider_status"] = r.status_code
                if not ok:
                    record["provider_error"] = payload.get("error") or f"HTTP {r.status_code}"
            except Exception as e:
                record["status"] = "failed"
                record["provider_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                logger.exception("[sms/textbelt] send failed")

            await self._record(record)
            return {"ok": record["status"] == "sent", "mode": "textbelt", "id": record["id"]}

        # Unknown provider
        record["status"] = "failed"
        record["provider_error"] = f"Unknown sms provider: {cfg['provider']}"
        await self._record(record)
        return {"ok": False, "mode": cfg["provider"], "id": record["id"]}

    async def _record(self, doc: Dict[str, Any]) -> None:
        try:
            await self.db.sms_outbox.insert_one(doc)
        except Exception:
            logger.exception("[sms] outbox insert failed")


def _default_sound(event: str) -> str:
    return {
        EVENT_PAYMENT_CONFIRMED: "payment",
        EVENT_ORDER_FINISHED:    "success",
        EVENT_PAYMENT_REMINDER:  "alert",
    }.get(event, "alert")


# ── template rendering ─────────────────────────────────────────────────
_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def render(text: str, context: Dict[str, Any]) -> str:
    """Very small {{ path.to.value }} renderer — no eval, no surprises."""
    if not text:
        return ""

    def _resolve(path: str) -> str:
        cur: Any = context
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif cur is not None and hasattr(cur, part):
                cur = getattr(cur, part)
            else:
                return ""
            if cur is None:
                return ""
        return str(cur)

    return _TOKEN.sub(lambda m: _resolve(m.group(1)), text)


def money(amount, currency: str = "USD") -> str:
    try:
        a = float(amount or 0)
    except Exception:
        a = 0
    return f"{a:,.2f} {(currency or 'USD').upper()}"


# ── defaults (seeded on boot) ──────────────────────────────────────────
# NOTE: edit in /admin/settings/email-templates — these are just seeds.
DEFAULT_TEMPLATES = [
    # ── INVOICE SENT ──────────────────────────────────────────────
    {
        "event": EVENT_INVOICE_SENT,
        "audience": "customer",
        "lang": "ua",
        "subject": "Новий рахунок №{{ invoice.id }} · {{ invoice.total_fmt }}",
        "html": """
            <h2 style="color:#18181B">Вітаємо, {{ customer.name }}!</h2>
            <p>Ваш менеджер {{ manager.name }} сформував рахунок <b>{{ invoice.id }}</b> на суму <b>{{ invoice.total_fmt }}</b>.</p>
            <p>Ви можете сплатити його за посиланням або зв'язатися з менеджером для уточнень.</p>
            <p style="margin-top:24px;color:#71717A">— команда BIBI Cars</p>
        """,
        "text_template": "Привіт, {{ customer.name }}! Рахунок {{ invoice.id }} на {{ invoice.total_fmt }} готовий до оплати.",
    },
    {
        "event": EVENT_INVOICE_SENT,
        "audience": "customer",
        "lang": "en",
        "subject": "New invoice #{{ invoice.id }} · {{ invoice.total_fmt }}",
        "html": """
            <h2>Hi {{ customer.name }},</h2>
            <p>Your manager {{ manager.name }} has issued invoice <b>{{ invoice.id }}</b> for <b>{{ invoice.total_fmt }}</b>.</p>
            <p>You can pay it via the link or contact your manager for details.</p>
            <p style="margin-top:24px;color:#71717A">— BIBI Cars team</p>
        """,
        "text_template": "Hi {{ customer.name }}! Invoice {{ invoice.id }} for {{ invoice.total_fmt }} is ready for payment.",
    },
    {
        "event": EVENT_INVOICE_SENT,
        "audience": "customer",
        "lang": "bg",
        "subject": "Нова фактура №{{ invoice.id }} · {{ invoice.total_fmt }}",
        "html": """
            <h2 style="color:#18181B">Здравейте, {{ customer.name }}!</h2>
            <p>Вашият мениджър {{ manager.name }} издаде фактура <b>{{ invoice.id }}</b> на стойност <b>{{ invoice.total_fmt }}</b>.</p>
            <p>Можете да я платите чрез линка или да се свържете с мениджъра за уточнения.</p>
            <p style="margin-top:24px;color:#71717A">— екипът на BIBI Cars</p>
        """,
        "text_template": "Здравейте, {{ customer.name }}! Фактура {{ invoice.id }} на стойност {{ invoice.total_fmt }} е готова за плащане.",
    },
    # ── PAYMENT CONFIRMED ────────────────────────────────────────
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "audience": "customer",
        "lang": "ua",
        "subject": "Оплату прийнято · {{ invoice.id }}",
        "html": """
            <h2 style="color:#059669">Дякуємо, {{ customer.name }}!</h2>
            <p>Ми отримали вашу оплату за рахунком <b>{{ invoice.id }}</b> на суму <b>{{ invoice.total_fmt }}</b>.</p>
            <p>Команда BIBI Cars вже почала роботу над вашим замовленням. Статус можна відслідковувати в особистому кабінеті.</p>
        """,
    },
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "audience": "customer",
        "lang": "en",
        "subject": "Payment received · {{ invoice.id }}",
        "html": """
            <h2 style="color:#059669">Thank you, {{ customer.name }}!</h2>
            <p>We have received your payment for invoice <b>{{ invoice.id }}</b>, amount <b>{{ invoice.total_fmt }}</b>.</p>
            <p>BIBI Cars team is starting to work on your order. You can track the progress in your cabinet.</p>
        """,
    },
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "audience": "customer",
        "lang": "bg",
        "subject": "Плащането е получено · {{ invoice.id }}",
        "html": """
            <h2 style="color:#059669">Благодарим, {{ customer.name }}!</h2>
            <p>Получихме вашето плащане по фактура <b>{{ invoice.id }}</b> на стойност <b>{{ invoice.total_fmt }}</b>.</p>
            <p>Екипът на BIBI Cars вече започна работа по поръчката ви. Можете да проследявате прогреса в личния си кабинет.</p>
        """,
    },
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "audience": "manager",
        "lang": "ua",
        "subject": "[inApp] Оплата по {{ invoice.id }}",
        "html": "Клієнт {{ customer.name }} оплатив {{ invoice.total_fmt }} — замовлення створено.",
    },
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "audience": "manager",
        "lang": "en",
        "subject": "[inApp] Payment on {{ invoice.id }}",
        "html": "Customer {{ customer.name }} paid {{ invoice.total_fmt }} — order created.",
    },
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "audience": "manager",
        "lang": "bg",
        "subject": "[inApp] Плащане по {{ invoice.id }}",
        "html": "Клиент {{ customer.name }} плати {{ invoice.total_fmt }} — поръчката е създадена.",
    },
    # ── ORDER STARTED ────────────────────────────────────────────
    {
        "event": EVENT_ORDER_STARTED,
        "audience": "customer",
        "lang": "ua",
        "subject": "Замовлення {{ order.id }} в роботі",
        "html": """
            <h2>Замовлення в роботі 🚀</h2>
            <p>Ми почали виконувати послуги за рахунком <b>{{ invoice.id }}</b>.</p>
            <p>Кількість етапів: {{ order.steps_total }}. Дивіться прогрес у особистому кабінеті.</p>
        """,
    },
    {
        "event": EVENT_ORDER_STARTED,
        "audience": "customer",
        "lang": "en",
        "subject": "Order {{ order.id }} in progress",
        "html": """
            <h2>Your order is in progress 🚀</h2>
            <p>We started executing services from invoice <b>{{ invoice.id }}</b>.</p>
            <p>Total steps: {{ order.steps_total }}. Track status in your cabinet.</p>
        """,
    },
    {
        "event": EVENT_ORDER_STARTED,
        "audience": "customer",
        "lang": "bg",
        "subject": "Поръчка {{ order.id }} е в процес",
        "html": """
            <h2>Поръчката ви е в процес 🚀</h2>
            <p>Започнахме изпълнението на услугите по фактура <b>{{ invoice.id }}</b>.</p>
            <p>Общо стъпки: {{ order.steps_total }}. Проследявайте статуса в личния си кабинет.</p>
        """,
    },
    {
        "event": EVENT_ORDER_STARTED,
        "audience": "manager",
        "lang": "ua",
        "subject": "[inApp] Нове замовлення {{ order.id }}",
        "html": "Запустилось замовлення {{ order.id }} — {{ order.steps_total }} кроків.",
    },
    {
        "event": EVENT_ORDER_STARTED,
        "audience": "manager",
        "lang": "en",
        "subject": "[inApp] New order {{ order.id }}",
        "html": "Order {{ order.id }} started — {{ order.steps_total }} steps.",
    },
    {
        "event": EVENT_ORDER_STARTED,
        "audience": "manager",
        "lang": "bg",
        "subject": "[inApp] Нова поръчка {{ order.id }}",
        "html": "Поръчка {{ order.id }} стартира — {{ order.steps_total }} стъпки.",
    },
    # ── ORDER FINISHED ───────────────────────────────────────────
    {
        "event": EVENT_ORDER_FINISHED,
        "audience": "customer",
        "lang": "ua",
        "subject": "Замовлення {{ order.id }} виконано ✓",
        "html": """
            <h2>Готово!</h2>
            <p>Ваше замовлення <b>{{ order.id }}</b> успішно виконано. Дякуємо, що обрали BIBI Cars.</p>
        """,
    },
    {
        "event": EVENT_ORDER_FINISHED,
        "audience": "customer",
        "lang": "en",
        "subject": "Order {{ order.id }} completed ✓",
        "html": """
            <h2>Done!</h2>
            <p>Your order <b>{{ order.id }}</b> has been completed. Thank you for choosing BIBI Cars.</p>
        """,
    },
    {
        "event": EVENT_ORDER_FINISHED,
        "audience": "customer",
        "lang": "bg",
        "subject": "Поръчка {{ order.id }} е приключена ✓",
        "html": """
            <h2>Готово!</h2>
            <p>Вашата поръчка <b>{{ order.id }}</b> е успешно приключена. Благодарим, че избрахте BIBI Cars.</p>
        """,
    },
    {
        "event": EVENT_ORDER_FINISHED,
        "audience": "manager",
        "lang": "ua",
        "subject": "[inApp] Замовлення {{ order.id }} виконано",
        "html": "Всі кроки завершено. Клієнт: {{ customer.name }}.",
    },
    {
        "event": EVENT_ORDER_FINISHED,
        "audience": "manager",
        "lang": "en",
        "subject": "[inApp] Order {{ order.id }} finished",
        "html": "All steps completed. Customer: {{ customer.name }}.",
    },
    {
        "event": EVENT_ORDER_FINISHED,
        "audience": "manager",
        "lang": "bg",
        "subject": "[inApp] Поръчка {{ order.id }} приключена",
        "html": "Всички стъпки са завършени. Клиент: {{ customer.name }}.",
    },
    # ── PAYMENT REMINDER ─────────────────────────────────────────
    {
        "event": EVENT_PAYMENT_REMINDER,
        "audience": "customer",
        "lang": "ua",
        "subject": "Нагадування про оплату · {{ invoice.id }}",
        "html": """
            <h2>Нагадуємо про оплату</h2>
            <p>Рахунок <b>{{ invoice.id }}</b> на суму <b>{{ invoice.total_fmt }}</b> ще не сплачений.</p>
            <p>Будь ласка, оплатіть якомога швидше — або зв'яжіться з менеджером, якщо потрібна допомога.</p>
        """,
    },
    {
        "event": EVENT_PAYMENT_REMINDER,
        "audience": "customer",
        "lang": "en",
        "subject": "Payment reminder · {{ invoice.id }}",
        "html": """
            <h2>Friendly reminder</h2>
            <p>Invoice <b>{{ invoice.id }}</b> for <b>{{ invoice.total_fmt }}</b> is still unpaid.</p>
            <p>Please settle it at your earliest convenience, or contact your manager if you need help.</p>
        """,
    },
    {
        "event": EVENT_PAYMENT_REMINDER,
        "audience": "customer",
        "lang": "bg",
        "subject": "Напомняне за плащане · {{ invoice.id }}",
        "html": """
            <h2>Напомняме за плащане</h2>
            <p>Фактура <b>{{ invoice.id }}</b> на стойност <b>{{ invoice.total_fmt }}</b> все още не е платена.</p>
            <p>Моля, погасете я възможно най-скоро или се свържете с мениджъра си, ако имате нужда от помощ.</p>
        """,
    },
    {
        "event": EVENT_PAYMENT_REMINDER,
        "audience": "manager",
        "lang": "ua",
        "subject": "[inApp] Нагадування надіслано · {{ invoice.id }}",
        "html": "Клієнту {{ customer.name }} відправлено нагадування щодо {{ invoice.total_fmt }}.",
    },
    {
        "event": EVENT_PAYMENT_REMINDER,
        "audience": "manager",
        "lang": "en",
        "subject": "[inApp] Reminder dispatched · {{ invoice.id }}",
        "html": "Reminder sent to {{ customer.name }} for {{ invoice.total_fmt }}.",
    },
    {
        "event": EVENT_PAYMENT_REMINDER,
        "audience": "manager",
        "lang": "bg",
        "subject": "[inApp] Изпратено напомняне · {{ invoice.id }}",
        "html": "Изпратено е напомняне към {{ customer.name }} за {{ invoice.total_fmt }}.",
    },
    # ── PROVIDER TIER CHANGED ─────────────────────────────────────
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "audience": "manager",
        "lang": "ua",
        "subject": "[inApp] Твій рівень змінився · {{ new_tier }} (score {{ score }})",
        "html": "{{ message_ua }} · score {{ score }} · {{ prev_tier }} → {{ new_tier }}",
    },
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "audience": "manager",
        "lang": "en",
        "subject": "[inApp] Your tier changed · {{ new_tier }} (score {{ score }})",
        "html": "{{ message_en }} · score {{ score }} · {{ prev_tier }} → {{ new_tier }}",
    },
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "audience": "manager",
        "lang": "bg",
        "subject": "[inApp] Вашето ниво се промени · {{ new_tier }} (score {{ score }})",
        "html": "{{ message_bg }} · score {{ score }} · {{ prev_tier }} → {{ new_tier }}",
    },
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "audience": "master_admin",
        "lang": "ua",
        "subject": "[inApp] Менеджер {{ manager.name }} — {{ prev_tier }} → {{ new_tier }}",
        "html": "Менеджер {{ manager.name }} ({{ manager.email }}) {{ prev_tier }} → <b>{{ new_tier }}</b>, score {{ score }}.",
    },
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "audience": "master_admin",
        "lang": "en",
        "subject": "[inApp] Manager {{ manager.name }} — {{ prev_tier }} → {{ new_tier }}",
        "html": "Manager {{ manager.name }} ({{ manager.email }}) moved {{ prev_tier }} → <b>{{ new_tier }}</b>, score {{ score }}.",
    },
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "audience": "master_admin",
        "lang": "bg",
        "subject": "[inApp] Мениджър {{ manager.name }} — {{ prev_tier }} → {{ new_tier }}",
        "html": "Мениджър {{ manager.name }} ({{ manager.email }}) премина {{ prev_tier }} → <b>{{ new_tier }}</b>, score {{ score }}.",
    },
]


# Default routing rules — which audiences / channels get each event
DEFAULT_RULES = [
    {
        "event": EVENT_INVOICE_SENT,
        "enabled": True,
        "targets": [
            {"audience": "customer", "channels": ["email"]},
        ],
    },
    {
        "event": EVENT_PAYMENT_CONFIRMED,
        "enabled": True,
        "targets": [
            {"audience": "customer", "channels": ["email"]},
            {"audience": "manager",  "channels": ["in_app"]},
        ],
    },
    {
        "event": EVENT_ORDER_STARTED,
        "enabled": True,
        "targets": [
            {"audience": "customer", "channels": ["email"]},
            {"audience": "manager",  "channels": ["in_app"]},
        ],
    },
    {
        "event": EVENT_ORDER_FINISHED,
        "enabled": True,
        "targets": [
            {"audience": "customer", "channels": ["email"]},
            {"audience": "manager",  "channels": ["in_app"]},
        ],
    },
    {
        "event": EVENT_PAYMENT_REMINDER,
        "enabled": True,
        "targets": [
            {"audience": "customer", "channels": ["email"]},
            {"audience": "manager",  "channels": ["in_app"]},
        ],
    },
    {
        "event": EVENT_PROVIDER_TIER_CHANGED,
        "enabled": True,
        "targets": [
            {"audience": "manager",     "channels": ["in_app"]},
            {"audience": "master_admin","channels": ["in_app"]},
        ],
    },
]


# ── NotificationService ────────────────────────────────────────────────
class NotificationService:
    def __init__(self, db, sio=None):
        self.db = db
        self.email = EmailChannel(db)
        self.in_app = InAppChannel(db, sio)
        self.sms = SmsChannel(db)
        # Phase 5.3 / C-8 — db.email_templates ownership routes
        # through EmailTemplateRepository.
        # Phase 5.3 / C-9 — db.notification_rules ownership
        # routes through NotificationRuleRepository. Both
        # repositories are constructed once at service
        # construction and reused across seed_defaults /
        # get_template / get_rule / dispatch call paths.
        from app.repositories import (
            EmailTemplateRepository,
            NotificationRuleRepository,
        )
        self._templates_repo = EmailTemplateRepository(db)
        self._rules_repo = NotificationRuleRepository(db)

    async def seed_defaults(self) -> None:
        """Insert default rules + templates if collections are empty.
        Idempotent — will never overwrite user edits."""
        if await self._rules_repo.count_all() == 0:
            docs = []
            for r in DEFAULT_RULES:
                docs.append({
                    "id": f"rule_{r['event']}",
                    **r,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            await self._rules_repo.bulk_create(docs)
            if docs:
                logger.info("[notif] seeded %d notification rules", len(docs))

        if await self._templates_repo.count_all() == 0:
            docs = []
            for t in DEFAULT_TEMPLATES:
                docs.append({
                    "id": f"tpl_{t['event']}_{t['audience']}_{t['lang']}",
                    **t,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            await self._templates_repo.bulk_create(docs)
            if docs:
                logger.info("[notif] seeded %d email templates", len(docs))

    async def get_rule(self, event: str) -> Dict[str, Any]:
        r = await self._rules_repo.find_by_event(event)
        if r:
            return r
        # fallback to compiled default
        for d in DEFAULT_RULES:
            if d["event"] == event:
                return {"id": f"rule_{event}", **d, "created_at": None}
        return {"event": event, "enabled": False, "targets": []}

    async def get_template(self, event: str, audience: str, lang: str) -> Dict[str, Any]:
        # Normalise lang (uk → ua is a legacy alias)
        norm = (lang or "").strip().lower()
        if norm == "uk":
            norm = "ua"
        # Try exact match → fallback (lang → en → ua → bg).
        # Customers can be EN/BG/UK; managers/admins were historically UA/EN.
        # `en` is the universal fallback because every event has an EN seed.
        seen = []
        for ll in (norm, "en", "ua", "bg"):
            if not ll or ll in seen:
                continue
            seen.append(ll)
            t = await self._templates_repo.find_for_dispatch(
                event, audience=audience, lang=ll,
            )
            if t:
                return t
        # Generic defaults from code (same fallback chain)
        for ll in seen:
            for d in DEFAULT_TEMPLATES:
                if d["event"] == event and d["audience"] == audience and d["lang"] == ll:
                    return d
        # last resort: any default for this event+audience
        for d in DEFAULT_TEMPLATES:
            if d["event"] == event and d["audience"] == audience:
                return d
        return {"subject": event, "html": event, "text_template": ""}

    async def _resolve_recipients(self, audience: str, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return list of recipient dicts: {email, name, lang, user_id}."""
        recs: List[Dict[str, Any]] = []
        customer = ctx.get("customer") or {}
        manager = ctx.get("manager") or {}
        invoice = ctx.get("invoice") or {}
        order = ctx.get("order") or {}

        if audience == "customer":
            email = customer.get("email") or ctx.get("customerEmail") or invoice.get("customerEmail")
            if email:
                recs.append({
                    "email": email,
                    "phone": customer.get("phone") or ctx.get("customerPhone") or invoice.get("customerPhone"),
                    "name": customer.get("name") or customer.get("firstName") or "",
                    "lang": (customer.get("lang") or customer.get("language") or "ua").lower()[:2],
                    "user_id": customer.get("id") or invoice.get("customerId") or order.get("customerId"),
                })
        elif audience == "manager":
            mid = manager.get("id") or invoice.get("managerId") or order.get("managerId")
            memail = manager.get("email") or invoice.get("managerEmail") or order.get("managerEmail")
            if mid or memail:
                recs.append({
                    "email": memail,
                    "phone": manager.get("phone") or invoice.get("managerPhone") or order.get("managerPhone"),
                    "name": manager.get("name") or memail or "",
                    "lang": (manager.get("lang") or "ua").lower()[:2],
                    "user_id": mid,
                })
        elif audience == "team_lead":
            async for u in self.db.users.find({"role": {"$in": ["team_lead"]}}, {"_id": 0}):
                recs.append({
                    "email": u.get("email"),
                    "phone": u.get("phone"),
                    "name": u.get("name") or u.get("email") or "",
                    "lang": (u.get("lang") or "ua").lower()[:2],
                    "user_id": u.get("id") or u.get("_id"),
                })
        elif audience == "master_admin":
            async for u in self.db.users.find({"role": {"$in": ["master_admin", "owner", "admin"]}}, {"_id": 0}):
                recs.append({
                    "email": u.get("email"),
                    "phone": u.get("phone"),
                    "name": u.get("name") or u.get("email") or "",
                    "lang": (u.get("lang") or "ua").lower()[:2],
                    "user_id": u.get("id") or u.get("_id"),
                })
        return recs

    async def dispatch(self, event: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Central dispatch: rule → audiences → channels → render → send."""
        rule = await self.get_rule(event)
        if not rule.get("enabled", True):
            logger.info("[notif] rule for %s disabled — skipping", event)
            return {"event": event, "skipped": True, "reason": "disabled"}

        # enrich context with convenience formatting
        ctx = dict(ctx or {})
        invoice = ctx.get("invoice") or {}
        if invoice and "total_fmt" not in invoice:
            invoice["total_fmt"] = money(invoice.get("total") or invoice.get("amount"), invoice.get("currency"))
            ctx["invoice"] = invoice
        order = ctx.get("order") or {}
        if order and "steps_total" not in order:
            order["steps_total"] = len(order.get("steps") or [])
            ctx["order"] = order
        customer = ctx.get("customer") or {}
        if customer and not customer.get("name"):
            customer["name"] = (customer.get("firstName") or customer.get("email") or "клієнт").strip()
            ctx["customer"] = customer

        sent = []
        for target in rule.get("targets", []):
            audience = target.get("audience")
            channels = set(target.get("channels", []))
            if not audience or not channels:
                continue
            recipients = await self._resolve_recipients(audience, ctx)
            for r in recipients:
                lang = r.get("lang") or "ua"
                tpl = await self.get_template(event, audience, lang)
                subject = render(tpl.get("subject") or event, ctx)
                html = render(tpl.get("html") or "", ctx)
                text = render(tpl.get("text_template") or "", ctx)

                if "email" in channels and r.get("email"):
                    await self.email.send(
                        to=r["email"], subject=subject, html=html, text=text,
                        event=event, context={"recipient": r},
                    )
                    sent.append({"audience": audience, "channel": "email", "to": r["email"]})
                if "in_app" in channels and r.get("user_id"):
                    await self.in_app.send(
                        user_id=r["user_id"],
                        title=subject,
                        message=_html_to_text(html),
                        event=event,
                        meta={"link": _default_link(event, ctx)},
                    )
                    sent.append({"audience": audience, "channel": "in_app", "user": r["user_id"]})
                if "sms" in channels and r.get("phone"):
                    sms_body = text or _html_to_text(html) or subject
                    await self.sms.send(
                        to=r["phone"],
                        message=sms_body,
                        subject=subject,
                        event=event,
                        context={"recipient": r},
                    )
                    sent.append({"audience": audience, "channel": "sms", "to": r["phone"]})
        return {"event": event, "sent": sent, "total": len(sent)}


def _html_to_text(html: str) -> str:
    """Dumb HTML → text stripper (good enough for in-app previews)."""
    if not html:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()[:240]


def _default_link(event: str, ctx: Dict[str, Any]) -> str:
    invoice = ctx.get("invoice") or {}
    order = ctx.get("order") or {}
    customer = ctx.get("customer") or {}
    customer_id = customer.get("id") or invoice.get("customerId") or order.get("customerId")

    # Manager/team in-app notifications → their own pages
    if event in (EVENT_PAYMENT_CONFIRMED, EVENT_ORDER_STARTED, EVENT_ORDER_FINISHED):
        if order.get("id"):
            return f"/manager/orders?focus={order['id']}"
        return "/manager/orders"
    if event == EVENT_INVOICE_SENT and invoice.get("id"):
        return f"/manager/invoices?focus={invoice['id']}"
    if event == EVENT_PAYMENT_REMINDER:
        if invoice.get("id"):
            return f"/manager/invoices?focus={invoice['id']}"
        return "/manager/invoices"
    return ""


# ── runtime singletons (wired up by server.py on startup) ─────────────
service: NotificationService | None = None


def init(db, sio=None) -> NotificationService:
    global service
    service = NotificationService(db, sio)
    # All business events flow through `service.dispatch`.
    async def _handler(payload):
        event = payload.pop("__event", None)
        if not event:
            return
        await service.dispatch(event, payload)
    # Register the same handler for every event
    for ev in ALL_EVENTS:
        bus.on(ev, _handler_for(ev))
    return service


def _handler_for(event: str):
    async def _h(payload):
        if service is None:
            return
        await service.dispatch(event, payload)
    return _h


async def emit(event: str, payload: Dict[str, Any]) -> None:
    """Sugar wrapper — used from server.py business logic."""
    await bus.emit(event, payload)


# ════════════════════════════════════════════════════════════════════════════
#   HTTP SURFACE  — absorbed from server.py on 2026-05-17  (Wave 1 / Commit 6)
# ════════════════════════════════════════════════════════════════════════════
#
# This block is the bounded HTTP surface for the notifications domain.
# It owns:
#   * 16 endpoints under /api/notifications/*  (user-facing CRUD + customer
#     read-only views + rule stubs + test)
#   * 3 endpoints under /api/admin/notification-rules*
#   * 3 endpoints under /api/admin/email-templates*
#   * 1 endpoint  under /api/admin/email-outbox
#   * 1 endpoint  under /api/admin/notifications/test-dispatch
#
# Discipline (per the refactor playbook):
#   * Mechanical move only — no behavior change.
#   * Pure HTTP surface: this block does NOT touch the EventBus, the
#     NotificationService, the InAppChannel sio.emit broadcast or any
#     async-worker code above.  Service / event infrastructure remains
#     untouched.
#   * stubs remain stubs (frontend backward-compat).
#   * `_notif` self-reference uses Python's late-binding closure on the
#     module's already-defined globals (ALL_EVENTS, DEFAULT_RULES,
#     AUDIENCES, CHANNELS, LANGUAGES, service).  This avoids a
#     pointless `import notifications` round-trip.
#
# !!! TEMP BRIDGE !!!  Lazy `_db()` resolver + `from fastapi import APIRouter`
# locally to keep this block self-contained.  Will graduate to module-level
# imports + DI in Phase 2.
# ════════════════════════════════════════════════════════════════════════════
from fastapi import APIRouter, Body, Depends, HTTPException  # noqa: E402
from security import require_admin, require_master_admin, require_user  # noqa: E402

# Phase 5.4 / C-4g — db_runtime accessor (module-level function reference).
# This imports the `get_db` CALLABLE at module-load time, not the database
# handle itself. Each invocation of `_db()` below re-reads the live Motor
# handle via `get_db()`, which resolves the module-private cached reference
# inside `app.core.db_runtime` at CALL-TIME. The lazy semantics of the
# legacy `from server import db` bridge are therefore preserved 1:1: no
# module-level db snapshot is taken, no constructor-time freeze happens,
# and rebinding via `db_runtime.set_db(...)` in `_main_startup()` is
# observed by every subsequent endpoint call.
#
# Boundary note: this accessor is for the HTTP surface block ONLY (the 23
# endpoints mounted on `router` below). The orchestration entry point —
# `init(db, sio)` (notifications.py:837) — continues to receive `db` via
# parameter capture from `server.py:_main_startup()` and is mandate-forbidden
# from being touched in C-4g (see PHASE5_4_C4G_CLOSED.md). The two surfaces
# (HTTP-block `_db()` vs orchestration `init()` capture) reach the SAME
# Motor object because the startup-time split-brain assertion at
# `server.py:2058` pins `get_db() is db` immediately before `init(db, sio)`
# runs.
from app.core.db_runtime import get_db  # noqa: E402 (C-4g: lazy-bridge → accessor)

router = APIRouter(tags=["notifications"])


def _db():
    """Lazy Mongo handle — resolves at call-time, not at module-load time.

    Phase 5.4 / C-4g — migrated from the legacy ``from server import db as
    _server_db`` lazy bridge to ``app.core.db_runtime.get_db()``. Lazy
    semantics preserved 1:1:
      * no module-level db capture (only the `get_db` callable is imported
        at module-load time — the db handle stays unread until call-time);
      * no constructor-time db freeze inside the HTTP surface block;
      * `_db()` continues to be a callable wrapper, invoked on each request,
        so post-startup rebinds are observed without restart.
    Object identity vs the orchestration boundary (`init(db, sio)` capture
    into `NotificationService.db`) is pinned by the startup-time split-brain
    assertion in `server.py:_main_startup()` immediately before
    `notifications.init(db, sio)` runs.
    """
    return get_db()


# ─────────── User-facing notifications CRUD ────────────────────────────────

@router.get("/api/notifications")
async def list_notifications(limit: int = 50):
    """List notifications"""
    db = _db()
    cursor = db.notifications.find({}, {'_id': 0}).sort('created_at', -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"success": True, "data": items}


@router.get("/api/notifications/me")
async def my_notifications(limit: int = 20, user: dict = Depends(require_user)):
    """My notifications (user-scoped)."""
    db = _db()
    q = {"userId": user.get("id")}
    cursor = db.notifications.find(q, {'_id': 0}).sort('created_at', -1).limit(int(limit))
    items = await cursor.to_list(length=int(limit))
    # Normalise shape expected by the frontend hook
    norm = []
    for n in items:
        norm.append({
            "id": n.get("id"),
            "type": n.get("type") or n.get("event"),
            "event": n.get("event") or n.get("type"),
            "title": n.get("title"),
            "message": n.get("message"),
            "severity": n.get("severity", "info"),
            "soundKey": n.get("soundKey"),
            "meta": n.get("meta") or {},
            # Доопр #22 — preserve i18n keys so the frontend can translate
            # the title/message into the user's current language.
            "i18n_key":    n.get("i18n_key"),
            "i18n_params": n.get("i18n_params") or {},
            "isRead": bool(n.get("isRead") if "isRead" in n else n.get("read")),
            "read": bool(n.get("read") if "read" in n else n.get("isRead")),
            "createdAt": n.get("createdAt") or n.get("created_at"),
            "created_at": n.get("created_at") or n.get("createdAt"),
        })
    unread = await db.notifications.count_documents({"userId": user.get("id"), "$or": [{"read": False}, {"isRead": False}]})
    return {"success": True, "notifications": norm, "data": norm, "unreadCount": unread}


@router.get("/api/notifications/unread-count")
async def notifications_unread_count(user: dict = Depends(require_user)):
    db = _db()
    count = await db.notifications.count_documents({"userId": user.get("id"), "$or": [{"read": False}, {"isRead": False}]})
    return {"success": True, "count": count}


@router.post("/api/notifications")
async def create_notification(data: Dict[str, Any] = Body(...)):
    """Create notification"""
    db = _db()
    notification = {
        "id": f"notif-{datetime.now(timezone.utc).timestamp()}",
        "type": data.get("type", "info"),
        "title": data.get("title"),
        "message": data.get("message"),
        "userId": data.get("userId"),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.notifications.insert_one(notification)
    return {"success": True, "id": notification["id"]}


@router.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(require_user)):
    """Mark a notification as read (only own)."""
    db = _db()
    r = await db.notifications.update_one(
        {"id": notification_id, "userId": user.get("id")},
        {"$set": {"read": True, "isRead": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "modified": r.modified_count}


@router.post("/api/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(require_user)):
    """Mark all my notifications as read."""
    db = _db()
    r = await db.notifications.update_many(
        {"userId": user.get("id")},
        {"$set": {"read": True, "isRead": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "modified": r.modified_count}


@router.patch("/api/notifications/read-all")
async def mark_all_notifications_read_patch(user: dict = Depends(require_user)):
    """Alias (PATCH) of read-all — the frontend hook uses PATCH."""
    return await mark_all_notifications_read(user)


# ─────────── Admin: notification rules (enable/disable + channels) ─────────

@router.get("/api/admin/notification-rules", dependencies=[Depends(require_admin)])
async def list_notification_rules():
    from app.repositories import NotificationRuleRepository
    repo = NotificationRuleRepository(_db())
    rules = await repo.list_all_sorted()
    # fill missing events with defaults
    existing = {r["event"] for r in rules}
    for ev in ALL_EVENTS:
        if ev not in existing:
            for d in DEFAULT_RULES:
                if d["event"] == ev:
                    rules.append({"id": f"rule_{ev}", **d, "missing_in_db": True})
                    break
    return {"success": True, "items": rules, "events": ALL_EVENTS,
            "audiences": list(AUDIENCES), "channels": list(CHANNELS)}


@router.get("/api/admin/notifications/channel-status", dependencies=[Depends(require_admin)])
async def get_channel_status():
    """Текущее состояние каналов доставки. Admin видит сразу — настроен Resend,
    SMTP или ничего (тогда dry_run). Никаких ключей в ответе не раскрывается.
    """
    db = _db()
    # Email — приоритет: integration_configs.resend (UI) > env RESEND_API_KEY > integration_configs.email (SMTP) > dry_run
    resend_doc = (
        await db.integration_configs.find_one({"provider": "resend"})
        or await db.integration_configs.find_one({"_id": "resend"})
        or await db.integration_configs.find_one({"id": "resend"})
    ) or {}
    resend_creds = resend_doc.get("credentials") or {}
    resend_settings = resend_doc.get("settings") or {}
    resend_key_db = (resend_creds.get("apiKey") or resend_creds.get("resendKey") or "").strip()
    resend_db_ready = bool(resend_key_db and resend_doc.get("isEnabled"))

    has_resend_env = bool(os.environ.get("RESEND_API_KEY"))
    smtp_doc = (
        await db.integration_configs.find_one({"provider": "email"})
        or await db.integration_configs.find_one({"_id": "email"})
        or await db.integration_configs.find_one({"id": "email"})
    ) or {}
    smtp_creds = smtp_doc.get("credentials") or {}
    smtp_ready = bool(smtp_creds.get("smtpHost") and smtp_creds.get("smtpLogin") and smtp_creds.get("smtpPassword"))
    smtp_enabled = bool(smtp_doc.get("isEnabled"))

    if resend_db_ready:
        email_mode = "resend"
        email_from = (resend_creds.get("from") or resend_settings.get("from")
                      or os.environ.get("RESEND_FROM") or "BIBI Cars <no-reply@bibi.cars>")
        email_status = "live"
        email_source = "db"
    elif has_resend_env:
        email_mode = "resend"
        email_from = os.environ.get("RESEND_FROM", "BIBI Cars <no-reply@bibi.cars>")
        email_status = "live"
        email_source = "env"
    elif smtp_enabled and smtp_ready:
        email_mode = "smtp"
        email_from = smtp_creds.get("from") or smtp_doc.get("settings", {}).get("from") or ""
        email_status = "live"
        email_source = "db"
    else:
        email_mode = "dry_run"
        email_from = "(no provider configured)"
        email_status = "dry_run"
        email_source = "none"

    # In-app — всегда работает (это просто запись в БД + socket.io).
    sio_attached = bool(service and getattr(service, "in_app_channel", None) and service.in_app_channel.sio)

    # Statistics
    sent_24h = 0
    dry_24h = 0
    failed_24h = 0
    try:
        from datetime import timedelta
        since_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        sent_24h   = await db.email_outbox.count_documents({"status": "sent",   "created_at": {"$gte": since_iso}})
        dry_24h    = await db.email_outbox.count_documents({"status": "dry_run","created_at": {"$gte": since_iso}})
        failed_24h = await db.email_outbox.count_documents({"status": "failed", "created_at": {"$gte": since_iso}})
    except Exception:
        pass
    in_app_24h = 0
    try:
        from datetime import timedelta
        since_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        in_app_24h = await db.notifications.count_documents({"created_at": {"$gte": since_iso}})
    except Exception:
        pass

    # Free-tier limits для Resend (3000/мес + 100/день). Считаем из outbox.
    sent_30d = 0
    try:
        from datetime import timedelta
        since_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        sent_30d = await db.email_outbox.count_documents({"status": "sent", "created_at": {"$gte": since_30d}})
    except Exception:
        pass

    return {
        "success": True,
        "channels": {
            "email": {
                "mode":   email_mode,        # "resend" | "smtp" | "dry_run"
                "status": email_status,      # "live"   | "dry_run"
                "source": email_source,      # "db" | "env" | "none"
                "from":   email_from,
                "stats_24h": {"sent": sent_24h, "dry_run": dry_24h, "failed": failed_24h},
                "stats_30d": {"sent": sent_30d},
                "free_tier": {
                    "daily_limit":   100,   # Resend free
                    "monthly_limit": 3000,  # Resend free
                    "daily_used":    sent_24h,
                    "monthly_used":  sent_30d,
                    "daily_remaining":   max(0, 100 - sent_24h),
                    "monthly_remaining": max(0, 3000 - sent_30d),
                },
                "hint": (
                    "Резервный режим dry_run: настройте Resend в /admin/integrations → Resend "
                    "(введите re_xxx API-ключ) ИЛИ SMTP-блок в Email."
                    if email_mode == "dry_run" else
                    f"Готово к продакшну (источник: {email_source})"
                ),
            },
            "in_app": {
                "mode":   "live",
                "status": "live",
                "socketio_attached": sio_attached,
                "stats_24h": {"created": in_app_24h},
            },
            "sms": await _sms_channel_status(db),
        },
    }


async def _sms_channel_status(db) -> Dict[str, Any]:
    """Build the sms section of channel-status."""
    sms_doc = (
        await db.integration_configs.find_one({"provider": "sms"})
        or await db.integration_configs.find_one({"_id": "sms"})
        or await db.integration_configs.find_one({"id": "sms"})
    ) or {}
    creds = sms_doc.get("credentials") or {}
    settings = sms_doc.get("settings") or {}
    enabled = sms_doc.get("isEnabled")
    api_key = (creds.get("apiKey") or creds.get("textbeltKey") or "").strip()
    has_custom_key = bool(api_key and api_key.lower() != "textbelt")
    sender = (settings.get("sender") or creds.get("sender") or "BIBI Cars")[:11]

    if enabled is False:
        mode, status, hint = "dry_run", "dry_run", (
            "SMS канал выключен. Включите в /admin/integrations → SMS. "
            "По умолчанию используется TextBelt FREE (1 SMS/день/IP, без регистрации)."
        )
    elif has_custom_key:
        mode, status, hint = "textbelt", "live", "Готово к продакшну (TextBelt paid quota)"
    else:
        mode, status, hint = "textbelt_free", "live", (
            "TextBelt FREE: 1 SMS/день/IP без регистрации. "
            "Для безлимита введите textbelt API key через /admin/integrations → SMS."
        )

    sent_24h = dry_24h = failed_24h = 0
    try:
        from datetime import timedelta
        since_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        if "sms_outbox" in await db.list_collection_names():
            sent_24h   = await db.sms_outbox.count_documents({"status": "sent",   "created_at": {"$gte": since_iso}})
            dry_24h    = await db.sms_outbox.count_documents({"status": "dry_run","created_at": {"$gte": since_iso}})
            failed_24h = await db.sms_outbox.count_documents({"status": "failed", "created_at": {"$gte": since_iso}})
    except Exception:
        pass

    return {
        "mode":   mode,        # "textbelt" | "textbelt_free" | "dry_run"
        "status": status,      # "live" | "dry_run"
        "sender": sender,
        "stats_24h": {"sent": sent_24h, "dry_run": dry_24h, "failed": failed_24h},
        "hint": hint,
    }


@router.patch("/api/admin/notification-rules/{event}", dependencies=[Depends(require_master_admin)])
async def update_notification_rule(event: str, data: Dict[str, Any] = Body(...)):
    """Update (or upsert) a rule. Body: {enabled, targets: [{audience, channels:[]}]}"""
    from app.repositories import NotificationRuleRepository
    repo = NotificationRuleRepository(_db())
    if event not in ALL_EVENTS:
        raise HTTPException(400, f"Unknown event: {event}")
    targets = data.get("targets")
    if targets is not None:
        if not isinstance(targets, list):
            raise HTTPException(400, "targets must be a list")
        for t in targets:
            if t.get("audience") not in AUDIENCES:
                raise HTTPException(400, f"unknown audience: {t.get('audience')}")
            for ch in (t.get("channels") or []):
                if ch not in CHANNELS:
                    raise HTTPException(400, f"unknown channel: {ch}")
    upd = {k: v for k, v in (data or {}).items() if k in {"enabled", "targets"}}
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await repo.upsert_by_event(
        event,
        set_doc={**upd, "event": event, "id": f"rule_{event}"},
    )
    fresh = await repo.find_by_event(event)
    return {"success": True, "rule": fresh}


# ─────────── Admin: email templates (editable UI) ──────────────────────────

@router.get("/api/admin/email-templates", dependencies=[Depends(require_admin)])
async def list_email_templates(event: str = "", audience: str = "", lang: str = ""):
    from app.repositories import EmailTemplateRepository
    repo = EmailTemplateRepository(_db())
    items = await repo.list_filtered(event=event, audience=audience, lang=lang)
    return {"success": True, "items": items}


@router.patch("/api/admin/email-templates/{template_id}", dependencies=[Depends(require_master_admin)])
async def update_email_template(template_id: str, data: Dict[str, Any] = Body(...)):
    from app.repositories import EmailTemplateRepository
    repo = EmailTemplateRepository(_db())
    allowed = {"subject", "html", "text_template", "active"}
    upd = {k: v for k, v in (data or {}).items() if k in allowed}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    if not await repo.exists_by_id(template_id):
        raise HTTPException(404, "Template not found")
    await repo.apply_patch(template_id, set_doc=upd)
    t = await repo.get_by_id(template_id)
    return {"success": True, "template": t}


@router.post("/api/admin/email-templates", dependencies=[Depends(require_master_admin)])
async def create_email_template(data: Dict[str, Any] = Body(...)):
    from app.repositories import EmailTemplateRepository
    repo = EmailTemplateRepository(_db())
    required = {"event", "audience", "lang", "subject", "html"}
    if not required.issubset(data.keys()):
        raise HTTPException(400, f"Missing fields: {required - set(data.keys())}")
    if data["event"] not in ALL_EVENTS:
        raise HTTPException(400, "Unknown event")
    if data["audience"] not in AUDIENCES:
        raise HTTPException(400, "Unknown audience")
    if data["lang"] not in LANGUAGES:
        raise HTTPException(400, "Unknown lang")
    tid = f"tpl_{data['event']}_{data['audience']}_{data['lang']}"
    doc = {
        "id": tid,
        "event": data["event"],
        "audience": data["audience"],
        "lang": data["lang"],
        "subject": data["subject"],
        "html": data["html"],
        "text_template": data.get("text_template", ""),
        "active": bool(data.get("active", True)),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await repo.upsert_by_id(tid, doc=doc)
    return {"success": True, "template": doc}


# ─────────── Admin: test-dispatch (fires synthetic event via service) ───────

@router.post("/api/admin/notifications/test-dispatch", dependencies=[Depends(require_master_admin)])
async def test_dispatch(data: Dict[str, Any] = Body(...), user: dict = Depends(require_master_admin)):
    """Fire a synthetic event against the notification dispatcher — useful
    for `master_admin` to verify a new template renders correctly and the
    right channels are triggered. Body: {event, invoice?, order?, customer?}.
    Returns the dispatch summary (audiences, channels, recipient counts).
    """
    event = data.get("event")
    if event not in ALL_EVENTS:
        raise HTTPException(400, f"Unknown event: {event}")
    ctx = {
        "invoice": data.get("invoice") or {
            "id": "inv_TEST",
            "total": 1234.56,
            "currency": "USD",
            "customerId": user.get("id"),
            "managerId": user.get("id"),
            "managerEmail": user.get("email"),
        },
        "order": data.get("order") or {"id": "ord_TEST", "steps": [{}, {}, {}]},
        "customer": data.get("customer") or {
            "id": user.get("id"),
            "email": user.get("email"),
            "phone": user.get("phone") or data.get("test_phone"),
            "name": user.get("email"),
            "lang": "ua",
        },
        "manager": data.get("manager") or {
            "id": user.get("id"),
            "email": user.get("email"),
            "phone": user.get("phone") or data.get("test_phone"),
            "name": user.get("email"),
            "lang": "ua",
        },
    }
    # Late binding: 'service' is created by init() (called from server.startup())
    # and bound at module level.  We resolve it lazily so this block does not
    # crash if test-dispatch is hit before init() — which should not happen,
    # but defensive.
    if 'service' not in globals() or globals().get('service') is None:
        raise HTTPException(503, "Notification service not initialised yet")
    result = await service.dispatch(event, ctx)  # type: ignore[name-defined]
    return {"success": True, "dispatch": result}


# ─────────── Admin: email outbox view (what was actually sent / logged) ────

@router.get("/api/admin/email-outbox", dependencies=[Depends(require_admin)])
async def list_email_outbox(limit: int = 100, event: str = "", status: str = ""):
    from app.repositories import EmailOutboxRepository
    repo = EmailOutboxRepository(_db())
    items = await repo.list_recent(event=event, status=status, limit=limit)
    return {"success": True, "items": items, "provider": (
        "resend" if os.environ.get("RESEND_API_KEY") else "dry_run"
    )}


# ─────────── Admin: SMS outbox view (parallel to email-outbox) ─────────────
# The SmsChannel writes every send-attempt (success / failed / dry_run) into
# the `sms_outbox` Mongo collection.  This endpoint exposes that history to
# master_admin so they can audit who got which message, see provider errors
# (e.g. TextBelt "Out of quota" when free key is exhausted), and confirm that
# the channel is healthy.
#
# Mirrors the /api/admin/email-outbox shape: {success, items, provider}.

@router.get("/api/admin/sms-outbox", dependencies=[Depends(require_admin)])
async def list_sms_outbox(limit: int = 100, event: str = "", status: str = ""):
    db = _db()
    query: Dict[str, Any] = {}
    if event:
        query["event"] = event
    if status:
        query["status"] = status
    limit = max(1, min(int(limit or 100), 500))
    try:
        cursor = db.sms_outbox.find(query).sort("created_at", -1).limit(limit)
        items = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)
    except Exception:
        logger.exception("[sms-outbox] list failed")
        items = []
    # Determine current provider (textbelt / textbelt_free / dry_run).
    sms_cfg = (
        await db.integration_configs.find_one({"provider": "sms"})
        or await db.integration_configs.find_one({"_id": "sms"})
        or await db.integration_configs.find_one({"id": "sms"})
    ) or {}
    creds = sms_cfg.get("credentials") or {}
    api_key = (creds.get("apiKey") or creds.get("textbeltKey") or "").strip()
    if sms_cfg.get("isEnabled") is False:
        provider = "dry_run"
    elif api_key and api_key.lower() != "textbelt":
        provider = "textbelt"
    else:
        provider = "textbelt_free"
    return {"success": True, "items": items, "provider": provider}


# ─────────── Admin: send a one-off test SMS ────────────────────────────────
# Used by /admin/integrations → SMS to verify the configured TextBelt key
# actually works (or that the free key still has a quota for this IP today).
# Body: {to: "+359...", message?: "Hello from BIBI"}

@router.post("/api/admin/notifications/sms/test", dependencies=[Depends(require_master_admin)])
async def send_test_sms(data: Dict[str, Any] = Body(...)):
    to = (data.get("to") or data.get("phone") or "").strip()
    if not to:
        raise HTTPException(400, "Field 'to' (phone) is required")
    message = (data.get("message") or "BIBI Cars: SMS test ✓").strip()
    db = _db()
    channel = SmsChannel(db)
    result = await channel.send(
        to=to,
        message=message,
        event="admin_test_sms",
        context={"source": "admin_test_sms"},
    )
    # Pull the just-written outbox entry so the UI can show provider response.
    last_doc = None
    try:
        last_doc = await db.sms_outbox.find_one({"id": result.get("id")})
        if last_doc:
            last_doc.pop("_id", None)
    except Exception:
        pass
    return {
        "success": bool(result.get("ok")),
        "mode": result.get("mode"),
        "id": result.get("id"),
        "error": result.get("error"),
        "outbox": last_doc,
    }


# ─────────── Admin: send a one-off test Email ──────────────────────────────
# Используется в /admin/integrations → Resend (и Email/SMTP) чтобы проверить,
# что введённый ключ реально работает. Резолвится через ту же конфигурацию,
# что и боевые рассылки (DB Resend > env > SMTP > dry_run).
# Body: {to: "user@example.com", subject?, html?}

@router.post("/api/admin/notifications/email/test", dependencies=[Depends(require_master_admin)])
async def send_test_email(data: Dict[str, Any] = Body(...)):
    to = (data.get("to") or data.get("email") or "").strip()
    if not to or "@" not in to:
        raise HTTPException(400, "Field 'to' (valid email) is required")
    subject = (data.get("subject") or "BIBI Cars · test email").strip()
    html = data.get("html") or (
        "<div style='font-family:system-ui,sans-serif;padding:24px;background:#fafafa'>"
        "<h2 style='margin:0 0 12px 0;color:#18181B'>BIBI Cars — test email</h2>"
        "<p style='color:#3F3F46;line-height:1.5'>Если вы видите это письмо — email-канал работает. "
        "Отправлено через текущий настроенный провайдер (Resend / SMTP).</p>"
        f"<p style='color:#A1A1AA;font-size:12px;margin-top:24px'>timestamp: {datetime.now(timezone.utc).isoformat()}</p>"
        "</div>"
    )
    text = data.get("text") or "BIBI Cars — test email. If you see this, the email channel works."
    db = _db()
    channel = EmailChannel(db)
    result = await channel.send(
        to=to,
        subject=subject,
        html=html,
        text=text,
        event="admin_test_email",
        context={"source": "admin_test_email"},
    )
    # Подтягиваем outbox-запись, чтобы UI показал provider_response/provider_error.
    last_doc = None
    try:
        last_doc = await db.email_outbox.find_one({"id": result.get("id")})
        if last_doc:
            last_doc.pop("_id", None)
    except Exception:
        pass
    return {
        "success": bool(result.get("ok")),
        "mode": result.get("mode"),
        "id": result.get("id"),
        "outbox": last_doc,
    }


# ─────────── Admin: email usage (Resend free-tier counters) ────────────────
# Resend бесплатный план: 3000 писем/месяц + 100 писем/день.
# Считаем из email_outbox по статусу=sent. Возвращаем daily/monthly used+remaining,
# чтобы admin сразу видел сколько ещё можно отправить без апгрейда плана.

@router.get("/api/admin/notifications/email/usage", dependencies=[Depends(require_admin)])
async def email_usage():
    from datetime import timedelta
    db = _db()
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(days=1)).isoformat()
    since_30d = (now - timedelta(days=30)).isoformat()
    sent_24h = sent_30d = 0
    failed_24h = dry_24h = 0
    try:
        sent_24h   = await db.email_outbox.count_documents({"status": "sent",   "created_at": {"$gte": since_24h}})
        sent_30d   = await db.email_outbox.count_documents({"status": "sent",   "created_at": {"$gte": since_30d}})
        failed_24h = await db.email_outbox.count_documents({"status": "failed", "created_at": {"$gte": since_24h}})
        dry_24h    = await db.email_outbox.count_documents({"status": "dry_run","created_at": {"$gte": since_24h}})
    except Exception:
        pass
    return {
        "success": True,
        "free_tier": {
            "daily_limit":   100,
            "monthly_limit": 3000,
            "daily_used":    sent_24h,
            "monthly_used":  sent_30d,
            "daily_remaining":   max(0, 100  - sent_24h),
            "monthly_remaining": max(0, 3000 - sent_30d),
        },
        "stats_24h": {"sent": sent_24h, "failed": failed_24h, "dry_run": dry_24h},
    }



# ─────────── Resend Webhook RECEIVER (public, signature-verified) ──────────
# Resend POST'ит сюда события (email.delivered / email.bounced / ...). Мы:
#   1) Валидируем Svix-сигнатуру через webhook_secret (хранится в
#      integration_configs.resend.settings.webhook_secret).
#   2) Находим запись в email_outbox по email_id (Resend message id), который
#      мы сохраняем в provider_response.id при отправке.
#   3) Обновляем поля: events.{type} = timestamp, last_event = type.
#
# Эндпоинт ПУБЛИЧНЫЙ (Resend не умеет передавать наш JWT). Безопасность —
# через подпись Svix. Если secret не настроен — принимаем без валидации.

from fastapi import Request  # noqa: E402

@router.post("/api/webhooks/resend/events")
async def receive_resend_event(request: Request):
    raw_body = await request.body()
    headers = request.headers
    db = _db()

    # Достаём webhook_secret из БД (если был сохранён при создании webhook через UI)
    secret = ""
    try:
        doc = (
            await db.integration_configs.find_one({"provider": "resend"})
            or await db.integration_configs.find_one({"_id": "resend"})
            or await db.integration_configs.find_one({"id": "resend"})
        ) or {}
        secret = ((doc.get("settings") or {}).get("webhook_secret") or "").strip()
    except Exception:
        logger.exception("[resend/webhook] settings load failed")

    # ─── Подпись Svix (если есть секрет) ────────────────────────────────
    payload: Dict[str, Any] = {}
    if secret:
        try:
            from svix.webhooks import Webhook, WebhookVerificationError  # type: ignore
            wh = Webhook(secret)
            svix_id = headers.get("svix-id") or headers.get("Svix-Id")
            svix_ts = headers.get("svix-timestamp") or headers.get("Svix-Timestamp")
            svix_sig = headers.get("svix-signature") or headers.get("Svix-Signature")
            payload = wh.verify(raw_body, {
                "svix-id": svix_id or "",
                "svix-timestamp": svix_ts or "",
                "svix-signature": svix_sig or "",
            })
        except WebhookVerificationError as e:
            logger.warning("[resend/webhook] signature invalid: %s", e)
            raise HTTPException(401, "Invalid signature")
        except ImportError:
            logger.warning("[resend/webhook] svix lib missing, accepting without check")
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except Exception:
                payload = {}
        except Exception:
            logger.exception("[resend/webhook] verify failed")
            try:
                payload = json.loads(raw_body) if raw_body else {}
            except Exception:
                payload = {}
    else:
        logger.warning("[resend/webhook] no secret — accepting unverified event")
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except Exception:
            payload = {}

    # ─── Обработка события ─────────────────────────────────────────────
    event_type = (payload.get("type") or "").strip()
    data = payload.get("data") or {}
    email_id = (data.get("email_id") or data.get("id") or "").strip()
    created_at = payload.get("created_at") or datetime.now(timezone.utc).isoformat()

    if not event_type or not email_id:
        return {"success": False, "error": "missing type or email_id", "event_type": event_type}

    short = event_type.replace("email.", "")
    try:
        update_doc: Dict[str, Any] = {
            "$set": {
                f"events.{short}": created_at,
                "last_event": short,
                "last_event_at": created_at,
            },
        }
        if short in ("bounced", "complained", "failed"):
            update_doc["$set"][f"events.{short}_data"] = data
        result = await db.email_outbox.update_one(
            {"provider_response.id": email_id},
            update_doc,
        )
        matched = result.matched_count
        try:
            await db.email_webhook_events.insert_one({
                "received_at": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "email_id": email_id,
                "payload": payload,
                "matched_outbox": bool(matched),
            })
        except Exception:
            pass
        return {"success": True, "event": short, "email_id": email_id, "matched": bool(matched)}
    except Exception:
        logger.exception("[resend/webhook] db update failed")
        raise HTTPException(500, "Failed to process event")


# ─────────── Notifications: misc (delete, customer-views, stats, stubs) ────

@router.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete notification"""
    db = _db()
    await db.notifications.delete_one({"id": notification_id})
    return {"success": True}


@router.get("/api/notifications/customer/me")
async def customer_notifications():
    """Customer notifications"""
    return {"success": True, "data": []}


@router.get("/api/notifications/customer/unread-count")
async def customer_notifications_unread():
    """Customer unread count"""
    return {"success": True, "count": 0}


@router.get("/api/notifications/stats")
async def notifications_stats():
    """Notification stats"""
    return {"success": True, "stats": {"total": 0, "unread": 0, "today": 0}}


@router.get("/api/notifications/rules")
async def notification_rules():
    """Get notification rules - returns direct array"""
    return [
        {"eventType": "lead.created", "isActive": True, "severity": "info", "channels": {"inApp": True, "telegram": False, "sound": True, "email": False}, "soundKey": "lead", "debounceMinutes": 10},
        {"eventType": "invoice.overdue", "isActive": True, "severity": "critical", "channels": {"inApp": True, "telegram": True, "sound": True, "email": True}, "soundKey": "alert", "debounceMinutes": 30},
    ]


@router.post("/api/notifications/rules")
async def create_notification_rule(data: Dict[str, Any] = Body(...)):
    """Create notification rule"""
    return {"success": True}


@router.put("/api/notifications/rules/{rule_id}")
async def update_notification_rule_by_id(rule_id: str, data: Dict[str, Any] = Body(...)):
    """Update notification rule"""
    return {"success": True}


@router.patch("/api/notifications/rules/{event_type}")
async def patch_notification_rule(event_type: str, data: Dict[str, Any] = Body(...)):
    """Patch notification rule"""
    return {"success": True}


@router.post("/api/notifications/test")
async def test_notification(data: Dict[str, Any] = Body(...)):
    """Test notification"""
    return {"success": True, "sent": True}
