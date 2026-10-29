"""
Тесты версий задач (S14-005).
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)


async def _create(client: AsyncClient, token: str) -> dict[str, Any]:
    response = await client.post(
        TASKS_URL, json=TASK_PAYLOAD, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_update_saves_previous_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Правка задачи сохраняет снимок старого состояния"""
    token = await teacher_token(client, db_session, "verteacher")
    task = await _create(client, token)

    response = await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"description": "Новое описание задачи для проверки версий."},
        headers=auth(token),
    )

    assert response.status_code == 200
    versions = await client.get(
        f"{TASKS_URL}/{task['id']}/versions", headers=auth(token)
    )
    assert versions.status_code == 200
    items = versions.json()["items"]
    assert len(items) == 1
    assert items[0]["version"] == 1
    assert items[0]["test_cases_count"] == 2


async def test_restore_version_returns_old_tests(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Откат возвращает старые тест-кейсы и сохраняет текущее состояние"""
    token = await teacher_token(client, db_session, "restoreteacher")
    task = await _create(client, token)
    await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"description": "Первое изменение описания задачи."},
        headers=auth(token),
    )
    await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={
            "test_cases": [
                {"input": "1\n1\n", "expected_output": "2", "description": "Один"}
            ]
        },
        headers=auth(token),
    )

    restored = await client.post(
        f"{TASKS_URL}/{task['id']}/versions/1/restore", headers=auth(token)
    )

    assert restored.status_code == 200, restored.text
    assert len(restored.json()["test_cases"]) == 2
    versions = await client.get(
        f"{TASKS_URL}/{task['id']}/versions", headers=auth(token)
    )
    numbers = [item["version"] for item in versions.json()["items"]]
    assert numbers[:3] == [3, 2, 1]


async def test_versions_require_teacher(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """История версий недоступна ученику"""
    teacher = await teacher_token(client, db_session, "verteacher2")
    task = await _create(client, teacher)
    student = await register_and_login(client, "verstudent")

    response = await client.get(
        f"{TASKS_URL}/{task['id']}/versions", headers=auth(student)
    )

    assert response.status_code == 403


async def test_restore_missing_version_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Несуществующая версия — 404"""
    token = await teacher_token(client, db_session, "vermissing")
    task = await _create(client, token)

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/versions/99/restore", headers=auth(token)
    )

    assert response.status_code == 404
