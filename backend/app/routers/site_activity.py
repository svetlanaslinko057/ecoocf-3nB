"""
Site-activity tracking (Доопр #19).

Receives events from the public site (cabinet_login/cabinet_active/form_active/
form_submitted/callback_request/session_end) and updates the online-status of
the matching lead/customer in real time. CRM frontend then shows a badge.

Endpoints:
  POST /api/v1/site-activity            — public ingest (API key in header)
  GET  /api/v1/site-activity/online     — list currently-online leads/customers
  GET  /api/v1/site-activity/tracker.js — public JS-snippet for external sites
  GET  /api/v1/site-activity/setup      — installation guide (Markdown)
  GET  /api/v1/site-activity/{entity_id} — last activity for one entity
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.db_runtime import get_db
from security import require_user

logger = logging.getLogger("bibi.site_activity")
router = APIRouter(prefix="/api/v1/site-activity", tags=["site-activity"])

VALID_EVENTS = {
    "cabinet_login", "cabinet_active", "form_active",
    "form_submitted", "callback_request", "session_end",
}

# События, которые НЕ показываем менеджерам (технический шум):
# - session_end — закрытие вкладки, бесполезно бизнесу
# - cabinet_active — heartbeat, генерируется автоматически каждую минуту,
#   замусоривает ленту. Используем только для подсчёта времени в кабинете.
HIDDEN_EVENT_TYPES = {"session_end", "cabinet_active"}

# Бизнес-категории действий (для KPI-агрегации).
EVENT_CATEGORY = {
    "form_active":      "form",
    "form_submitted":   "form",
    "callback_request": "callback",
    "cabinet_login":    "cabinet",
    "cabinet_active":   "cabinet",
    "session_end":      "system",
}

# Public API key — set BIBI_SITE_TRACK_KEY in .env. Empty default means the
# tracker requires an explicit key in production (no committed secret).
INGEST_KEY = os.environ.get("BIBI_SITE_TRACK_KEY", "")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _find_target(db, phone: Optional[str], email: Optional[str]) -> Dict[str, Any]:
    """Locate lead or customer by phone/email. Returns {kind, id, name} or empty."""
    if not phone and not email:
        return {}
    or_clauses: List[Dict[str, Any]] = []
    if phone:
        or_clauses += [{"phone": phone}, {"phoneNumber": phone}]
    if email:
        or_clauses += [{"email": (email or "").lower()}]
    if not or_clauses:
        return {}
    flt = {"$or": or_clauses}
    # customers first
    cust = await db.customers.find_one(flt, {"_id": 0, "id": 1, "firstName": 1, "lastName": 1, "email": 1})
    if cust:
        nm = f"{cust.get('firstName','')} {cust.get('lastName','')}".strip() or cust.get("email") or cust["id"]
        return {"kind": "customer", "id": cust["id"], "name": nm}
    lead = await db.leads.find_one(flt, {"_id": 0, "id": 1, "name": 1, "email": 1})
    if lead:
        return {"kind": "lead", "id": lead["id"], "name": lead.get("name") or lead.get("email") or lead["id"]}
    return {}


@router.post("")
async def ingest(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
):
    if (x_api_key or "") != INGEST_KEY:
        # also accept ?key=... for ease of testing
        if (request.query_params.get("key") or "") != INGEST_KEY:
            raise HTTPException(401, "Invalid API key")
    event_type = (payload.get("event_type") or "").strip()
    if event_type not in VALID_EVENTS:
        raise HTTPException(400, f"event_type must be one of {sorted(VALID_EVENTS)}")
    db = get_db()
    phone = (payload.get("phone") or "").strip() or None
    email = ((payload.get("email") or "").strip() or None)
    email_norm = email.lower() if email else None
    target = await _find_target(db, phone, email_norm)
    now = _now()
    event_doc = {
        "event_type": event_type,
        "phone": phone,
        "email": email_norm,
        "session_id": payload.get("session_id"),
        "user_agent": payload.get("user_agent") or request.headers.get("user-agent"),
        "received_at": _iso(now),
        "target_kind": target.get("kind"),
        "target_id": target.get("id"),
    }
    await db.site_activity_events.insert_one(event_doc)

    # update online status if we have a target
    if target.get("id"):
        upsert_doc = {
            "target_kind": target["kind"],
            "target_id":   target["id"],
            "target_name": target["name"],
            "last_event":  event_type,
            "last_seen_at": _iso(now),
            "last_phone":  phone,
            "last_email":  email_norm,
        }
        if event_type == "session_end":
            upsert_doc["last_seen_at"] = _iso(now - timedelta(minutes=30))
        await db.site_activity_status.update_one(
            {"target_kind": target["kind"], "target_id": target["id"]},
            {"$set": upsert_doc, "$inc": {"visits": 1}},
            upsert=True,
        )

    return {"success": True, "matched": bool(target.get("id")), "target": target}


def _status_badge(last_seen_iso: Optional[str], last_event: Optional[str]) -> Dict[str, Any]:
    if not last_seen_iso:
        return {"status": "offline", "color": "gray"}
    try:
        last = datetime.fromisoformat(last_seen_iso.replace("Z", "+00:00"))
    except Exception:
        return {"status": "offline", "color": "gray"}
    delta_min = (_now() - last).total_seconds() / 60
    base: Dict[str, Any] = {"minutes_ago": int(delta_min)}
    if last_event == "callback_request" and delta_min <= 30:
        return {**base, "status": "callback",     "color": "red"}
    if delta_min <= 5:
        return {**base, "status": "online_now",   "color": "green"}
    if delta_min <= 30:
        return {**base, "status": "recent",       "color": "yellow"}
    return {**base, "status": "offline", "color": "gray"}


@router.get("/online")
async def list_online(
    kind: Optional[str] = Query(None, regex="^(lead|customer)$"),
    minutes: int = 30,
    current_user: Dict[str, Any] = Depends(require_user),
):
    db = get_db()
    cutoff = _iso(_now() - timedelta(minutes=minutes))
    flt: Dict[str, Any] = {"last_seen_at": {"$gte": cutoff}}
    if kind:
        flt["target_kind"] = kind
    items = await db.site_activity_status.find(flt, {"_id": 0}).sort("last_seen_at", -1).to_list(length=500)
    for it in items:
        it["badge"] = _status_badge(it.get("last_seen_at"), it.get("last_event"))
    return {"success": True, "items": items, "count": len(items)}


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC JS-TRACKER  +  SETUP DOCS  (declared BEFORE the /{entity_id} catch-all
# so that "tracker.js" / "setup" are never swallowed by the path-converter)
# ─────────────────────────────────────────────────────────────────────────────


def _build_tracker_js() -> str:
    """Render the JS-tracker source.

    The default INGEST endpoint is derived from the script's own ``src``
    attribute, so a single bundle works for staging/production without any
    edit on the client side. ``data-api-key`` is read from the script tag.
    """
    return r"""/*!
 * BIBI Cars · site-activity tracker · v1.0.0
 * Lightweight (≈3 kB) drop-in snippet that pings the CRM ingest endpoint
 * with anonymised events (cabinet_login, cabinet_active, form_active,
 * form_submitted, callback_request, session_end).
 *
 *   <script src="https://YOUR_CRM/api/v1/site-activity/tracker.js"
 *           data-api-key="YOUR_PUBLIC_INGEST_KEY"
 *           data-debug="false"
 *           async></script>
 *
 * No external dependencies, no cookies, sendBeacon-first for reliability.
 */
