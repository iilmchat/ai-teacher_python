"""
Тесты модерации задач (S47-003).

Очередь — только LLM-генерация и импорт. Задачи, созданные учителем вручную,
в очередь не попадают, но их можно снять с публикации. Метрики считаются по
засчитанным попыткам и сводке прогресса.
"""

from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.audit import AuditLog
from app.models.task import (
    Task,
    TaskAttempt,
    TaskDifficulty,
    TaskStatus,
    UserTaskProgress,
)
from app.models.user import User, UserRole
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

ADMIN_REVIEW_URL = "/api/v1/admin/tasks/review"
ADMIN_MODERATE_URL = "/api/v1/admin/tasks/{task_id}/moderate"


def _admin_url(task_id: object) -> str:
    return ADMIN_MODERATE_URL.format(task_id=task_id)


async def _admin_token(
    client: AsyncClient, db: AsyncSession, username: str
) -> str:
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token


async def _student(
    client: AsyncClient, db: AsyncSession, username: str
) -> User:
    await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user


async def _make_task(
    db: AsyncSession,
    *,
    title: str,
    source: str,
    difficulty: TaskDifficulty = TaskDifficulty.EASY,
    is_active: bool = True,
    moderation_comment: str | None = None,
) -> Task:
    task = Task(
        title=title,
        description=f"Условие задачи «{title}».",
        difficulty=difficulty,
        category="moderation",
        source=source,
        is_active=is_active,
        moderation_comment=moderation_comment,
        tags=["moderation"],
        test_cases=[{"input": "1\n", "expected_output": "1"}],
        hints=["Подсказка"],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _add_attempts(
    db: AsyncSession,
    *,
    user: User,
    task: Task,
    attempts: int,
    passed_attempts: int,
    status: TaskStatus,
) -> None:
    db.add(
        UserTaskProgress(
            user_id=user.id,
            task_id=task.id,
            status=status,
            attempts=attempts,
            completed_at=None,
        )
    )
    for index in range(attempts):
        db.add(
            TaskAttempt(
                user_id=user.id,
                task_id=task.id,
                code=f"print({index})",
                passed=index < passed_attempts,
                passed_count=1 if index < passed_attempts else 0,
                total_count=1,
                results=[],
            )
        )
    await db.commit()


# --- Очередь ------------------------------------------------------------


async def test_queue_contains_only_generated_and_imported(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Задачи, созданные вручную, в очередь не попадают."""
    token = await _admin_token(client, db_session, "modadmin1")
    await _make_task(db_session, title="Ручная", source="manual")
    generated = await _make_task(
        db_session, title="Сгенерированная", source="generated"
    )
    imported = await _make_task(
        db_session, title="Импортированная", source="imported"
    )

    response = await client.get(ADMIN_REVIEW_URL, headers=auth(token))

    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Сгенерированная", "Импортированная"}
    assert {item["id"] for item in data["items"]} == {
        str(generated.id),
        str(imported.id),
    }
    assert data["total"] == 2
    assert data["threshold"] == 3


async def test_queue_metrics_and_problem_sorting(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Метрики: попытки, успешность, среднее, ученики и застрявшие."""
    token = await _admin_token(client, db_session, "modadmin2")
    task = await _make_task(
        db_session, title="Проблемная", source="generated"
    )
    quiet = await _make_task(
        db_session, title="Без попыток", source="imported"
    )
    manual = await _make_task(db_session, title="Ручная", source="manual")

    first = await _student(client, db_session, "modpupil1")
    second = await _student(client, db_session, "modpupil2")
    third = await _student(client, db_session, "modpupil3")
    await _add_attempts(
        db_session,
        user=first,
        task=task,
        attempts=5,
        passed_attempts=1,
        status=TaskStatus.IN_PROGRESS,
    )
    await _add_attempts(
        db_session,
        user=second,
        task=task,
        attempts=2,
        passed_attempts=2,
        status=TaskStatus.COMPLETED,
    )
    await _add_attempts(
        db_session,
        user=third,
        task=task,
        attempts=4,
        passed_attempts=0,
        status=TaskStatus.IN_PROGRESS,
    )
    # Ручная задача не должна влиять на очередь даже при большом числе попыток
    await _add_attempts(
        db_session,
        user=first,
        task=manual,
        attempts=15,
        passed_attempts=0,
        status=TaskStatus.IN_PROGRESS,
    )

    response = await client.get(
        ADMIN_REVIEW_URL, params={"threshold": 3}, headers=auth(token)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["title"] for item in data["items"]] == [
        "Проблемная",
        "Без попыток",
    ]
    metrics = data["items"][0]["metrics"]
    assert metrics["attempts"] == 11
    assert metrics["passed_attempts"] == 3
    assert metrics["success_rate"] == 0.2727
    assert metrics["avg_attempts"] == 3.67
    assert metrics["students"] == 3
    assert metrics["stuck_students"] == 2
    assert len(data["items"][0]["recent_attempts"]) == 5
    assert data["items"][1]["id"] == str(quiet.id)
    assert data["items"][1]["metrics"] == {
        "attempts": 0,
        "passed_attempts": 0,
        "success_rate": 0.0,
        "avg_attempts": 0.0,
        "students": 0,
        "stuck_students": 0,
    }
    assert data["items"][1]["recent_attempts"] == []


async def test_queue_filters_by_source_and_difficulty(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Фильтры очереди: источник и сложность."""
    token = await _admin_token(client, db_session, "modadmin3")
    await _make_task(db_session, title="Gen easy", source="generated")
    await _make_task(
        db_session,
        title="Gen hard",
        source="generated",
        difficulty=TaskDifficulty.HARD,
    )
    await _make_task(
        db_session,
        title="Imported easy",
        source="imported",
        difficulty=TaskDifficulty.EASY,
    )

    by_source = await client.get(
        ADMIN_REVIEW_URL, params={"source": "generated"}, headers=auth(token)
    )
    by_difficulty = await client.get(
        ADMIN_REVIEW_URL, params={"difficulty": "hard"}, headers=auth(token)
    )
    combined = await client.get(
        ADMIN_REVIEW_URL,
        params={"source": "imported", "difficulty": "easy"},
        headers=auth(token),
    )

    assert by_source.json()["total"] == 2
    assert all(item["source"] == "generated" for item in by_source.json()["items"])
    assert [item["title"] for item in by_difficulty.json()["items"]] == ["Gen hard"]
    assert [item["title"] for item in combined.json()["items"]] == [
        "Imported easy"
    ]


# --- Действия модератора -------------------------------------------------


async def _moderate(
    client: AsyncClient, token: str, task_id: object, payload: dict[str, Any]
) -> Any:
    return await client.post(
        _admin_url(task_id), json=payload, headers=auth(token)
    )


async def test_publish_clears_comment_and_writes_audit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Публикация включает задачу, очищает комментарий и пишет аудит."""
    token = await _admin_token(client, db_session, "modadmin4")
    task = await _make_task(
        db_session,
        title="На публикацию",
        source="generated",
        is_active=False,
        moderation_comment="Вернуть в доработку",
    )

    response = await _moderate(client, token, task.id, {"action": "publish"})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_active"] is True
    assert data["moderation_comment"] is None
    await db_session.refresh(task)
    assert task.is_active is True
    assert task.moderation_comment is None

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "task.moderated")
        )
    ).scalars().all()
    assert [item.payload["action"] for item in audit] == ["publish"]
    assert "comment_length" not in audit[0].payload


