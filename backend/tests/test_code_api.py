"""
Тесты Code API (S6-005, S6-007).

Песочница подменяется зависимостью `get_executor`, чтобы API-тесты не
запускали отдельный интерпретатор на каждый запрос.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.executor import ExecutionResult, SandboxedExecutor
from app.main import app

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


class FakeExecutor(SandboxedExecutor):
    """Песочница-заглушка с заранее заданным результатом"""

    def __init__(self, result: ExecutionResult) -> None:
        super().__init__(timeout=1)
        self.result = result
        self.calls: list[str] = []

    async def execute(  # type: ignore[override]
        self, code: str, stdin_text: str = ""
    ) -> ExecutionResult:
        self.calls.append(code)
        return self.result


@pytest.fixture
def fake_executor() -> Iterator[FakeExecutor]:
    """Подменить песочницу в приложении"""
    from app.api.v1.code import get_executor

    executor = FakeExecutor(
        ExecutionResult(success=True, output="10\n", execution_time=0.01)
    )
    app.dependency_overrides[get_executor] = lambda: executor
    yield executor
    app.dependency_overrides.pop(get_executor, None)


async def _register_and_login(client: AsyncClient, username: str = "codeuser") -> str:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": "password123",
        },
    )
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": "password123"}
    )
    token: str = response.json()["access_token"]
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_execute_returns_result_and_saves_record(
    client: AsyncClient, fake_executor: FakeExecutor
) -> None:
    """Успешный запуск возвращает вывод и пишет запись в историю"""
    token = await _register_and_login(client)

    response = await client.post(
        "/api/v1/code/execute",
        json={"code": "print(sum([1, 2, 3, 4]))"},
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["success"] is True
    assert data["output"] == "10\n"
    assert fake_executor.calls == ["print(sum([1, 2, 3, 4]))"]

    history = await client.get("/api/v1/code/history", headers=_auth(token))
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["success"] is True


async def test_execute_rejects_empty_code(
    client: AsyncClient, fake_executor: FakeExecutor
) -> None:
    """Пустой код отклоняется схемой"""
    token = await _register_and_login(client, username="codeempty")

    response = await client.post(
        "/api/v1/code/execute", json={"code": ""}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_execute_requires_auth(client: AsyncClient, fake_executor: FakeExecutor) -> None:
    """Без токена выполнение недоступно"""
    response = await client.post("/api/v1/code/execute", json={"code": "print(1)"})

    assert response.status_code in (401, 403)


async def test_lint_reports_issues(client: AsyncClient) -> None:
    """Линт возвращает замечания с счётчиками"""
    response = await client.post(
        "/api/v1/code/lint", json={"code": "import os\nprint(1)"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["errors"] == 1
    assert data["issues"][0]["code"] == "S001"


async def test_lint_clean_code(client: AsyncClient) -> None:
    """Чистый код — без замечаний"""
    response = await client.post(
        "/api/v1/code/lint", json={"code": "print(sum([1, 2]))"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["issues"] == []
    assert data["errors"] == 0


async def test_analyze_returns_stats_and_summary(
    client: AsyncClient, fake_executor: FakeExecutor
) -> None:
    """Анализ отдаёт метрики и резюме"""
    token = await _register_and_login(client, username="codeanalyze")

    response = await client.post(
        "/api/v1/code/analyze",
        json={"code": "def f(x):\n    for i in range(3):\n        print(i)\n"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["functions"] == 1
    assert data["stats"]["loops"] == 1
    assert data["summary"]


async def test_history_is_isolated_per_user(
    client: AsyncClient, fake_executor: FakeExecutor
) -> None:
    """История другого пользователя недоступна"""
    owner_token = await _register_and_login(client, username="codeowner")
    await client.post(
        "/api/v1/code/execute", json={"code": "print(1)"}, headers=_auth(owner_token)
    )
    record_id = (
        await client.get("/api/v1/code/history", headers=_auth(owner_token))
    ).json()[0]["id"]

    other_token = await _register_and_login(client, username="codeother")

    list_response = await client.get("/api/v1/code/history", headers=_auth(other_token))
    item_response = await client.get(
        f"/api/v1/code/history/{record_id}", headers=_auth(other_token)
    )

    assert list_response.json() == []
    assert item_response.status_code == 403


async def test_history_missing_record_returns_404(
    client: AsyncClient, fake_executor: FakeExecutor
) -> None:
    """Несуществующая запись — 404"""
    token = await _register_and_login(client, username="codemissing")

    response = await client.get(
        "/api/v1/code/history/00000000-0000-0000-0000-000000000000",
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_limits_endpoint_describes_sandbox(client: AsyncClient) -> None:
    """Описание ограничений песочницы"""
    response = await client.get("/api/v1/code/limits")

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert "timeout_seconds" in data
    assert "allowed_modules" in data
    assert "math" in data["allowed_modules"]
    assert "os" not in data["allowed_modules"]
