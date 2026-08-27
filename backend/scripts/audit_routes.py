"""Security audit: introspect every FastAPI route + its auth dependencies.

Outputs JSON to stdout:
  [{path, methods, name, guards:[...], has_auth, public_candidate}, ...]

`guards` lists the security dependency callables wired into each route
(require_user / require_admin / require_master_admin / require_manager_or_admin /
get_current_user_optional / require_extension_hmac / verify_* etc.).
"""
import json
import sys

sys.path.insert(0, "/app/backend")

# Import the assembled app WITHOUT starting uvicorn / startup workers.
from server import fastapi_app  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

AUTH_DEP_NAMES = {
    "require_user", "get_current_user", "require_admin", "require_master_admin",
    "require_manager_or_admin", "optional_user", "get_current_user_optional",
    "require_extension_hmac", "require_staff", "_resolve_bearer",
}


def collect_dep_names(dependant, acc):
    call = getattr(dependant, "call", None)
    if call is not None:
        acc.add(getattr(call, "__name__", str(call)))
    for sub in getattr(dependant, "dependencies", []) or []:
        collect_dep_names(sub, acc)


rows = []
for route in fastapi_app.routes:
    if not isinstance(route, APIRoute):
        continue
    names = set()
    try:
        collect_dep_names(route.dependant, names)
    except Exception:
        pass
    guards = sorted(n for n in names if n in AUTH_DEP_NAMES)
    has_auth = bool(guards) and guards != ["optional_user"] and guards != ["get_current_user_optional"]
    rows.append({
        "path": route.path,
        "methods": sorted(m for m in route.methods if m not in ("HEAD", "OPTIONS")),
        "name": route.name,
        "guards": guards,
        "has_auth": has_auth,
    })

rows.sort(key=lambda r: r["path"])
print(json.dumps(rows))
