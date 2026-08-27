#!/usr/bin/env python3
"""
Wave 2A — /api/admin/* topology mapper (READ-ONLY analysis).

Goal: produce a comprehensive map of the /api/admin/* surface as it
currently lives in server.py and the extracted Wave-1 modules, broken
down by:
  1. endpoint ownership (which sub-prefix → which logical sub-domain)
  2. import dependency (top-level imports each endpoint uses)
  3. db collection usage (which Mongo collections are touched)
  4. shared-helper usage (security deps, common functions)
  5. auth boundary (require_admin / require_master_admin / require_user / open)
  6. file-location heatmap (where each endpoint lives today)

NO refactoring is done. This script only inspects source files.
Output: stdout + machine-readable JSON file for later diffing.

Discipline reminders (from project plan):
  * topology first, hygiene later
  * admin is a FACADE domain, not a real domain
  * subdomains must be discovered by latent ownership, not by URL prefix
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent  # /app/backend
ADMIN_PREFIX_RE = re.compile(r'/api/admin/([a-zA-Z0-9_-]+)')
ROUTE_DECORATOR_RE = re.compile(
    r'@(fastapi_app|router|[a-zA-Z_][a-zA-Z0-9_]*_router)\.(get|post|put|delete|patch)\(\s*["\']'
    r'(?P<path>[^"\']*)["\']'
)
# Detect APIRouter(prefix="/api/...") so that relative @router.get("/x") paths
# inside extracted Wave-2 routers can be reconstructed to full URLs.
APIROUTER_PREFIX_RE = re.compile(
    r'APIRouter\s*\([^)]*?prefix\s*=\s*["\'](?P<prefix>/api/[^"\']+)["\']',
    re.DOTALL,
)

# Mongo collection access patterns we recognise
DB_COLLECTION_RE = re.compile(r'\bdb\.([a-zA-Z_][a-zA-Z0-9_]*)\b')

# Security dependency patterns
SECURITY_DEPS = ("require_admin", "require_master_admin", "require_user",
                 "require_master_admin_or_team_lead", "require_team_lead",
                 "require_staff", "require_manager")


def _detect_router_prefix(src: str) -> Optional[str]:
    """If the file declares `APIRouter(prefix="/api/...")`, return that prefix.

    Used to reconstruct full URL paths for routers whose endpoints use
    relative `@router.get("/x")` decorators (Wave 2B pattern).
    """
    m = APIROUTER_PREFIX_RE.search(src)
    if not m:
        return None
    return m.group("prefix").rstrip("/")


def _detect_router_auth(src: str) -> List[str]:
    """If the file declares `APIRouter(..., dependencies=[Depends(require_x)])`,
    return the list of security-dep names declared at router level.

    These dependencies apply to every endpoint inside the router and would
    otherwise be invisible to the per-endpoint body-window scan.
    """
    # Look at the APIRouter(...) block — restrict to the body window
    m = re.search(r'APIRouter\s*\([^)]*?dependencies\s*=\s*\[[^\]]*\]',
                  src, re.DOTALL)
    if not m:
        return []
    block = m.group(0)
    return [d for d in SECURITY_DEPS if d in block]


def scan_file(path: Path) -> List[Dict[str, Any]]:
    """Line-based scan: locate /api/admin/* decorators, then peek at the
    immediately-following function definition (next ~80 lines) for auth
    dependencies, collection accesses, and the function name.

    This deliberately avoids ast.get_source_segment, which is unreliable
    on the 25k-line server.py with multi-line decorator continuations.
    """
    src = path.read_text(encoding="utf-8", errors="ignore")
    lines = src.split("\n")
    endpoints: List[Dict[str, Any]] = []
    n = len(lines)
    router_prefix = _detect_router_prefix(src)
    router_auth = _detect_router_auth(src)

    for i, line in enumerate(lines):
        m = ROUTE_DECORATOR_RE.search(line)
        if not m:
            continue
        raw_path = m.group("path")
        mounter = m.group(1)

        # Reconstruct full URL for relative @router paths inside extracted
        # routers (Wave-2 pattern: APIRouter(prefix="/api/admin/x") + @router.get("/y")).
        # mounter is "fastapi_app" or any "*router" name (router, site_info_router, etc.).
        if mounter != "fastapi_app" and router_prefix and not raw_path.startswith("/api/"):
            route_path = router_prefix + raw_path
        else:
            route_path = raw_path

        if "/api/admin/" not in route_path:
            continue

        method = m.group(2).upper()

        sub = ADMIN_PREFIX_RE.search(route_path)
        sub_prefix = sub.group(1) if sub else "(none)"

        # Capture the decorator line + a window of follow-up source until
        # we hit the next @decorator OR the next module-level def at col 0.
        body_lines: List[str] = [line]
        func_name: Optional[str] = None
        j = i + 1
        while j < n and j < i + 200:
            cur = lines[j]
            # If we hit another decorator on a separate function — stop
            if cur.startswith("@") and j > i + 1 and func_name is not None:
                break
            # Capture function name on first def encountered
            if func_name is None:
                dm = re.match(r'^\s*async\s+def\s+(\w+)|^\s*def\s+(\w+)', cur)
                if dm:
                    func_name = dm.group(1) or dm.group(2)
            body_lines.append(cur)
            j += 1
        body_text = "\n".join(body_lines)

        # Security deps from the captured decorator+signature+body window
        sec_deps: List[str] = []
        for d in SECURITY_DEPS:
            if d in body_text:
                sec_deps.append(d)
        # Inherit router-level auth dependencies (Wave 2B pattern)
        for d in router_auth:
            if d not in sec_deps:
                sec_deps.append(d)

        # Collections accessed
        collections = sorted(set(DB_COLLECTION_RE.findall(body_text)))

        endpoints.append({
            "file": str(path.relative_to(BACKEND_DIR)),
            "line": i + 1,
            "method": method,
            "path": route_path,
            "sub_prefix": sub_prefix,
            "function": func_name or "(unknown)",
            "is_async": "async def" in body_text[:200],
            "auth": sec_deps,
            "collections": collections,
            "mounter": mounter,
        })
    return endpoints


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default="/tmp/admin_topology.json")
    parser.add_argument("--md-out",   default="/app/WAVE2_ADMIN_MAPPING.md")
    args = parser.parse_args()

    # Wave-1 + Wave-2 router locations.  app/routers/* is auto-discovered
    # so future Wave 2B extractions are picked up without script edits.
    targets = [
        BACKEND_DIR / "server.py",
        BACKEND_DIR / "notifications.py",
        BACKEND_DIR / "legal_workflow.py",
        BACKEND_DIR / "cabinet_financials.py",
        BACKEND_DIR / "payments_tracking.py",
        BACKEND_DIR / "financial_breakdown.py",
    ]
    routers_dir = BACKEND_DIR / "app" / "routers"
    if routers_dir.is_dir():
        for r in sorted(routers_dir.glob("*.py")):
            if r.name == "__init__.py":
                continue
            targets.append(r)

    all_endpoints: List[Dict[str, Any]] = []
    for t in targets:
        if not t.exists():
            continue
        all_endpoints.extend(scan_file(t))

    # ── Aggregations ────────────────────────────────────────────────
    by_subprefix = defaultdict(list)
    for e in all_endpoints:
        by_subprefix[e["sub_prefix"]].append(e)

    by_file = defaultdict(list)
    for e in all_endpoints:
        by_file[e["file"]].append(e)

    collection_to_endpoints = defaultdict(set)
    for e in all_endpoints:
        for c in e["collections"]:
            collection_to_endpoints[c].add(
                f"{e['method']} {e['path']}"
            )

    # Auth boundary distribution
    auth_dist = Counter()
    for e in all_endpoints:
        if not e["auth"]:
            auth_dist["(none / open)"] += 1
        else:
            auth_dist[" + ".join(sorted(e["auth"]))] += 1

    # ── JSON output ─────────────────────────────────────────────────
    Path(args.json_out).write_text(
        json.dumps(
            {
                "summary": {
                    "total_admin_endpoints": len(all_endpoints),
                    "sub_prefixes": len(by_subprefix),
                    "files_touched": len(by_file),
                    "unique_collections": len(collection_to_endpoints),
                },
                "by_subprefix": {
                    k: [dict(e) for e in v]
                    for k, v in sorted(by_subprefix.items())
                },
                "by_file": {
                    k: [dict(e) for e in v]
                    for k, v in sorted(by_file.items())
                },
                "collections": {
                    k: sorted(v) for k, v in collection_to_endpoints.items()
                },
                "auth_distribution": dict(auth_dist),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ── Markdown report ─────────────────────────────────────────────
    md: List[str] = []
    md.append("# Wave 2A — /api/admin/* Topology Mapping")
    md.append("")
    md.append("**Mode:** READ-ONLY analysis · NO refactoring · NO extraction")
    md.append("")
    md.append("**Purpose:** discover latent ownership of the `/api/admin/*` ")
    md.append("facade-domain before any Wave 2B extraction is attempted.")
    md.append("")
    md.append("> _admin is NOT a domain — it is a multi-domain umbrella surface._  ")
    md.append("> _A naive `admin_router.py` extraction would create a distributed monolith v2._  ")
    md.append("> _Sub-domains must be discovered by latent ownership, not by URL prefix._")
    md.append("")
    md.append("---")
    md.append("")

    # Summary
    md.append("## 1. Summary")
    md.append("")
    md.append(f"- **Total `/api/admin/*` endpoints:** {len(all_endpoints)}")
    md.append(f"- **Distinct sub-prefixes:** {len(by_subprefix)}")
    md.append(f"- **Files currently hosting admin endpoints:** {len(by_file)}")
    md.append(f"- **Unique Mongo collections touched:** {len(collection_to_endpoints)}")
    md.append("")

    # Wave 2B extraction progress
    server_count = sum(len(v) for k, v in by_file.items() if k == "server.py")
    wave2b_count = sum(len(v) for k, v in by_file.items()
                       if k.startswith("app/routers/admin_")
                       or k == "app/routers/content.py")
    wave1_count = sum(len(v) for k, v in by_file.items()
                      if k in ("notifications.py", "legal_workflow.py",
                               "cabinet_financials.py", "payments_tracking.py",
                               "financial_breakdown.py")
                      or (k.startswith("app/routers/")
                          and not k.startswith("app/routers/admin_")
                          and k != "app/routers/content.py"))
    total = len(all_endpoints)
    extracted = total - server_count
    pct = (extracted * 100 // total) if total else 0
    md.append("### Wave 2B extraction progress")
    md.append("")
    md.append(f"- **In `server.py` monolith:** {server_count} ({100 - pct}%)")
    md.append(f"- **In Wave 2B routers (`app/routers/admin_*.py`):** {wave2b_count}")
    md.append(f"- **In Wave 1 modules (legacy locations + `app/routers/`):** {wave1_count}")
    md.append(f"- **Total extracted from monolith:** {extracted} ({pct}%)")
    md.append("")

    # File heatmap
    md.append("## 2. File-location heatmap (where admin endpoints live today)")
    md.append("")
    md.append("| File | Count | Notes |")
    md.append("|------|-------|-------|")
    for f, eps in sorted(by_file.items(), key=lambda x: -len(x[1])):
        if f == "server.py":
            note = "monolith shell"
        elif f.startswith("app/routers/admin_"):
            note = "Wave 2B extracted router"
        elif f == "app/routers/content.py":
            note = "Wave 2B extracted router (Content cluster, Batch 7)"
        elif f.startswith("app/routers/"):
            note = "Wave 1 extracted router"
        else:
            note = "Wave 1 extracted module (legacy location)"
        md.append(f"| `{f}` | {len(eps)} | {note} |")
    md.append("")

    # Sub-prefix table
    md.append("## 3. Sub-prefix ownership map (latent sub-domains)")
    md.append("")
    md.append("Each row is a *candidate* sub-domain. Coupling, db collections")
    md.append("and auth-boundary columns hint whether the sub-prefix is")
    md.append("**cohesive** (= safe to extract) or **bleeds across boundaries**")
    md.append("(= needs decomposition before extraction).")
    md.append("")
    md.append("| Sub-prefix | Endpoints | Files | Collections | Auth boundary |")
    md.append("|-----------|----------:|-------|-------------|---------------|")
    for sub, eps in sorted(by_subprefix.items(), key=lambda x: -len(x[1])):
        files = sorted({e["file"] for e in eps})
        cols = sorted({c for e in eps for c in e["collections"]})
        auths = sorted({tuple(e["auth"]) for e in eps})
        auth_str = "<br>".join(
            " + ".join(a) if a else "(open)" for a in auths
        )
        md.append(
            f"| `/api/admin/{sub}/*` | {len(eps)} | "
            f"{', '.join('`'+f+'`' for f in files)} | "
            f"{', '.join('`'+c+'`' for c in cols[:6])}"
            f"{' …' if len(cols) > 6 else ''} | "
            f"{auth_str} |"
        )
    md.append("")

    # Auth distribution
    md.append("## 4. Auth boundary distribution")
    md.append("")
    md.append("| Required role(s) | # endpoints |")
    md.append("|------------------|-----------:|")
    for k, n in sorted(auth_dist.items(), key=lambda x: -x[1]):
        md.append(f"| `{k}` | {n} |")
    md.append("")

    # ── Sub-domain clustering via shared-collection graph ───────────
    # Two sub-prefixes belong to the same "natural domain" if they share
    # ≥1 collection. Find connected components in that graph.
    coll_to_subs_local: Dict[str, Set[str]] = defaultdict(set)
    for e in all_endpoints:
        for c in e["collections"]:
            coll_to_subs_local[c].add(e["sub_prefix"])

    # adjacency: sub → set(subs that share at least 1 collection)
    adj: Dict[str, Set[str]] = defaultdict(set)
    for c, subs in coll_to_subs_local.items():
        subs_list = list(subs)
        for i_, a in enumerate(subs_list):
            for b in subs_list[i_ + 1:]:
                adj[a].add(b)
                adj[b].add(a)

    # connected components (DFS)
    visited: Set[str] = set()
    clusters: List[Set[str]] = []
    all_subs_with_eps = set(by_subprefix.keys())
    for sub in all_subs_with_eps:
        if sub in visited:
            continue
        stack = [sub]
        comp: Set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            stack.extend(adj.get(cur, set()) - visited)
        clusters.append(comp)

    # Sort clusters by total endpoint count desc
    clusters.sort(
        key=lambda c: -sum(len(by_subprefix[s]) for s in c if s in by_subprefix)
    )

    md.append("## 5. Natural domain clusters (connected components via shared collections)")
    md.append("")
    md.append("Sub-prefixes that share ≥1 Mongo collection are connected in")
    md.append("the coupling graph. Connected components = **natural domain**")
    md.append("**clusters** that should be extracted *together* (or kept")
    md.append("together in `server.py`) — otherwise extraction creates a")
    md.append("distributed monolith.")
    md.append("")
    md.append("**Singletons** (clusters of size 1 with no shared collections)")
    md.append("are the easiest Wave 2B candidates — they own their entire data")
    md.append("footprint with zero coupling to the rest of admin.")
    md.append("")
    for ci, comp in enumerate(clusters, 1):
        total = sum(len(by_subprefix[s]) for s in comp if s in by_subprefix)
        comp_sorted = sorted(comp, key=lambda s: -len(by_subprefix.get(s, [])))
        shared = set()
        for s in comp:
            for e in by_subprefix.get(s, []):
                for c in e["collections"]:
                    if len(coll_to_subs_local[c]) > 1 and \
                       all(t in comp for t in coll_to_subs_local[c]):
                        shared.add(c)
        bridges = set()
        for s in comp:
            for e in by_subprefix.get(s, []):
                for c in e["collections"]:
                    others = coll_to_subs_local[c] - comp
                    if others:
                        bridges.add(c)
        size_label = "SINGLETON" if len(comp) == 1 else f"CLUSTER ({len(comp)} sub-prefixes)"
        md.append(f"### Cluster #{ci} — {size_label} · {total} endpoint(s)")
        md.append("")
        md.append(f"**Sub-prefixes:** {', '.join('`/api/admin/'+s+'/*`' for s in comp_sorted)}")
        md.append("")
        if shared:
            md.append(f"**Internally shared collections (cluster glue):** "
                      f"{', '.join('`'+c+'`' for c in sorted(shared))}")
            md.append("")
        if bridges:
            md.append(f"**Bridge collections (also used outside cluster — coupling risk):** "
                      f"{', '.join('`'+c+'`' for c in sorted(bridges))}")
            md.append("")
        if not shared and not bridges and len(comp) == 1:
            sub = next(iter(comp))
            own_cols = sorted({c for e in by_subprefix.get(sub, []) for c in e["collections"]})
            md.append(f"**Owns:** {', '.join('`'+c+'`' for c in own_cols) or '(no Mongo writes detected — likely service-only)'}")
            md.append("")
        md.append("")

    # Collection sharing
    md.append("## 6. Collection-sharing map (coupling indicator)")
    md.append("")
    md.append("Collections touched by **multiple** sub-prefixes signal")
    md.append("**cross-cutting coupling** and should NOT be the seam for")
    md.append("sub-domain extraction. Collections touched by a **single**")
    md.append("sub-prefix indicate **bounded ownership**.")
    md.append("")
    md.append("| Collection | # endpoints | Sub-prefixes that use it |")
    md.append("|-----------|------------:|--------------------------|")

    coll_to_subs: Dict[str, Set[str]] = defaultdict(set)
    for e in all_endpoints:
        for c in e["collections"]:
            coll_to_subs[c].add(e["sub_prefix"])

    for c, subs in sorted(coll_to_subs.items(),
                          key=lambda x: (-len(x[1]), -len(collection_to_endpoints[x[0]]))):
        n_eps = len(collection_to_endpoints[c])
        sub_list = ", ".join(f"`{s}`" for s in sorted(subs))
        marker = "⚠️ shared" if len(subs) > 1 else "✓ bounded"
        md.append(f"| `{c}` | {n_eps} | {marker} — {sub_list} |")
    md.append("")

    # Wave 2B extraction-readiness scorecard
    md.append("## 7. Wave 2B extraction-readiness scorecard")
    md.append("")
    md.append("**Heuristic:** a sub-prefix is *low-risk* for extraction if it")
    md.append("(a) has ≤ 1 file footprint, (b) does NOT share its top")
    md.append("collections with other sub-prefixes, (c) has a consistent auth")
    md.append("boundary.")
    md.append("")
    md.append("| Sub-prefix | Risk | Reason |")
    md.append("|-----------|------|--------|")
    for sub, eps in sorted(by_subprefix.items(), key=lambda x: -len(x[1])):
        files = {e["file"] for e in eps}
        sub_cols = {c for e in eps for c in e["collections"]}
        shared_cols = {c for c in sub_cols if len(coll_to_subs[c]) > 1}
        auths = {tuple(e["auth"]) for e in eps}
        problems = []
        if len(files) > 1:
            problems.append(f"split across {len(files)} files")
        if len(shared_cols) > 0:
            problems.append(f"shares {len(shared_cols)} collection(s) with other sub-prefixes")
        if len(auths) > 1:
            problems.append(f"inconsistent auth ({len(auths)} distinct boundaries)")
        if not problems:
            risk = "🟢 LOW"
            reason = "single file, bounded collections, consistent auth"
        elif len(problems) == 1:
            risk = "🟡 MED"
            reason = problems[0]
        else:
            risk = "🔴 HIGH"
            reason = "; ".join(problems)
        md.append(f"| `/api/admin/{sub}/*` ({len(eps)}) | {risk} | {reason} |")
    md.append("")

    # Endpoint inventory
    md.append("## 8. Full endpoint inventory (grouped by sub-prefix)")
    md.append("")
    md.append("<details><summary>Click to expand — full 1:1 inventory</summary>")
    md.append("")
    for sub, eps in sorted(by_subprefix.items()):
        md.append(f"### `/api/admin/{sub}/*` ({len(eps)} endpoints)")
        md.append("")
        md.append("| Method | Path | File:Line | Auth | Collections |")
        md.append("|--------|------|-----------|------|-------------|")
        for e in sorted(eps, key=lambda x: (x["file"], x["line"])):
            md.append(
                f"| {e['method']} | `{e['path']}` | "
                f"`{e['file']}:{e['line']}` | "
                f"{', '.join('`'+a+'`' for a in e['auth']) or '(open)'} | "
                f"{', '.join('`'+c+'`' for c in e['collections'][:5])}"
                f"{' …' if len(e['collections']) > 5 else ''} |"
            )
        md.append("")
    md.append("</details>")
    md.append("")

    # Recommended Wave 2A → 2B handoff
    md.append("## 9. Recommended next steps")
    md.append("")
    md.append("**Wave 2A (this report) is complete.** No extraction performed.")
    md.append("")
    md.append("Wave 2B candidates (in order of safety / expected ROI):")
    md.append("")
    md.append("1. **🟢-tier first** — extract sub-prefixes flagged LOW risk above.")
    md.append("   These are the *real* domains hiding in `/api/admin/*`.")
    md.append("2. **🟡-tier second** — sub-prefixes with one isolated issue;")
    md.append("   resolve coupling before extracting.")
    md.append("3. **🔴-tier last** — sub-prefixes with multiple cross-cutting")
    md.append("   problems; do NOT extract until coupling is reduced via")
    md.append("   *targeted* surgical refactors (separate roadmap).")
    md.append("")
    md.append("> Reminder: admin must NOT be unified under a single")
    md.append("> `admin_router.py`. The facade pattern is fine; the *content*")
    md.append("> must remain split by ownership.")
    md.append("")

    Path(args.md_out).write_text("\n".join(md), encoding="utf-8")

    # ── stdout digest ───────────────────────────────────────────────
    print(f"[admin_topology_map] scanned {len(targets)} files")
    print(f"[admin_topology_map] found {len(all_endpoints)} /api/admin/* endpoints")
    print(f"[admin_topology_map] {len(by_subprefix)} distinct sub-prefixes")
    print(f"[admin_topology_map] JSON → {args.json_out}")
    print(f"[admin_topology_map] MD   → {args.md_out}")
    print()
    print("Top 10 sub-prefixes by endpoint count:")
    for sub, eps in sorted(by_subprefix.items(), key=lambda x: -len(x[1]))[:10]:
        files = {e["file"] for e in eps}
        print(f"  /api/admin/{sub}/*  →  {len(eps):3d} eps in {len(files)} file(s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
