import os, requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("TOKEN", "demo123")
H = {"X-API-TOKEN": TOKEN}

def ping(method, url, **kw):
    r = requests.request(method, url, **kw)
    print(f"{method} {url} -> {r.status_code}")
    return r

# 1) List embryos
r = ping("GET", f"{BASE}/api/embryos", headers=H, timeout=5)
r.raise_for_status()
embryos = r.json()
assert isinstance(embryos, list) and embryos, "no embryos returned"
print("✓ /api/embryos returned", len(embryos), "embryos")

# 2) Detail for first embryo
eid = embryos[0]["embryo_id"]
r = ping("GET", f"{BASE}/api/embryos/{eid}", headers=H, timeout=5)
r.raise_for_status()
detail = r.json()
assert {"embryo_id","polygenic","monogenic","overall_score"} <= detail.keys()
print(f"✓ detail OK for embryo {eid}: overall={detail['overall_score']}")

# 3) Unauthorized should be 401
r = ping("GET", f"{BASE}/api/embryos", timeout=5)
assert r.status_code == 401, "expected 401 without token"
print("✓ unauthorized request correctly blocked (401)")

# 4) PDF endpoint
r = ping("GET", f"{BASE}/report/{eid}.pdf", timeout=20)
r.raise_for_status()
ct = (r.headers.get("content-type") or "").lower()
assert ct.startswith("application/pdf"), f"unexpected content-type: {ct}"
open(f"_tmp_report_{eid}.pdf","wb").write(r.content)
print(f"✓ PDF downloaded to _tmp_report_{eid}.pdf")

print("\nALL SMOKE TESTS PASSED ✅")
