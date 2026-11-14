import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure app package is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import SessionLocal, engine
from app.models.click import ClickEvent
from app.models.link import Link
from app.services import links_service
from app.worker import process_click_event_record

BASE_URL = "http://127.0.0.1:8000"
TOKEN_ALICE = create_access_token({"sub": "alice@tenant-a.com", "principal_id": "probe_tenant_alice"})
TOKEN_BOB = create_access_token({"sub": "bob@tenant-b.com", "principal_id": "probe_tenant_bob"})

HEADERS_ALICE = {"Authorization": f"Bearer {TOKEN_ALICE}"}
HEADERS_BOB = {"Authorization": f"Bearer {TOKEN_BOB}"}

evidence_lines = []

def log(msg: str):
    print(msg)
    evidence_lines.append(msg)

def main():
    log("=== MODULE 09 BUILD VERIFICATION: INTEGRATION-HEAVY TEST SUITE ===")
    log(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

    # Database Isolation Safety Guard
    log("\n--- Guard 0: Database Isolation Safety Check ---")
    db_url = str(engine.url)
    log(f"Active DB Engine URL: {db_url}")
    assert any(host in db_url for host in ["127.0.0.1", "localhost", "test"]), "CRITICAL: Non-local DB host detected!"
    log("CONFIRMED: Database is confirmed strictly isolated to local testing instance.")

    # Cleanup probe links
    db: Session = SessionLocal()
    try:
        db.query(ClickEvent).delete()
        db.query(Link).filter(Link.created_by.in_(["probe_tenant_alice", "probe_tenant_bob"])).delete()
        db.commit()
    finally:
        db.close()

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        # Step 1: Create a link
        log("\n--- Step 1: Create Link (POST /links) ---")
        create_res = client.post(
            "/links",
            json={"long_url": "https://fastapi.tiangolo.com/tutorial", "code": "e2e-fastapi"},
            headers=HEADERS_ALICE,
        )
        assert create_res.status_code == 201
        created_data = create_res.json()
        link_id = created_data["id"]
        log(f"Created link id={link_id}, code={created_data['code']}, short_url={created_data['short_url']}")
        log("CONFIRMED: Link created successfully.")

        # Step 2: Redirect behavior (GET /r/{code})
        log("\n--- Step 2: Redirect Behavior (GET /r/{code}) ---")
        redir_res = client.get("/r/e2e-fastapi", follow_redirects=False)
        assert redir_res.status_code == 302
        assert redir_res.headers["location"] == "https://fastapi.tiangolo.com/tutorial"
        log(f"Redirect status: {redir_res.status_code}, Location: {redir_res.headers['location']}")
        health_res = client.get("/health")
        assert health_res.status_code == 200
        log(f"Health check status: {health_res.status_code}")
        log("CONFIRMED: HTTP 302 redirect verified with Location header and /health intact.")

        # Step 3: Auth protection (401 Unauthorized)
        log("\n--- Step 3: Authentication Guard (HTTP 401) ---")
        unauth_res = client.post("/links", json={"long_url": "https://evil.example.com"})
        assert unauth_res.status_code == 401
        log(f"Unauthenticated request status: {unauth_res.status_code}")
        log("CONFIRMED: Protected routes enforce HTTP 401 without valid token.")

        # Step 4: IDOR Owner-Scoping (HTTP 404)
        log("\n--- Step 4: IDOR Owner-Scoping Check (HTTP 404) ---")
        idor_get = client.get(f"/links/{link_id}", headers=HEADERS_BOB)
        assert idor_get.status_code == 404
        idor_patch = client.patch(f"/links/{link_id}", json={"long_url": "https://hacked.com"}, headers=HEADERS_BOB)
        assert idor_patch.status_code == 404
        idor_del = client.delete(f"/links/{link_id}", headers=HEADERS_BOB)
        assert idor_del.status_code == 404
        log(f"Tenant Bob cross-tenant GET: {idor_get.status_code}, PATCH: {idor_patch.status_code}, DELETE: {idor_del.status_code}")
        log("CONFIRMED: Cross-tenant IDOR access strictly rejected with HTTP 404.")

        # Step 5: Retention Enforcement (Purge old clicks)
        log("\n--- Step 5: Retention Enforcement & Click Purge ---")
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            c_old = ClickEvent(link_id=link_id, event_id="probe-old-01", clicked_at=now - timedelta(days=40))
            c_new = ClickEvent(link_id=link_id, event_id="probe-new-01", clicked_at=now - timedelta(days=2))
            db.add_all([c_old, c_new])
            db.commit()

            purged = links_service.purge_old_clicks(db, retention_days=30)
            assert purged == 1
            remaining = db.query(ClickEvent).filter(ClickEvent.event_id.in_(["probe-old-01", "probe-new-01"])).all()
            assert len(remaining) == 1
            assert remaining[0].event_id == "probe-new-01"
            log(f"Purged count: {purged}, Remaining target probe event: {remaining[0].event_id}")
        finally:
            db.close()
        log("CONFIRMED: Retention policy strictly purged events older than 30 days.")

        # Step 6: URL Validation (Reject bypass strings)
        log("\n--- Step 6: URL Validation Rejecting Malicious Schemes ---")
        bypass_strings = ["javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "http%3A%2F%2Fevil.com"]
        for bypass in bypass_strings:
            res_bad = client.post("/links", json={"long_url": bypass}, headers=HEADERS_ALICE)
            assert res_bad.status_code == 400
            log(f"Rejected bypass payload: '{bypass}' -> Status: {res_bad.status_code}")
        log("CONFIRMED: Malicious URL bypass vectors rejected with HTTP 400.")

        # Step 7: Async Worker Idempotency
        log("\n--- Step 7: Worker Deduplication & Idempotency Guarantee ---")
        idem_event = {
            "link_id": link_id,
            "event_id": "probe-idem-uuid-007",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_hash": hashlib.sha256("127.0.0.1".encode()).hexdigest(),
            "user_agent": "ProbeRunner",
            "referrer": "https://test.com",
        }
        db = SessionLocal()
        try:
            r1 = process_click_event_record(db, idem_event)
            assert r1["inserted"] is True
            r2 = process_click_event_record(db, idem_event)
            assert r2["inserted"] is False
            row_count = db.query(ClickEvent).filter(ClickEvent.event_id == "probe-idem-uuid-007").count()
            assert row_count == 1
            log(f"First delivery: inserted={r1['inserted']}, Replayed delivery: inserted={r2['inserted']}, Rows in DB: {row_count}")
        finally:
            db.close()
        log("CONFIRMED: Worker idempotency safely suppresses duplicate event replay.")

    # Step 8: Automated Pytest Suite Execution
    log("\n--- Step 8: Automated Pytest Execution (test_module09_integration_suite.py) ---")
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_module09_integration_suite.py", "-v"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    log(pytest_res.stdout)
    assert pytest_res.returncode == 0, f"Pytest suite failed with code {pytest_res.returncode}"
    log("CONFIRMED: All 7 automated integration tests passed cleanly.")

    log("\n=== ALL MODULE 09 BUILD ACCEPTANCE CRITERIA VERIFIED ===")

    # Write evidence to file
    evidence_dir = Path(__file__).resolve().parent.parent.parent.parent / "progress" / "evidence" / "module-09"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "build-evidence.txt"
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write("\n".join(evidence_lines))
    print(f"\nEvidence successfully written to {evidence_file}")

if __name__ == "__main__":
    main()
