"""Контрактные формы ответов ключевых эндпоинтов (S22-001).

Сценарий проходит «счастливый путь» по ключевым эндпоинтам (auth, tasks,
chat, classrooms, admin analytics) и сравнивает **форму** JSON-ответов с
фикстурой `tests/contracts/endpoints.json`. Значения не сравниваются —
только структура: набор полей и типы. Новые поля разрешены, пропавшие — нет.

Перегенерировать фикстуру (осознанно, отдельным коммитом):

    UPDATE_CONTRACT_FIXTURES=1 pytest -q tests/test_api_contract_shapes.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.user import UserRole
from tests.contract_utils import diff_shape, shape
from tests.fake_llm import FakeProvider, install_fake_provider, uninstall_fake_provider
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

FIXTURES = Path(__file__).parent / "contracts" / "endpoints.json"
UPDATE = os.environ.get("UPDATE_CONTRACT_FIXTURES") == "1"

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CHAT = "/api/v1/chat"
CHAT_SESSIONS = f"{CHAT}/sessions"
CLASSROOMS = "/api/v1/classrooms"

STUDENT_CODE = "a = int(input())\nb = int(input())\nprint(a + b)\n"


@pytest.fixture
def fake_provider() -> Any:
    provider = FakeProvider()
    install_fake_provider(provider)
    yield provider
    uninstall_fake_provider()


def _capture(observed: dict[str, Any], key: str, response: Any) -> dict[str, Any]:
    assert response.status_code < 400, f"{key}: {response.status_code} {response.text}"
    payload: dict[str, Any] = response.json()
    observed[key] = shape(payload)
    return payload


def _capture_error(observed: dict[str, Any], key: str, response: Any) -> None:
    assert response.status_code >= 400, f"{key}: ожидалась ошибка, пришло {response.status_code}"
    observed[key] = shape(response.json())


async def _admin_token(
    client: AsyncClient, db: AsyncSession, username: str = "shape_admin"
) -> str:
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


async def test_key_endpoint_shapes(
    client: AsyncClient, db_session: AsyncSession, fake_provider: FakeProvider
) -> None:
    observed: dict[str, Any] = {}

    student = await register_and_login(client, "shape_student")
    teacher = await teacher_token(client, db_session, "shape_teacher")
    admin = await _admin_token(client, db_session)

    # --- auth -------------------------------------------------------------
    _capture(
        observed,
        "POST /auth/register",
        await client.post(
            REGISTER_URL,
            json={
                "email": "shape_registered@example.com",
                "username": "shape_registered",
                "password": "password123",
            },
        ),
    )
    _capture(
        observed,
        "POST /auth/login",
        await client.post(
            LOGIN_URL, data={"username": "shape_student", "password": "password123"}
        ),
    )
    _capture(
        observed,
        "GET /auth/me",
        await client.get("/api/v1/auth/me", headers=auth(student)),
    )

    # --- tasks ------------------------------------------------------------
    task = _capture(
        observed,
        "POST /tasks",
        await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher)),
    )
    task_id = task["id"]
    _capture(
        observed, "GET /tasks", await client.get(TASKS_URL, headers=auth(student))
    )
    _capture(
        observed,
        "GET /tasks/{id}",
        await client.get(f"{TASKS_URL}/{task_id}", headers=auth(student)),
    )
    _capture(
        observed,
        "POST /tasks/{id}/submit",
        await client.post(
            f"{TASKS_URL}/{task_id}/submit",
            json={"code": STUDENT_CODE},
            headers=auth(student),
        ),
    )
    _capture(
        observed,
        "GET /tasks/progress",
        await client.get(f"{TASKS_URL}/progress", headers=auth(student)),
    )
    _capture_error(
        observed,
        "GET /tasks/{id} 404",
        await client.get(f"{TASKS_URL}/{uuid4()}", headers=auth(student)),
    )

    # --- chat -------------------------------------------------------------
    session = _capture(
        observed,
        "POST /chat/sessions",
        await client.post(CHAT_SESSIONS, json={"level": "basic"}, headers=auth(student)),
    )
    session_id = session["id"]
    _capture(
        observed,
        "POST /chat/sessions/{id}/messages",
        await client.post(
            f"{CHAT_SESSIONS}/{session_id}/messages",
            json={"content": "Как сложить два числа?"},
            headers=auth(student),
        ),
    )
    _capture(
        observed,
        "GET /chat/sessions",
        await client.get(CHAT_SESSIONS, headers=auth(student)),
    )
    _capture(
        observed,
        "GET /chat/sessions/{id}",
        await client.get(f"{CHAT_SESSIONS}/{session_id}", headers=auth(student)),
    )
    _capture(
        observed,
        "GET /chat/search",
        await client.get(f"{CHAT}/search", params={"q": "числа"}, headers=auth(student)),
    )

    # --- classrooms -------------------------------------------------------
    classroom = _capture(
        observed,
        "POST /classrooms",
        await client.post(CLASSROOMS, json={"name": "7А класс"}, headers=auth(teacher)),
    )
    classroom_id = classroom["id"]
    _capture(
        observed,
        "POST /classrooms/join",
        await client.post(
            f"{CLASSROOMS}/join",
            json={"join_code": classroom["join_code"]},
            headers=auth(student),
        ),
    )
    _capture(
        observed,
        "POST /classrooms/{id}/assignments",
        await client.post(
            f"{CLASSROOMS}/{classroom_id}/assignments",
            json={"task_id": task_id},
            headers=auth(teacher),
        ),
    )
    _capture(
        observed,
        "GET /classrooms/{id}",
        await client.get(f"{CLASSROOMS}/{classroom_id}", headers=auth(teacher)),
    )
    _capture(
        observed,
        "GET /classrooms/{id}/progress",
        await client.get(f"{CLASSROOMS}/{classroom_id}/progress", headers=auth(teacher)),
    )
    _capture(
        observed,
        "GET /me/assignments",
        await client.get("/api/v1/me/assignments", headers=auth(student)),
    )

    # --- admin ------------------------------------------------------------
    _capture(
        observed,
        "GET /admin/analytics",
        await client.get("/api/v1/admin/analytics", headers=auth(admin)),
    )

    # --- сравнение с фикстурой -------------------------------------------
    if UPDATE or not FIXTURES.is_file():
        if not UPDATE:
            pytest.fail(
                f"нет фикстуры {FIXTURES}; создайте её: "
                "UPDATE_CONTRACT_FIXTURES=1 pytest -q tests/test_api_contract_shapes.py"
            )
        FIXTURES.parent.mkdir(parents=True, exist_ok=True)
        FIXTURES.write_text(
            json.dumps(observed, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    expected: dict[str, Any] = json.loads(FIXTURES.read_text(encoding="utf-8"))

    assert set(expected) == set(observed), (
        "набор эндпоинтов в фикстуре разошёлся: "
        f"лишние в фикстуре — {sorted(set(expected) - set(observed))}, "
        f"новые в тесте — {sorted(set(observed) - set(expected))}"
    )

    problems: list[str] = []
    for key, expected_shape in expected.items():
        problems.extend(diff_shape(expected_shape, observed[key], key))

    assert problems == [], (
        "форма ответов изменилась:\n  - "
        + "\n  - ".join(problems)
        + "\nЕсли изменение осознанное — перегенерируйте фикстуру: "
        "UPDATE_CONTRACT_FIXTURES=1 pytest -q tests/test_api_contract_shapes.py"
    )
