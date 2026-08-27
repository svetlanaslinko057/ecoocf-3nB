"""
Phase 4 / C-5 — Invariant helpers (shared across pytest + shell).
=================================================================

This module provides the read-only inspection primitives that the
Phase 4 invariant test suite (``test_phase4_invariants.py``) and
the standalone smoke script (``tools/check_phase4_invariants.sh``)
use to assert architectural state.

Design notes
------------
* All helpers are **read-only** — they never mutate runtime state,
  never POST to the backend, never write any file.  They scrape
  HTTP endpoints, read on-disk artifacts, and parse Python source.
* No dependency on FastAPI / motor / pytest at import time.  Only
  stdlib + ``httpx`` (already in requirements.txt).
* The AST analyser performs **semantic** classification, not
  grep-driven counting.  See ``find_unsupervised_hot_path_spawns``.
"""
from __future__ import annotations

import ast
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx


# ─────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────
DEFAULT_BACKEND_URL = os.environ.get("BIBI_BACKEND_URL", "http://localhost:8001")
DEFAULT_SERVER_PY = Path(os.environ.get("BIBI_SERVER_PY", "/app/backend/server.py"))
DEFAULT_STRUCTURED_LOG = Path(
    os.environ.get(
        "BIBI_STRUCTURED_LOG_PATH",
        "/var/log/supervisor/backend.structured.jsonl",
    )
)

# Phase 3.4 / 4 frozen invariants.
OPENAPI_PATHS_FREEZE = 618
OPENAPI_OPERATIONS_FREEZE = 679
WORKER_REGISTRY_COUNT_FREEZE = 7
EXPECTED_WORKER_NAMES: Set[str] = {
    "ops_guardian",
    "payment_reminder",
    "resolver_worker",
    "ringostat_cron",
    "tracking_worker",
    "transfer_detector",
    "watchlist_live_poll",
}

# Current baselines (RATCHET ceilings — must NEVER grow, can shrink).
# These are the LIVE measured values at Phase 4 / C-5 closure (2026-05-18).
# Tightening rule: when a Phase 5 cleanup commit lowers either count,
# ratchet the ceiling down to the new measured value in the same commit.
# A test that fails because count < ceiling is NOT a regression — it is
# a forgotten ratchet adjustment.
ADMIN_ROUTER_CEILING = 27          # was 28 buffer; tightened to live value
ASYNCIO_CREATE_TASK_CEILING = 31   # was 34 buffer; tightened to live value

# Aspirational targets (XFAIL — Phase 5 cleanup will close these).
ADMIN_ROUTER_TARGET = 6
ASYNCIO_CREATE_TASK_TARGET = 0

# Naming convention: a function whose name matches this regex is
# considered a long-running supervised loop.  Used by the semantic
# AST classifier to decide whether a given `asyncio.create_task(X())`
# spawn site is a hot-path or an ad-hoc short-lived task.
HOT_PATH_LOOP_NAME_RE = re.compile(
    r"(_loop|_worker|_cron|_poll|_supervised|_runner|_scheduler)$"
)


# ─────────────────────────────────────────────────────────────────
# HTTP scrapers
# ─────────────────────────────────────────────────────────────────
def fetch_openapi(base_url: str = DEFAULT_BACKEND_URL,
                  timeout: float = 10.0) -> Dict[str, Any]:
    """GET /api/openapi.json — full schema dict."""
    r = httpx.get(f"{base_url}/api/openapi.json", timeout=timeout)
    r.raise_for_status()
    return r.json()


def count_openapi_surface(schema: Dict[str, Any]) -> Tuple[int, int]:
    """Return (paths_count, operations_count) from an OpenAPI schema."""
    paths = schema.get("paths", {}) or {}
    methods = ("get", "post", "put", "patch", "delete", "head", "options")
    ops = sum(
        1
        for _p, m in paths.items()
        for k in (m or {})
        if isinstance(k, str) and k.lower() in methods
    )
    return len(paths), ops


def fetch_metrics_text(base_url: str = DEFAULT_BACKEND_URL,
                       timeout: float = 10.0) -> str:
    """GET /metrics — Prometheus text exposition."""
    r = httpx.get(f"{base_url}/metrics", timeout=timeout)
    r.raise_for_status()
    return r.text


