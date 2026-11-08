"""Персональный экспорт данных — GET /users/me/export (S45-003).

Выгрузка содержит только собственные данные пользователя; служебная
колонка `embedding` сообщений чата в файл не попадает, хэш пароля — тем
более. Действие пишется в аудит (`user.data_exported`).
"""
import json
from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.engagement import Notification
from app.models.task import (
    AttemptFeedback,
    Task,
    TaskAttempt,
    TaskDifficulty,
    TaskStatus,
    UserTaskProgress,
)
from app.models.user import User, UserRole

REGISTER_URL = "/api/v1/auth/register"
EXPORT_URL = "/api/v1/users/me/export"


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
    login = await client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    return login.json()


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _get_user(db_session: AsyncSession, username: str) -> User:
    return (
        (await db_session.execute(select(User).where(User.username == username)))
        .scalars()
        .one()
    )


async def _create_chat_session(
    db_session: AsyncSession, user: User, question: str
) -> ChatSession:
    """Напрямую создать сессию чата с одним сообщением пользователя"""
    now = datetime.utcnow()
    session = ChatSession(
        user_id=user.id,
        level="basic",
        title=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(session)
    await db_session.flush()
    message = ChatMessage(
        session_id=session.id,
        role=MessageRole.USER,
        content=question,
        # Служебный вектор семантического поиска: в экспорт попасть не должен
        embedding=[0.1] * 1536,
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def test_export_requires_auth(client: AsyncClient) -> None:
    """Без токена выгрузка недоступна"""
    response = await client.get(EXPORT_URL)
    assert response.status_code in (401, 403)


async def test_export_returns_json_attachment(client: AsyncClient) -> None:
    """Ответ — JSON с Content-Disposition: attachment и датой в имени файла"""
    tokens = await _register_and_login(client, "exportfile")

    response = await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert "ai-teacher-export-" in disposition
    json.loads(response.content)


async def test_export_contains_profile_and_sections(client: AsyncClient) -> None:
    """Все ожидаемые разделы присутствуют, данные совпадают с профилем"""
    tokens = await _register_and_login(client, "sections")

    response = await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))
    assert response.status_code == 200
    data = json.loads(response.content)

    assert data["profile"]["username"] == "sections"
    assert data["profile"]["email"] == "sections@example.com"
    assert data["profile"]["role"] == "student"
    for key in (
        "exported_at",
        "profile",
        "task_progress",
        "task_attempts",
        "teacher_feedback",
        "chat_sessions",
        "notifications",
        "achievements",
    ):
        assert key in data


async def test_export_contains_chat_without_other_user_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Сообщения чата включены; чужие чаты — нет; embedding исключён"""
    tokens = await _register_and_login(client, "chatexport")
    user = await _get_user(db_session, "chatexport")
    other_tokens = await _register_and_login(client, "chatother")
    other_user = await _get_user(db_session, "chatother")

    await _create_chat_session(db_session, user, "мой секретный вопрос")
    await _create_chat_session(db_session, other_user, "чужой вопрос")

    response = await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))
    assert response.status_code == 200
    data = json.loads(response.content)

    assert len(data["chat_sessions"]) == 1
    message = data["chat_sessions"][0]["messages"][0]
    assert message["content"] == "мой секретный вопрос"
    assert message["role"] == "user"
    assert "embedding" not in message

    # Другой пользователь видит только своё
    other_response = await client.get(
        EXPORT_URL, headers=_auth_header(other_tokens["access_token"])
    )
    other_data = json.loads(other_response.content)
    assert len(other_data["chat_sessions"]) == 1
    assert other_data["chat_sessions"][0]["messages"][0]["content"] == "чужой вопрос"


async def test_export_attempts_and_progress(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Попытки сдачи и прогресс попадают в выгрузку"""
    tokens = await _register_and_login(client, "attemptexport")
    user = await _get_user(db_session, "attemptexport")

    # Реальная задача, чтобы соблюсти FK-целостность
    task = Task(
        title="Экспорт-задача",
        description="Тест",
        difficulty=TaskDifficulty.EASY,
        category="test",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(task)
    await db_session.flush()
    attempt = TaskAttempt(
        user_id=user.id,
        task_id=task.id,
        code="print('hi')",
        passed=True,
        passed_count=3,
        total_count=3,
        results=[],
        created_at=datetime.utcnow(),
    )
    db_session.add(attempt)
    await db_session.flush()
    teacher = User(
        email="export_feedback_teacher@example.com",
        username="export_feedback_teacher",
        hashed_password="x",
        role=UserRole.TEACHER,
    )
    db_session.add(teacher)
    await db_session.flush()
    db_session.add(
        AttemptFeedback(
            attempt_id=attempt.id,
            teacher_id=teacher.id,
            comment="Проверь ввод",
            created_at=datetime.utcnow(),
        )
    )
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

    response = await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))
    assert response.status_code == 200
    data = json.loads(response.content)

    assert len(data["task_attempts"]) == 1
    attempt_data = data["task_attempts"][0]
    assert attempt_data["code"] == "print('hi')"
    assert attempt_data["passed"] is True
    assert attempt_data["passed_count"] == 3

    assert len(data["teacher_feedback"]) == 1
    feedback = data["teacher_feedback"][0]
    assert feedback["attempt_id"] == str(attempt.id)
    assert feedback["comment"] == "Проверь ввод"
    assert feedback["teacher_name"] == "export_feedback_teacher"

    progress = data["task_progress"][0]
    assert progress["status"] == "completed"
    assert progress["attempts"] == 1
    assert "task_id" in progress


async def test_export_notifications_and_achievements(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Уведомления и достижения попадают в выгрузку"""
    tokens = await _register_and_login(client, "notifexport")
    user = await _get_user(db_session, "notifexport")
    db_session.add(
        Notification(
            user_id=user.id,
            type="assignment_created",
            payload={"classroom": "5А"},
            created_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    response = await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))
    assert response.status_code == 200
    data = json.loads(response.content)

    assert data["notifications"] != []
    assert data["notifications"][0]["type"] == "assignment_created"
    assert data["notifications"][0]["payload"]["classroom"] == "5А"
    assert data["achievements"] == []


async def test_export_password_hash_not_included(client: AsyncClient) -> None:
    """Хэш пароля и другие внутренние поля пользователя не выгружаются"""
    tokens = await _register_and_login(client, "nohash")
    response = await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))
    text = response.content.decode("utf-8")

    assert "hashed_password" not in text
    assert "$2b$" not in text  # префикс bcrypt


async def test_export_audited(client: AsyncClient, db_session: AsyncSession) -> None:
    """Выгрузка попадает в журнал аудита с привязкой к пользователю"""
    from app.models.audit import AuditLog

    tokens = await _register_and_login(client, "auditedexport")
    user = await _get_user(db_session, "auditedexport")

    await client.get(EXPORT_URL, headers=_auth_header(tokens["access_token"]))

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user.data_exported",
                    AuditLog.actor_id == user.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) >= 1
