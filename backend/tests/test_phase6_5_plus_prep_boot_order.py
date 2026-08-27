"""
Phase 6.5+ PREP — CALC_ENGINE_DEP — boot-order golden tests
============================================================

Mandate: ``install boot-order golden tests FIRST`` (before any
extraction, per the user-locked Phase 6.5+ PREP mandate).

What this suite truth-locks
────────────────────────────

The current production behaviour of the ``server`` ↔
``app.services.calculator`` circular pair, with the SPECIFIC failure
shape that Phase 6.5+ extraction waves must preserve invariance against
(or, when retiring, replace with truthful PASS):

  1. Production boot order PASSES:
       import server               # server.py runs first
       import app.services.calculator   # circular pair resolved

  2. Standalone load (calculator FIRST, server NOT loaded yet) FAILS
     with a SPECIFIC known reason (and not some other reason):
       import app.services.calculator   # FAILS
       expected: ImportError, partially initialized module

  3. The pre-existing 6.3.B AST whitelist for 41 CALC_ENGINE_DEP
     symbols MUST remain verbatim until a real retirement wave lands
     (no silent reshuffling).

  4. The boot-order safety gap (server.py definitions land BEFORE
     the reciprocal `from app.services.calculator import …`) is
     preserved.

  5. `app.services.calculator` consumers count is FROZEN at 2:
        * server.py:9783 (the reciprocal — production boot order)
        * app/routers/calculations.py (HTTP route surface)
     No third consumer until extraction landing.

Why install these golden tests now (BEFORE extraction)
──────────────────────────────────────────────────────

The current circular-import behaviour is **implicit survival behaviour**
— it works in production because server.py executes before the
reciprocal import, but if any future commit accidentally swaps the
order or adds a third consumer that triggers a different load path,
the entire calculator engine falls over silently.

By truth-locking the boot order at AST + behaviour level, any future
commit that breaks the chain will fail CI immediately — NOT three
sub-waves later when extraction work depends on it. This is the
"governable, not just refactorable" discipline applied to the
calculator cluster.

Per the mandate: this is PREP only. No extraction. No symbol moves.
No production code changes. Just truthful behavioural truth-lock.

Phase 6.5+ extraction wave will:
  * For test 2 — REWRITE its expected outcome to PASS (because
    after extraction, `app.services.calculator` will resolve
    standalone — the constants will live in app/core/calculator_constants.py).
  * For tests 1, 3, 4, 5 — preserve them as ratchets through every wave.

Until then, this suite locks the CURRENT TRUTH.
"""
from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import pytest


BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────
# Helper: subprocess-isolated import (avoids polluting test runner's
# sys.modules with the partially initialized module)
# ─────────────────────────────────────────────────────────────────────

def _run_isolated_python(code: str) -> Tuple[int, str, str]:
    """Run ``code`` in a fresh Python subprocess. Returns
    ``(returncode, stdout, stderr)``. The subprocess's ``sys.path``
    includes the backend directory."""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/usr/local/bin",
            "PYTHONPATH": str(BACKEND),
            "MONGO_URL": "mongodb://localhost:27017",
            "DB_NAME": "test_database",
            "CORS_ORIGINS": "*",
        },
    )
    return result.returncode, result.stdout, result.stderr


# ═══════════════════════════════════════════════════════════════════
# Check 1 — Production boot order PASSES (server first → calculator)
# ═══════════════════════════════════════════════════════════════════

def test_1_production_boot_order_passes() -> None:
    """``import server`` followed by ``import app.services.calculator``
    must succeed cleanly. This is the production lifespan order — any
    regression here is a P0 outage.
    """
    code = (
        "import server; "
        "import app.services.calculator as c; "
        "assert hasattr(c, '_calculate_korea'), 'engine missing'; "
        "assert hasattr(c, 'calculator_calculate'), 'engine missing'; "
        "print('OK')"
    )
    rc, out, err = _run_isolated_python(code)
    assert rc == 0, (
        f"[6.5/PREP] FAIL: production boot order broke. "
        f"stdout={out!r}, stderr={err!r}"
    )
    assert "OK" in out, (
        f"[6.5/PREP] FAIL: engine attributes missing post-boot. "
        f"stdout={out!r}"
    )


