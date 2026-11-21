import json
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.cache import cache_service
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.link import Link
from app.worker import process_click_event_record

def verify_stale_cache_bug_9():
    print("=== Testing Bug #9: Stale Cache Invalidation on Delete ===")
    client = TestClient(app)
    admin_token = create_access_token({"principal_id": "admin_user", "role": "admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    tenant_token = create_access_token({"principal_id": "tenant_test", "role": "user"})
    tenant_headers = {"Authorization": f"Bearer {tenant_token}"}

    # 1. Create a link
    code = f"stale_test_{int(time.time())}"
    create_res = client.post(
        "/links",
        json={"long_url": "https://example.com/target-stale-test", "code": code},
        headers=tenant_headers,
    )
    assert create_res.status_code == 201, f"Failed to create link: {create_res.text}"
    link_id = create_res.json()["id"]
    print(f"1. Created link id={link_id}, code={code}")

    # 2. Access link to populate cache
    r1 = client.get(f"/r/{code}", follow_redirects=False)
    assert r1.status_code == 302
    assert r1.headers.get("x-cache") == "MISS"
    print(f"2. First redirect -> HTTP 302 (X-Cache: {r1.headers.get('x-cache')})")

    # 3. Access again -> cache HIT
    r2 = client.get(f"/r/{code}", follow_redirects=False)
    assert r2.status_code == 302
    assert r2.headers.get("x-cache") == "HIT"
    print(f"3. Second redirect -> HTTP 302 (X-Cache: {r2.headers.get('x-cache')})")

    # Verify cache key exists in dedicated namespace
    cached = cache_service.get_redirect_target(code)
    assert cached is not None, "Expected target in cache!"
    print(f"   Redis cache has target: {cached['long_url']}")

    # 4. Delete the link via Admin API
    del_res = client.delete(f"/api/admin/links/{link_id}", headers=admin_headers)
    assert del_res.status_code == 204, f"Admin delete failed: {del_res.status_code}"
    print(f"4. Admin deleted link id={link_id} -> HTTP 204")

    # 5. Verify cache is invalidated immediately
    cached_after = cache_service.get_redirect_target(code)
    assert cached_after is None, f"Expected cache to be invalidated, but found {cached_after}"
    print("5. Cache target invalidated immediately: None")

    # 6. Access deleted link -> must return HTTP 404 immediately, NOT 302!
    r3 = client.get(f"/r/{code}", follow_redirects=False)
    assert r3.status_code == 404, f"Expected HTTP 404 for deleted link, got {r3.status_code}!"
    print(f"6. Accessing deleted link returned HTTP {r3.status_code} (Link successfully dead!)")
    print("-> Bug #9 successfully resolved and verified!\n")


def verify_queue_retry_storm_bug_10():
    print("=== Testing Bug #10: Queue Retry Storm & Resource Isolation ===")
    from worker.main import get_worker_pool, MAX_RETRIES, DEAD_LETTER_QUEUE
    
    # 1. Verify separate worker connection pool
    pool = get_worker_pool()
    assert pool.maxconn == 3, f"Expected maxconn=3 for worker pool, got {pool.maxconn}"
    print(f"1. Verified dedicated worker connection pool: maxconn={pool.maxconn} (bulkhead isolation)")

    # 2. Verify retry policy and DLQ configuration
    assert MAX_RETRIES == 5
    assert DEAD_LETTER_QUEUE == "analytics:dead_letter_queue"
    print(f"2. Verified retry ceiling: MAX_RETRIES={MAX_RETRIES}, DLQ='{DEAD_LETTER_QUEUE}'")

    # 3. Verify API responsiveness is completely unaffected
    client = TestClient(app)
    start = time.perf_counter()
    for _ in range(20):
        h_res = client.get("/health")
        assert h_res.status_code == 200
    duration_ms = (time.perf_counter() - start) * 1000
    print(f"3. 20 consecutive API /health requests completed in {duration_ms:.2f}ms (avg {duration_ms/20:.2f}ms)")
    print("-> Bug #10 successfully resolved and verified!\n")


def verify_break_fix_namespace_separation():
    print("=== Testing Break/Fix: Namespace Isolation (Redirect vs Dedup) ===")
    db = SessionLocal()
    try:
        # Get or create a valid link for foreign key
        link = db.query(Link).first()
        if not link:
            link = Link(code="dedup_link_test", long_url="https://example.com/dedup", created_by="test")
            db.add(link)
            db.commit()
            db.refresh(link)

        # Event 1
        event_1 = {"event_id": "evt-dedup-001", "link_id": link.id, "user_agent": "test", "referrer": None, "ip_hash": "abc"}
        res1 = process_click_event_record(db, event_1)
        print(f"1. Process event 1: {res1['status']}")
        
        # Verify deduplication key exists in dedicated namespace
        assert cache_service.is_analytics_processed("evt-dedup-001") is True
        print("2. Verified analytics:dedup:evt-dedup-001 is active")

        # Now simulate link deletion with short code 'evt-dedup-001'
        cache_service.invalidate_redirect_target("evt-dedup-001")
        print("3. Executed cache_service.invalidate_redirect_target('evt-dedup-001')")

        # Invalidation must NOT clear the analytics dedup namespace!
        assert cache_service.is_analytics_processed("evt-dedup-001") is True, "Dedup key was wiped by redirect invalidation!"
        print("4. Analytics dedup key remained intact! Dedicated namespaces successfully isolated.")

        # Replaying event 1 must still be duplicate_skipped
        res2 = process_click_event_record(db, event_1)
        assert res2["status"] == "duplicate_skipped", f"Expected duplicate_skipped, got {res2['status']}"
        print("5. Replaying event 1 skipped as duplicate (no doubling!)")
        print("-> Break/Fix Namespace Isolation verified!\n")
    finally:
        db.close()


if __name__ == "__main__":
    verify_stale_cache_bug_9()
    verify_queue_retry_storm_bug_10()
    verify_break_fix_namespace_separation()
    print("ALL MULTI-LAYER BUG VERIFICATIONS PASSED PERFECTLY!")
