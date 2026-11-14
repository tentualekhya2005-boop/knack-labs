import json
from pathlib import Path
import httpx

base_url = "http://127.0.0.1:8000"
evidence = []

# 1. Health check
res = httpx.get(f"{base_url}/health")
evidence.append(f"=== Health Check ===\nStatus: {res.status_code}\nBody: {res.text}")
print(f"Health check: {res.status_code} {res.text}")

# 2. Create link
create_payload = {"long_url": "https://example.com"}
res = httpx.post(f"{base_url}/links", json=create_payload)
evidence.append(f"=== Create Link ===\nStatus: {res.status_code}\nBody: {res.text}")
print(f"Create link: {res.status_code} {res.text}")
data = res.json()
code = data["code"]

# 3. Redirect /r/{code}
res = httpx.get(f"{base_url}/r/{code}", follow_redirects=False)
evidence.append(f"=== Redirect /r/{code} ===\nStatus: {res.status_code}\nLocation: {res.headers.get('location')}")
print(f"Redirect /r/{code}: {res.status_code} {res.headers.get('location')}")

# 4. Abuse checks
abuse_cases = [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1) ",
    "data:text/html,<svg/onload=alert(1)>",
    "//evil.example.com",
    "http:%2f%2fevil.example.com",
    "http%3A%2F%2Fevil.example.com",
    "http:\\\\evil.example.com",
    "https://good.com@evil.example.com",
    "https://example.com\n",
]

for bad_url in abuse_cases:
    res = httpx.post(f"{base_url}/links", json={"long_url": bad_url})
    evidence.append(f"=== Abuse Check: {bad_url!r} ===\nStatus: {res.status_code}\nBody: {res.text}")
    print(f"Abuse [{bad_url!r}]: Status {res.status_code} (detail: {res.json().get('detail')})")

out_dir = Path("progress/evidence/module-03")
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / "build-evidence.txt"
out_file.write_text("\n\n".join(evidence), encoding="utf-8")
print(f"Evidence successfully written to {out_file}")

