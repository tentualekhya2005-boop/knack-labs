import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

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
def cleanup():
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


def test_health_check_works():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_create_link_success():
    payload = {"long_url": "https://example.com"}
    response = client.post("/links", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "code" in data
    assert len(data["code"]) == 8
    assert data["long_url"] == "https://example.com"
    assert "/r/" in data["short_url"]
    assert "created_at" in data


def test_create_link_with_custom_code():
    payload = {"long_url": "https://gmrit.edu.in", "code": "gmrit-2026"}
    response = client.post("/links", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "gmrit-2026"
    assert data["long_url"] == "https://gmrit.edu.in"


def test_duplicate_code_returns_409():
    payload = {"long_url": "https://example.com", "code": "dup-test"}
    res1 = client.post("/links", json=payload, headers=AUTH_HEADERS)
    assert res1.status_code == 201

    res2 = client.post("/links", json=payload, headers=AUTH_HEADERS)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_get_link_by_id():
    res = client.post("/links", json={"long_url": "https://example.com/item"}, headers=AUTH_HEADERS)
    link_id = res.json()["id"]

    get_res = client.get(f"/links/{link_id}", headers=AUTH_HEADERS)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == link_id
    assert get_res.json()["long_url"] == "https://example.com/item"


def test_get_link_by_id_not_found():
    response = client.get("/links/999999", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_list_links_paged():
    client.post("/links", json={"long_url": "https://example1.com"}, headers=AUTH_HEADERS)
    client.post("/links", json={"long_url": "https://example2.com"}, headers=AUTH_HEADERS)
    client.post("/links", json={"long_url": "https://example3.com"}, headers=AUTH_HEADERS)

    res = client.get("/links?skip=0&limit=2", headers=AUTH_HEADERS)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2


def test_redirect_by_code_and_click_recording():
    create_res = client.post(
        "/links",
        json={"long_url": "https://example.com/target", "code": "target-code"},
        headers=AUTH_HEADERS,
    )
    assert create_res.status_code == 201

    # Follow redirect is disabled to verify 302 and Location header
    redir_res = client.get("/r/target-code", follow_redirects=False)
    assert redir_res.status_code == 302
    assert redir_res.headers["location"] == "https://example.com/target"

    # Verify click was recorded
    db = SessionLocal()
    try:
        clicks = db.query(ClickEvent).all()
        assert len(clicks) == 1
        assert clicks[0].link.code == "target-code"
    finally:
        db.close()


def test_redirect_not_found():
    response = client.get("/r/non-existent-code", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_expired():
    # Link that already expired
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    db = SessionLocal()
    try:
        link = Link(
            code="expired-code",
            long_url="https://expired.example.com",
            created_by="test_admin",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db.add(link)
        db.commit()
    finally:
        db.close()

    res = client.get("/r/expired-code", follow_redirects=False)
    assert res.status_code == 404


@pytest.mark.parametrize(
    "bad_url",
    [
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
    ],
)
def test_validation_abuse_strings_return_400(bad_url):
    response = client.post("/links", json={"long_url": bad_url}, headers=AUTH_HEADERS)
    assert response.status_code == 400, f"Expected 400 for '{bad_url}', got {response.status_code}"
