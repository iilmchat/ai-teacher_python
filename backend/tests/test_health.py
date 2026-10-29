"""
Tests for health check endpoints
"""
from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    """Health check возвращает ok и версию"""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "app_name" in data


async def test_root_endpoint(client: AsyncClient) -> None:
    """Корневой эндпоинт возвращает ссылки на docs и health"""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data
    assert "health" in data


async def test_openapi_schema_available(client: AsyncClient) -> None:
    """OpenAPI-схема доступна"""
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()