# ─────────────────────────────────────────────────────────────────
# Prometheus text parser (minimal — just what invariant tests need)
# ─────────────────────────────────────────────────────────────────
@dataclass
class Sample:
    name: str
    labels: Dict[str, str]
    value: float


def parse_prometheus(text: str) -> Dict[str, List[Sample]]:
    """Parse a Prometheus exposition text dump into name → samples.

    Only handles the subset we need: counter / gauge / histogram_sum /
    histogram_count / histogram_bucket lines.  Ignores ``# HELP`` and
    ``# TYPE`` comments for value parsing but USES ``# TYPE`` to
    pre-populate the result dict with empty-list entries — so the
    suite can assert "metric NAME is declared" even when the metric
    has zero samples (e.g. ``socketio_emit_total`` before adoption).
    """
    out: Dict[str, List[Sample]] = {}
    label_re = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')
    sample_re = re.compile(
        r'^(\w+)(?:\{([^}]*)\})?\s+([\-+]?(?:\d+\.?\d*|\.\d+|nan|inf|-inf|\+inf)(?:[eE][\-+]?\d+)?)'
    )

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# TYPE "):
            # "# TYPE name kind"
            parts = line.split()
            if len(parts) >= 3:
                out.setdefault(parts[2], [])
                out.setdefault(parts[2] + "_total", [])
                out.setdefault(parts[2] + "_count", [])
                out.setdefault(parts[2] + "_sum", [])
                out.setdefault(parts[2] + "_bucket", [])
            continue
        if line.startswith("#"):
            continue
        m = sample_re.match(line)
        if not m:
            continue
        name, labels_blob, value_str = m.group(1), m.group(2) or "", m.group(3)
        labels = dict(label_re.findall(labels_blob))
        try:
            value = float(value_str)
        except ValueError:
            continue
        out.setdefault(name, []).append(Sample(name=name, labels=labels, value=value))
    return out


# ─────────────────────────────────────────────────────────────────
# Structured-log file checks
# ─────────────────────────────────────────────────────────────────
def structured_log_is_writable(path: Path = DEFAULT_STRUCTURED_LOG) -> Tuple[bool, str]:
    """Return ``(ok, diagnostic)``.

    ``ok=True`` requires:
      * file exists AND
      * file is non-empty AND
      * last line parses as JSON with at least ``ts`` + ``level`` +
        ``logger`` + ``msg`` keys.
    """
    if not path.exists():
        return False, f"missing: {path}"
    if path.stat().st_size == 0:
        return False, f"empty: {path}"
    try:
        with path.open("rb") as f:
            # Read just the tail to avoid loading 100MB+ of log
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 32_768))
            tail = f.read().decode("utf-8", errors="replace")
        last_line = next(
            (ln for ln in reversed(tail.splitlines()) if ln.strip()),
            "",
        )
        if not last_line:
            return False, "no parseable last line"
        rec = json.loads(last_line)
    except Exception as exc:
        return False, f"parse error: {exc}"
    required = {"ts", "level", "logger", "msg"}
    missing = required - set(rec)
    if missing:
        return False, f"last record missing keys: {sorted(missing)}"
    return True, f"ok ({path.stat().st_size} bytes)"