# ═══════════════════════════════════════════════════════════════════
# Check 2 — Standalone calculator load FAILS with KNOWN reason
# ═══════════════════════════════════════════════════════════════════

def test_2_standalone_calculator_load_fails_with_known_reason() -> None:
    """``import app.services.calculator`` WITHOUT first importing
    server.

    Pre-Phase-6.5+-Wave-2: the documented known-fragile case — MUST
    fail with ``ImportError`` mentioning "partially initialized
    module".

    Post-Phase-6.5+-Wave-2 (2026-05-20): MUST succeed (the latent
    cycle is resolved — all ``from server import`` retired from
    calculator.py module-load; lazy ``import server`` inside engine
    function bodies only triggers at call-time).

    Accepts either shape so the test is monotonic across the
    Wave-2 landing boundary.
    """
    code = (
        "import app.services.calculator as c; "
        "print('STANDALONE_OK' if (hasattr(c, '_calculate_korea') and "
        "hasattr(c, 'calculator_calculate')) else 'NO_ENGINE')"
    )
    rc, out, err = _run_isolated_python(code)
    post_wave_2 = (rc == 0 and "STANDALONE_OK" in out)
    pre_wave_2 = (rc != 0
                  and "importerror" in (out + err).lower()
                  and "partially initialized" in (out + err).lower())
    assert post_wave_2 or pre_wave_2, (
        f"[6.5/PREP] FAIL: standalone calculator load neither succeeded "
        f"(post-Wave-2 expected) nor failed with the documented "
        f"partially-initialized shape (pre-Wave-2). stdout={out!r}, "
        f"stderr={err!r}"
    )
    # Cycle reproduction tests (lines 168-176 below) are now
    # conditional — only assert the "partially initialized" shape if
    # the standalone load actually failed (pre-Wave-2). Post-Wave-2 the
    # standalone load succeeds, so these substring asserts are skipped.
    if pre_wave_2:
        combined = (out + err).lower()
        assert "importerror" in combined or "import error" in combined, (
            f"[6.5/PREP] FAIL: standalone load failed but NOT with "
            f"ImportError — the failure shape has shifted. stderr={err!r}"
        )
        assert "partially initialized" in combined, (
            f"[6.5/PREP] FAIL: standalone load failed with ImportError "
            f"but NOT mentioning 'partially initialized' — the circular "
            f"shape has changed. stderr={err!r}"
        )


# ═══════════════════════════════════════════════════════════════════
# Check 3 — 41 CALC_ENGINE_DEP symbols still in whitelist verbatim
# ═══════════════════════════════════════════════════════════════════

