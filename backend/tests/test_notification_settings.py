"""Настройки уведомлений и языка (S45-004).

Ключи `language`, `email_notifications`, `deadline_notifications`,
`deadline_days` в `users.settings`; рассылка и напоминания уважают их.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserLevel, UserRole
from app.services.notification_prefs import notification_preferences

REGISTER_URL = "/api/v1/auth/register"
SETUP_URL = "/api/v1/users/me/settings"

QUIET_ID = UUID("00000000-0000-0000-0000-000000000001")
LOUD_ID = UUID("11111111-1111-1111-1111-111111111111")


async def _register_and_login(
    client: AsyncClient, username: str, password: str = "password123"
) -> dict:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": password,
        },
    )
    return (
        await client.post(
            "/api/v1/auth/login", data={"username": username, "password": password}
        )
    ).json()


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_default_preferences() -> None:
    """Без настроек применяются значения по умолчанию"""
    assert notification_preferences(None) == {
        "language": "ru",
        "email_notifications": True,
        "deadline_notifications": True,
        "deadline_days": 3,
    }


async def test_unknown_language_falls_back() -> None:
    """Ломаный язык в старых данных не ломает сведение настроек"""
    assert notification_preferences({"language": "klingon"})["language"] == "ru"


async def test_deadline_days_is_clamped() -> None:
    """Число дней удерживается в границах 1–14"""
    assert notification_preferences({"deadline_days": 100})["deadline_days"] == 14
    assert notification_preferences({"deadline_days": 0})["deadline_days"] == 1


async def test_settings_save_and_read(client: AsyncClient) -> None:
    """PATCH /users/me/settings принимает новые ключи и сохраняет их"""
    tokens = await _register_and_login(client, "settingsave")

    response = await client.patch(
        SETUP_URL,
        json={
            "language": "en",
            "email_notifications": False,
            "deadline_notifications": True,
            "deadline_days": 7,
        },
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["language"] == "en"
    assert settings["email_notifications"] is False
    assert settings["deadline_notifications"] is True
    assert settings["deadline_days"] == 7

    # Чтение профиля возвращает те же настройки
    me = await client.get(
        "/api/v1/users/me", headers=_auth_header(tokens["access_token"])
    )
    assert me.json()["settings"]["language"] == "en"


async def test_unknown_language_rejected(client: AsyncClient) -> None:
    """Недопустимый язык отклоняется валидацией 422"""
    tokens = await _register_and_login(client, "langbad")

    response = await client.patch(
        SETUP_URL,
        json={"language": "fr"},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 422


async def test_deadline_days_bounds(client: AsyncClient) -> None:
    """deadline_days вне 1–14 отклоняется"""
    tokens = await _register_and_login(client, "daysbad")

    response = await client.patch(
        SETUP_URL,
        json={"deadline_days": 30},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 422


async def test_settings_patch_is_partial(client: AsyncClient) -> None:
    """Частичный PATCH не трогает уже сохранённые ключи"""
    tokens = await _register_and_login(client, "partialpatch")

    await client.patch(
        SETUP_URL,
        json={"email_notifications": False},
        headers=_auth_header(tokens["access_token"]),
    )
    response = await client.patch(
        SETUP_URL,
        json={"language": "en"},
        headers=_auth_header(tokens["access_token"]),
    )

    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["email_notifications"] is False
    assert settings["language"] == "en"


async def _seed_student(
    db_session: AsyncSession,
    username: str,
    settings: dict,
    user_id: UUID,
) -> User:
    now = datetime.utcnow()
    user = User(
        id=user_id,
        email=f"{username}@example.com",
        username=username,
        hashed_password="$2b$12$testing",
        role=UserRole.STUDENT,
        level=UserLevel.BASIC,
        is_active=True,
        settings=settings,
        created_at=now,
        last_active=now,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _deadline_fixture(
    db_session: AsyncSession,
    *,
    username: str,
    settings: dict,
    hours_until_due: int,
) -> int:
    """Класс с назначением и учеником с заданными настройками"""
    from app.models.classroom import (
        Assignment,
        Classroom,
        ClassroomMember,
        ClassroomRole,
    )
    from app.models.task import Task, TaskDifficulty
    from app.services.engagement_service import sync_deadline_notifications

    now = datetime.utcnow()
    student = await _seed_student(
        db_session,
        username,
        settings,
        uuid4(),
    )

    task = Task(
        title="Дедлайн-задача",
        description="Тест",
        difficulty=TaskDifficulty.EASY,
        category="test",
        is_active=True,
        created_at=now,
    )
    classroom = Classroom(
        name="5А",
        owner_id=student.id,
        join_code=f"J{uuid4().hex[:8].upper()}",
        created_at=now,
    )
    db_session.add_all([task, classroom])
    await db_session.flush()

    member = ClassroomMember(
        classroom_id=classroom.id,
        user_id=student.id,
        role=ClassroomRole.STUDENT.value,
        joined_at=now,
    )
    assignment = Assignment(
        classroom_id=classroom.id,
        task_id=task.id,
        due_at=now + timedelta(hours=hours_until_due),
        created_at=now,
    )
    db_session.add_all([member, assignment])
    await db_session.commit()

    return await sync_deadline_notifications(db_session, student.id)


def _install_recording_sender(monkeypatch) -> list[str]:
    """Подменить get_email_sender и включить e-mail-рассылку (S45-004)"""
    sent_to: list[str] = []

    class RecordingSender:
        async def send(self, *, to: str, subject: str, body: str) -> None:
            sent_to.append(to)

    import app.services.email as email_module
    from app.config import settings

    monkeypatch.setattr(settings, "notifications_email_enabled", True)
    monkeypatch.setattr(email_module, "get_email_sender", lambda: RecordingSender())
    return sent_to


async def test_deadline_disabled_no_notifications(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Выключенные уведомления о дедлайнах не создают уведомлений"""
    created = await _deadline_fixture(
        db_session,
        username="noldeads",
        settings={"deadline_notifications": False},
        hours_until_due=24,
    )
    assert created == 0


async def test_deadline_days_window(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Порог дней: дедлайн внутри окна попадает, снаружи — нет"""
    within = await _deadline_fixture(
        db_session,
        username="daywin1",
        settings={"deadline_days": 1},
        hours_until_due=12,
    )
    outside = await _deadline_fixture(
        db_session,
        username="daywin2",
        settings={"deadline_days": 1},
        hours_until_due=48,
    )

    assert within == 1
    assert outside == 0


async def test_email_notifications_respected(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    """Рассылка пропускает учеников с выключенными e-mail-уведомлениями"""
    user = await _seed_student(db_session, "quietuser", {"email_notifications": False}, QUIET_ID)
    assert user.settings["email_notifications"] is False

    sent_to = _install_recording_sender(monkeypatch)

    from app.services.classroom_service import ClassroomService

    service = ClassroomService(db_session)
    await service._send_assignment_emails(
        SimpleNamespace(name="5А"),
        [QUIET_ID],
        [SimpleNamespace(title="Задача")],
        None,
    )

    assert sent_to == []


async def test_email_notifications_sends_to_opted_in(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    """Включённые уведомления получают письмо"""
    user = await _seed_student(db_session, "louduser", {}, LOUD_ID)
    user.email = "enabled@example.com"
    await db_session.commit()

    sent_to = _install_recording_sender(monkeypatch)

    from app.services.classroom_service import ClassroomService

    service = ClassroomService(db_session)
    await service._send_assignment_emails(
        SimpleNamespace(name="5А"),
        [LOUD_ID],
        [SimpleNamespace(title="Задача")],
        None,
    )

    assert sent_to == ["enabled@example.com"]