def grep_structured_log(path: Path, msg_substring: str, *,
                        tail_bytes: int = 4 * 1024 * 1024) -> List[Dict[str, Any]]:
    """Return the parsed JSON records whose ``msg`` contains the substring.

    Reads only the last ``tail_bytes`` of the file (default 4 MiB) so
    we never page huge log volumes.
    """
    if not path.exists():
        return []
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - tail_bytes))
        blob = f.read().decode("utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in blob.splitlines():
        line = line.strip()
        if not line or msg_substring not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if msg_substring in str(rec.get("msg", "")):
            out.append(rec)
    return out


# ─────────────────────────────────────────────────────────────────
# AST static-analysis primitives (semantic — not grep)
# ─────────────────────────────────────────────────────────────────
@dataclass
class CreateTaskSpawn:
    """A single ``asyncio.create_task(...)`` call site in source."""
    line: int
    callee_name: Optional[str]      # e.g. "ringostat_cron_loop"
    is_long_running_name: bool      # by HOT_PATH_LOOP_NAME_RE
    enclosing_try_has_registry_register: bool
    is_inside_except_branch: bool
    notes: List[str] = field(default_factory=list)


def _extract_callee_name(call_node: ast.AST) -> Optional[str]:
    """Given the *argument* of ``asyncio.create_task(...)``, try to
    extract the called function's bare name.

    Handles common shapes:
      asyncio.create_task(foo())              → "foo"
      asyncio.create_task(foo(x, y))          → "foo"
      asyncio.create_task(mod.foo())          → "foo"
      asyncio.create_task(self.foo())         → "foo"
    Returns None for anything we can't pattern-match.
    """
    if not isinstance(call_node, ast.Call):
        return None
    func = call_node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _try_block_contains_registry_register(try_node: ast.Try) -> bool:
    """Walk a Try node's body and return True iff it contains a call
    of the form ``worker_registry.register(...)``.
    """
    for node in ast.walk(try_node):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "register":
            # check that the receiver is named worker_registry
            receiver = fn.value
            if isinstance(receiver, ast.Name) and receiver.id == "worker_registry":
                return True
            if isinstance(receiver, ast.Attribute) and receiver.attr == "worker_registry":
                return True
    return False


def find_create_task_spawns(source_path: Path = DEFAULT_SERVER_PY) -> List[CreateTaskSpawn]:
    """Locate every ``asyncio.create_task(...)`` call in the given
    Python source, and classify each one as supervised vs orphan.

    Classification rule (semantic, per Phase 4 / C-5 mandate option C-b):
      * If the call site is inside an ``except`` branch of a ``try``
        whose ``try`` body contains a ``worker_registry.register(...)``
        call → SUPERVISED (legacy fallback path; acceptable).
      * Else if the spawned coroutine's name does NOT match
        ``HOT_PATH_LOOP_NAME_RE`` → ad-hoc short-lived task; not a
        hot-path concern.
      * Else → ORPHAN long-running spawn → VIOLATION.

    Returns a list of CreateTaskSpawn instances annotated with the
    classification context. Callers (test suite) decide which ones
    constitute a failure.
    """
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(source_path))

    # Pre-compute parent map for Try / ExceptHandler lookup, because
    # `ast` doesn't carry parent links.
    parents: Dict[int, ast.AST] = {}

    def _annotate(node: ast.AST, parent: Optional[ast.AST] = None) -> None:
        if parent is not None:
            parents[id(node)] = parent
        for child in ast.iter_child_nodes(node):
            _annotate(child, node)
    _annotate(tree)

    def _find_enclosing_tries(node: ast.AST) -> List[Tuple[ast.Try, bool]]:
        """Walk upward and collect ALL enclosing ``Try`` nodes
        together with a flag indicating whether the upward path
        crossed an ``ExceptHandler`` (i.e. the call is inside an
        ``except`` branch of that Try, not its ``try`` body).

        Returning the full chain (not just the innermost) lets us
        correctly classify spawns nested inside ``except:`` →
        ``try:`` → ``asyncio.create_task(...)``.  Example pattern
        used throughout server.py:

            try:
                worker_registry.register("foo", foo_loop)        # OUTER try
            except Exception:
                try:
                    asyncio.create_task(foo_loop())              # legacy fallback
                except Exception:
                    ...

        Here the innermost Try has no register call, but the OUTER
        one does — and the spawn is inside an ExceptHandler of that
        outer Try.  The pattern is the canonical legacy-fallback
        idiom and must be classified as SUPERVISED.
        """
        chain: List[Tuple[ast.Try, bool]] = []
        cur = parents.get(id(node))
        in_except = False
        while cur is not None:
            if isinstance(cur, ast.ExceptHandler):
                in_except = True
            if isinstance(cur, ast.Try):
                chain.append((cur, in_except))
                # Reset in_except for the next outer Try — the next
                # iteration starts fresh from this Try's boundary.
                in_except = False
            cur = parents.get(id(cur))
        return chain

    spawns: List[CreateTaskSpawn] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # match asyncio.create_task(...)
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "create_task"):
            continue
        recv = fn.value
        if not (isinstance(recv, ast.Name) and recv.id == "asyncio"):
            continue
        if not node.args:
            continue
        callee_arg = node.args[0]
        callee_name = _extract_callee_name(callee_arg)
        is_long_running = bool(
            callee_name and HOT_PATH_LOOP_NAME_RE.search(callee_name)
        )
        # SUPERVISED iff ANY enclosing Try's `try` body contains a
        # worker_registry.register(...) call AND the current node is
        # inside that Try's except branch (the legacy fallback path).
        chain = _find_enclosing_tries(node)
        registry_in_any_try = False
        in_except_of_registry_try = False
        for try_node, in_except_of_this in chain:
            if _try_block_contains_registry_register(try_node):
                registry_in_any_try = True
                if in_except_of_this:
                    in_except_of_registry_try = True
                    break
        spawns.append(CreateTaskSpawn(
            line=node.lineno,
            callee_name=callee_name,
            is_long_running_name=is_long_running,
            enclosing_try_has_registry_register=registry_in_any_try,
            is_inside_except_branch=in_except_of_registry_try,
        ))
    return spawns


