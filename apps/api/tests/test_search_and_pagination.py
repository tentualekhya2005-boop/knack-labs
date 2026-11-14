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

client = TestClient(app)

USER_A_TOKEN = create_access_token({"sub": "alice@example.com", "principal_id": "tenant_alice"})
USER_B_TOKEN = create_access_token({"sub": "bob@example.com", "principal_id": "tenant_bob"})

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


def test_keyword_search_and_tag_filtering():
    """Verify search returns matching links by keyword across url/code/tags and filters by tag."""
    # Seed links for Tenant Alice
    client.post(
        "/links",
        json={"long_url": "https://docs.python.org/3/library", "code": "py-docs", "tags": ["python", "docs"]},
        headers=AUTH_A,
    )
    client.post(
        "/links",
        json={"long_url": "https://fastapi.tiangolo.com/tutorial", "code": "fastapi-guide", "tags": ["python", "web"]},
        headers=AUTH_A,
    )
    client.post(
        "/links",
        json={"long_url": "https://react.dev/reference", "code": "react-ref", "tags": ["javascript", "frontend"]},
        headers=AUTH_A,
    )

    # 1. Search by keyword matching URL substring
    res_kw = client.get("/links/search?q=tiangolo", headers=AUTH_A)
    assert res_kw.status_code == 200
    data_kw = res_kw.json()
    assert data_kw["total"] == 1
    assert data_kw["items"][0]["code"] == "fastapi-guide"

    # 2. Search by keyword matching code
    res_code = client.get("/links/search?q=react", headers=AUTH_A)
    assert res_code.status_code == 200
    data_code = res_code.json()
    assert data_code["total"] == 1
    assert data_code["items"][0]["code"] == "react-ref"

    # 3. Filter by tag
    res_tag = client.get("/links/search?tag=python", headers=AUTH_A)
    assert res_tag.status_code == 200
    data_tag = res_tag.json()
    assert data_tag["total"] == 2
    codes = {item["code"] for item in data_tag["items"]}
    assert codes == {"py-docs", "fastapi-guide"}


def test_pagination_offset_calculation_and_metadata():
    """Verify pagination formula: page 1 and page 2 contain distinct records without overlap."""
    # Create 5 links with sequential codes
    for i in range(1, 6):
        client.post(
            "/links",
            json={"long_url": f"https://example.com/page-test-{i}", "code": f"page-{i}"},
            headers=AUTH_A,
        )

    # Page 1 with page_size=2
    res_p1 = client.get("/links/search?page=1&page_size=2&sort_by=code&order=asc", headers=AUTH_A)
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert p1_data["page"] == 1
    assert p1_data["page_size"] == 2
    assert p1_data["total"] == 5
    assert p1_data["total_pages"] == 3
    assert len(p1_data["items"]) == 2
    p1_codes = [item["code"] for item in p1_data["items"]]
    assert p1_codes == ["page-1", "page-2"]

    # Page 2 with page_size=2
    res_p2 = client.get("/links/search?page=2&page_size=2&sort_by=code&order=asc", headers=AUTH_A)
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    assert p2_data["page"] == 2
    assert p2_data["page_size"] == 2
    assert len(p2_data["items"]) == 2
    p2_codes = [item["code"] for item in p2_data["items"]]
    assert p2_codes == ["page-3", "page-4"]

    # Ensure no overlap
    assert set(p1_codes).isdisjoint(set(p2_codes))

    # Page 3 with page_size=2 (final page with 1 remaining item)
    res_p3 = client.get("/links/search?page=3&page_size=2&sort_by=code&order=asc", headers=AUTH_A)
    assert res_p3.status_code == 200
    p3_data = res_p3.json()
    assert len(p3_data["items"]) == 1
    assert p3_data["items"][0]["code"] == "page-5"


def test_page_size_capping():
    """Verify that attempting an excessively large page_size is capped at 100."""
    res = client.get("/links/search?page=1&page_size=500", headers=AUTH_A)
    assert res.status_code == 200
    data = res.json()
    assert data["page_size"] == 100


def test_tenant_isolation_in_search():
    """Verify that Tenant Bob cannot see links belonging to Tenant Alice."""
    # Alice creates a secret link
    client.post(
        "/links",
        json={"long_url": "https://confidential.example.com/roadmap", "code": "alice-secret"},
        headers=AUTH_A,
    )
    # Bob creates a link
    client.post(
        "/links",
        json={"long_url": "https://public.example.com/blog", "code": "bob-blog"},
        headers=AUTH_B,
    )

    # Bob searches for 'confidential' or 'roadmap' -> must return 0 results
    res_bob = client.get("/links/search?q=roadmap", headers=AUTH_B)
    assert res_bob.status_code == 200
    data_bob = res_bob.json()
    assert data_bob["total"] == 0
    assert len(data_bob["items"]) == 0

    # Alice searches for 'roadmap' -> returns her link
    res_alice = client.get("/links/search?q=roadmap", headers=AUTH_A)
    assert res_alice.status_code == 200
    data_alice = res_alice.json()
    assert data_alice["total"] == 1
    assert data_alice["items"][0]["code"] == "alice-secret"


def test_allowlisted_sorting_validation():
    """Verify that invalid sort_by or order parameters are rejected with HTTP 422."""
    # Illegal sort_by field (SQL injection attempt or unsupported column)
    res_bad_sort = client.get("/links/search?sort_by=password;DROP TABLE links;--", headers=AUTH_A)
    assert res_bad_sort.status_code == 422

    # Illegal order direction
    res_bad_order = client.get("/links/search?sort_by=created_at&order=sideways", headers=AUTH_A)
    assert res_bad_order.status_code == 422

    # Valid sort parameters succeed
    res_ok = client.get("/links/search?sort_by=created_at&order=asc", headers=AUTH_A)
    assert res_ok.status_code == 200


def test_pagination_boundaries_and_empty_pages():
    """Verify edge boundaries: requesting page beyond total results returns empty list with accurate metadata."""
    # Seed 2 links
    client.post(
        "/links",
        json={"long_url": "https://example.com/item1", "code": "bnd-1"},
        headers=AUTH_A,
    )
    client.post(
        "/links",
        json={"long_url": "https://example.com/item2", "code": "bnd-2"},
        headers=AUTH_A,
    )

    # 1. Boundary: Page beyond range (page=999)
    res_beyond = client.get("/links/search?page=999&page_size=10", headers=AUTH_A)
    assert res_beyond.status_code == 200
    beyond_data = res_beyond.json()
    assert beyond_data["total"] == 2
    assert beyond_data["total_pages"] == 1
    assert beyond_data["items"] == []

    # 2. Boundary: Minimum page_size=1
    res_min_size = client.get("/links/search?page=1&page_size=1&sort_by=code&order=asc", headers=AUTH_A)
    assert res_min_size.status_code == 200
    min_data = res_min_size.json()
    assert len(min_data["items"]) == 1
    assert min_data["items"][0]["code"] == "bnd-1"
    assert min_data["total_pages"] == 2


