import pytest
from fastapi.testclient import TestClient

from app.core.logging import StructuredJsonFormatter, redact_data, redact_text
from app.core.security import create_access_token
from app.main import app

client = TestClient(app)
TEST_TOKEN = create_access_token({"sub": "admin@example.com", "principal_id": "test_admin"})
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}


def test_validation_error_envelope_and_no_stack_trace():
    response = client.post(
        "/links",
        json={"long_url": "not-a-valid-url"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in data["error"]
    assert "request_id" in data["error"]
    assert data["error"]["request_id"].startswith("req_")
    assert "traceback" not in str(data).lower()
    assert "Traceback" not in response.text
    # Verify response header
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"] == data["error"]["request_id"]


def test_unauthorized_error_envelope():
    response = client.post(
        "/links",
        json={"long_url": "https://example.com"},
        # No auth header
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in data["error"]
    assert "x-request-id" in response.headers


def test_not_found_error_envelope():
    response = client.get("/links/999999", headers=AUTH_HEADERS)
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "request_id" in data["error"]
    assert "x-request-id" in response.headers


def test_custom_request_id_header_propagation():
    custom_id = "req_custom_trace_98765"
    response = client.get(
        "/links/999999",
        headers={**AUTH_HEADERS, "X-Request-ID": custom_id},
    )
    assert response.status_code == 404
    assert response.headers["x-request-id"] == custom_id
    assert response.json()["error"]["request_id"] == custom_id


def test_secrets_redaction_utility():
    sentinel = "DO_NOT_LOG_ME_123"
    raw_text = f"User request failed with secret token: Bearer my-secret-jwt and sentinel {sentinel}"
    sanitized = redact_text(raw_text)
    assert sentinel not in sanitized
    assert "my-secret-jwt" not in sanitized
    assert "[REDACTED]" in sanitized

    headers = {
        "authorization": f"Bearer {sentinel}",
        "x-api-key": "secret-api-key-999",
        "content-type": "application/json",
    }
    redacted_headers = redact_data(headers)
    assert redacted_headers["authorization"] == "[REDACTED]"
    assert redacted_headers["x-api-key"] == "[REDACTED]"
    assert redacted_headers["content-type"] == "application/json"


def test_unhandled_server_error_sanitization(monkeypatch):
    # Simulate an unexpected internal database explosion in a route
    def raise_db_crash(*args, **kwargs):
        raise RuntimeError("FATAL: database password=super_secret_db_pass leaked in internal crash")

    from app.services import links_service
    monkeypatch.setattr(links_service, "get_link_by_id", raise_db_crash)

    response = client.get("/links/123", headers=AUTH_HEADERS)
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "Internal Server Error"
    assert "request_id" in data["error"]
    assert "super_secret_db_pass" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text

