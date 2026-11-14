import hashlib
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.cache import cache_service
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.click import ClickEvent
from app.models.link import Link
from app.services import links_service
from app.worker import process_click_event_record

client = TestClient(app)

TENANT_ALICE_TOKEN = create_access_token({"sub": "alice@tenant-a.com", "principal_id": "tenant_alice"})
TENANT_BOB_TOKEN = create_access_token({"sub": "bob@tenant-b.com", "principal_id": "tenant_bob"})

AUTH_ALICE = {"Authorization": f"Bearer {TENANT_ALICE_TOKEN}"}
AUTH_BOB = {"Authorization": f"Bearer {TENANT_BOB_TOKEN}"}


@pytest.fixture(autouse=True)
def isolated_cleanup():
    """Ensure database & cache are completely isolated and clean for each test."""
    # Database Safety Guard: Verify test runs against local development/test instance
    db_url_str = str(engine.url)
    assert any(host in db_url_str for host in ["127.0.0.1", "localhost", "test"]), (
        f"CRITICAL SAFETY ABORT: Tests attempted against non-local host: {db_url_str}"
    )

    limiter.reset()
    cache_service.reset_stats()
    db: Session = SessionLocal()
    try:
        db.query(ClickEvent).delete()
        db.query(Link).delete()
        db.commit()
    finally:
        db.close()

    yield

    limiter.reset()
    cache_service.reset_stats()
    db = SessionLocal()
    try:
        db.query(ClickEvent).delete()
        db.query(Link).delete()
        db.commit()
    finally:
        db.close()


def test_1_create_link():
    """Test 1: Create a link via authenticated POST /links."""
    res = client.post(
        "/links",
        json={"long_url": "https://fastapi.tiangolo.com", "code": "fastapi-mod9"},
        headers=AUTH_ALICE,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "fastapi-mod9"
    assert data["long_url"] == "https://fastapi.tiangolo.com"
    assert "/r/fastapi-mod9" in data["short_url"]
    assert "id" in data
    assert "created_at" in data


def test_2_redirect_prefix_r():
    """Test 2: Redirect GET /r/{code} returns HTTP 302 and correct Location header."""
    # 1. Create a link
    res_create = client.post(
        "/links",
        json={"long_url": "https://docs.python.org/3/library/unittest.html", "code": "py-unit"},
        headers=AUTH_ALICE,
    )
    assert res_create.status_code == 201

    # 2. Execute redirect request (do not follow redirect automatically)
    res_redir = client.get("/r/py-unit", follow_redirects=False)
    assert res_redir.status_code == 302
    assert res_redir.headers["location"] == "https://docs.python.org/3/library/unittest.html"

    # 3. Verify health endpoint remains unaffected by redirect prefixing
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"ok": True}


def test_3_auth_protection_401():
    """Test 3: Unauthenticated requests to protected endpoints return HTTP 401."""
    # Missing Authorization header
    res_missing = client.post("/links", json={"long_url": "https://unauthorized.example.com"})
    assert res_missing.status_code == 401
    assert "Missing or invalid authentication token" in res_missing.json()["detail"]

    # Invalid token format
    res_invalid = client.post(
        "/links",
        json={"long_url": "https://unauthorized.example.com"},
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert res_invalid.status_code == 401


def test_4_idor_owner_scoping_404():
    """Test 4: IDOR security check - Tenant Alice creates a link, Tenant Bob cannot read/update/delete."""
    # Alice creates a confidential link
    res_create = client.post(
        "/links",
        json={"long_url": "https://internal.tenant-a.com/finance", "code": "alice-finance"},
        headers=AUTH_ALICE,
    )
    assert res_create.status_code == 201
    link_id = res_create.json()["id"]

    # Bob attempts to GET Alice's link -> must return 404 Not Found (decision: not_owner_status=404)
    res_bob_get = client.get(f"/links/{link_id}", headers=AUTH_BOB)
    assert res_bob_get.status_code == 404
    assert "not found" in res_bob_get.json()["detail"].lower()

    # Bob attempts to UPDATE Alice's link -> must return 404 Not Found
    res_bob_patch = client.patch(
        f"/links/{link_id}",
        json={"long_url": "https://hijacked.example.com"},
        headers=AUTH_BOB,
    )
    assert res_bob_patch.status_code == 404

    # Bob attempts to DELETE Alice's link -> must return 404 Not Found
    res_bob_delete = client.delete(f"/links/{link_id}", headers=AUTH_BOB)
    assert res_bob_delete.status_code == 404


def test_5_retention_enforcement():
    """Test 5: Retention enforcement deletes clicks older than 30 days."""
    db: Session = SessionLocal()
    try:
        link = Link(code="retention-mod9", long_url="https://retention.example.com", created_by="tenant_alice")
        db.add(link)
        db.commit()
        db.refresh(link)

        now = datetime.now(timezone.utc)
        expired_click = ClickEvent(
            link_id=link.id,
            event_id="exp-001",
            clicked_at=now - timedelta(days=45),  # 45 days old -> expired
        )
        valid_click = ClickEvent(
            link_id=link.id,
            event_id="val-001",
            clicked_at=now - timedelta(days=5),   # 5 days old -> retained
        )
        db.add_all([expired_click, valid_click])
        db.commit()

        # Run retention purge job with 30-day retention
        purged_count = links_service.purge_old_clicks(db, retention_days=30)
        assert purged_count == 1

        # Verify only valid click remains
        remaining = db.query(ClickEvent).filter(ClickEvent.link_id == link.id).all()
        assert len(remaining) == 1
        assert remaining[0].event_id == "val-001"
    finally:
        db.close()


def test_6_url_validation_rejections():
    """Test 6: Reject bypass strings (javascript, data, unescaped schemes) with HTTP 400."""
    bypass_payloads = [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "http%3A%2F%2Fevil.example.com",
        "ftp://malicious.example.com/trojan",
        "file:///etc/passwd",
    ]

    db: Session = SessionLocal()
    try:
        initial_count = db.query(Link).count()
    finally:
        db.close()

    for payload in bypass_payloads:
        res = client.post(
            "/links",
            json={"long_url": payload},
            headers=AUTH_ALICE,
        )
        assert res.status_code == 400, f"Expected 400 for bypass payload: {payload}, got {res.status_code}"

    # Verify no new records were saved
    db = SessionLocal()
    try:
        final_count = db.query(Link).count()
        assert final_count == initial_count
    finally:
        db.close()


def test_7_async_worker_idempotency():
    """Test 7 (Jobs Strategy Option B): Worker idempotency handles duplicate deliveries atomically."""
    # Seed link
    db: Session = SessionLocal()
    try:
        link = Link(code="worker-idemp", long_url="https://worker.example.com", created_by="tenant_alice")
        db.add(link)
        db.commit()
        db.refresh(link)
        link_id = link.id
    finally:
        db.close()

    event_payload = {
        "link_id": link_id,
        "event_id": "idem-mod9-uuid-9999",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_hash": hashlib.sha256("192.168.1.1".encode("utf-8")).hexdigest(),
        "user_agent": "Pytest/TestRunner",
        "referer": "https://search.example.com",
    }

    # Delivery 1: fresh insertion
    db = SessionLocal()
    try:
        res1 = process_click_event_record(db, event_payload)
        assert res1["inserted"] is True

        # Delivery 2: replayed delivery with same idempotency key
        res2 = process_click_event_record(db, event_payload)
        assert res2["inserted"] is False

        # Verify exactly 1 record in database
        records = db.query(ClickEvent).filter(ClickEvent.event_id == "idem-mod9-uuid-9999").all()
        assert len(records) == 1
    finally:
        db.close()
