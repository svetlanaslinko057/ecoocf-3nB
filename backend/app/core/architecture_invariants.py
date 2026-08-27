"""app/core/architecture_invariants.py — Phase 6.3.A runtime contracts
========================================================================

**Phase 6.3.A — Runtime Contracts (invariant lock)** lands the
architectural contract that Phase 5 produced (the
disentangling endpoint state) as enforceable assertions that fire at
BOTH:

  * **App startup time** — wired into `server.lifespan()`, so a boot
    against a regressed inventory will fail loud at the earliest
    possible moment.
  * **Test time** — `tests/test_phase6_3_a_runtime_contracts.py`
    exercises the same assertions as a regular regression probe.

Mandate (per `PHASE6_KICKOFF.md`):

  * Hardening, NOT redesign — no new behavior, no new abstractions.
  * Single source of truth — all invariants encoded ONCE here, both
    runtime and tests consume the same function.
  * Anti-regression posture — if a future commit accidentally
    re-introduces a Tier-C bridge, startup AND tests will fail.
  * Live-configured contracts — the assertions read live
    `app_state_targets` data; they are not hand-coded numeric pins.

Architecture endpoint invariants (post-5.5/I; see
`PHASE_5_DISENTANGLING_ENDPOINT.md`):

  ============================== ============ ============
  Surface                        Expected     Source
  ============================== ============ ============
  BRIDGE_INVENTORY               <= 1         app_state_targets
  TIER_C_REQUIRES_REFACTOR       == 0         app_state_targets
  PHASE_5_5_BOUNDARY             == 0         app_state_targets
  QUALIFIED_USAGE_BRIDGES        == 0         app_state_targets
  EXTRACTION_AUX_BRIDGES         <= 47        app_state_targets
                                              (47 post-5.5/I;
                                               45 post-6.2.ACTUAL;
                                               44 post-6.4)
  OpenAPI paths                  == 618       fastapi_app.openapi()
  OpenAPI ops                    == 679       fastapi_app.openapi()
  ============================== ============ ============

Each assertion raises `ArchitectureInvariantViolation` (a subclass of
`AssertionError`) carrying the exact surface name, expected value, and
actual value. Tests check both the type AND the structured payload.

Phase 6.3.B (later) will add AST-level enforcement on top of this
runtime layer (zero `from server import X` outside whitelist, etc).
6.3.A is the runtime-only layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


# Post-5.5/I endpoint expectations. These are the LIVE FLOOR values;
# future waves only RATCHET DOWN (e.g. post-6.2.ACTUAL EXTRACTION_AUX
# becomes 45). The asserts use <= for monotonic invariants and ==
# for hard floors that are not allowed to drift.

_EXPECTED_BRIDGE_INVENTORY_MAX = 1            # _STATIC_DIR Tier-B
_EXPECTED_TIER_C = 0                          # ZERO Tier-C bridges
_EXPECTED_PHASE_5_5_BOUNDARY = 0              # Phase 5.5 closed
_EXPECTED_QUALIFIED_USAGE_BRIDGES = 0         # held since 5.5/F
_EXPECTED_EXTRACTION_AUX_BRIDGES_MAX = 47     # post-5.5/I; ratchet-down OK

_EXPECTED_OPENAPI_PATHS = 696  # + Message Center (waste/messages, client+cabinet notifications)
_EXPECTED_OPENAPI_OPS = 836


class ArchitectureInvariantViolation(AssertionError):
    """A Phase 5 endpoint invariant has been violated.

    Carries the exact surface and the actual vs expected values for
    structured CI diagnostics.
    """

    def __init__(
        self,
        surface: str,
        expected: Any,
        actual: Any,
        *,
        relation: str = "==",
        note: Optional[str] = None,
    ) -> None:
        self.surface = surface
        self.expected = expected
        self.actual = actual
        self.relation = relation
        self.note = note or ""
        msg = (
            f"[Phase 5 endpoint invariant violated] surface={surface!r} "
            f"expected ({relation} {expected}) actual={actual}"
        )
        if note:
            msg = f"{msg}  ── {note}"
        super().__init__(msg)


@dataclass(frozen=True)
class InvariantSnapshot:
    """Read-only structured payload of the architecture state for a
    given probe.  Returned by `compute_snapshot()` and re-emitted via
    structured logging at startup."""
    bridge_inventory: int
    tier_c_requires_refactor: int
    phase_5_5_boundary: int
    qualified_usage_bridges: int
    extraction_aux_bridges: int
    openapi_paths: Optional[int]
    openapi_ops: Optional[int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "bridge_inventory": self.bridge_inventory,
            "tier_c_requires_refactor": self.tier_c_requires_refactor,
            "phase_5_5_boundary": self.phase_5_5_boundary,
            "qualified_usage_bridges": self.qualified_usage_bridges,
            "extraction_aux_bridges": self.extraction_aux_bridges,
            "openapi_paths": self.openapi_paths,
            "openapi_ops": self.openapi_ops,
        }


def compute_snapshot(fastapi_app: Optional[Any] = None) -> InvariantSnapshot:
    """Compute the LIVE architectural snapshot.

    `fastapi_app` is optional — if provided, the OpenAPI shape probe is
    included (618/679 expected). If omitted, OpenAPI fields are None
    and `assert_openapi_surface_frozen()` will skip them.
    """
    from app.core import app_state_targets as t

    openapi_paths: Optional[int] = None
    openapi_ops: Optional[int] = None
    if fastapi_app is not None:
        try:
            schema = fastapi_app.openapi()
            paths = schema.get("paths", {}) or {}
            openapi_paths = len(paths)
            openapi_ops = sum(
                1
                for _p, methods in paths.items()
                for k in (methods or {})
                if k.lower()
                in ("get", "post", "put", "patch", "delete", "head", "options")
            )
        except Exception:
            # Defensive: openapi() can fail on partial mounts during boot.
            # We still want assert_phase_5_endpoint_invariants() to run.
            openapi_paths = None
            openapi_ops = None

    return InvariantSnapshot(
        bridge_inventory=len(t.BRIDGE_INVENTORY),
        tier_c_requires_refactor=len(t.TIER_C_REQUIRES_REFACTOR),
        phase_5_5_boundary=len(t.PHASE_5_5_BOUNDARY),
        qualified_usage_bridges=len(t.QUALIFIED_USAGE_BRIDGES),
        extraction_aux_bridges=len(t.EXTRACTION_AUX_BRIDGES),
        openapi_paths=openapi_paths,
        openapi_ops=openapi_ops,
    )


def assert_phase_5_endpoint_invariants(
    snapshot: Optional[InvariantSnapshot] = None,
    *,
    fastapi_app: Optional[Any] = None,
) -> InvariantSnapshot:
    """Assert ALL Phase 5 disentangling-endpoint invariants.

    Raises `ArchitectureInvariantViolation` on the first failed
    invariant. Returns the snapshot on success so callers can log it.

    If `snapshot` is provided, the OpenAPI fields inside it are NOT
    re-asserted here — use `assert_openapi_surface_frozen()` separately
    or pass `fastapi_app=` to have it computed in this call.

    The OpenAPI shape assertion is intentionally SEPARATE because
    during partial-import test scenarios the FastAPI app may not be
    available; the inventory invariants ARE always available and must
    always pass.
    """
    if snapshot is None:
        snapshot = compute_snapshot(fastapi_app)

    if snapshot.bridge_inventory > _EXPECTED_BRIDGE_INVENTORY_MAX:
        raise ArchitectureInvariantViolation(
            "BRIDGE_INVENTORY",
            _EXPECTED_BRIDGE_INVENTORY_MAX,
            snapshot.bridge_inventory,
            relation="<=",
            note=(
                "post-5.5/I expects <= 1 (only _STATIC_DIR Tier-B for "
                "Phase 5.8). Any growth indicates a regression that "
                "re-introduced a `from server import X` bridge."
            ),
        )

    if snapshot.tier_c_requires_refactor != _EXPECTED_TIER_C:
        raise ArchitectureInvariantViolation(
            "TIER_C_REQUIRES_REFACTOR",
            _EXPECTED_TIER_C,
            snapshot.tier_c_requires_refactor,
            note=(
                "post-5.5/I expects == 0 (Phase 5 disentangling endpoint "
                "— ZERO Tier-C bridges). Any non-zero value indicates "
                "the disentangling endpoint has regressed."
            ),
        )

    if snapshot.phase_5_5_boundary != _EXPECTED_PHASE_5_5_BOUNDARY:
        raise ArchitectureInvariantViolation(
            "PHASE_5_5_BOUNDARY",
            _EXPECTED_PHASE_5_5_BOUNDARY,
            snapshot.phase_5_5_boundary,
            note=(
                "post-5.5/I expects == 0 (Phase 5.5 officially closed). "
                "Non-zero value means a new boundary entry was added — "
                "no Phase 5.5 wave is in flight; this is a structural "
                "regression."
            ),
        )

    if snapshot.qualified_usage_bridges != _EXPECTED_QUALIFIED_USAGE_BRIDGES:
        raise ArchitectureInvariantViolation(
            "QUALIFIED_USAGE_BRIDGES",
            _EXPECTED_QUALIFIED_USAGE_BRIDGES,
            snapshot.qualified_usage_bridges,
            note=(
                "Held at 0 since 5.5/F. Non-zero indicates a regression "
                "to qualified `server.X` access."
            ),
        )

    if snapshot.extraction_aux_bridges > _EXPECTED_EXTRACTION_AUX_BRIDGES_MAX:
        raise ArchitectureInvariantViolation(
            "EXTRACTION_AUX_BRIDGES",
            _EXPECTED_EXTRACTION_AUX_BRIDGES_MAX,
            snapshot.extraction_aux_bridges,
            relation="<=",
            note=(
                "post-5.5/I expects <= 47 (ratchet-down only). Future "
                "waves (6.2.ACTUAL, 6.4) will lower this. Growth means "
                "a new aux-bridge was added — Phase 6 forbids that "
                "(Phase 5 closed the taxonomy)."
            ),
        )

    return snapshot


def assert_openapi_surface_frozen(
    snapshot: InvariantSnapshot,
) -> None:
    """Assert OpenAPI paths/ops match the Phase 5 frozen baseline.

    Separate from `assert_phase_5_endpoint_invariants()` because the
    snapshot's OpenAPI fields can be None during partial-import test
    runs. This function ASSUMES snapshot.openapi_paths is not None —
    callers must pass a snapshot that was computed with `fastapi_app=`.
    """
    if snapshot.openapi_paths is None or snapshot.openapi_ops is None:
        raise ArchitectureInvariantViolation(
            "OpenAPI",
            f"{_EXPECTED_OPENAPI_PATHS} paths / {_EXPECTED_OPENAPI_OPS} ops",
            "snapshot.openapi_* is None (FastAPI app not provided to compute_snapshot)",
            note="Pass fastapi_app= to compute_snapshot() to enable the OpenAPI probe.",
        )

    if snapshot.openapi_paths != _EXPECTED_OPENAPI_PATHS:
        raise ArchitectureInvariantViolation(
            "OpenAPI.paths",
            _EXPECTED_OPENAPI_PATHS,
            snapshot.openapi_paths,
            note=(
                "OpenAPI surface baseline (post auto-domain cleanup + ECO "
                "waste domain + /api/public/geo). Any drift indicates a route "
                "was added or removed — update _EXPECTED_OPENAPI_PATHS if intentional."
            ),
        )

    if snapshot.openapi_ops != _EXPECTED_OPENAPI_OPS:
        raise ArchitectureInvariantViolation(
            "OpenAPI.ops",
            _EXPECTED_OPENAPI_OPS,
            snapshot.openapi_ops,
            note=(
                "OpenAPI ops baseline (post auto-domain cleanup). Drift "
                "indicates a method was added/removed on an existing path — "
                "update _EXPECTED_OPENAPI_OPS if intentional."
            ),
        )


def run_all_phase_5_endpoint_assertions(
    fastapi_app: Optional[Any] = None,
) -> InvariantSnapshot:
    """Convenience wrapper — run BOTH inventory + OpenAPI invariants.

    Used by:
    * `server.lifespan()` at startup, after every router is mounted
      but before yielding to `running`.
    * `tests/test_phase6_3_a_runtime_contracts.py` for the test-time
      verification.

    On success returns the snapshot for logging. On failure raises
    `ArchitectureInvariantViolation` with structured payload.
    """
    snapshot = compute_snapshot(fastapi_app)
    assert_phase_5_endpoint_invariants(snapshot)
    if fastapi_app is not None and snapshot.openapi_paths is not None:
        assert_openapi_surface_frozen(snapshot)
    return snapshot


__all__: Tuple[str, ...] = (
    "ArchitectureInvariantViolation",
    "InvariantSnapshot",
    "compute_snapshot",
    "assert_phase_5_endpoint_invariants",
    "assert_openapi_surface_frozen",
    "run_all_phase_5_endpoint_assertions",
)
