"""Generate ACCESS_CONTROL_REPORT.md from the route inventory + live probing.

- Classifies every route by its strongest guard.
- For UNGUARDED GET routes without path params, probes UNAUTHENTICATED and
  records HTTP status + a data-leak heuristic (non-trivial body on 200).
"""
import json
import os
import re

import httpx

BU = os.environ.get("AUDIT_BASE_URL", "http://localhost:8001")
ROUTES = json.load(open("/tmp/routes_clean.json"))

PUBLIC_OK = re.compile(
    r"^/api/(auth/(google-client-id|password-policy)|customer-auth/(register|login|verify-email|resend-email-code|google)|"
    r"health|healthz|system/health|stripe/webhook|stripe/public-config|contracts/view|public/|"
    r"calculator/(config|ports|quote)|vin/search|tracker|site-activity|extension/(download|info)|legal/(catalog|deal-stages))"
)


def strongest_guard(g):
    for k in ("require_master_admin", "require_admin", "require_manager_or_admin",
              "require_user", "get_current_user", "require_extension_hmac"):
        if k in g:
            return k
    if g in (["optional_user"], ["get_current_user_optional"]):
        return "optional"
    return "UNGUARDED"


def probe(path):
    try:
        r = httpx.get(BU + path, timeout=12.0)
        body = r.text or ""
        leak = False
        if r.status_code == 200:
            # heuristic: non-empty data payloads
            stripped = body.strip()
            empty_markers = ('{"success":true,"data":[]}', '[]', '{}', '{"alerts":[]}',
                             '{"orders":[]}', '{"data":[]}', '{"total":0,"online":0,"offline":0,"clients":[]}')
            leak = bool(stripped) and stripped not in empty_markers and len(stripped) > 25
        return r.status_code, len(body), leak
    except Exception as e:
        return f"ERR:{type(e).__name__}", 0, False


guard_rows = {}
for r in ROUTES:
    g = strongest_guard(r["guards"])
    guard_rows.setdefault(g, []).append(r)

# Probe unguarded GET routes without path params
probe_results = {}
for r in ROUTES:
    if strongest_guard(r["guards"]) == "UNGUARDED" and "GET" in r["methods"] and "{" not in r["path"]:
        probe_results[r["path"]] = probe(r["path"])

lines = []
lines.append("# BIBI Cars — ACCESS CONTROL REPORT")
lines.append("")
lines.append("> PHASE SECURITY · Wave S1 · Stage 2 — every route classified by guard; unguarded GET routes probed UNAUTHENTICATED on preview.")
lines.append(f"> Total routes audited: **{len(ROUTES)}**")
lines.append("")
lines.append("## Guard distribution")
lines.append("")
lines.append("| Guard | Routes |")
lines.append("|---|---:|")
for g in sorted(guard_rows, key=lambda k: -len(guard_rows[k])):
    lines.append(f"| `{g}` | {len(guard_rows[g])} |")
lines.append("")

# Confirmed leaks
leaks = [(p, v) for p, v in probe_results.items() if v[2]]
lines.append(f"## 🔴 Unauthenticated data exposure — CONFIRMED ({len(leaks)} routes returned non-trivial data with NO token)")
lines.append("")
lines.append("| Status | Bytes | Endpoint |")
lines.append("|---|---:|---|")
for p, (code, blen, leak) in sorted(leaks):
    lines.append(f"| {code} | {blen} | `{p}` |")
lines.append("")

# Open but empty (manual-auth or empty-without-token)
open_empty = [(p, v) for p, v in probe_results.items() if not v[2] and str(v[0]) == "200"]
lines.append(f"## 🟠 Unguarded but returned empty/trivial unauthenticated ({len(open_empty)}) — verify ownership scoping / manual auth")
lines.append("")
lines.append("| Status | Endpoint |")
lines.append("|---|---|")
for p, (code, blen, leak) in sorted(open_empty):
    lines.append(f"| {code} | `{p}` |")
lines.append("")

# Rejected (good — manual auth working)
rejected = [(p, v) for p, v in probe_results.items() if str(v[0]) in ("401", "403")]
lines.append(f"## ✅ Unguarded routes that correctly rejected unauthenticated ({len(rejected)}) — manual auth present")
lines.append("")
for p, (code, blen, leak) in sorted(rejected):
    lines.append(f"- {code} `{p}`")
lines.append("")

# Unguarded with path params (need manual review)
unguarded_param = [r for r in ROUTES if strongest_guard(r["guards"]) == "UNGUARDED" and "{" in r["path"]]
lines.append(f"## ⚠️ Unguarded routes WITH path params — manual IDOR review required ({len(unguarded_param)})")
lines.append("")
for r in sorted(unguarded_param, key=lambda x: x["path"]):
    lines.append(f"- {','.join(r['methods'])} `{r['path']}`")
lines.append("")

# Full guarded inventory (compact)
lines.append("## Guarded route inventory (by guard)")
for g in ("require_master_admin", "require_admin", "require_manager_or_admin", "require_user", "require_extension_hmac", "optional"):
    rs = guard_rows.get(g, [])
    if not rs:
        continue
    lines.append(f"\n<details><summary><b>{g}</b> ({len(rs)})</summary>\n")
    for r in sorted(rs, key=lambda x: x["path"]):
        lines.append(f"- {','.join(r['methods'])} `{r['path']}`")
    lines.append("\n</details>")
lines.append("")

open("/app/docs/security/ACCESS_CONTROL_REPORT.md", "w").write("\n".join(lines))
print("WROTE /app/docs/security/ACCESS_CONTROL_REPORT.md")
print("confirmed leaks:", len(leaks))
print("open-empty:", len(open_empty))
print("rejected(manual-auth):", len(rejected))
print("unguarded-with-params:", len(unguarded_param))
print()
print("=== CONFIRMED LEAK PATHS ===")
for p, v in sorted(leaks):
    print(f"  {v[0]}  {p}")
