import base64
import hashlib
import hmac
import json
import time
from typing import Dict, Optional

from app.config import settings

SECRET_KEY = settings.jwt_secret or "dev-insecure-jwt-secret-key-32-chars-min"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 3600

# Mock multi-tenant users for development and demonstration
MOCK_USERS: Dict[str, Dict[str, str]] = {
    "tenant_a@example.com": {
        "password": "password123",
        "principal_id": "tenant_a",
        "name": "Acme Corp (Tenant A)",
    },
    "tenant_b@example.com": {
        "password": "password123",
        "principal_id": "tenant_b",
        "name": "Beta LLC (Tenant B)",
    },
    "test@example.com": {
        "password": "password123",
        "principal_id": "tenant_test",
        "name": "Test User",
    },
}


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(data: dict, expires_delta_seconds: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = time.time() + (expires_delta_seconds or ACCESS_TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})

    header = {"alg": ALGORITHM, "typ": "JWT"}
    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(to_encode, separators=(",", ":")).encode("utf-8"))

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token structure")

    header_b64, payload_b64, sig_b64 = parts
    expected_sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(_b64_encode(expected_sig), sig_b64):
        raise ValueError("Invalid JWT token signature")

    payload = json.loads(_b64_decode(payload_b64))
    if "exp" in payload and payload["exp"] < time.time():
        raise ValueError("JWT token has expired")

    return payload

