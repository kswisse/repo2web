import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_health_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_analyze_invalid_url(client):
    response = await client.post(
        "/api/v1/repositories/analyze",
        json={"url": "not-a-valid-url"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_analyze_non_github_url(client):
    response = await client.post(
        "/api/v1/repositories/analyze",
        json={"url": "https://gitlab.com/user/repo"},
    )
    assert response.status_code == 422


@pytest.mark.skip(reason="Requires running PostgreSQL")
@pytest.mark.anyio
async def test_get_deployment_not_found(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/api/v1/deployments/{fake_id}")
    assert response.status_code in (404, 500)


@pytest.mark.anyio
async def test_create_deployment_missing_fields(client):
    response = await client.post(
        "/api/v1/deployments",
        json={},
    )
    assert response.status_code == 422
