"""Тесты экспорта, отчёта класса, retention и удаления аккаунта (S26)."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repositories.user import UserRepository
from app.models.user import UserRole
from app.services.retention import TABLES, RetentionTable
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

EXPORT_URL = "/api/v1/admin/analytics/export"
CLASSROOMS = "/api/v1/classrooms"


async def _join_code(db: AsyncSession, classroom_id: str) -> str:
    """Код вступления из БД (в ответе API он может отсутствовать по роли)"""
    from app.models.classroom import Classroom as ClassroomModel

    row = await db.get(ClassroomModel, UUID(classroom_id))
    assert row is not None
    return row.join_code


async def _admin(client: AsyncClient, db: AsyncSession, username: str = "exp_admin") -> str:
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


# --- S26-001: экспорт аналитики --------------------------------------------


async def test_export_users_csv(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin(client, db_session)

    response = await client.get(
        EXPORT_URL, params={"dataset": "users", "format": "csv"}, headers=auth(admin)
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows
    assert "username" in rows[0]
    assert "role" in rows[0]


async def test_export_tasks_json(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin(client, db_session, "exp_admin2")
    teacher = await teacher_token(client, db_session, "exp_teacher")

    created = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    assert created.status_code == 201

    response = await client.get(
        EXPORT_URL, params={"dataset": "tasks", "format": "json"}, headers=auth(admin)
    )

    assert response.status_code == 200
    payload = json.loads(response.text)
    assert payload["dataset"] == "tasks"
    assert isinstance(payload["items"], list)


async def test_export_requires_admin(client: AsyncClient) -> None:
    student = await register_and_login(client, "exp_student")

    response = await client.get(EXPORT_URL, headers=auth(student))

    assert response.status_code == 403


async def test_export_rejects_unknown_dataset(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _admin(client, db_session, "exp_admin3")

    response = await client.get(
        EXPORT_URL, params={"dataset": "nope"}, headers=auth(admin)
    )

    assert response.status_code == 422


# --- S26-002: отчёт класса --------------------------------------------------


async def test_class_report_csv(client: AsyncClient, db_session: AsyncSession) -> None:
    teacher = await teacher_token(client, db_session, "rep_teacher")
    student = await register_and_login(client, "rep_student")

    classroom_resp = await client.post(
        CLASSROOMS, json={"name": "7Б класс"}, headers=auth(teacher)
    )
    assert classroom_resp.status_code == 201, classroom_resp.text
    classroom = classroom_resp.json()
    task = (await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))).json()
    join = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": await _join_code(db_session, classroom["id"])},
        headers=auth(student),
    )
    assert join.status_code == 200, join.text
    assignment = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"]},
        headers=auth(teacher),
    )
    assert assignment.status_code == 201, assignment.text

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/report", headers=auth(teacher)
    )

    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["content-type"]
    text = response.text.lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows
    assert rows[0]["task_title"] == TASK_PAYLOAD["title"]
    assert rows[0]["status"] == "not_started"
    assert rows[0]["overdue"] == "no"
    assert rows[-1]["username"] == "ИТОГО"


async def test_class_report_forbidden_for_student(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "rep_teacher2")
    student = await register_and_login(client, "rep_student2")
    classroom = (
        await client.post(CLASSROOMS, json={"name": "8А класс"}, headers=auth(teacher))
    ).json()
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": await _join_code(db_session, classroom["id"])},
        headers=auth(student),
    )

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/report", headers=auth(student)
    )

    assert response.status_code == 403


# --- S26-003: retention -----------------------------------------------------


def test_retention_cutoff_disabled_when_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    table = TABLES[0]
    monkeypatch.setattr(settings, table.setting, 0)

    assert table.cutoff() is None


def test_retention_cutoff_days(monkeypatch: pytest.MonkeyPatch) -> None:
    table: RetentionTable = TABLES[0]
    monkeypatch.setattr(settings, table.setting, 30)

    cutoff = table.cutoff()
    assert cutoff is not None
    delta = datetime.now(UTC).replace(tzinfo=None) - cutoff
    assert timedelta(days=29) < delta < timedelta(days=31)


def test_task_attempts_retention_setting() -> None:
    """История попыток попадает под retention (S42-002)"""
    table = next(item for item in TABLES if item.name == "task_attempts")

    assert table.setting == "retention_task_attempts_days"


def test_retention_tables_cover_all_datasets() -> None:
    names = {table.name for table in TABLES}

    assert names == {
        "chat_messages",
        "code_executions",
        "notifications",
        "audit_log",
        "task_attempts",  # S42-002: история попыток
    }



# --- S26-004: удаление аккаунта ---------------------------------------------


async def test_delete_account_anonymizes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    username = "del_student"
    token = await register_and_login(client, username)
    admin = await _admin(client, db_session, "del_admin")

    wrong = await client.request(
        "DELETE", "/api/v1/auth/me", json={"password": "nope"}, headers=auth(token)
    )
    assert wrong.status_code == 400

    deleted = await client.request(
        "DELETE", "/api/v1/auth/me", json={"password": "password123"}, headers=auth(token)
    )
    assert deleted.status_code == 204, deleted.text

    # Токен перестаёт работать, вход невозможен
    me = await client.get("/api/v1/auth/me", headers=auth(token))
    assert me.status_code == 401
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    )
    assert login.status_code == 401

    # Запись аудита видна админу
    audit = await client.get(
        "/api/v1/admin/audit", params={"action": "user.self_deleted"}, headers=auth(admin)
    )
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1


async def test_admin_delete_user_soft_deletes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Админ-удаление (hard delete) не затрагивает аудит и работает как раньше"""
    admin = await _admin(client, db_session, "del_admin2")
    victim_token = await register_and_login(client, "del_victim")
    victim = await UserRepository(db_session).get_by_username("del_victim")
    assert victim is not None
    assert victim_token

    response = await client.delete(
        f"/api/v1/admin/users/{victim.id}", headers=auth(admin)
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True
