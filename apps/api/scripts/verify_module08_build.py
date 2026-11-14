import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure app package is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.link import Link

BASE_URL = "http://127.0.0.1:8000"
TOKEN_A = create_access_token({"sub": "admin@example.com", "principal_id": "tenant_mod8_alpha"})
TOKEN_B = create_access_token({"sub": "intruder@example.com", "principal_id": "tenant_mod8_beta"})

HEADERS_A = {"Authorization": f"Bearer {TOKEN_A}"}
HEADERS_B = {"Authorization": f"Bearer {TOKEN_B}"}

evidence_lines = []

def log(msg: str):
    print(msg)
    evidence_lines.append(msg)

def main():
    log("=== MODULE 08 BUILD VERIFICATION: SEARCH, DISCOVERY & PAGINATION ===")
    log(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # 1. Clean up test links for this tenant
    db: Session = SessionLocal()
    try:
        db.query(Link).filter(Link.created_by.in_(["tenant_mod8_alpha", "tenant_mod8_beta"])).delete()
        db.commit()
    finally:
        db.close()

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # Step 1: Create several links with tags
        log("\n--- Step 1: Seed Links with Tags for Tenant Alpha ---")
        links_to_create = [
            {"long_url": "https://docs.docker.com/get-started", "code": "docker-guide", "tags": ["devops", "containers"]},
            {"long_url": "https://kubernetes.io/docs/tutorials", "code": "k8s-tutorial", "tags": ["devops", "cloud"]},
            {"long_url": "https://fastapi.tiangolo.com/loves-search", "code": "fastapi-docs", "tags": ["python", "api"]},
            {"long_url": "https://pypi.org/project/celery", "code": "celery-pypi", "tags": ["python", "async"]},
        ]
        created_ids = []
        for l in links_to_create:
            r = client.post("/links", json=l, headers=HEADERS_A)
            assert r.status_code == 201, f"Failed to create link {l['code']}: {r.text}"
            data = r.json()
            created_ids.append(data["id"])
            log(f"Created link: {data['code']} -> {data['long_url']} (tags: {data['tags']})")

        # Step 2: Search by keyword matching URL substring
        log("\n--- Step 2: Search by Keyword Substring (q=kubernetes) ---")
        res_q = client.get("/links/search?q=kubernetes&page=1&page_size=10", headers=HEADERS_A)
        log(f"GET /links/search?q=kubernetes Status: {res_q.status_code}")
        data_q = res_q.json()
        log(f"Total matching: {data_q['total']}, Returned items: {len(data_q['items'])}")
        assert data_q["total"] == 1
        assert data_q["items"][0]["code"] == "k8s-tutorial"
        log("CONFIRMED: Keyword substring search accurately located 'k8s-tutorial'.")

        # Step 3: Search by tag
        log("\n--- Step 3: Filter by Tag (tag=devops) ---")
        res_tag = client.get("/links/search?tag=devops&page=1&page_size=10", headers=HEADERS_A)
        log(f"GET /links/search?tag=devops Status: {res_tag.status_code}")
        data_tag = res_tag.json()
        log(f"Total matching: {data_tag['total']}, Returned items: {len(data_tag['items'])}")
        assert data_tag["total"] == 2
        matched_codes = {item["code"] for item in data_tag["items"]}
        assert matched_codes == {"docker-guide", "k8s-tutorial"}
        log("CONFIRMED: Tag filtering correctly matched both 'docker-guide' and 'k8s-tutorial'.")

        # Step 4: Verify pagination metadata and 0-based offset calculation
        log("\n--- Step 4: Pagination Metadata & Offset Verification ---")
        res_p1 = client.get("/links/search?page=1&page_size=2&sort_by=code&order=asc", headers=HEADERS_A)
        data_p1 = res_p1.json()
        log(f"Page 1: items={[item['code'] for item in data_p1['items']]}, total={data_p1['total']}, total_pages={data_p1['total_pages']}")
        assert data_p1["page"] == 1
        assert data_p1["page_size"] == 2
        assert data_p1["total"] == 4
        assert data_p1["total_pages"] == 2

        res_p2 = client.get("/links/search?page=2&page_size=2&sort_by=code&order=asc", headers=HEADERS_A)
        data_p2 = res_p2.json()
        log(f"Page 2: items={[item['code'] for item in data_p2['items']]}")
        assert data_p2["page"] == 2
        assert len(data_p2["items"]) == 2

        # Verify disjoint pages
        p1_set = {item["code"] for item in data_p1["items"]}
        p2_set = {item["code"] for item in data_p2["items"]}
        assert p1_set.isdisjoint(p2_set), "Page 1 and Page 2 must not have overlapping records"
        log("CONFIRMED: Pagination correctly partitioned records across pages without off-by-one errors.")

        # Step 5: Verify page_size capping
        log("\n--- Step 5: Page Size Capping Verification ---")
        res_cap = client.get("/links/search?page=1&page_size=500", headers=HEADERS_A)
        data_cap = res_cap.json()
        log(f"Requested page_size=500 -> Received page_size: {data_cap['page_size']}")
        assert data_cap["page_size"] == 100, "page_size must be capped at 100"
        log("CONFIRMED: Unbounded queries neutralized by capping page_size to 100.")

        # Step 6: Verify tenant isolation in search
        log("\n--- Step 6: Tenant Isolation Verification ---")
        res_intruder = client.get("/links/search?q=docker", headers=HEADERS_B)
        data_intruder = res_intruder.json()
        log(f"Tenant Beta search for Tenant Alpha's 'docker' link: total={data_intruder['total']}")
        assert data_intruder["total"] == 0
        log("CONFIRMED: Cross-tenant search returns 0 results, strictly scoped to principal_id.")

        # Step 7: Verify allowlisted sort validation
        log("\n--- Step 7: Allowlist Sort Parameter Validation ---")
        res_bad_sort = client.get("/links/search?sort_by=password_hash;DROP%20TABLE;", headers=HEADERS_A)
        log(f"Invalid sort parameter status: {res_bad_sort.status_code}")
        assert res_bad_sort.status_code == 422
        log("CONFIRMED: Unallowlisted sort fields strictly rejected with HTTP 422.")

    log("\n=== ALL MODULE 08 BUILD ACCEPTANCE CRITERIA VERIFIED ===")

    # Write evidence file to repository root
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    evidence_dir = repo_root / "progress" / "evidence" / "module-08"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "build-evidence.txt"
    evidence_file.write_text("\n".join(evidence_lines), encoding="utf-8")
    log(f"Evidence successfully written to {evidence_file}")

if __name__ == "__main__":
    main()