def find_unsupervised_hot_path_spawns(
    source_path: Path = DEFAULT_SERVER_PY,
) -> List[CreateTaskSpawn]:
    """Return only the create_task spawns that violate the supervised
    hot-path invariant: long-running by name, NOT a legacy fallback
    branch of a registry-register try/except.
    """
    out: List[CreateTaskSpawn] = []
    for spawn in find_create_task_spawns(source_path):
        if not spawn.is_long_running_name:
            continue  # short-lived ad-hoc — acceptable
        if spawn.is_inside_except_branch and spawn.enclosing_try_has_registry_register:
            continue  # legacy fallback inside `except` of registry try
        spawn.notes.append("orphan long-running spawn (no registry register in enclosing try)")
        out.append(spawn)
    return out


def count_admin_router_mounts(source_path: Path = DEFAULT_SERVER_PY) -> int:
    """Count ``fastapi_app.include_router(<…admin…>)`` call sites.

    Uses AST to avoid false positives in comments / docstrings.
    """
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(source_path))
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "include_router"):
            continue
        # Argument 0 should reference an admin router module
        if not node.args:
            continue
        arg = node.args[0]
        # match patterns like _admin_kpi_mod.router, admin_security.router, etc.
        as_text = ast.unparse(arg).lower() if hasattr(ast, "unparse") else ""
        if "admin" in as_text:
            count += 1
    return count


def count_total_create_task(source_path: Path = DEFAULT_SERVER_PY) -> int:
    """Raw count of ``asyncio.create_task(...)`` calls (any kind).

    Used by the RATCHET ceiling invariant — must not grow.
    """
    return len(find_create_task_spawns(source_path))


