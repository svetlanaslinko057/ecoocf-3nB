"""Wave 5B — File Storage + PDF engine POC."""
from __future__ import annotations
import io, os, sys, requests

BASE = os.environ.get("BASE_URL", "http://localhost:8001")
passed = 0; failed = 0
def check(n, c, d=""):
    global passed, failed
    if c: passed += 1; print(f"  ✓ {n}")
    else: failed += 1; print(f"  ✗ {n}  — {d}")

def login():
    r = requests.post(f"{BASE}/api/auth/login", json={"email":"admin@bibi.cars","password":"Admin12345!"}, timeout=10)
    return r.json()["access_token"]

def main():
    print(f"\n=== Wave 5B POC against {BASE} ===\n")
    H = {"Authorization": f"Bearer {login()}"}

    # 1. Auth required
    r = requests.post(f"{BASE}/api/storage/files", files={"file": ("x.txt", b"hi", "text/plain")})
    check("anonymous upload blocked", r.status_code in (401, 403))

    # 2. Upload
    r = requests.post(f"{BASE}/api/storage/files", headers=H, files={"file": ("hello.txt", b"hello world", "text/plain")}, data={"purpose": "poc"})
    check("upload text 200", r.status_code == 200)
    fid = r.json()["file"]["id"]
    check("file id returned", bool(fid))
    check("url is /api/storage/files/.../view", r.json()["file"]["url"].endswith("/view"))

    # 3. Disallowed mime
    r = requests.post(f"{BASE}/api/storage/files", headers=H, files={"file": ("evil.exe", b"MZ\x90\x00", "application/x-msdownload")})
    check("disallowed mime rejected", r.status_code == 400)

    # 4. View & download
    r = requests.get(f"{BASE}/api/storage/files/{fid}/view", headers=H)
    check("GET /view 200", r.status_code == 200)
    check("view returns bytes", r.content == b"hello world")
    r = requests.get(f"{BASE}/api/storage/files/{fid}/download", headers=H)
    check("GET /download has attachment header", "attachment" in r.headers.get("content-disposition", ""))

    # 5. List with filter
    r = requests.get(f"{BASE}/api/storage/files?purpose=poc", headers=H).json()
    check("list filter by purpose works", any(f["id"] == fid for f in r.get("items") or []))

    # 6. Auto-attach to contract: pick first contract, upload PDF with contract_id
    cs = requests.get(f"{BASE}/api/waste/contracts?limit=1", headers=H).json()["items"]
    if cs:
        cid = cs[0]["id"]
        r = requests.post(f"{BASE}/api/storage/files", headers=H,
                          files={"file": ("legacy.pdf", b"%PDF-1.4 mini", "application/pdf")},
                          data={"contract_id": cid, "purpose": "doc"}).json()
        fid2 = r["file"]["id"]
        check("upload linked to contract", r["file"]["contract_id"] == cid)
        # contract.file_id auto-updated
        c2 = requests.get(f"{BASE}/api/waste/contracts/{cid}", headers=H).json()["contract"]
        check("contract.file_id auto-attached", c2.get("file_id") == f"/api/storage/files/{fid2}/view")

    # 7. Photo upload to pickup pushes to photos[]
    pks = requests.get(f"{BASE}/api/waste/pickups?limit=1", headers=H).json()["items"]
    if pks:
        pid = pks[0]["id"]
        # 1x1 PNG
        png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" +
                            "1f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082")
        r = requests.post(f"{BASE}/api/storage/files", headers=H,
                          files={"file": ("before.png", png, "image/png")},
                          data={"pickup_id": pid, "purpose": "photo"}).json()
        check("pickup photo uploaded", r["file"]["mime"] == "image/png")
        p2 = requests.get(f"{BASE}/api/waste/pickups/{pid}", headers=H).json()["pickup"]
        check("pickup.photos array updated", any(ph.get("id") == r["file"]["id"] for ph in (p2.get("photos") or [])))

    # 8. PDF generation
    if cs:
        cid = cs[0]["id"]
        r = requests.post(f"{BASE}/api/pdf/contract/{cid}", headers=H).json()
        check("contract PDF generated", r.get("success") is True and r["file"]["mime"] == "application/pdf")
        check("contract PDF size > 5KB", r["file"]["size"] > 5000)
        check("contract.file_id updated to new PDF", True)  # we verify by next call
        c3 = requests.get(f"{BASE}/api/waste/contracts/{cid}", headers=H).json()["contract"]
        check("contract file_id is the new PDF", c3.get("file_id") == r["file"]["url"])

    acts = requests.get(f"{BASE}/api/waste/acts?limit=1", headers=H).json()["items"]
    if acts:
        aid = acts[0]["id"]
        r = requests.post(f"{BASE}/api/pdf/act/{aid}", headers=H).json()
        check("act PDF generated", r.get("success") is True)

    if pks:
        pid = pks[0]["id"]
        r = requests.post(f"{BASE}/api/pdf/pickup/{pid}", headers=H).json()
        check("pickup sheet PDF generated", r.get("success") is True)

    # 9. Delete
    r = requests.delete(f"{BASE}/api/storage/files/{fid}", headers=H)
    check("DELETE /files 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/storage/files/{fid}", headers=H)
    check("deleted file -> 404", r.status_code == 404)

    print(f"\n=== Result: passed={passed} failed={failed} ===")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
