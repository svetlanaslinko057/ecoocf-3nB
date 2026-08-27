"""
admin_security — /api/admin/security/* HTTP surface (2FA / Google Authenticator)
=============================================================================

Wave 2B / Batch 2 / Commit 8 (original extraction — sibling of
admin_history_reports).

**Phase 5.3 / C-3 update (2026-05-18):** ALL ``db.admin_security``
access now flows through ``AdminSecurityRepository``. This router
no longer issues raw Motor calls against the collection; it
delegates state I/O to the repository and keeps ONLY the
HTTP / crypto / response-shape concerns (TOTP secret generation,
QR PNG rendering, code verification, payload assembly).

Layer separation (per architect mandate)
----------------------------------------

* **Router** knows: HTTP, auth boundary, request shape, response
  shape, TOTP/QR rendering, the single-tenant scoping rule
  (``_get_admin_id``).
* **Repository** knows: the ``admin_security`` collection — and
  ONLY the collection. No HTTP, no crypto, no auth, no Socket.IO,
  no audit.

The lazy ``from server import db`` bridge survives ONLY inside
``_repo()`` and will dissolve in Phase 5.8 with DI.

What's preserved (byte-for-byte vs original Wave-2B extraction)
---------------------------------------------------------------

  * implementations of TOTP secret generation, QR encoding,
    setup-pending state, verify-then-enable transition,
    disable-with-code
  * auth boundary (require_admin via router-level dependency)
  * the ``_get_admin_id`` helper (single-tenant scoping rule)
  * payload shapes (FE contract):
      - GET  /2fa/status   → ``{enabled, setupPending}``
      - POST /2fa/setup    → ``{secret, qrCode, uri, issuer, account}``
      - POST /2fa/verify   → ``{success, enabled}`` | HTTP 400
      - POST /2fa/disable  → ``{success, enabled}`` | HTTP 400
  * legacy storage shape: timestamps as ``datetime`` (not ISO),
    ``_id`` is the admin scope string, ``setupPending`` derives
    from ``(twofa_secret AND NOT twofa_enabled)``

What's NOT touched
------------------

  * no signature change, no schema, no DTO
  * no DI / app.state / lifespan
  * no normalisation of the legacy timestamp shape
"""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, Dict, Optional

import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from security import require_admin  # noqa: E402

from app.repositories import AdminSecurityRepository

router = APIRouter(
    prefix="/api/admin/security",
    tags=["admin-security"],
    dependencies=[Depends(require_admin)],
)


def _repo() -> AdminSecurityRepository:
    """Lazy repository factory.

    Phase 5.4 / C-4f — migrated from the legacy ``from server import db
    as _server_db`` lazy bridge to ``app.core.db_runtime.get_db()``.
    Object identity is preserved 1:1: the canonical ``server.db`` and
    ``get_db()`` reference the same Motor handle (pinned by the
    startup-time identity assertion in ``server.py`` and by
    ``tests/test_phase5_4_c4f_db_repo_batch2.py``). The ``_repo()``
    wrapper, the ``AdminSecurityRepository`` constructor, and the
    endpoint signatures are byte-for-byte unchanged. The ``_server_db``
    local alias is dropped because the accessor returns the handle
    directly.
    """
    from app.core.db_runtime import get_db  # noqa: E402 (C-4f: lazy-bridge → accessor)
    return AdminSecurityRepository(get_db())


def _get_admin_id(request: Optional[Request] = None) -> str:
    """Extract admin user id from auth header/session. Default 'admin' for single-tenant."""
    # In single-tenant mode the panel is protected by session auth.
    # We scope 2FA by a stable id, default 'admin'.
    return "admin"


@router.get("/2fa/status")
async def security_2fa_status():
    admin_id = _get_admin_id()
    doc = (await _repo().get_state(admin_id)) or {}
    return {
        'enabled': bool(doc.get('twofa_enabled')),
        'setupPending': bool(doc.get('twofa_secret') and not doc.get('twofa_enabled')),
    }


@router.post("/2fa/setup")
async def security_2fa_setup():
    """Generate a fresh TOTP secret + QR PNG. Doesn't activate yet — verify step required."""
    admin_id = _get_admin_id()
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    issuer = 'BIBI Cars CRM'
    account = f'{admin_id}@bibi.cars'
    uri = totp.provisioning_uri(name=account, issuer_name=issuer)

    img = qrcode.make(uri)
    buf = BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    await _repo().record_setup_pending(admin_id, secret=secret)
    return {
        'secret': secret,
        'qrCode': f'data:image/png;base64,{qr_b64}',
        'uri': uri,
        'issuer': issuer,
        'account': account,
    }


@router.post("/2fa/verify")
async def security_2fa_verify(data: Dict[str, Any] = Body(...)):
    admin_id = _get_admin_id()
    code = str(data.get('code', '')).strip()
    if not code:
        raise HTTPException(status_code=400, detail='code required')

    doc = (await _repo().get_state(admin_id)) or {}
    secret = doc.get('twofa_secret')
    if not secret:
        raise HTTPException(status_code=400, detail='2FA setup not started')

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail='Invalid code')

    await _repo().mark_enabled(admin_id)
    return {'success': True, 'enabled': True}


@router.post("/2fa/disable")
async def security_2fa_disable(data: Dict[str, Any] = Body(default={})):
    admin_id = _get_admin_id()
    code = str((data or {}).get('code', '')).strip()
    doc = (await _repo().get_state(admin_id)) or {}
    # If already enabled — require current code to disable
    if doc.get('twofa_enabled'):
        secret = doc.get('twofa_secret')
        if not code or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise HTTPException(status_code=400, detail='Invalid code')
    await _repo().clear_2fa(admin_id)
    return {'success': True, 'enabled': False}
