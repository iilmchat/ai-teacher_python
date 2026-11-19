"""Карточка пользователя, мягкая деактивация и bulk (S47-002)."""

from datetime import datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.audit import AuditLog
from app.models.task import Task, TaskDifficulty, TaskStatus, UserTaskProgress
from app.models.user import User, UserRole, UserSession
from tests.task_helpers import auth, register_and_login

USERS_URL = "/api/v1/admin/users"


async def _admin(
    client: AsyncClient, db: AsyncSession, username: str = "users_admin"
) -> tuple[str, User]:
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    await db.refresh(user)
    return token, user


async def _user(
    client: AsyncClient, db: AsyncSession, username: str
) -> tuple[str, User]:
    """Регистрирует/логинит пользователя и возвращает (токен, модель)"""
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return token, user


async def _task(db: AsyncSession, title: str) -> Task:
    task = Task(
        title=title,
        description=f"Описание задачи {title}.",
        difficulty=TaskDifficulty.EASY,
        category="test",
        test_cases=[{"input": "", "expected_output": "x"}],
        hints=[],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _sessions(db: AsyncSession, user_id: object) -> list[UserSession]:
    return list(
        (
            await db.execute(
                select(UserSession).where(UserSession.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )


# --- Карточка пользователя ------------------------------------------------


async def test_user_detail_contains_profile_progress_audit_and_sessions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Карточка: профиль, решено/попытки, последние действия и активные сессии"""
    admin_token, _ = await _admin(client, db_session, "detail_admin")
    _, student = await _user(client, db_session, "detail_student")

    completed = await _task(db_session, "Карточка: решено")
    started = await _task(db_session, "Карточка: в процессе")
    db_session.add_all(
        [
            UserTaskProgress(
                user_id=student.id,
                task_id=completed.id,
                status=TaskStatus.COMPLETED,
                attempts=2,
                completed_at=datetime.utcnow(),
            ),
            UserTaskProgress(
                user_id=student.id,
                task_id=started.id,
                status=TaskStatus.IN_PROGRESS,
                attempts=1,
            ),
        ]
    )
    await db_session.commit()

    # Действие «по пользователю» — смена роли админом
    await client.patch(
        f"{USERS_URL}/{student.id}",
        json={"level": "advanced"},
        headers=auth(admin_token),
    )

    response = await client.get(
        f"{USERS_URL}/{student.id}", headers=auth(admin_token)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["username"] == "detail_student"
    assert data["user"]["is_active"] is True
    assert data["progress"] == {"solved": 1, "attempts": 3}
    assert data["audit"]
    assert any(item["action"] == "user.updated" for item in data["audit"])
    assert any(item["actor_username"] == "detail_admin" for item in data["audit"])
    assert data["sessions"]
    session = data["sessions"][0]
    assert set(session) == {"id", "created_at", "last_used_at", "user_agent", "ip"}


async def test_user_detail_unknown_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token, _ = await _admin(client, db_session, "detail404_admin")

    response = await client.get(f"{USERS_URL}/{uuid4()}", headers=auth(admin_token))

    assert response.status_code == 404


async def test_user_detail_forbidden_for_student(client: AsyncClient) -> None:
    token = await register_and_login(client, "detail_plain")

    response = await client.get(f"{USERS_URL}/{uuid4()}", headers=auth(token))

    assert response.status_code == 403


# --- Мягкая деактивация (D-004) -------------------------------------------


async def test_deactivation_revokes_sessions_and_bumps_token_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """is_active=false: сессии отозваны, token_version увеличен, аудит записан"""
    admin_token, _ = await _admin(client, db_session, "deact_admin")
    _, target = await _user(client, db_session, "deact_target")
    # Второе устройство
    await client.post(
        "/api/v1/auth/login",
        data={"username": "deact_target", "password": "password123"},
    )
    version_before = target.token_version
    sessions_before = await _sessions(db_session, target.id)
    assert len(sessions_before) >= 2

    response = await client.patch(
        f"{USERS_URL}/{target.id}",
        json={"is_active": False},
        headers=auth(admin_token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False
    await db_session.refresh(target)
    assert target.is_active is False
    assert target.token_version == version_before + 1
    sessions = await _sessions(db_session, target.id)
    assert sessions and all(item.revoked_at is not None for item in sessions)

    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user.deactivated",
                AuditLog.entity_id == str(target.id),
            )
        )
    ).scalars().all()
    assert audit


async def test_activation_writes_activated_audit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Повторная активация возвращает доступ, но старые сессии не оживают"""
    admin_token, _ = await _admin(client, db_session, "react_admin")
    _, target = await _user(client, db_session, "react_target")
    await client.patch(
        f"{USERS_URL}/{target.id}",
        json={"is_active": False},
        headers=auth(admin_token),
    )

    response = await client.patch(
        f"{USERS_URL}/{target.id}",
        json={"is_active": True},
        headers=auth(admin_token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True
    sessions = await _sessions(db_session, target.id)
    assert sessions and all(item.revoked_at is not None for item in sessions)
    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "user.activated")
        )
    ).scalars().all()
    assert audit


async def test_admin_cannot_deactivate_self(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token, admin = await _admin(client, db_session, "self_deact_admin")

    response = await client.patch(
        f"{USERS_URL}/{admin.id}",
        json={"is_active": False},
        headers=auth(admin_token),
    )

    assert response.status_code == 400
    await db_session.refresh(admin)
    assert admin.is_active is True


# --- Bulk (D-005) ---------------------------------------------------------


async def test_bulk_partial_success_and_skipped_reasons(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Bulk применяется к валидным, объясняет пропуски и не трогает остальных"""
    admin_token, admin = await _admin(client, db_session, "bulk_admin")
    _, student = await _user(client, db_session, "bulk_student")
    _, teacher = await _user(client, db_session, "bulk_teacher")
    _, other_admin = await _user(client, db_session, "bulk_other_admin")
    await UserRepository(db_session).update_role(other_admin.id, UserRole.ADMIN)
    _, unchanged = await _user(client, db_session, "bulk_unchanged")
    await UserRepository(db_session).update_role(unchanged.id, UserRole.TEACHER)
    await UserRepository(db_session).update(unchanged.id, is_active=False)
    missing = uuid4()
    version_before = student.token_version

    response = await client.patch(
        f"{USERS_URL}/bulk",
        json={
            "user_ids": [
                str(student.id),
                str(teacher.id),
                str(other_admin.id),
                str(unchanged.id),
                str(missing),
                str(admin.id),
            ],
            "changes": {"role": "teacher", "is_active": False},
        },
        headers=auth(admin_token),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data["updated"]) == {str(student.id), str(teacher.id)}
    reasons = {item["id"]: item["reason"] for item in data["skipped"]}
    assert reasons[str(other_admin.id)] == "admin_role"
    assert reasons[str(unchanged.id)] == "no_changes"
    assert reasons[str(missing)] == "not_found"
    assert reasons[str(admin.id)] == "self"

    await db_session.refresh(student)
    await db_session.refresh(teacher)
    await db_session.refresh(other_admin)
    await db_session.refresh(unchanged)
    assert student.role == UserRole.TEACHER and student.is_active is False
    assert teacher.role == UserRole.TEACHER and teacher.is_active is False
    assert student.token_version == version_before + 1
    # Пропущенные не изменены
    assert other_admin.role == UserRole.ADMIN and other_admin.is_active is True
    assert unchanged.role == UserRole.TEACHER and unchanged.is_active is False
    sessions = await _sessions(db_session, student.id)
    assert sessions and all(item.revoked_at is not None for item in sessions)

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "user.bulk_updated")
        )
    ).scalars().all()
    assert audit
    payload = audit[-1].payload
    assert payload["updated"] == 2
    assert payload["skipped"] == 4
    assert payload["deactivated"] == 2
    assert "user_ids" not in payload


async def test_bulk_empty_updated_is_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Если менять нечего — 200 и пустой updated, без ошибки"""
    admin_token, admin = await _admin(client, db_session, "bulk_empty_admin")

    response = await client.patch(
        f"{USERS_URL}/bulk",
        json={"user_ids": [str(admin.id)], "changes": {"role": "student"}},
        headers=auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["updated"] == []
    assert response.json()["skipped"] == [
        {"id": str(admin.id), "reason": "self"}
    ]


async def test_bulk_requires_at_least_one_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token, _ = await _admin(client, db_session, "bulk_validate_admin")

    response = await client.patch(
        f"{USERS_URL}/bulk",
        json={"user_ids": [str(uuid4())], "changes": {}},
        headers=auth(admin_token),
    )

    assert response.status_code == 422


async def test_bulk_limit_100_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_token, _ = await _admin(client, db_session, "bulk_limit_admin")

    response = await client.patch(
        f"{USERS_URL}/bulk",
        json={
            "user_ids": [str(uuid4()) for _ in range(101)],
            "changes": {"is_active": False},
        },
        headers=auth(admin_token),
    )

    assert response.status_code == 422


async def test_bulk_forbidden_for_student(client: AsyncClient) -> None:
    token = await register_and_login(client, "bulk_plain")

    response = await client.patch(
        f"{USERS_URL}/bulk",
        json={"user_ids": [str(uuid4())], "changes": {"is_active": False}},
        headers=auth(token),
    )

    assert response.status_code == 403
