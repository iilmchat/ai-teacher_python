"""
Тесты центра уведомлений (S47-005).

Массовое прочтение, фильтр по типу и безопасные ссылки в payload новых
уведомлений (D-007).
"""

from datetime import datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.engagement import Notification
from app.models.user import User
from app.services.engagement_service import (
    create_announcement_notifications,
    create_assignment_notifications,
    create_feedback_notification,
)
from tests.task_helpers import auth, register_and_login

NOTIFICATIONS_URL = "/api/v1/me/notifications"


async def _student(db: AsyncSession, username: str) -> User:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return user


def _notification(user_id: object, type_: str, payload: dict | None = None) -> Notification:
    return Notification(
        user_id=user_id,
        type=type_,
        payload=payload or {},
    )


async def test_read_all_marks_only_own_unread(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """read-all ставит read_at только своим непрочитанным."""
    token = await register_and_login(client, "notify_all")
    owner = await _student(db_session, "notify_all")
    await register_and_login(client, "notify_other")
    other = await _student(db_session, "notify_other")

    db_session.add_all(
        [
            _notification(owner.id, "assignment", {"title": "A"}),
            _notification(owner.id, "deadline", {"title": "D"}),
            _notification(owner.id, "achievement", {"title": "C"}),
            _notification(other.id, "assignment", {"title": "O"}),
        ]
    )
    await db_session.commit()
    # Одно уведомление владельца уже прочитано — оно не должно попасть в счётчик
    already = _notification(owner.id, "achievement", {"title": "old"})
    already.read_at = datetime.utcnow()
    db_session.add(already)
    await db_session.commit()

    before = await client.get(NOTIFICATIONS_URL, headers=auth(token))
    assert before.status_code == 200
    assert before.json()["unread"] == 3

    read_all = await client.post(
        f"{NOTIFICATIONS_URL}/read-all", headers=auth(token)
    )

    assert read_all.status_code == 200, read_all.text
    assert read_all.json() == {"updated": 3}

    after = await client.get(NOTIFICATIONS_URL, headers=auth(token))
    assert after.json()["unread"] == 0
    assert all(item["read_at"] is not None for item in after.json()["items"])

    other_items = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == other.id)
        )
    ).scalars().all()
    assert len(other_items) == 1
    assert other_items[0].read_at is None

    again = await client.post(
        f"{NOTIFICATIONS_URL}/read-all", headers=auth(token)
    )
    assert again.json() == {"updated": 0}


async def test_filter_notifications_by_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Фильтр type возвращает только выбранный тип, unread остаётся общим."""
    token = await register_and_login(client, "notify_filter")
    user = await _student(db_session, "notify_filter")
    db_session.add_all(
        [
            _notification(user.id, "assignment", {"title": "A"}),
            _notification(user.id, "deadline", {"title": "D"}),
            _notification(user.id, "achievement", {"title": "C"}),
        ]
    )
    await db_session.commit()

    filtered = await client.get(
        NOTIFICATIONS_URL, params={"type": "deadline"}, headers=auth(token)
    )
    empty = await client.get(
        NOTIFICATIONS_URL, params={"type": "unknown"}, headers=auth(token)
    )

    assert filtered.status_code == 200, filtered.text
    assert [item["type"] for item in filtered.json()["items"]] == ["deadline"]
    assert filtered.json()["unread"] == 3
    assert empty.json()["items"] == []
    assert empty.json()["unread"] == 3


async def test_new_notifications_have_safe_links_and_task_id(
    db_session: AsyncSession,
) -> None:
    """Создатели кладут относительный link и task_id там, где он нужен."""
    # Пользователь создаётся напрямую: проверяем только payload создателей.
    from app.core.security import hash_password

    user = User(
        email="links@example.com",
        username="links",
        hashed_password=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    classroom_id = uuid4()
    task_id = uuid4()
    assignment_id = uuid4()
    attempt_id = uuid4()
    announcement_id = uuid4()

    await create_assignment_notifications(
        db_session,
        [user.id],
        classroom_id=classroom_id,
        classroom_name="7Б",
        assignment_id=assignment_id,
        task_id=task_id,
        task_title="Циклы",
        due_at=datetime.utcnow() + timedelta(days=3),
    )
    await create_feedback_notification(
        db_session,
        user.id,
        attempt_id=attempt_id,
        task_id=task_id,
        task_title="Циклы",
        teacher_name="Учитель",
    )
    await create_announcement_notifications(
        db_session,
        [user.id],
        classroom_id=classroom_id,
        classroom_name="7Б",
        announcement_id=announcement_id,
        title="Контрольная",
    )

    rows = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == user.id)
        )
    ).scalars().all()
    by_type = {item.type: item.payload for item in rows}

    assert by_type["assignment"]["link"] == "/assignments"
    assert by_type["assignment"]["task_id"] == str(task_id)
    assert by_type["attempt_feedback"]["link"] == f"/tasks/{task_id}"
    assert by_type["attempt_feedback"]["task_id"] == str(task_id)
    assert by_type["announcement"]["link"] == f"/classrooms/{classroom_id}"