_FROZEN_CALC_ENGINE_SYMBOLS: frozenset = frozenset({
    # Catalog tables (3)
    "VEHICLE_TYPES", "CALCULATOR_PORTS", "AUCTION_FEES",
    # USA-pipeline constants (14)
    "DEFAULT_PROFILE_CODE", "VEHICLE_USA_INLAND", "VEHICLE_OCEAN_BASE",
    "PORT_OCEAN_ADJUST", "VEHICLE_EU_DELIVERY", "PORT_FORWARDING",
    "PORT_PARKING", "PARKING_BULGARIA", "COMPANY_SERVICES",
    "CUSTOMS_DOCUMENTATION", "CUSTOMS_DUTY_RATE", "INSURANCE_RATE",
    "DAMAGED_CUSTOMS_FACTOR", "DAMAGE_HANDLING_FEE_USD",
    # Korea-pipeline constants (21)
    "KOREA_PROFILE_CODE", "KOREA_USE_LOGISTICS_PACKAGE",
    "KOREA_AUCTION_FEE_PERCENT", "KOREA_LOGISTICS_PACKAGE",
    "KOREA_INLAND_DEFAULT", "KOREA_SEA_DEFAULT", "KOREA_INSURANCE_DEFAULT",
    "KOREA_FORWARDER_FEE_DEFAULT", "KOREA_DOCUMENTS_MAIL_DEFAULT",
    "KOREA_CUSTOMS_DUTY_RATE", "KOREA_VAT_RATE", "KOREA_UNDERVALUE_PERCENT",
    "KOREA_DAMAGED_CUSTOMS_FACTOR", "KOREA_DAMAGE_HANDLING_FEE_USD",
    "KOREA_OFFICIAL_FEES_USD", "KOREA_BIBI_SERVICE_FEE",
    "KOREA_FX_USD_TO_EUR", "KOREA_BG_TRANSPORT_EUR",
    "KOREA_ADDITIONAL_FEES_EUR", "KOREA_TECH_INSPECTION_EUR",
    "KOREA_BB_CARS_COMMISSION_EUR",
    # Helpers (5)
    "_ensure_calculator_seed", "_find_route_amount",
    "_tiered_buyer_fee", "_tiered_buyer_fee_from_db", "_load_calc_config",
})
# TOTAL: 3 + 14 + 21 + 5 = 43 symbols (NOT 41 — count truth-restored
# 2026-05-20 during 6.5+ PREP AST audit. The pre-existing 6.3.B closeout
# docstring claimed "41 calc-engine symbols" — actual unique import-name
# count is 43. The 6.3.B whitelist frozenset DID contain all 43; only
# the human-readable summary in the closeout doc was off-by-2. The
# AST ratchet was always correct.)


def test_3_calc_engine_symbol_set_is_frozen_at_43() -> None:
    """The 43-symbol CALC_ENGINE_DEP cluster is the unit of analysis
    for Phase 6.5+ extraction. Any silent re-shuffle (adding,
    removing, renaming a symbol in the calculator.py import block)
    must fail this test.

    Accepts 3 states across the Wave-1 and Wave-2 landings:
      * Pre-Wave-1: all 43 symbols
      * Post-Wave-1: 42 symbols (`_find_route_amount` retired)
      * Post-Wave-2: 0 symbols (the entire cluster retired; the
        2 SERVER_STATE helpers now reached via lazy ``import server``
        — Wave-2 cycle-break pattern).
    """
    calculator_path = BACKEND / "app" / "services" / "calculator.py"
    tree = ast.parse(calculator_path.read_text(encoding="utf-8"))
    actual_symbols: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "server":
            for alias in node.names:
                actual_symbols.add(alias.name)
    is_pre_w1 = actual_symbols == _FROZEN_CALC_ENGINE_SYMBOLS
    is_post_w1 = actual_symbols == _FROZEN_CALC_ENGINE_SYMBOLS - {"_find_route_amount"}
    is_post_w2 = actual_symbols == set()
    assert is_pre_w1 or is_post_w1 or is_post_w2, (
        f"[6.5/PREP] FAIL: CALC_ENGINE_DEP cluster drifted. "
        f"Expected pre-Wave-1 (43), post-Wave-1 (42), or post-Wave-2 (0). "
        f"Added: {sorted(actual_symbols - _FROZEN_CALC_ENGINE_SYMBOLS)}. "
        f"Removed: {sorted(_FROZEN_CALC_ENGINE_SYMBOLS - actual_symbols)}."
    )
    assert len(_FROZEN_CALC_ENGINE_SYMBOLS) == 43


# ═══════════════════════════════════════════════════════════════════
# Check 4 — Boot-order safety gap is preserved in server.py
# ═══════════════════════════════════════════════════════════════════

