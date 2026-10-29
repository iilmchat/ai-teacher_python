"""
Тесты Teacher API (S15): ученики, прогресс, все задачи, импорт-файл.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.task import Task, TaskDifficulty, TaskStatus, UserTaskProgress
from app.models.user import User
from tests.task_helpers import (
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)


async def _make_task(db: AsyncSession, title: str, *, active: bool = True) -> Task:
    task = Task(
        title=title,
        description=f"Описание задачи {title}.",
        difficulty=TaskDifficulty.EASY,
        category="loops",
        test_cases=[{"input": "", "expected_output": "1"}],
        hints=["hint"],
        solution_template="print(1)",
        is_active=active,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _student(db: AsyncSession, username: str) -> User:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user


async def test_teacher_lists_students_with_aggregates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Учитель видит учеников, число решённых задач и попыток"""
    teacher = await teacher_token(client, db_session, "tstudents")
    await register_and_login(client, "pupil_a")
    pupil = await _student(db_session, "pupil_a")
    task = await _make_task(db_session, "Задача для прогресса")
    db_session.add(
        UserTaskProgress(
            user_id=pupil.id,
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            attempts=2,
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/teacher/students", headers=auth(teacher)
    )

    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    item = next(row for row in data["items"] if row["username"] == "pupil_a")
    assert item["completed_tasks"] == 1
    assert item["attempts"] == 2


async def test_teacher_sees_student_progress(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Карточка ученика содержит прогресс по задачам"""
    teacher = await teacher_token(client, db_session, "tprogress")
    await register_and_login(client, "pupil_b")
    pupil = await _student(db_session, "pupil_b")
    task = await _make_task(db_session, "Задача прогресса 2")
    db_session.add(
        UserTaskProgress(
            user_id=pupil.id,
            task_id=task.id,
            status=TaskStatus.IN_PROGRESS,
            attempts=3,
        )
    )
    await db_session.commit()

    response = await client.get(
        f"/api/v1/teacher/students/{pupil.id}/progress",
        headers=auth(teacher),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["student"]["username"] == "pupil_b"
    assert data["in_progress"] == 1
    row = next(item for item in data["items"] if item["task_id"] == str(task.id))
    assert row["attempts"] == 3
    assert row["status"] == "in_progress"


async def test_teacher_tasks_include_inactive(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Учитель видит и деактивированные задачи"""
    teacher = await teacher_token(client, db_session, "ttasks")
    await _make_task(db_session, "Активная", active=True)
    await _make_task(db_session, "Выключенная", active=False)

    response = await client.get("/api/v1/teacher/tasks", headers=auth(teacher))

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert "Выключенная" in titles


async def test_student_cannot_use_teacher_api(client: AsyncClient) -> None:
    """Ученик получает 403 на всех маршрутах учителя"""
    token = await register_and_login(client, "notateacher")

    assert (
        await client.get("/api/v1/teacher/students", headers=auth(token))
    ).status_code == 403
    assert (
        await client.get("/api/v1/teacher/tasks", headers=auth(token))
    ).status_code == 403


async def test_teacher_progress_missing_student_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Несуществующий ученик — 404"""
    teacher = await teacher_token(client, db_session, "tmissing")

    response = await client.get(
        "/api/v1/teacher/students/00000000-0000-0000-0000-000000000000/progress",
        headers=auth(teacher),
    )

    assert response.status_code == 404


async def test_import_preview_and_file(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Предпросмотр и загрузка файла возвращают отчёт импорта"""
    teacher = await teacher_token(client, db_session, "timport")
    content = (
        '{"tasks": ['
        '{"title": "Из файла", "description": "Описание из файла задачи.", '
        '"difficulty": "easy", "test_cases": [{"input": "", "expected_output": "1"}]},'
        '{"title": "Битая", "description": "коротко", "test_cases": []}'
        "]}"
    )

    preview = await client.post(
        f"{TASKS_URL}/import/preview",
        json={"content": content},
        headers=auth(teacher),
    )
    upload = await client.post(
        f"{TASKS_URL}/import/file",
        files={"file": ("tasks.json", content.encode(), "application/json")},
        headers=auth(teacher),
    )

    assert preview.status_code == 200
    assert preview.json()["tasks"] == 1
    assert len(preview.json()["errors"]) == 1
    assert upload.status_code == 200
    assert upload.json()["created"] == 1
