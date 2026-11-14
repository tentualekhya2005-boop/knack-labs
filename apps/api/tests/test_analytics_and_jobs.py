import hashlib
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.cache import cache_service
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.click import ClickEvent
from app.models.link import Link
from app.services import links_service
from app.worker import process_click_event_record

client = TestClient(app)

USER_A_TOKEN = create_access_token({"sub": "user_a@example.com", "principal_id": "tenant_alpha"})
USER_B_TOKEN = create_access_token({"sub": "user_b@example.com", "principal_id": "tenant_beta"})

AUTH_A = {"Authorization": f"Bearer {USER_A_TOKEN}"}
AUTH_B = {"Authorization": f"Bearer {USER_B_TOKEN}"}


@pytest.fixture(autouse=True)
def cleanup():
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


def test_async_click_enqueuing_and_processing():
    """Verify that redirect triggers async click enqueue and worker records it into PostgreSQL."""
    # 1. Create a link
    res = client.post(
        "/links",
        json={"long_url": "https://analytics-target.example.com", "code": "async-test-1"},
        headers=AUTH_A,
    )
    assert res.status_code == 201
    link_id = res.json()["id"]

    # 2. Redirect request with client metadata
    redirect_res = client.get(
        "/r/async-test-1",
        headers={"User-Agent": "PyTestAgent/1.0", "Referer": "https://search.example.com"},
        follow_redirects=False,
    )
    assert redirect_res.status_code == 302
    assert redirect_res.headers["location"] == "https://analytics-target.example.com"

    # Allow worker a moment to process the task
    time.sleep(1.0)

    # 3. Read analytics
    analytics_res = client.get(f"/links/{link_id}/analytics", headers=AUTH_A)
    assert analytics_res.status_code == 200
    data = analytics_res.json()
    assert data["link_id"] == link_id
    assert data["total_clicks"] >= 1
    click = data["clicks"][0]
    assert click["user_agent"] == "PyTestAgent/1.0"
    assert click["referrer"] == "https://search.example.com"
    # Privacy check: ip_hash must be a SHA-256 hash or None, never a raw IP
    if click["ip_hash"]:
        assert len(click["ip_hash"]) == 64


def test_worker_idempotency_guarantee():
    """Verify that processing the exact same event_id multiple times does NOT create duplicates."""
    db: Session = SessionLocal()
    try:
        # Create a test link
        link = Link(
            code="idem-code",
            long_url="https://idempotent.example.com",
            created_by="tenant_alpha",
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        event_payload = {
            "event_id": "test-uuid-idempotency-key-001",
            "link_id": link.id,
            "clicked_at": datetime.now(timezone.utc).isoformat(),
            "user_agent": "TestBrowser/2.0",
            "referrer": "https://ref.example.com",
            "ip_hash": hashlib.sha256(b"198.51.100.42").hexdigest(),
        }

        # First run: should insert
        res1 = process_click_event_record(db, event_payload)
        assert res1["inserted"] is True

        # Second run (replayed retry of the same event): must be an idempotent no-op
        res2 = process_click_event_record(db, event_payload)
        assert res2["inserted"] is False

        # Database verification: only 1 record exists
        count = db.query(ClickEvent).filter(ClickEvent.event_id == "test-uuid-idempotency-key-001").count()
        assert count == 1
    finally:
        db.close()


def test_analytics_owner_scoping_and_date_filtering():
    """Verify that analytics endpoint enforces owner-scoping (404 for non-owners) and filters by dates."""
    # 1. Create Link as Tenant Alpha
    res = client.post(
        "/links",
        json={"long_url": "https://tenant-scoped.example.com", "code": "scope-test-1"},
        headers=AUTH_A,
    )
    assert res.status_code == 201
    link_id = res.json()["id"]

    # 2. Insert clicks across different dates
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        c1 = ClickEvent(link_id=link_id, event_id="ev-1", clicked_at=last_week)
        c2 = ClickEvent(link_id=link_id, event_id="ev-2", clicked_at=yesterday)
        c3 = ClickEvent(link_id=link_id, event_id="ev-3", clicked_at=now)
        db.add_all([c1, c2, c3])
        db.commit()
    finally:
        db.close()

    # 3. Owner (Tenant Alpha) requests all clicks
    res_a = client.get(f"/links/{link_id}/analytics", headers=AUTH_A)
    assert res_a.status_code == 200
    assert res_a.json()["total_clicks"] == 3

    # 4. Filter by date window (past 2 days)
    filter_from = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    filter_to = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    res_filtered = client.get(
        f"/links/{link_id}/analytics?from={filter_from}&to={filter_to}",
        headers=AUTH_A,
    )
    assert res_filtered.status_code == 200
    filtered_data = res_filtered.json()
    assert filtered_data["total_clicks"] == 2  # yesterday + today, excludes last_week

    # 5. Non-owner (Tenant Beta) requests analytics: must return 404 to defeat IDOR
    res_b = client.get(f"/links/{link_id}/analytics", headers=AUTH_B)
    assert res_b.status_code == 404


def test_retention_purge_mechanism():
    """Verify that purge_old_clicks deletes click events older than retention threshold."""
    db: Session = SessionLocal()
    try:
        link = Link(code="purge-test", long_url="https://purge.example.com", created_by="tenant_alpha")
        db.add(link)
        db.commit()
        db.refresh(link)

        now = datetime.now(timezone.utc)
        old_click = ClickEvent(
            link_id=link.id,
            event_id="old-click-1",
            clicked_at=now - timedelta(days=35),  # 35 days old
        )
        recent_click = ClickEvent(
            link_id=link.id,
            event_id="recent-click-1",
            clicked_at=now - timedelta(days=5),   # 5 days old
        )
        db.add_all([old_click, recent_click])
        db.commit()

        # Run retention purge for 30 days
        deleted = links_service.purge_old_clicks(db, retention_days=30)
        assert deleted == 1

        remaining = db.query(ClickEvent).filter(ClickEvent.link_id == link.id).all()
        assert len(remaining) == 1
        assert remaining[0].event_id == "recent-click-1"
    finally:
        db.close()


def test_queue_broker_outage_graceful_degradation():
    """Verify that if Celery/Redis fails during enqueue, redirect still returns HTTP 302 without hanging."""
    # 1. Create a link
    res = client.post(
        "/links",
        json={"long_url": "https://fallback-target.example.com", "code": "queue-outage-code"},
        headers=AUTH_A,
    )
    assert res.status_code == 201

    # 2. Mock enqueue failure to simulate Redis outage
    with patch("app.core.queue.enqueue_click_event") as mock_enqueue:
        mock_enqueue.side_effect = Exception("Connection refused: Redis broker down")
        
        # Must still redirect successfully with HTTP 302
        redirect_res = client.get("/r/queue-outage-code", follow_redirects=False)
        assert redirect_res.status_code == 302
        assert redirect_res.headers["location"] == "https://fallback-target.example.com"

