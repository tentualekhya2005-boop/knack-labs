import pytest
import httpx
from app.main import app


@pytest.mark.anyio
async def test_health_check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


@pytest.mark.anyio
async def test_ready_check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["status"] == "ready"
        assert "dependencies" in data
        assert data["dependencies"]["database"] == "ready"
