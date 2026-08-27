"""
admin_workers.py
================

Modular FastAPI router for supervised worker administration.

Endpoints (admin-only):
  GET  /api/admin/workers              — list all workers + summary
  POST /api/admin/workers/{name}/restart  — stop + launch via existing registry
  POST /api/admin/workers/{name}/stop     — stop a worker without restart
  POST /api/admin/workers/{name}/start    — start a stopped/crashed worker

Design notes
------------
* Zero new business logic in server.py — this router uses `worker_registry`
  public surface (status / stop / _launch_supervised).
* Auth gating reuses existing `require_admin` dependency if available,
  otherwise falls back to a header-based admin gate that's compatible
  with the rest of the admin surface (Bearer + role check happens upstream
  via the same JWT middleware that gates the other /api/admin/* routes).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends, Header

logger = logging.getLogger("bibi.admin_workers")

router = APIRouter(prefix="/api/admin/workers", tags=["admin-workers"])


# ── Auth guard ───────────────────────────────────────────────────────────────────
# Try to import the canonical admin guard. Defensive fallback if symbol
# moves around — we accept anything callable as a FastAPI dependency.
try:
    from server import require_admin as _require_admin  # type: ignore
except Exception:  # pragma: no cover
    async def _require_admin(authorization: str = Header(default=None)):
        # Best-effort: in dev the public access has been disabled at the
        # ingress level. We just need a non-empty Authorization header so
        # this endpoint is not callable anonymously.
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="admin auth required")
        return True


# ── Helpers ────────────────────────────────────────────────────────────────────────
def _get_registry():
    try:
        from app.core.worker_registry import worker_registry as _wr
        return _wr
    except Exception as _e:  # pragma: no cover
        raise HTTPException(status_code=503, detail=f"worker_registry unavailable: {_e}")


def _serialize_worker(w: Dict[str, Any]) -> Dict[str, Any]:
    """Strip non-JSON-safe fields from a registry status row."""
    return {
        "name": w.get("name"),
        "state": w.get("state"),
        "restarts": w.get("restarts", 0),
        "max_restarts": w.get("max_restarts"),
        "critical": w.get("critical", False),
        "restart_policy": w.get("restart_policy"),
        "restart_backoff_sec": w.get("restart_backoff_sec"),
        "started_at": w.get("started_at"),
        "last_error": w.get("last_error"),
        "last_error_at": w.get("last_error_at"),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────────
@router.get("", dependencies=[Depends(_require_admin)])
async def list_workers() -> Dict[str, Any]:
    """Return summary + per-worker status."""
    wr = _get_registry()
    rows: List[Dict[str, Any]] = [_serialize_worker(w) for w in wr.status()]
    return {
        "summary": wr.status_summary(),
        "workers": rows,
    }


@router.post("/{name}/restart", dependencies=[Depends(_require_admin)])
async def restart_worker(name: str) -> Dict[str, Any]:
    """Stop the worker (if running), then re-launch via the existing supervisor.

    Implementation simply re-uses ``stop()`` + ``_launch_supervised()`` so the
    semantics are identical to a fresh boot launch (restart counter is reset).
    """
    wr = _get_registry()
    spec = wr._workers.get(name) if hasattr(wr, "_workers") else None  # noqa: SLF001
    if spec is None:
        raise HTTPException(status_code=404, detail=f"worker '{name}' not registered")
    try:
        await wr.stop(name, grace_period_sec=5.0)
    except Exception as _e:
        logger.warning("[admin_workers] stop(%s) raised: %s", name, _e)
    # Reset transient state
    spec.state = "registered"
    spec.restarts = 0
    spec.last_error = None
    spec.last_error_at = None
    try:
        wr._launch_supervised(spec)  # noqa: SLF001
    except Exception as _e:
        raise HTTPException(status_code=500, detail=f"restart failed: {_e}")
    return {"success": True, "worker": name, "state": spec.state}


@router.post("/{name}/stop", dependencies=[Depends(_require_admin)])
async def stop_worker(name: str) -> Dict[str, Any]:
    wr = _get_registry()
    if not hasattr(wr, "_workers") or name not in wr._workers:  # noqa: SLF001
        raise HTTPException(status_code=404, detail=f"worker '{name}' not registered")
    await wr.stop(name, grace_period_sec=5.0)
    return {"success": True, "worker": name, "state": "stopped"}


@router.post("/{name}/start", dependencies=[Depends(_require_admin)])
async def start_worker(name: str) -> Dict[str, Any]:
    wr = _get_registry()
    spec = wr._workers.get(name) if hasattr(wr, "_workers") else None  # noqa: SLF001
    if spec is None:
        raise HTTPException(status_code=404, detail=f"worker '{name}' not registered")
    if spec.state == "running":
        return {"success": True, "worker": name, "state": "running", "note": "already running"}
    try:
        wr._launch_supervised(spec)  # noqa: SLF001
    except Exception as _e:
        raise HTTPException(status_code=500, detail=f"start failed: {_e}")
    return {"success": True, "worker": name, "state": spec.state}
