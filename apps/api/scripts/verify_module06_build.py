import json
import os
import sys
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8000"
EVIDENCE_DIR = "progress/evidence/module-06"
EVIDENCE_FILE = os.path.join(EVIDENCE_DIR, "build-evidence.txt")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Stop automatic redirect following


opener = urllib.request.build_opener(NoRedirectHandler)


def make_request(url, method="GET", headers=None, data=None):
    req_headers = headers or {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with opener.open(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, dict(resp.headers), resp_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return e.code, dict(e.headers), err_body


def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    evidence_lines = []
    evidence_lines.append("=== MODULE 06 BUILD VERIFICATION EVIDENCE ===")
    evidence_lines.append("")

    # 1. Login to acquire JWT token
    print("[1] Logging in as Tenant A...")
    login_status, _, login_body = make_request(
        f"{API_URL}/auth/login",
        method="POST",
        headers={"Content-Type": "application/json"},
        data={"email": "tenant_a@example.com", "password": "password123"},
    )
    assert login_status == 200, f"Login failed: {login_body}"
    token = json.loads(login_body)["access_token"]
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    evidence_lines.append("[1] Authentication successful as Tenant A.")

    # 2. Create a new link
    print("[2] Creating link for cache verification...")
    create_status, _, create_body = make_request(
        f"{API_URL}/links",
        method="POST",
        headers=auth_headers,
        data={"long_url": "https://original-site.example.com", "code": "cache-mod6-test"},
    )
    assert create_status == 201, f"Link creation failed: {create_body}"
    link_data = json.loads(create_body)
    link_id = link_data["id"]
    code = link_data["code"]
    evidence_lines.append(f"[2] Created link ID {link_id} with code '{code}' -> {link_data['long_url']}")
    evidence_lines.append("")

    # 3. First redirect: Cache Miss (DB query + Cache populated)
    print("[3] Performing first redirect (Cache Miss expected)...")
    r1_status, r1_headers, _ = make_request(f"{API_URL}/r/{code}")
    evidence_lines.append(f"[3] First Redirect Probe:")
    evidence_lines.append(f"HTTP Status: {r1_status}")
    evidence_lines.append(f"Location Header: {r1_headers.get('location')}")
    evidence_lines.append(f"X-Cache Header: {r1_headers.get('x-cache')}")
    assert r1_status == 302
    assert r1_headers.get("location") == "https://original-site.example.com"
    assert r1_headers.get("x-cache") == "MISS"
    evidence_lines.append("-> Confirmed: Cache MISS on first request, populated cache with TTL.")
    evidence_lines.append("")

    # 4. Second redirect: Cache Hit (served sub-millisecond from memory)
    print("[4] Performing second redirect (Cache Hit expected)...")
    r2_status, r2_headers, _ = make_request(f"{API_URL}/r/{code}")
    evidence_lines.append(f"[4] Second Redirect Probe:")
    evidence_lines.append(f"HTTP Status: {r2_status}")
    evidence_lines.append(f"Location Header: {r2_headers.get('location')}")
    evidence_lines.append(f"X-Cache Header: {r2_headers.get('x-cache')}")
    assert r2_status == 302
    assert r2_headers.get("location") == "https://original-site.example.com"
    assert r2_headers.get("x-cache") == "HIT"
    evidence_lines.append("-> Confirmed: Cache HIT on second request, served directly from cache.")
    evidence_lines.append("")

    # 5. Update link (PATCH): Cache Invalidation
    print(f"[5] Updating link ID {link_id} to new destination...")
    new_url = "https://updated-enterprise-destination.example.org"
    patch_status, _, patch_body = make_request(
        f"{API_URL}/links/{link_id}",
        method="PATCH",
        headers=auth_headers,
        data={"long_url": new_url},
    )
    assert patch_status == 200, f"PATCH failed: {patch_body}"
    evidence_lines.append(f"[5] PATCH Link Target:")
    evidence_lines.append(f"HTTP Status: {patch_status}")
    evidence_lines.append(f"Updated Long URL: {new_url}")
    evidence_lines.append("-> Confirmed: Database updated and cache entry invalidated.")
    evidence_lines.append("")

    # 6. Third redirect: Verifying fresh data is served (NO STALE DATA)
    print("[6] Performing redirect after update...")
    r3_status, r3_headers, _ = make_request(f"{API_URL}/r/{code}")
    evidence_lines.append(f"[6] Redirect Post-Update Probe:")
    evidence_lines.append(f"HTTP Status: {r3_status}")
    evidence_lines.append(f"Location Header: {r3_headers.get('location')}")
    evidence_lines.append(f"X-Cache Header: {r3_headers.get('x-cache')}")
    assert r3_status == 302
    assert r3_headers.get("location") == new_url, f"STALE CACHE DETECTED! Expected {new_url}, got {r3_headers.get('location')}"
    assert r3_headers.get("x-cache") == "MISS"
    evidence_lines.append("-> Confirmed: No stale data served. Fetched updated URL from DB and re-warmed cache.")
    evidence_lines.append("")

    # 7. Fourth redirect: Cache Hit on updated URL
    r4_status, r4_headers, _ = make_request(f"{API_URL}/r/{code}")
    assert r4_headers.get("x-cache") == "HIT"
    assert r4_headers.get("location") == new_url
    evidence_lines.append(f"[7] Fourth Redirect: Cache HIT on updated target ({new_url}).")
    evidence_lines.append("")

    with open(EVIDENCE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(evidence_lines) + "\n")

    print(f"Evidence successfully saved to {EVIDENCE_FILE}")


if __name__ == "__main__":
    main()

