"""Тесты спринта 28: массовые назначения, шаблоны, журнал, email (S28)."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import email as email_module
from tests.task_helpers import TASK_PAYLOAD, TASKS_URL, auth, register_and_login, teacher_token

CLASSROOMS = "/api/v1/classrooms"
TEMPLATES = "/api/v1/teacher/assignment-templates"


class FakeSender:
    """Записывает письма вместо отправки"""

    def __init__(self, fail: bool = False) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail = fail

    async def send(self, *, to: str, subject: str, body: str) -> None:
        if self.fail:
            raise OSError("smtp is down")
        self.sent.append({"to": to, "subject": subject, "body": body})


async def _classroom(client: AsyncClient, token: str, name: str) -> dict[str, Any]:
    response = await client.post(CLASSROOMS, json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _task(client: AsyncClient, token: str, title: str) -> dict[str, Any]:
    payload = dict(TASK_PAYLOAD)
    payload["title"] = title
    response = await client.post(TASKS_URL, json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _join(client: AsyncClient, student: str, classroom_id: str) -> None:
    from uuid import UUID

    join_code = None
    response = await client.get(
        f"{CLASSROOMS}/{classroom_id}", headers=auth(student)
    )
    if response.status_code == 200:
        join_code = response.json().get("join_code")
    assert join_code is not None, response.text
    joined = await client.post(
        f"{CLASSROOMS}/join", json={"join_code": join_code}, headers=auth(student)
    )
    assert joined.status_code == 200, joined.text
    assert UUID(classroom_id)


# --- S28-001: массовые назначения ------------------------------------------


async def test_bulk_assign_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "bulk_teacher")
    classroom = await _classroom(client, teacher, "9А класс")
    first = await _task(client, teacher, "Задача 1")
    second = await _task(client, teacher, "Задача 2")

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": [first["id"], second["id"], first["id"]]},
        headers=auth(teacher),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert len(data["created"]) == 2
    assert len(data["skipped"]) == 1
    assert data["unknown"] == []

    again = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": [first["id"]]},
        headers=auth(teacher),
    )
    assert again.json()["created"] == []
    assert len(again.json()["skipped"]) == 1


async def test_bulk_assign_reports_unknown(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "bulk_teacher2")
    classroom = await _classroom(client, teacher, "9Б класс")

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=auth(teacher),
    )

    assert response.status_code == 201
    assert len(response.json()["unknown"]) == 1


async def test_bulk_assign_requires_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await teacher_token(client, db_session, "bulk_owner")
    other = await teacher_token(client, db_session, "bulk_other")
    classroom = await _classroom(client, owner, "9В класс")
    task = await _task(client, owner, "Задача 3")

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": [task["id"]]},
        headers=auth(other),
    )

    assert response.status_code == 403


# --- S28-002: шаблоны -------------------------------------------------------


async def test_template_create_apply_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "tpl_teacher")
    classroom = await _classroom(client, teacher, "10А класс")
    first = await _task(client, teacher, "Шаблонная 1")
    second = await _task(client, teacher, "Шаблонная 2")

    created = await client.post(
        TEMPLATES,
        json={"name": "Стартовый набор", "task_ids": [first["id"], second["id"]]},
        headers=auth(teacher),
    )
    assert created.status_code == 201, created.text
    template = created.json()

    listed = await client.get(TEMPLATES, headers=auth(teacher))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    applied = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/from-template",
        json={"template_id": template["id"]},
        headers=auth(teacher),
    )
    assert applied.status_code == 201, applied.text
    assert len(applied.json()["created"]) == 2

    deleted = await client.delete(
        f"{TEMPLATES}/{template['id']}", headers=auth(teacher)
    )
    assert deleted.status_code == 204


async def test_template_cannot_be_deleted_by_other(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await teacher_token(client, db_session, "tpl_owner")
    other = await teacher_token(client, db_session, "tpl_other")
    task = await _task(client, owner, "Шаблонная 3")
    template = (
        await client.post(
            TEMPLATES,
            json={"name": "Чужой", "task_ids": [task["id"]]},
            headers=auth(owner),
        )
    ).json()

    response = await client.delete(f"{TEMPLATES}/{template['id']}", headers=auth(other))

    assert response.status_code == 403


# --- S28-003: журнал оценок -------------------------------------------------


async def test_gradebook_matrix_and_csv(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "gb_teacher")
    student = await register_and_login(client, "gb_student")
    classroom = await _classroom(client, teacher, "11А класс")
    task = await _task(client, teacher, "Журнальная 1")
    join = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    assert join.status_code == 200, join.text
    await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": [task["id"]]},
        headers=auth(teacher),
    )

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/gradebook", headers=auth(teacher)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["students"]) == 1
    assert len(data["tasks"]) == 1
    assert data["cells"][0]["status"] == "not_started"
    assert data["overdue"] == 0

    csv_response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/gradebook/csv", headers=auth(teacher)
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]


async def test_gradebook_forbidden_for_student(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    teacher = await teacher_token(client, db_session, "gb_teacher2")
    student = await register_and_login(client, "gb_student2")
    classroom = await _classroom(client, teacher, "11Б класс")

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/gradebook", headers=auth(student)
    )

    assert response.status_code == 403


# --- S28-004: email-уведомления --------------------------------------------


async def test_email_sent_on_assignment(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: Any
) -> None:
    sender = FakeSender()
    monkeypatch.setattr(settings, "notifications_email_enabled", True)
    monkeypatch.setattr(email_module, "get_email_sender", lambda: sender)

    teacher = await teacher_token(client, db_session, "mail_teacher")
    student = await register_and_login(client, "mail_student")
    classroom = await _classroom(client, teacher, "12А класс")
    task = await _task(client, teacher, "Почтовая 1")
    join = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    assert join.status_code == 200

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": [task["id"]]},
        headers=auth(teacher),
    )

    assert response.status_code == 201
    assert sender.sent
    assert sender.sent[0]["to"] == "mail_student@example.com"


async def test_email_failure_does_not_break_assignment(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "notifications_email_enabled", True)
    monkeypatch.setattr(email_module, "get_email_sender", lambda: FakeSender(fail=True))

    teacher = await teacher_token(client, db_session, "mail_teacher2")
    student = await register_and_login(client, "mail_student2")
    classroom = await _classroom(client, teacher, "12Б класс")
    task = await _task(client, teacher, "Почтовая 2")
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments/bulk",
        json={"task_ids": [task["id"]]},
        headers=auth(teacher),
    )

    assert response.status_code == 201
