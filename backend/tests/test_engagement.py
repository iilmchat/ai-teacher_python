"""
Тесты достижений, статистики и уведомлений (S17-001…S17-004).
"""

from datetime import datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.engagement import Notification, UserAchievement
from app.models.task import Task, TaskDifficulty, TaskStatus, UserTaskProgress
from app.models.user import User
from app.services.engagement_service import (
    evaluate_achievements,
    max_streak,
    stats,
)
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

CLASSROOMS = "/api/v1/classrooms"


async def _make_task(
    db: AsyncSession, title: str, difficulty: TaskDifficulty = TaskDifficulty.EASY
) -> Task:
    task = Task(
        title=title,
        description=f"Описание задачи {title}.",
        difficulty=difficulty,
        category="loops",
        test_cases=[{"input": "", "expected_output": "1"}],
        hints=["hint"],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _student(db: AsyncSession, username: str) -> User:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user


def test_max_streak_counts_consecutive_days() -> None:
    base = datetime(2026, 10, 1)
    dates = [base, base + timedelta(days=1), base + timedelta(days=3)]

    assert max_streak(dates) == 2


async def test_first_task_achievement_and_notification(
    db_session: AsyncSession,
) -> None:
    """Первая решённая задача выдаёт достижение и уведомление"""

    # Пользователь создаётся напрямую: БД-сессия теста транзакционная
    from app.core.security import hash_password

    user = User(
        email="achieve@example.com",
        username="achieve",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    task = await _make_task(db_session, "Достижение 1")
    db_session.add(
        UserTaskProgress(
            user_id=user.id,
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            attempts=1,
            completed_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    achievements = await evaluate_achievements(db_session, user.id)

    codes = {item.code for item in achievements}
    assert "first_task" in codes
    earned = (
        await db_session.execute(
            UserAchievement.__table__.select().where(
                UserAchievement.user_id == user.id
            )
        )
    ).all()
    assert earned
    notifications = (
        await db_session.execute(
            Notification.__table__.select().where(
                Notification.user_id == user.id,
                Notification.type == "achievement",
            )
        )
    ).all()
    assert notifications


async def test_stats_reports_streak_and_attempts(
    db_session: AsyncSession,
) -> None:
    """Статистика: решено, серия дней, средние попытки"""
    from app.core.security import hash_password

    user = User(
        email="stats@example.com",
        username="statsuser",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    for index in range(3):
        task = await _make_task(db_session, f"Серия {index}")
        db_session.add(
            UserTaskProgress(
                user_id=user.id,
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                attempts=2,
                completed_at=datetime.utcnow() - timedelta(days=index),
            )
        )
    await db_session.commit()

    data = await stats(db_session, user.id)

    assert data["solved"] == 3
    assert data["streak_days"] == 3
    assert data["avg_attempts"] == 2.0


async def test_achievements_and_stats_endpoints(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /me/achievements и /me/stats"""
    token = await register_and_login(client, "statsapi")
    user = await _student(db_session, "statsapi")
    task = await _make_task(db_session, "API достижение")
    db_session.add(
        UserTaskProgress(
            user_id=user.id,
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            attempts=1,
            completed_at=datetime.utcnow(),
        )
    )
    await db_session.commit()
    await evaluate_achievements(db_session, user.id)

    achievements = await client.get("/api/v1/me/achievements", headers=auth(token))
    stats_response = await client.get("/api/v1/me/stats", headers=auth(token))

    assert achievements.status_code == 200
    assert any(item["code"] == "first_task" for item in achievements.json()["items"])
    assert stats_response.status_code == 200
    assert stats_response.json()["solved"] == 1


async def test_assignment_notification_and_read(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Назначение создаёт уведомление, его можно прочитать"""
    teacher = await teacher_token(client, db_session, "notifyteacher")
    student = await register_and_login(client, "notifystudent")
    task = (
        await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    ).json()
    classroom = (
        await client.post(
            CLASSROOMS, json={"name": "7Б класс"}, headers=auth(teacher)
        )
    ).json()
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={
            "task_id": task["id"],
            "due_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        },
        headers=auth(teacher),
    )

    response = await client.get("/api/v1/me/notifications", headers=auth(student))

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assignment_items = [
        item for item in data["items"] if item["type"] == "assignment"
    ]
    assert assignment_items
    assert data["unread"] >= 1
    assignment_payload = assignment_items[0]["payload"]
    assert assignment_payload["link"] == "/assignments"
    assert assignment_payload["task_id"] == task["id"]

    notification_id = assignment_items[0]["id"]
    read = await client.post(
        f"/api/v1/me/notifications/{notification_id}/read",
        headers=auth(student),
    )
    assert read.status_code == 200
    assert read.json()["read_at"] is not None


async def test_deadline_notification_created(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Дедлайн в ближайшие 72 часа создаёт уведомление deadline"""
    teacher = await teacher_token(client, db_session, "deadlineteacher")
    student = await register_and_login(client, "deadlinestudent")
    task = (
        await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    ).json()
    classroom = (
        await client.post(
            CLASSROOMS, json={"name": "7В класс"}, headers=auth(teacher)
        )
    ).json()
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={
            "task_id": task["id"],
            "due_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        },
        headers=auth(teacher),
    )

    response = await client.get("/api/v1/me/notifications", headers=auth(student))

    deadline_items = [
        item for item in response.json()["items"] if item["type"] == "deadline"
    ]
    assert deadline_items
    assert deadline_items[0]["payload"]["link"] == "/assignments"
    assert deadline_items[0]["payload"]["task_id"] == task["id"]


async def test_notification_of_other_user_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Чужое уведомление нельзя прочитать"""
    await register_and_login(client, "notifyowner")
    other = await register_and_login(client, "notifyother")
    user = await _student(db_session, "notifyowner")
    notification = Notification(
        user_id=user.id, type="assignment", payload={"title": "x"}
    )
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)

    response = await client.post(
        f"/api/v1/me/notifications/{notification.id}/read",
        headers=auth(other),
    )

    assert response.status_code == 404