(function () {
  'use strict';
  if (window.__BIBI_TRACKER_LOADED__) return;
  window.__BIBI_TRACKER_LOADED__ = true;

  /* ---------------- config ------------------------------------------------ */
  var script = document.currentScript || (function () {
    var ss = document.getElementsByTagName('script');
    for (var i = ss.length - 1; i >= 0; i--) {
      if (ss[i].src && /site-activity\/tracker\.js/.test(ss[i].src)) return ss[i];
    }
    return null;
  })();
  if (!script) return;

  var SRC = script.src.replace(/[?#].*$/, '');
  var ENDPOINT = SRC.replace(/\/tracker\.js$/, '');
  var API_KEY  = script.getAttribute('data-api-key') || '';
  var DEBUG    = (script.getAttribute('data-debug') || '').toLowerCase() === 'true';
  var HEARTBEAT_MS = 60 * 1000;
  var IDLE_MS      = 30 * 1000;
  var SESSION_KEY  = 'bibi_track_sid';

  if (!API_KEY) {
    if (DEBUG) console.warn('[bibi-tracker] missing data-api-key attribute');
    return;
  }

  /* ---------------- helpers ----------------------------------------------- */
  function log() { if (DEBUG) console.log.apply(console, ['[bibi-tracker]'].concat([].slice.call(arguments))); }

  function uid() {
    return (Date.now().toString(36) +
            Math.random().toString(36).slice(2, 10));
  }

  function getSid() {
    try {
      var v = sessionStorage.getItem(SESSION_KEY);
      if (!v) { v = uid(); sessionStorage.setItem(SESSION_KEY, v); }
      return v;
    } catch (e) { return uid(); }
  }

  function readField(name) {
    // Read identity hints from window.bibiTracker.identity OR from common form fields
    try {
      var b = window.bibiTracker && window.bibiTracker.identity;
      if (b && b[name]) return String(b[name]).trim();
    } catch (e) {}
    var sel = '[name="' + name + '"],[data-bibi="' + name + '"],[autocomplete*="' + name + '"]';
    var el = document.querySelector(sel);
    if (el && el.value) return String(el.value).trim();
    return null;
  }

  function send(eventType, extra) {
    if (!eventType) return;
    var payload = {
      event_type: eventType,
      session_id: getSid(),
      user_agent: navigator.userAgent,
      page_url:   location.href,
      referrer:   document.referrer || null,
      phone:      readField('phone'),
      email:      readField('email'),
    };
    if (extra && typeof extra === 'object') {
      for (var k in extra) if (Object.prototype.hasOwnProperty.call(extra, k)) payload[k] = extra[k];
    }
    var body = JSON.stringify(payload);
    var headers = { type: 'application/json' };
    log('→', eventType, payload);
    try {
      if (navigator.sendBeacon) {
        // Beacon can't set custom headers — pass key via query string fallback
        var url = ENDPOINT + '?key=' + encodeURIComponent(API_KEY);
        navigator.sendBeacon(url, new Blob([body], headers));
        return;
      }
    } catch (e) { /* fall-through to fetch */ }
    try {
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Api-Key': API_KEY },
        body: body,
        keepalive: true,
        credentials: 'omit',
      }).catch(function (err) { log('fetch error', err); });
    } catch (e) { log('fetch error', e); }
  }

  /* ---------------- heartbeat & idle detection ---------------------------- */
  var lastActivityAt = Date.now();
  var beatTimer = null;
  function markActivity() { lastActivityAt = Date.now(); }
  ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'].forEach(function (ev) {
    window.addEventListener(ev, markActivity, { passive: true });
  });

  function startHeartbeat(label) {
    if (beatTimer) return;
    label = label || 'cabinet_active';
    beatTimer = setInterval(function () {
      if (Date.now() - lastActivityAt > IDLE_MS) return; // user is idle
      if (document.visibilityState !== 'visible') return;
      send(label);
    }, HEARTBEAT_MS);
  }

  /* ---------------- automatic detection ----------------------------------- */
  // 1) Cabinet pages: any URL containing "/cabinet" → emit cabinet_login on first load
  var isCabinet = /\/cabinet(\/|$)/i.test(location.pathname);
  if (isCabinet) {
    send('cabinet_login');
    startHeartbeat('cabinet_active');
  }

  // 2) Forms: focus on any phone/email input → form_active (debounced once per session)
  var formActiveSent = false;
  function onFormFocus(e) {
    if (formActiveSent) return;
    var t = e.target;
    if (!t || !t.matches) return;
    if (t.matches('input[type="tel"], input[type="email"], [name="phone"], [name="email"], [data-bibi="phone"], [data-bibi="email"]')) {
      formActiveSent = true;
      send('form_active');
      startHeartbeat('form_active');
    }
  }
  document.addEventListener('focusin', onFormFocus);

  // 3) Form submission: bubble-listen on every <form> that asks for phone/email
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || !f.matches || !f.matches('form')) return;
    if (!f.querySelector('input[type="tel"], input[type="email"], [name="phone"], [name="email"]')) return;
    send('form_submitted', { form_id: f.id || null, form_name: f.getAttribute('name') || null });
  }, true);

  // 4) Page unload → session_end
  function flushUnload() {
    try { send('session_end'); } catch (e) {}
  }
  window.addEventListener('pagehide', flushUnload);
  window.addEventListener('beforeunload', flushUnload);

  /* ---------------- manual API -------------------------------------------- */
  window.bibiTracker = window.bibiTracker || {};
  window.bibiTracker.identity = window.bibiTracker.identity || {};
  window.bibiTracker.track = send;             // bibiTracker.track('callback_request', {phone:'+359...'})
  window.bibiTracker.identify = function (obj) {
    if (!obj || typeof obj !== 'object') return;
    Object.assign(window.bibiTracker.identity, obj);
    log('identified', window.bibiTracker.identity);
  };

  log('initialised', { endpoint: ENDPOINT, debug: DEBUG });
})();
"""


@router.get("/tracker.js")
async def tracker_js(request: Request):
    """Serve the public JS tracker snippet.

    Cache-friendly (short max-age) so that future fixes propagate quickly.
    Returns ``Cache-Control: public, max-age=300`` (5 min).
    """
    body = _build_tracker_js()
    return Response(
        content=body,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
            # Allow loading the file from any origin
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.options("")
async def ingest_preflight():
    """CORS preflight for the public POST ingest endpoint."""
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Api-Key",
            "Access-Control-Max-Age":       "600",
        },
    )


@router.get("/setup")
async def setup_docs(request: Request) -> Dict[str, Any]:
    """Return install instructions + the ready-to-paste snippet for the
    Admin UI to display.

    The base URL is derived from forwarded proxy headers when present
    (so the snippet always points to the public CRM URL, not the
    internal cluster URL)."""
    fwd_proto = request.headers.get("x-forwarded-proto")
    fwd_host  = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if fwd_proto and fwd_host:
        base = f"{fwd_proto}://{fwd_host}"
    else:
        base = str(request.base_url).rstrip("/")
    tracker_url = f"{base}/api/v1/site-activity/tracker.js"
    snippet = (
        f'<!-- BIBI Cars site-activity tracker -->\n'
        f'<script src="{tracker_url}"\n'
        f'        data-api-key="{INGEST_KEY}"\n'
        f'        data-debug="false"\n'
        f'        async></script>\n'
    )
    identify_example = (
        "<script>\n"
        "  // OPTIONAL — bind the visitor to a known lead/customer\n"
        "  // when you already have their phone or email (e.g. after they\n"
        "  // log into the cabinet or fill the contact form).\n"
        "  window.bibiTracker = window.bibiTracker || {};\n"
        "  window.bibiTracker.identity = {\n"
        "    phone: '+359888123456',\n"
        "    email: 'visitor@example.com'\n"
        "  };\n"
        "</script>\n"
    )
    manual_example = (
        "<script>\n"
        "  // OPTIONAL — fire a custom event (e.g. when the user clicks\n"
        "  // a 'Request a call-back' button).\n"
        "  document.getElementById('callback-btn').addEventListener('click', function () {\n"
        "    window.bibiTracker && window.bibiTracker.track('callback_request', {\n"
        "      phone: document.getElementById('phone').value\n"
        "    });\n"
        "  });\n"
        "</script>\n"
    )
    return {
        "success": True,
        "tracker_url": tracker_url,
        "ingest_url":  f"{base}/api/v1/site-activity",
        "api_key_header": "X-Api-Key",
        "api_key_value":  INGEST_KEY,
        "valid_events":  sorted(VALID_EVENTS),
        "snippet":        snippet,
        "identify_example": identify_example,
        "manual_event_example": manual_example,
        "notes": [
            "Place the <script> tag just before </body> on EVERY page of the public site.",
            "The tracker auto-detects cabinet pages (URL contains '/cabinet') and emits 'cabinet_login' + heartbeat.",
            "Focusing any phone/email input emits 'form_active'.",
            "Submitting any <form> that contains phone/email emits 'form_submitted'.",
            "Page-unload emits 'session_end' via navigator.sendBeacon (works even on tab close).",
            "Manual events: window.bibiTracker.track('callback_request', { phone: '+359…' }).",
            "Identity binding: window.bibiTracker.identity = { phone, email } before the event fires.",
            "Cookies are NOT used; a session id is held in sessionStorage only.",
        ],
    }


# NOTE: catch-all /{entity_id} **must** be the last route in the file —
# otherwise FastAPI's path converter swallows /tracker.js, /setup, /online.
def _classify_status(last_seen_iso: Optional[str]) -> Dict[str, Any]:
    """Translate the last-seen-at timestamp into the three business buckets:
       🟢 active   — visited in the last 24 h
       🟡 warm     — visited 1–7 days ago
       🔴 inactive — > 7 days ago, or never
    """
    if not last_seen_iso:
        return {"status": "inactive", "color": "red",    "label_key": "activity_inactive"}
    try:
        last = datetime.fromisoformat(last_seen_iso.replace("Z", "+00:00"))
    except Exception:
        return {"status": "inactive", "color": "red",    "label_key": "activity_inactive"}
    delta_hours = (_now() - last).total_seconds() / 3600
    if delta_hours <= 24:
        return {"status": "active", "color": "green",  "label_key": "activity_active",   "hours_ago": round(delta_hours, 1)}
    if delta_hours <= 7 * 24:
        return {"status": "warm",   "color": "yellow", "label_key": "activity_warm",     "days_ago": round(delta_hours / 24, 1)}
    return {"status": "inactive",  "color": "red",    "label_key": "activity_inactive", "days_ago": round(delta_hours / 24, 1)}


@router.get("/by-entity/{entity_id}")
async def entity_activity_detail(
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(require_user),
):
    """Return a business-friendly activity view for a single lead / customer.

    Returns:
        {
          "found":        bool,            # any event recorded for this id?
          "target":       {kind, id, name},
          "kpi": {
            "last_visit_at": iso | null,
            "status":      "active" | "warm" | "inactive",
            "color":       "green" | "yellow" | "red",
            "visits_30d":  int,            # distinct session_ids in 30 days
            "forms_count": int,            # form_submitted in 30 days
            "callbacks_count": int,        # callback_request in 30 days
            "cabinet_logins": int,         # cabinet_login in 30 days
            "total_events": int,
          },
          "timeline":     [                # newest first, business events only
            {
              "id":          str,
              "event_type":  str,          # raw type (frontend translates)
              "received_at": iso,
              "page_url":    str | null,
              "phone":       str | null,
              "email":       str | null,
            },
            ...
          ]
        }
    """
    db = get_db()
    # Find the status doc for KPI aggregation
    status_doc = await db.site_activity_status.find_one(
        {"target_id": entity_id}, {"_id": 0}
    )

    # Identity → try customer first, then lead
    target_name = None
    target_kind = None
    if status_doc:
        target_name = status_doc.get("target_name")
        target_kind = status_doc.get("target_kind")
    if not target_name:
        cust = await db.customers.find_one(
            {"id": entity_id},
            {"_id": 0, "id": 1, "firstName": 1, "lastName": 1, "email": 1, "name": 1},
        )
        if cust:
            target_kind = "customer"
            target_name = (
                f"{cust.get('firstName', '')} {cust.get('lastName', '')}".strip()
                or cust.get("name")
                or cust.get("email")
                or entity_id
            )
        else:
            lead = await db.leads.find_one(
                {"id": entity_id},
                {"_id": 0, "id": 1, "name": 1, "email": 1},
            )
            if lead:
                target_kind = "lead"
                target_name = lead.get("name") or lead.get("email") or entity_id

    # ── KPI ────────────────────────────────────────────────────────────────
    cutoff_30d = _iso(_now() - timedelta(days=30))
    kpi = {
        "last_visit_at":   None,
        "status":          "inactive",
        "color":           "red",
        "label_key":       "activity_inactive",
        "visits_30d":      0,
        "forms_count":     0,
        "callbacks_count": 0,
        "cabinet_logins":  0,
        "total_events":    0,
    }
    if status_doc:
        kpi["last_visit_at"] = status_doc.get("last_seen_at")
        bucket = _classify_status(status_doc.get("last_seen_at"))
        kpi.update(bucket)

        # Count events in the last 30 days
        agg_pipeline = [
            {"$match": {
                "target_id":  entity_id,
                "received_at": {"$gte": cutoff_30d},
            }},
            {"$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
            }},
        ]
        counts: Dict[str, int] = {}
        try:
            async for row in db.site_activity_events.aggregate(agg_pipeline):
                counts[row["_id"]] = row["count"]
        except Exception as exc:  # pragma: no cover - defensive
            logging.warning("activity-kpi aggregate failed: %s", exc)
        kpi["forms_count"]     = counts.get("form_submitted", 0)
        kpi["callbacks_count"] = counts.get("callback_request", 0)
        kpi["cabinet_logins"]  = counts.get("cabinet_login", 0)
        kpi["total_events"]    = sum(counts.values())

        # Distinct session count in 30 days
        try:
            sessions = await db.site_activity_events.distinct(
                "session_id",
                {"target_id": entity_id, "received_at": {"$gte": cutoff_30d}},
            )
            kpi["visits_30d"] = len([s for s in sessions if s])
        except Exception as exc:  # pragma: no cover
            logging.warning("activity-kpi distinct failed: %s", exc)

    # ── Timeline ───────────────────────────────────────────────────────────
    timeline_raw = await (
        db.site_activity_events
        .find(
            {
                "target_id":  entity_id,
                "event_type": {"$nin": list(HIDDEN_EVENT_TYPES)},
            },
            {"_id": 0},
        )
        .sort("received_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )

    # Deduplicate consecutive identical events from the same session within
    # 90 seconds — keeps the timeline clean when the user re-focuses a form.
    timeline: List[Dict[str, Any]] = []
    last_sig = None
    last_ts: Optional[datetime] = None
    for ev in timeline_raw:
        sig = (ev.get("event_type"), ev.get("session_id"))
        try:
            ts = datetime.fromisoformat((ev.get("received_at") or "").replace("Z", "+00:00"))
        except Exception:
            ts = None
        if sig == last_sig and last_ts and ts and abs((last_ts - ts).total_seconds()) < 90:
            continue
        timeline.append({
            "id":          str(ev.get("_id") or ev.get("session_id") or "") + (ev.get("received_at") or ""),
            "event_type":  ev.get("event_type"),
            "received_at": ev.get("received_at"),
            "page_url":    ev.get("page_url"),
            "phone":       ev.get("phone"),
            "email":       ev.get("email"),
            "session_id":  ev.get("session_id"),
        })
        last_sig, last_ts = sig, ts

    return {
        "success": True,
        "found":   bool(status_doc) or bool(timeline_raw),
        "target":  {"kind": target_kind, "id": entity_id, "name": target_name},
        "kpi":     kpi,
        "timeline": timeline,
    }


@router.get("/{entity_id}")
async def entity_activity(entity_id: str, current_user: Dict[str, Any] = Depends(require_user)):
    db = get_db()
    doc = await db.site_activity_status.find_one({"target_id": entity_id}, {"_id": 0})
    if not doc:
        return {"success": True, "data": None, "badge": {"status": "offline", "color": "gray"}}
    doc["badge"] = _status_badge(doc.get("last_seen_at"), doc.get("last_event"))
    # last 20 events
    events = await db.site_activity_events.find({"target_id": entity_id}, {"_id": 0}).sort("received_at", -1).to_list(length=20)
    return {"success": True, "data": doc, "events": events}


__all__ = ["router"]
