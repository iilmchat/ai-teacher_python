"""
Тесты классов и назначений (S16-002…S16-004).
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.task import TaskStatus, UserTaskProgress
from app.models.user import User
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


async def _classroom(
    client: AsyncClient, token: str, name: str = "7А класс"
) -> dict[str, Any]:
    response = await client.post(
        CLASSROOMS, json={"name": name}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _user(db: AsyncSession, username: str) -> User:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user


async def test_teacher_creates_class_and_student_joins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Класс создаётся с кодом, ученик вступает по коду"""
    teacher = await teacher_token(client, db_session, "classteacher")
    student = await register_and_login(client, "classstudent")
    classroom = await _classroom(client, teacher)

    assert len(classroom["join_code"]) == 6
    joined = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"].lower()},
        headers=auth(student),
    )

    assert joined.status_code == 200, joined.text
    detail = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(student)
    )
    assert detail.status_code == 200
    usernames = [member["username"] for member in detail.json()["members"]]
    assert "classstudent" in usernames


async def test_join_with_wrong_code_404(client: AsyncClient, db_session: AsyncSession) -> None:
    """Неверный код — 404"""
    student = await register_and_login(client, "wrongcode")

    response = await client.post(
        f"{CLASSROOMS}/join", json={"join_code": "ZZZZZZ"}, headers=auth(student)
    )

    assert response.status_code == 404


async def test_non_member_cannot_read_class(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Чужой класс — 403"""
    teacher = await teacher_token(client, db_session, "ownerclass")
    outsider = await register_and_login(client, "outsider")
    classroom = await _classroom(client, teacher)

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(outsider)
    )

    assert response.status_code == 403


async def test_assignments_and_my_assignments(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Владелец назначает задачу, ученик видит её в «моих заданиях»"""
    teacher = await teacher_token(client, db_session, "assignteacher")
    student_token = await register_and_login(client, "assignstudent")
    task = await _make_task(client, teacher)
    classroom = await _classroom(client, teacher)
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student_token),
    )
    due = (datetime.utcnow() - timedelta(days=1)).isoformat()

    created = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"], "due_at": due},
        headers=auth(teacher),
    )
    mine = await client.get("/api/v1/me/assignments", headers=auth(student_token))

    assert created.status_code == 201, created.text
    items = mine.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == TASK_PAYLOAD["title"]
    assert items[0]["overdue"] is True


async def test_student_cannot_assign_task(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ученик не может назначать задачи"""
    teacher = await teacher_token(client, db_session, "assignowner")
    student = await register_and_login(client, "assignpupil")
    task = await _make_task(client, teacher)
    classroom = await _classroom(client, teacher)
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"]},
        headers=auth(student),
    )

    assert response.status_code == 403


async def test_duplicate_assignment_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Одну задачу нельзя назначить дважды"""
    teacher = await teacher_token(client, db_session, "dupowner")
    task = await _make_task(client, teacher)
    classroom = await _classroom(client, teacher)
    payload = {"task_id": task["id"]}

    first = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json=payload,
        headers=auth(teacher),
    )
    second = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json=payload,
        headers=auth(teacher),
    )

    assert first.status_code == 201
    assert second.status_code == 409


async def test_class_progress_matrix(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Матрица прогресса: ученик × задача"""
    teacher = await teacher_token(client, db_session, "progressteacher")
    student_token = await register_and_login(client, "progresspupil")
    task = await _make_task(client, teacher)
    classroom = await _classroom(client, teacher)
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student_token),
    )
    await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"]},
        headers=auth(teacher),
    )
    pupil = await _user(db_session, "progresspupil")
    db_session.add(
        UserTaskProgress(
            user_id=pupil.id,
            task_id=UUID(task["id"]),
            status=TaskStatus.COMPLETED,
            attempts=2,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/progress", headers=auth(teacher)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["completion_rate"] == 100.0
    assert data["cells"][0]["status"] == "completed"
    assert data["cells"][0]["attempts"] == 2


async def test_owner_can_remove_member(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Владелец удаляет ученика из класса"""
    teacher = await teacher_token(client, db_session, "removeowner")
    student_token = await register_and_login(client, "removestudent")
    classroom = await _classroom(client, teacher)
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student_token),
    )
    student = await _user(db_session, "removestudent")

    response = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/members/{student.id}",
        headers=auth(teacher),
    )
    detail = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(teacher)
    )

    assert response.status_code == 204
    assert "removestudent" not in [
        member["username"] for member in detail.json()["members"]
    ]
