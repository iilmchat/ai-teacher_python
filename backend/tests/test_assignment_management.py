"""Тесты управления назначениями (S46-004)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.task import TaskStatus, UserTaskProgress
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

CLASSROOMS = "/api/v1/classrooms"


async def _make_task(client: AsyncClient, token: str) -> dict[str, Any]:
    response = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _setup(
    client: AsyncClient, db: AsyncSession, prefix: str
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """Учитель, класс с учеником, задача и назначение со сроком"""
    teacher = await teacher_token(client, db, f"{prefix}_teacher")
    student = await register_and_login(client, f"{prefix}_student")
    classroom_response = await client.post(
        CLASSROOMS, json={"name": f"Класс {prefix}"}, headers=auth(teacher)
    )
    assert classroom_response.status_code == 201, classroom_response.text
    classroom: dict[str, Any] = classroom_response.json()
    joined = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    assert joined.status_code == 200, joined.text
    task = await _make_task(client, teacher)
    due_at = datetime.utcnow() + timedelta(days=3)
    created = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"], "due_at": due_at.isoformat()},
        headers=auth(teacher),
    )
    assert created.status_code == 201, created.text
    assignment: dict[str, Any] = created.json()
    return teacher, classroom, task, assignment, student


async def _user_id(db: AsyncSession, username: str) -> UUID:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user.id


async def test_update_assignment_due_at(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Владелец переносит срок, ответ и список отражают новую дату"""
    teacher, classroom, _, assignment, _ = await _setup(
        client, db_session, "s4604u"
    )
    new_due = (datetime.utcnow() + timedelta(days=10)).replace(microsecond=0)

    response = await client.patch(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        json={"due_at": new_due.isoformat()},
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    assert response.json()["due_at"].startswith(
        new_due.isoformat()[:19]
    )

    listing = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/assignments", headers=auth(teacher)
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["due_at"].startswith(
        new_due.isoformat()[:19]
    )


async def test_update_assignment_requires_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Чужой учитель не переносит и не снимает назначение"""
    _, classroom, _, assignment, _ = await _setup(client, db_session, "s4604o")
    outsider = await teacher_token(client, db_session, "s4604o_outsider")

    patched = await client.patch(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        json={"due_at": None},
        headers=auth(outsider),
    )
    deleted = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        headers=auth(outsider),
    )

    assert patched.status_code == 403
    assert deleted.status_code == 403


async def test_delete_assignment_keeps_progress(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Снятие назначения удаляет его, но прогресс ученика остаётся в БД"""
    teacher, classroom, task, assignment, student = await _setup(
        client, db_session, "s4604d"
    )
    student_id = await _user_id(db_session, "s4604d_student")
    db_session.add(
        UserTaskProgress(
            user_id=student_id,
            task_id=UUID(task["id"]),
            status=TaskStatus.COMPLETED,
            attempts=2,
            completed_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    response = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        headers=auth(teacher),
    )

    assert response.status_code == 204, response.text
    listing = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/assignments", headers=auth(teacher)
    )
    assert listing.json()["items"] == []

    progress = (
        await db_session.execute(
            select(UserTaskProgress).where(
                UserTaskProgress.user_id == student_id,
                UserTaskProgress.task_id == UUID(task["id"]),
            )
        )
    ).scalar_one_or_none()
    assert progress is not None
    assert progress.attempts == 2
    assert student


async def test_delete_assignment_cancels_notifications(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """После снятия назначения у ученика не остаётся уведомления о нём"""
    teacher, classroom, _, assignment, student = await _setup(
        client, db_session, "s4604n"
    )
    before = await client.get("/api/v1/me/notifications", headers=auth(student))
    assert before.status_code == 200
    assert [
        item for item in before.json()["items"] if item["type"] == "assignment"
    ]

    await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        headers=auth(teacher),
    )
    after = await client.get("/api/v1/me/notifications", headers=auth(student))

    assert after.status_code == 200
    assert [
        item for item in after.json()["items"] if item["type"] == "assignment"
    ] == []


async def test_delete_assignment_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Повторное снятие — 204, а не ошибка"""
    teacher, classroom, _, assignment, _ = await _setup(
        client, db_session, "s4604i"
    )

    first = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        headers=auth(teacher),
    )
    second = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{assignment['id']}",
        headers=auth(teacher),
    )

    assert first.status_code == 204
    assert second.status_code == 204


async def test_update_unknown_assignment_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Несуществующее назначение: PATCH — 404, DELETE — 204 (уже нет)"""
    teacher, classroom, _, _, _ = await _setup(client, db_session, "s4604x")
    unknown = "00000000-0000-0000-0000-000000000000"

    patched = await client.patch(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{unknown}",
        json={"due_at": None},
        headers=auth(teacher),
    )
    deleted = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/assignments/{unknown}",
        headers=auth(teacher),
    )

    assert patched.status_code == 404
    assert deleted.status_code == 204