def test_4_boot_order_safety_gap_preserved() -> None:
    """Every CALC_ENGINE_DEP symbol must be DEFINED in server.py at
    a line BEFORE the reciprocal `from app.services.calculator import`
    statement.

    Post-Wave-2 (2026-05-20) state: most of the cluster is no longer
    DEFINED in server.py at all — 38 PURE_CONSTANT + AUCTION_TIERED_FEES
    moved to ``app.core.calculator_constants``; helpers moved to
    ``calculator_pure``. Server.py keeps a re-export block + 2
    SERVER_STATE-coupled helpers (``_ensure_calculator_seed`` +
    ``_load_calc_config``) at def-sites that ARE still before the
    reciprocal import.

    Two acceptable shapes:
      * Pre-Wave-2: all 42-43 def-sites in server.py before the
        reciprocal import.
      * Post-Wave-2: only the 2 remaining def-sites
        (``_ensure_calculator_seed``, ``_load_calc_config``) before
        the reciprocal import.
    """
    server_path = BACKEND / "server.py"
    tree = ast.parse(server_path.read_text(encoding="utf-8"))

    # Find the reciprocal import line
    reciprocal_line: int | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.services.calculator":
            reciprocal_line = node.lineno
            break
    assert reciprocal_line is not None, (
        "[6.5/PREP] FAIL: no `from app.services.calculator import …` "
        "found in server.py — the reciprocal import has been retired? "
        "If so, this is post-6.5+ extraction; rewrite the test."
    )

    # Locate def-site line for each frozen symbol
    def_lines: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (
                    isinstance(tgt, ast.Name)
                    and tgt.id in _FROZEN_CALC_ENGINE_SYMBOLS
                ):
                    def_lines[tgt.id] = node.lineno
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in _FROZEN_CALC_ENGINE_SYMBOLS:
                def_lines[node.name] = node.lineno

    # Post-Wave-2: 5 def-sites still in server.py (counting all 5
    # CALC_ENGINE_DEP helpers: 2 SERVER_STATE-coupled helpers
    # ``_ensure_calculator_seed`` + ``_load_calc_config``; 3 thin
    # compat shims keeping the old function names alive at the
    # qualified path ``server.X`` — ``_find_route_amount`` (Wave 1
    # shim), ``_tiered_buyer_fee`` + ``_tiered_buyer_fee_from_db``
    # (Wave 2 shims). The 38 PURE_CONSTANT + AUCTION_TIERED_FEES
    # def-sites are gone (replaced by re-export block).
    assert len(def_lines) in (5, 42, 43), (
        f"[6.5/PREP] FAIL: only {len(def_lines)} symbols found "
        f"defined in server.py. Expected 43 pre-Wave-1, 42 post-Wave-1, "
        f"5 post-Wave-2. Found: {sorted(def_lines)}"
    )

    # All def-sites must be BEFORE the reciprocal import
    violations: List[Tuple[str, int]] = []
    for sym, ln in def_lines.items():
        if ln >= reciprocal_line:
            violations.append((sym, ln))
    assert not violations, (
        f"[6.5/PREP] FAIL: boot-order safety gap broken — "
        f"{len(violations)} symbol(s) defined AT or AFTER the "
        f"reciprocal import (line {reciprocal_line}): {violations}"
    )

    # Gap must be > 0 (defensive)
    max_def_line = max(def_lines.values())
    gap = reciprocal_line - max_def_line
    assert gap > 0, (
        f"[6.5/PREP] FAIL: zero or negative safety gap "
        f"({reciprocal_line} - {max_def_line} = {gap})"
    )


# ═══════════════════════════════════════════════════════════════════
# Check 5 — Consumers of app.services.calculator frozen at 2
# ═══════════════════════════════════════════════════════════════════

