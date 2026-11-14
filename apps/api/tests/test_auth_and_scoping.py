import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.db.session import SessionLocal
from app.main import app
from app.models.click import ClickEvent
from app.models.link import Link

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    limiter.reset()
    yield
    limiter.reset()
    db = SessionLocal()
    try:
        db.query(ClickEvent).delete()
        db.query(Link).delete()
        db.commit()
    finally:
        db.close()


def test_login_success():
    res = client.post(
        "/auth/login",
        json={"email": "tenant_a@example.com", "password": "password123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["principal_id"] == "tenant_a"


def test_login_invalid_credentials():
    res = client.post(
        "/auth/login",
        json={"email": "tenant_a@example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401


def test_protected_endpoint_without_token_returns_401():
    res = client.post("/links", json={"long_url": "https://example.com"})
    assert res.status_code == 401
    assert "Missing or invalid authentication token" in res.json()["detail"]


def test_protected_endpoint_with_invalid_token_returns_401():
    res = client.post(
        "/links",
        json={"long_url": "https://example.com"},
        headers={"Authorization": "Bearer invalid.fake.token"},
    )
    assert res.status_code == 401


def test_tenant_a_can_create_and_read_own_link():
    # Login Tenant A
    login_a = client.post(
        "/auth/login",
        json={"email": "tenant_a@example.com", "password": "password123"},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create link as Tenant A
    create_res = client.post(
        "/links",
        json={"long_url": "https://company-a.com/portal"},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    link_a = create_res.json()
    assert link_a["created_by"] == "tenant_a"

    # Read link by ID as Tenant A
    get_res = client.get(f"/links/{link_a['id']}", headers=headers_a)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == link_a["id"]


def test_multi_tenant_isolation_and_idor_prevention():
    # 1. Login Tenant A & create link
    login_a = client.post(
        "/auth/login",
        json={"email": "tenant_a@example.com", "password": "password123"},
    )
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    create_a = client.post(
        "/links",
        json={"long_url": "https://company-a.com/secret-doc"},
        headers=headers_a,
    )
    link_id_a = create_a.json()["id"]

    # 2. Login Tenant B
    login_b = client.post(
        "/auth/login",
        json={"email": "tenant_b@example.com", "password": "password123"},
    )
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. Tenant B attempts to read Tenant A's link (IDOR attempt)
    # Expected: 404 Not Found (hiding existence per chosen strategy)
    idor_res = client.get(f"/links/{link_id_a}", headers=headers_b)
    assert idor_res.status_code == 404

    # 4. Tenant B lists links; Tenant A's link must NOT appear
    list_b = client.get("/links", headers=headers_b)
    assert list_b.status_code == 200
    b_link_ids = [item["id"] for item in list_b.json()]
    assert link_id_a not in b_link_ids


def test_public_redirect_requires_no_auth():
    # Create link as Tenant A
    login_a = client.post(
        "/auth/login",
        json={"email": "tenant_a@example.com", "password": "password123"},
    )
    token_a = login_a.json()["access_token"]
    create_res = client.post(
        "/links",
        json={"long_url": "https://example.com/public-target", "code": "publink1"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert create_res.status_code == 201

    # Public redirect request without Authorization header
    res = client.get("/r/publink1", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "https://example.com/public-target"


def test_rate_limit_login_throttling():
    limiter.reset()
    for _ in range(10):
        res = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong"},
        )
        assert res.status_code == 401

    # 11th request must be throttled with HTTP 429
    res_11 = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
    )
    assert res_11.status_code == 429
    assert "Rate limit exceeded" in res_11.json()["detail"]


def test_rate_limit_create_link_throttling():
    limiter.reset()
    login_a = client.post(
        "/auth/login",
        json={"email": "tenant_a@example.com", "password": "password123"},
    )
    token = login_a.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(30):
        res = client.post(
            "/links",
            json={"long_url": f"https://example.com/item-{i}"},
            headers=headers,
        )
        assert res.status_code == 201

    # 31st request throttles with HTTP 429
    res_31 = client.post(
        "/links",
        json={"long_url": "https://example.com/item-31"},
        headers=headers,
    )
    assert res_31.status_code == 429

