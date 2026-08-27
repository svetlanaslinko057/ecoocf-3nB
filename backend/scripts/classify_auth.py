"""Classify every route's auth flavour by scanning source files.

For each @router.<method>("/path") decorator, inspect the function body until the
next decorator/def and detect:
  - customer auth   : require_customer / _resolve_bearer
  - staff dep guard : Depends(require_user|require_admin|require_master_admin|require_manager_or_admin)
  - extension hmac  : require_extension_hmac
Outputs JSON groups.
"""
import json
import re
import glob

FILES = ["/app/backend/server.py"] + sorted(glob.glob("/app/backend/app/routers/*.py"))

DEC = re.compile(r'@(?:fastapi_app|router|app)\.(get|post|put|patch|delete)\(\s*[fr]?["\']([^"\']+)["\']')
DEFLINE = re.compile(r'^\s*(async\s+def|def)\s')

results = {"customer": set(), "staff_dep": set(), "extension": set(), "none": set()}
path_methods = {}

for f in FILES:
    lines = open(f, encoding="utf-8", errors="ignore").read().splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = DEC.search(lines[i])
        if not m:
            i += 1
            continue
        method, path = m.group(1).upper(), m.group(2)
        if not path.startswith("/api") and not path.startswith("/"):
            i += 1
            continue
        # collect decorator block + function body until next top-level def's end (next decorator or dedent def)
        j = i + 1
        # skip stacked decorators
        body = []
        # find the def line
        while j < n and not DEFLINE.match(lines[j]):
            body.append(lines[j])
            j += 1
        # capture body until next decorator at column 0/4 or next 'async def'/'def' at same indent
        k = j + 1
        while k < n:
            if DEC.search(lines[k]):
                break
            if re.match(r'^(async def|def|class)\s', lines[k]):
                break
            body.append(lines[k])
            k += 1
        blob = "\n".join(body)
        key = (method, path)
        path_methods.setdefault(path, set()).add(method)
        if "require_customer" in blob or "_resolve_bearer" in blob:
            results["customer"].add(path)
        elif "require_extension_hmac" in blob:
            results["extension"].add(path)
        elif re.search(r'Depends\(\s*(require_user|require_admin|require_master_admin|require_manager_or_admin|get_current_user)\s*\)', blob):
            results["staff_dep"].add(path)
        else:
            results["none"].add(path)
        i = j

# customer wins over none
results["none"] -= results["customer"]
results["none"] -= results["staff_dep"]
results["none"] -= results["extension"]

out = {k: sorted(v) for k, v in results.items()}
json.dump(out, open("/tmp/auth_classes.json", "w"))
for k in ("customer", "extension", "staff_dep", "none"):
    print(f"{k}: {len(out[k])}")
print("\n=== CUSTOMER routes ===")
for p in out["customer"]:
    print(" ", p)
