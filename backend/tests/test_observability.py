"""Тесты наблюдаемости и аудита (S25-001…S25-004)."""

from __future__ import annotations

import re
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import reset_metrics
from app.core.request_context import current_request_id
from app.db.repositories.user import UserRepository
from app.models.user import UserRole
from tests.task_helpers import TASK_PAYLOAD, TASKS_URL, auth, register_and_login, teacher_token

ADMIN_AUDIT = "/api/v1/admin/audit"


async def _admin_token(
    client: AsyncClient, db: AsyncSession, username: str = "obs_admin"
) -> str:
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


# --- S25-001: request id ----------------------------------------------------


async def test_request_id_is_echoed(client: AsyncClient) -> None:
    response = await client.get(
        "/health/live", headers={"X-Request-ID": "trace-123"}
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-123"


async def test_request_id_is_generated(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


async def test_request_id_available_in_context(client: AsyncClient) -> None:
    from app.main import app

    seen: list[str | None] = []

    @app.get("/__test/request-id")
    async def _probe() -> dict[str, str | None]:
        seen.append(current_request_id())
        return {"request_id": current_request_id()}

    response = await client.get("/__test/request-id", headers={"X-Request-ID": "abc"})

    assert response.json() == {"request_id": "abc"}
    assert seen == ["abc"]


# --- S25-002: metrics ------------------------------------------------------


async def test_metrics_endpoint_exposes_http_and_sandbox(client: AsyncClient) -> None:
    reset_metrics()
    await client.get("/health/live")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "http_requests_total" in body
    assert 'path="/health/live"' in body
    assert "sandbox_runs_total" in body


async def test_sandbox_metrics_recorded() -> None:
    from app.core.executor import SandboxedExecutor

    reset_metrics()
    executor = SandboxedExecutor(timeout=10, pool_size=0)

    await executor.execute_many("print(1)", [""])

    response_body = None
    from app.core.metrics import render_metrics

    response_body, _ = render_metrics()
    text = response_body.decode()
    assert "sandbox_runs_total" in text
    assert 'mode="native"' in text


# --- S25-003: liveness/readiness -------------------------------------------


async def test_liveness_ok(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_reports_checks(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code in (200, 503)
    data = response.json()
    assert data["checks"]["database"] is True
    assert "redis" in data["checks"]
    assert "llm_configured" in data["checks"]


async def test_legacy_health_still_works(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- S25-004: audit log -----------------------------------------------------


async def test_audit_records_task_lifecycle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "obs_teacher")
    admin = await _admin_token(client, db_session)

    created = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    updated = await client.patch(
        f"{TASKS_URL}/{task_id}",
        json={"title": "Сумма (обновлено)"},
        headers=auth(teacher),
    )
    assert updated.status_code == 200, updated.text

    deleted = await client.delete(f"{TASKS_URL}/{task_id}", headers=auth(teacher))
    assert deleted.status_code == 204, deleted.text

    response = await client.get(
        ADMIN_AUDIT, params={"entity_type": "task"}, headers=auth(admin)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    actions = [item["action"] for item in data["items"]]
    assert actions[:3] == ["task.deleted", "task.updated", "task.created"]
    assert data["items"][0]["entity_id"] == task_id
    assert data["items"][0]["actor_role"] == "teacher"
    assert data["items"][0]["ip"] is not None


async def test_audit_records_role_change_and_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _admin_token(client, db_session, "obs_admin2")
    student_token = await register_and_login(client, "obs_student")
    student = await UserRepository(db_session).get_by_username("obs_student")
    assert student is not None

    response = await client.patch(
        f"/api/v1/admin/users/{student.id}",
        json={"role": "teacher"},
        headers=auth(admin),
    )
    assert response.status_code == 200, response.text

    listed = await client.get(
        ADMIN_AUDIT, params={"action": "user.updated"}, headers=auth(admin)
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(item["entity_id"] == str(student.id) for item in items)

    filtered = await client.get(
        ADMIN_AUDIT, params={"actor_id": str(student.id)}, headers=auth(admin)
    )
    assert filtered.json()["total"] == 0
    # student_token нужен, чтобы пользователь точно существовал в БД
    assert student_token


async def test_audit_forbidden_for_student(client: AsyncClient) -> None:
    student = await register_and_login(client, "obs_plain")

    response = await client.get(ADMIN_AUDIT, headers=auth(student))

    assert response.status_code == 403


async def test_audit_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin_token(client, db_session, "obs_admin3")
    teacher = await teacher_token(client, db_session, "obs_teacher3")

    for index in range(3):
        payload: dict[str, Any] = dict(TASK_PAYLOAD)
        payload["title"] = f"Задача {index}"
        created = await client.post(TASKS_URL, json=payload, headers=auth(teacher))
        assert created.status_code == 201

    page = await client.get(ADMIN_AUDIT, params={"skip": 1, "limit": 2}, headers=auth(admin))

    data = page.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 3


@pytest.mark.parametrize("role", ["student"])
async def test_audit_requires_admin(client: AsyncClient, role: str) -> None:
    token = await register_and_login(client, f"obs_{role}_x")

    response = await client.get(ADMIN_AUDIT, headers=auth(token))

    assert response.status_code == 403