def find_live_on_event_decorators(source_path: Path = DEFAULT_SERVER_PY) -> List[int]:
    """Return line numbers of LIVE ``@app.on_event(...)`` decorators.

    Comment-out lines (e.g. `# @app.on_event("startup") at this site.`
    inside a forensic comment) are NOT live decorators and must NOT
    be reported.  AST traversal naturally ignores them.
    """
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(source_path))
    lines: List[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr == "on_event":
                lines.append(node.lineno)
    return lines


def fastapi_app_has_lifespan_kwarg(source_path: Path = DEFAULT_SERVER_PY) -> bool:
    """Check that the ``FastAPI(...)`` constructor at module level
    is invoked with a ``lifespan=...`` kwarg.

    Walks the AST to find the first top-level assignment
    ``fastapi_app = FastAPI(...)`` and inspects its keyword arguments.
    """
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(source_path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "fastapi_app"):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        fn = value.func
        if not ((isinstance(fn, ast.Name) and fn.id == "FastAPI")
                or (isinstance(fn, ast.Attribute) and fn.attr == "FastAPI")):
            continue
        for kw in value.keywords:
            if kw.arg == "lifespan":
                return True
    return False


# ─────────────────────────────────────────────────────────────────
# Composite assertion helpers (used by lifespan self-check + tests)
# ─────────────────────────────────────────────────────────────────
def assert_phase4_invariants(base_url: str = DEFAULT_BACKEND_URL,
                              source_path: Path = DEFAULT_SERVER_PY) -> List[str]:
    """Return a list of human-readable failure messages.  Empty list
    ⇒ all hard invariants hold.  Useful as a runtime self-check
    (e.g. from a future ``/api/admin/self-check`` endpoint or from
    operators' shell scripts).

    Excludes XFAIL targets — only enforces PASS / RATCHET / SEMANTIC.
    """
    failures: List[str] = []

    # I1 / I2 — OpenAPI freeze
    try:
        schema = fetch_openapi(base_url)
        paths, ops = count_openapi_surface(schema)
        if paths != OPENAPI_PATHS_FREEZE:
            failures.append(f"OpenAPI paths drift: {paths} != {OPENAPI_PATHS_FREEZE}")
        if ops != OPENAPI_OPERATIONS_FREEZE:
            failures.append(f"OpenAPI operations drift: {ops} != {OPENAPI_OPERATIONS_FREEZE}")
    except Exception as exc:
        failures.append(f"OpenAPI fetch failed: {exc}")

    # I3 / I4 / I5 — worker registry topology
    try:
        metrics = parse_prometheus(fetch_metrics_text(base_url))
        active = metrics.get("worker_active_instances", [])
        seen_names = {s.labels.get("name") for s in active if s.labels.get("name")}
        if seen_names != EXPECTED_WORKER_NAMES:
            failures.append(
                f"worker name set drift: {sorted(seen_names)} != {sorted(EXPECTED_WORKER_NAMES)}"
            )
        if len(active) != WORKER_REGISTRY_COUNT_FREEZE:
            failures.append(
                f"worker count drift: {len(active)} != {WORKER_REGISTRY_COUNT_FREEZE}"
            )
        # I5 — active_instances == 1 for each
        for s in active:
            if s.value != 1.0:
                failures.append(
                    f"worker {s.labels.get('name','?')} active_instances={s.value} (expected 1.0)"
                )
    except Exception as exc:
        failures.append(f"metrics fetch failed: {exc}")

    # I6 — no live @on_event decorators
    try:
        live = find_live_on_event_decorators(source_path)
        if live:
            failures.append(f"live @on_event decorators at lines: {live}")
    except Exception as exc:
        failures.append(f"on_event static check failed: {exc}")

    # I7 — admin perimeter ceiling
    try:
        admin = count_admin_router_mounts(source_path)
        if admin > ADMIN_ROUTER_CEILING:
            failures.append(
                f"admin router count {admin} exceeds ceiling {ADMIN_ROUTER_CEILING}"
            )
    except Exception as exc:
        failures.append(f"admin router count failed: {exc}")

    # I8 — semantic: no unsupervised hot-path workers
    try:
        orphans = find_unsupervised_hot_path_spawns(source_path)
        if orphans:
            failures.append(
                "unsupervised hot-path spawns: "
                + ", ".join(f"L{s.line}:{s.callee_name}" for s in orphans)
            )
    except Exception as exc:
        failures.append(f"semantic AST check failed: {exc}")

    # I9 — structured log writable
    ok, diag = structured_log_is_writable()
    if not ok:
        failures.append(f"structured log not writable: {diag}")

    # I10 — lifespan kwarg present
    try:
        if not fastapi_app_has_lifespan_kwarg(source_path):
            failures.append("FastAPI(...) constructor missing lifespan=lifespan kwarg")
    except Exception as exc:
        failures.append(f"lifespan kwarg check failed: {exc}")

    return failures


__all__ = [
    # constants
    "OPENAPI_PATHS_FREEZE",
    "OPENAPI_OPERATIONS_FREEZE",
    "WORKER_REGISTRY_COUNT_FREEZE",
    "EXPECTED_WORKER_NAMES",
    "ADMIN_ROUTER_CEILING",
    "ASYNCIO_CREATE_TASK_CEILING",
    "ADMIN_ROUTER_TARGET",
    "ASYNCIO_CREATE_TASK_TARGET",
    "HOT_PATH_LOOP_NAME_RE",
    "DEFAULT_BACKEND_URL",
    "DEFAULT_SERVER_PY",
    "DEFAULT_STRUCTURED_LOG",
    # data classes
    "Sample",
    "CreateTaskSpawn",
    # HTTP scrapers
    "fetch_openapi",
    "count_openapi_surface",
    "fetch_metrics_text",
    "parse_prometheus",
    # log helpers
    "structured_log_is_writable",
    "grep_structured_log",
    # AST helpers
    "find_create_task_spawns",
    "find_unsupervised_hot_path_spawns",
    "count_admin_router_mounts",
    "count_total_create_task",
    "find_live_on_event_decorators",
    "fastapi_app_has_lifespan_kwarg",
    # composite
    "assert_phase4_invariants",
]
