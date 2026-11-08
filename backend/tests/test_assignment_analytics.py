"""Тесты drill-down по назначению (S46-003)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
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


async def _classroom(
    client: AsyncClient, token: str, name: str = "7А класс"
) -> dict[str, Any]:
    response = await client.post(
        CLASSROOMS, json={"name": name}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _join(
    client: AsyncClient, token: str, classroom: dict[str, Any]
) -> None:
    response = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(token),
    )
    assert response.status_code == 200, response.text


async def _assign(
    client: AsyncClient,
    token: str,
    classroom: dict[str, Any],
    task: dict[str, Any],
    *,
    due_at: datetime | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"task_id": task["id"]}
    if due_at is not None:
        payload["due_at"] = due_at.isoformat()
    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json=payload,
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _user_id(db: AsyncSession, username: str) -> UUID:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user.id


async def _progress(
    db: AsyncSession,
    user_id: UUID,
    task_id: str,
    *,
    status: TaskStatus,
    attempts: int,
    completed_at: datetime | None = None,
) -> None:
    db.add(
        UserTaskProgress(
            user_id=user_id,
            task_id=UUID(task_id),
            status=status,
            attempts=attempts,
            completed_at=completed_at,
        )
    )
    await db.commit()


async def _setup(
    client: AsyncClient, db: AsyncSession, prefix: str
) -> tuple[str, str, dict[str, Any], dict[str, Any], list[str]]:
    """Учитель, класс с тремя учениками, задача и назначение"""
    teacher = await teacher_token(client, db, f"{prefix}_teacher")
    classroom = await _classroom(client, teacher, f"Класс {prefix}")
    students = [f"{prefix}_s1", f"{prefix}_s2", f"{prefix}_s3"]
    tokens = []
    for username in students:
        token = await register_and_login(client, username)
        await _join(client, token, classroom)
        tokens.append(token)
    task = await _make_task(client, teacher)
    assignment = await _assign(
        client,
        teacher,
        classroom,
        task,
        due_at=datetime.utcnow() - timedelta(days=1),
    )
    return teacher, classroom["id"], task, assignment, students


async def test_assignment_analytics_aggregates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Агрегаты drill-down совпадают с матрицей прогресса класса"""
    teacher, classroom_id, task, assignment, students = await _setup(
        client, db_session, "s4603"
    )
    completed_id = await _user_id(db_session, students[0])
    progress_id = await _user_id(db_session, students[1])
    await _progress(
        db_session,
        completed_id,
        task["id"],
        status=TaskStatus.COMPLETED,
        attempts=2,
        completed_at=datetime.utcnow(),
    )
    await _progress(
        db_session,
        progress_id,
        task["id"],
        status=TaskStatus.IN_PROGRESS,
        attempts=4,
    )

    response = await client.get(
        f"{CLASSROOMS}/{classroom_id}/assignments/"
        f"{assignment['id']}/analytics",
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_students"] == 3
    assert data["completed"] == 1
    assert data["in_progress"] == 1
    assert data["not_started"] == 1
    assert data["overdue"] == 2
    assert data["attempts_total"] == 6
    assert data["attempts_distribution"] == [
        {"attempts": 0, "students": 1},
        {"attempts": 2, "students": 1},
        {"attempts": 4, "students": 1},
    ]
    assert [item["username"] for item in data["problem_students"]] == [
        students[1]
    ]
    assert data["problem_threshold"] == 3
    assert {item["username"] for item in data["students"]} == set(students)

    progress = await client.get(
        f"{CLASSROOMS}/{classroom_id}/progress", headers=auth(teacher)
    )
    assert progress.status_code == 200
    cells = [
        cell
        for cell in progress.json()["cells"]
        if cell["task_id"] == task["id"]
    ]
    by_student = {cell["student_id"]: cell for cell in cells}
    analytics_by_student = {
        item["student_id"]: item for item in data["students"]
    }
    for student_id, cell in by_student.items():
        assert analytics_by_student[student_id]["status"] == cell["status"]
        assert analytics_by_student[student_id]["attempts"] == cell["attempts"]


async def test_assignment_analytics_custom_threshold(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Порог «проблемных» учеников задаётся запросом"""
    teacher, classroom_id, task, assignment, students = await _setup(
        client, db_session, "s4603t"
    )
    await _progress(
        db_session,
        await _user_id(db_session, students[0]),
        task["id"],
        status=TaskStatus.IN_PROGRESS,
        attempts=2,
    )

    response = await client.get(
        f"{CLASSROOMS}/{classroom_id}/assignments/"
        f"{assignment['id']}/analytics?problem_threshold=1",
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["problem_threshold"] == 1
    assert [item["username"] for item in data["problem_students"]] == [
        students[0]
    ]


async def test_assignment_analytics_access_denied(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Чужой учитель и ученик получают 403"""
    teacher, classroom_id, _, assignment, students = await _setup(
        client, db_session, "s4603a"
    )
    outsider = await teacher_token(client, db_session, "s4603a_outsider")
    student = await register_and_login(client, "s4603a_pupil")

    foreign = await client.get(
        f"{CLASSROOMS}/{classroom_id}/assignments/"
        f"{assignment['id']}/analytics",
        headers=auth(outsider),
    )
    pupil = await client.get(
        f"{CLASSROOMS}/{classroom_id}/assignments/"
        f"{assignment['id']}/analytics",
        headers=auth(student),
    )

    assert foreign.status_code == 403
    assert pupil.status_code == 403
    assert teacher and students


async def test_assignment_analytics_unknown_assignment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Несуществующее назначение — 404"""
    teacher, classroom_id, _, _, _ = await _setup(
        client, db_session, "s4603u"
    )

    response = await client.get(
        f"{CLASSROOMS}/{classroom_id}/assignments/"
        "00000000-0000-0000-0000-000000000000/analytics",
        headers=auth(teacher),
    )

    assert response.status_code == 404


async def test_assignment_analytics_empty_class(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Пустое назначение: нули и пустые списки"""
    teacher = await teacher_token(client, db_session, "s4603e_teacher")
    classroom = await _classroom(client, teacher, "Пустой класс S4603")
    task = await _make_task(client, teacher)
    assignment = await _assign(client, teacher, classroom, task)

    response = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/assignments/"
        f"{assignment['id']}/analytics",
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_students"] == 0
    assert data["completed"] == 0
    assert data["not_started"] == 0
    assert data["attempts_total"] == 0
    assert data["attempts_distribution"] == []
    assert data["problem_students"] == []
    assert data["students"] == []