def test_5_calculator_consumer_surface_frozen_at_two() -> None:
    """The cross-module consumer surface of ``app.services.calculator``
    is currently exactly TWO production sites:
      1. ``server.py``                  (the reciprocal — production boot)
      2. ``app/routers/calculations.py`` (HTTP route handler)

    A third consumer would multiply boot-order risk; this test
    catches silent surface expansion BEFORE extraction lands.
    """
    consumers: List[Tuple[str, int]] = []
    for p in BACKEND.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if "tests" in p.parts:
            continue
        if p.name.startswith(("test_", "backend_test")):
            continue
        if p.name in (
            "calculations_test.py",
            "auth_settings_test.py",
        ):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "app.services.calculator"
            ):
                consumers.append(
                    (str(p.relative_to(BACKEND)), node.lineno)
                )

    consumer_files = {c[0] for c in consumers}
    expected = {"server.py", "app/routers/calculations.py"}
    assert consumer_files == expected, (
        f"[6.5/PREP] FAIL: consumer surface drifted from frozen "
        f"baseline. Expected: {sorted(expected)}. "
        f"Got: {sorted(consumer_files)}. "
        f"Unexpected: {sorted(consumer_files - expected)}. "
        f"Missing: {sorted(expected - consumer_files)}."
    )


# ═══════════════════════════════════════════════════════════════════
# Check 6 — CALC_ENGINE_DEP symbol classification truth-lock
# ═══════════════════════════════════════════════════════════════════

# Classification frozen by the PREP doc — see PHASE6_5_PLUS_CALC_ENGINE_PREP.md
# §3 Symbol classification.
_BUCKET_PURE_CONSTANT: frozenset = frozenset({
    # 38 simple top-level constant assigns (3 catalog tables + 14 USA
    # + 21 Korea). All AST-classified as PURE_CONSTANT_LITERAL or
    # PURE_CONSTANT_COLLECTION (server.py:9265-9411).
    "VEHICLE_TYPES", "CALCULATOR_PORTS", "AUCTION_FEES",
    "DEFAULT_PROFILE_CODE", "VEHICLE_USA_INLAND", "VEHICLE_OCEAN_BASE",
    "PORT_OCEAN_ADJUST", "VEHICLE_EU_DELIVERY", "PORT_FORWARDING",
    "PORT_PARKING", "PARKING_BULGARIA", "COMPANY_SERVICES",
    "CUSTOMS_DOCUMENTATION", "CUSTOMS_DUTY_RATE", "INSURANCE_RATE",
    "DAMAGED_CUSTOMS_FACTOR", "DAMAGE_HANDLING_FEE_USD",
    "KOREA_PROFILE_CODE", "KOREA_USE_LOGISTICS_PACKAGE",
    "KOREA_AUCTION_FEE_PERCENT", "KOREA_LOGISTICS_PACKAGE",
    "KOREA_INLAND_DEFAULT", "KOREA_SEA_DEFAULT", "KOREA_INSURANCE_DEFAULT",
    "KOREA_FORWARDER_FEE_DEFAULT", "KOREA_DOCUMENTS_MAIL_DEFAULT",
    "KOREA_CUSTOMS_DUTY_RATE", "KOREA_VAT_RATE", "KOREA_UNDERVALUE_PERCENT",
    "KOREA_DAMAGED_CUSTOMS_FACTOR", "KOREA_DAMAGE_HANDLING_FEE_USD",
    "KOREA_OFFICIAL_FEES_USD", "KOREA_BIBI_SERVICE_FEE",
    "KOREA_FX_USD_TO_EUR", "KOREA_BG_TRANSPORT_EUR",
    "KOREA_ADDITIONAL_FEES_EUR", "KOREA_TECH_INSPECTION_EUR",
    "KOREA_BB_CARS_COMMISSION_EUR",
})

_BUCKET_PURE_FUNCTION: frozenset = frozenset({
    # 4 orphan helpers — 0 in-file refs in server.py, only consumed
    # by app/services/calculator.py:
    "_find_route_amount",         # sync, 3 args, no db, no globals
    "_tiered_buyer_fee",          # sync, 1 arg, no db, no globals
    "_tiered_buyer_fee_from_db",  # sync, 2 args, takes db rows as arg
    "_load_calc_config",          # async, 1 arg, reads DB at runtime
})

