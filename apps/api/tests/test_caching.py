import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache_service
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.click import ClickEvent
from app.models.link import Link

client = TestClient(app)
TEST_TOKEN = create_access_token({"sub": "admin@example.com", "principal_id": "test_admin"})
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture(autouse=True)
def setup_and_cleanup():
    limiter.reset()
    cache_service.reset_stats()
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


def test_cache_miss_then_cache_hit():
    # 1. Create a link
    res = client.post(
        "/links",
        json={"long_url": "https://first-site.example.com", "code": "cache-hit-test"},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 201

    # 2. First redirect: Cache Miss -> populates cache from DB
    res1 = client.get("/r/cache-hit-test", follow_redirects=False)
    assert res1.status_code == 302
    assert res1.headers["location"] == "https://first-site.example.com"
    assert res1.headers.get("x-cache") == "MISS"

    # 3. Second redirect: Cache Hit -> served directly from cache
    res2 = client.get("/r/cache-hit-test", follow_redirects=False)
    assert res2.status_code == 302
    assert res2.headers["location"] == "https://first-site.example.com"
    assert res2.headers.get("x-cache") == "HIT"


def test_cache_invalidation_on_update():
    # 1. Create link
    create_res = client.post(
        "/links",
        json={"long_url": "https://original.example.com", "code": "update-inv-test"},
        headers=AUTH_HEADERS,
    )
    assert create_res.status_code == 201
    link_id = create_res.json()["id"]

    # 2. Warm up cache
    r1 = client.get("/r/update-inv-test", follow_redirects=False)
    assert r1.status_code == 302
    assert r1.headers["location"] == "https://original.example.com"
    assert r1.headers.get("x-cache") == "MISS"

    r2 = client.get("/r/update-inv-test", follow_redirects=False)
    assert r2.status_code == 302
    assert r2.headers.get("x-cache") == "HIT"

    # 3. Update link target (PATCH)
    patch_res = client.patch(
        f"/links/{link_id}",
        json={"long_url": "https://updated-target.example.org"},
        headers=AUTH_HEADERS,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["long_url"] == "https://updated-target.example.org"

    # 4. Redirect must NOT return stale URL; it must fetch updated URL
    r3 = client.get("/r/update-inv-test", follow_redirects=False)
    assert r3.status_code == 302
    assert r3.headers["location"] == "https://updated-target.example.org"
    assert r3.headers.get("x-cache") == "MISS"

    # 5. Subsequent redirect hits newly warmed cache
    r4 = client.get("/r/update-inv-test", follow_redirects=False)
    assert r4.status_code == 302
    assert r4.headers["location"] == "https://updated-target.example.org"
    assert r4.headers.get("x-cache") == "HIT"


def test_cache_invalidation_on_delete():
    # 1. Create link
    create_res = client.post(
        "/links",
        json={"long_url": "https://delete-me.example.com", "code": "del-inv-test"},
        headers=AUTH_HEADERS,
    )
    assert create_res.status_code == 201
    link_id = create_res.json()["id"]

    # 2. Warm cache
    r1 = client.get("/r/del-inv-test", follow_redirects=False)
    assert r1.status_code == 302

    # 3. Delete link
    del_res = client.delete(f"/links/{link_id}", headers=AUTH_HEADERS)
    assert del_res.status_code == 204

    # 4. Redirect must return 404 (not cached stale redirect)
    r2 = client.get("/r/del-inv-test", follow_redirects=False)
    assert r2.status_code == 404


def test_graceful_fallback_when_cache_fails(monkeypatch):
    # 1. Create link
    client.post(
        "/links",
        json={"long_url": "https://db-fallback.example.com", "code": "fallback-test"},
        headers=AUTH_HEADERS,
    )

    # 2. Simulate Redis failure in cache service
    def simulate_redis_crash(*args, **kwargs):
        raise ConnectionError("Simulated Redis connection failure")

    monkeypatch.setattr(cache_service, "get_redirect_target", simulate_redis_crash)

    # 3. Redirect must STILL work via DB fallback without failing or 500 error!
    res = client.get("/r/fallback-test", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "https://db-fallback.example.com"