async def test_return_to_revision_saves_comment_and_writes_length(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Возврат в доработку требует комментарий и сохраняет его."""
    token = await _admin_token(client, db_session, "modadmin5")
    task = await _make_task(
        db_session, title="В доработку", source="imported", is_active=True
    )
    comment = "  Тесты не соответствуют условию  "

    response = await _moderate(
        client,
        token,
        task.id,
        {"action": "return_to_revision", "comment": comment},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_active"] is False
    assert data["moderation_comment"] == comment.strip()
    await db_session.refresh(task)
    assert task.moderation_comment == comment.strip()

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "task.moderated")
        )
    ).scalars().all()
    assert audit[0].payload == {
        "action": "return_to_revision",
        "comment_length": len(comment.strip()),
    }
    assert comment.strip() not in str(audit[0].payload)


async def test_return_to_revision_validates_comment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Пустой, отсутствующий и слишком длинный комментарий — 422."""
    token = await _admin_token(client, db_session, "modadmin6")
    task = await _make_task(db_session, title="Валидация", source="generated")

    missing = await _moderate(
        client, token, task.id, {"action": "return_to_revision"}
    )
    blank = await _moderate(
        client, token, task.id, {"action": "return_to_revision", "comment": "   "}
    )
    too_long = await _moderate(
        client,
        token,
        task.id,
        {"action": "return_to_revision", "comment": "x" * 1001},
    )

    assert missing.status_code == 422
    assert blank.status_code == 422
    assert too_long.status_code == 422


async def test_unpublish_any_task_but_manual_cannot_be_published(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Модератор снимает любую задачу; ручную нельзя вернуть в очередь."""
    token = await _admin_token(client, db_session, "modadmin7")
    manual = await _make_task(db_session, title="Ручная", source="manual")

    unpublish = await _moderate(
        client, token, manual.id, {"action": "unpublish"}
    )
    publish = await _moderate(client, token, manual.id, {"action": "publish"})
    revision = await _moderate(
        client,
        token,
        manual.id,
        {"action": "return_to_revision", "comment": "Не трогать"},
    )

    assert unpublish.status_code == 200
    assert unpublish.json()["is_active"] is False
    assert publish.status_code == 422
    assert revision.status_code == 422


async def test_moderate_unknown_task_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _admin_token(client, db_session, "modadmin8")

    response = await _moderate(client, token, uuid4(), {"action": "publish"})

    assert response.status_code == 404


async def test_publish_affects_student_catalog(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Снятая задача исчезает из каталога ученика, публикация возвращает."""
    token = await _admin_token(client, db_session, "modadmin9")
    task = await _make_task(
        db_session, title="Видимость", source="generated", is_active=False
    )
    student_token = await register_and_login(client, "modpupil5")

    hidden = await client.get(TASKS_URL, headers=auth(student_token))
    assert str(task.id) not in {item["id"] for item in hidden.json()}

    await _moderate(client, token, task.id, {"action": "publish"})
    visible = await client.get(TASKS_URL, headers=auth(student_token))
    assert str(task.id) in {item["id"] for item in visible.json()}

    await _moderate(client, token, task.id, {"action": "unpublish"})
    hidden_again = await client.get(TASKS_URL, headers=auth(student_token))
    assert str(task.id) not in {item["id"] for item in hidden_again.json()}


# --- Права и происхождение ----------------------------------------------


async def test_moderation_requires_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Очередь и действия доступны только администратору."""
    student_token = await register_and_login(client, "modstudent")
    teacher_token_value = await teacher_token(
        client, db_session, "modteacher"
    )
    task = await _make_task(db_session, title="Права", source="generated")

    student_queue = await client.get(
        ADMIN_REVIEW_URL, headers=auth(student_token)
    )
    teacher_queue = await client.get(
        ADMIN_REVIEW_URL, headers=auth(teacher_token_value)
    )
    anonymous = await client.get(ADMIN_REVIEW_URL)
    student_action = await _moderate(
        client, student_token, task.id, {"action": "publish"}
    )
    teacher_action = await _moderate(
        client, teacher_token_value, task.id, {"action": "publish"}
    )

    assert student_queue.status_code == 403
    assert teacher_queue.status_code == 403
    assert anonymous.status_code in (401, 403)
    assert student_action.status_code == 403
    assert teacher_action.status_code == 403


async def test_teacher_created_task_is_manual(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ручное создание через API проставляет source='manual'."""
    token = await teacher_token(client, db_session, "modcreator")

    response = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(token))

    assert response.status_code == 201, response.text
    task = (
        await db_session.execute(
            select(Task).where(Task.title == TASK_PAYLOAD["title"])
        )
    ).scalar_one()
    assert task.source == "manual"