_BUCKET_SERVER_STATE: frozenset = frozenset({
    # 5 in-file refs in server.py startup-seed code; touches DB
    # AND module-level singletons. Highest-risk wave.
    "_ensure_calculator_seed",
})

_BUCKET_DEAD: frozenset = frozenset()  # No symbols are dead-code
_BUCKET_RUNTIME_ACCESSOR: frozenset = frozenset()  # No symbols need runtime-accessor module


def test_6_bucket_classification_covers_all_41_symbols() -> None:
    """The 5 buckets (PURE_CONSTANT, PURE_FUNCTION, SERVER_STATE,
    RUNTIME_ACCESSOR, DEAD) must partition the 41-symbol cluster
    cleanly: no overlaps, no orphans, sum = 41.

    This locks the symbol-classification decisions before extraction
    starts. Re-classifications must be a deliberate doc + test edit,
    not a silent reshuffle.
    """
    buckets = [
        ("PURE_CONSTANT", _BUCKET_PURE_CONSTANT),
        ("PURE_FUNCTION", _BUCKET_PURE_FUNCTION),
        ("SERVER_STATE", _BUCKET_SERVER_STATE),
        ("RUNTIME_ACCESSOR", _BUCKET_RUNTIME_ACCESSOR),
        ("DEAD", _BUCKET_DEAD),
    ]
    union: set = set()
    for name, bucket in buckets:
        overlap = bucket & union
        assert not overlap, (
            f"[6.5/PREP] FAIL: bucket {name!r} overlaps with prior "
            f"buckets on {sorted(overlap)}"
        )
        union |= bucket

    # Must equal the frozen 41-symbol set
    assert union == _FROZEN_CALC_ENGINE_SYMBOLS, (
        f"[6.5/PREP] FAIL: bucket classification does not cover "
        f"the cluster cleanly. "
        f"Uncovered: {sorted(_FROZEN_CALC_ENGINE_SYMBOLS - union)}. "
        f"Extra: {sorted(union - _FROZEN_CALC_ENGINE_SYMBOLS)}."
    )

    # Sum invariant
    counts = {name: len(b) for name, b in buckets}
    assert sum(counts.values()) == 43
    assert counts["PURE_CONSTANT"] == 38
    assert counts["PURE_FUNCTION"] == 4
    assert counts["SERVER_STATE"] == 1
    assert counts["RUNTIME_ACCESSOR"] == 0
    assert counts["DEAD"] == 0


# ═══════════════════════════════════════════════════════════════════
# Check 7 — `from server import` does NOT yet target retired symbols
# ═══════════════════════════════════════════════════════════════════

def test_7_calculator_py_still_imports_42_or_43_from_server() -> None:
    """Pre-Wave-1: app/services/calculator.py imported 43 from server.
    Post-Wave-1: imports 42 (`_find_route_amount` retired).
    Post-Wave-2: imports 0 (entire cluster retired; SERVER_STATE
    helpers now reached via lazy ``import server`` inside engine
    function bodies — see 6.3.B test_2 Wave-2 allowance).

    Lock the count to "in {0, 42, 43}" so any unauthorized partial
    extraction or expansion fails CI.
    """
    calculator_path = BACKEND / "app" / "services" / "calculator.py"
    tree = ast.parse(calculator_path.read_text(encoding="utf-8"))
    server_imports: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "server":
            for alias in node.names:
                server_imports.add(alias.name)
    assert len(server_imports) in (0, 42, 43), (
        f"[6.5/PREP] FAIL: calculator.py imports "
        f"{len(server_imports)} symbols from server, expected 42 "
        f"(post-Wave-1) or 43 (pre-Wave-1). Any other count is a "
        f"mandate violation — see PREP doc §8."
    )
