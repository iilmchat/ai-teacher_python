"""Журнал аудита: фильтры, поиск, имя актора, пагинация и CSV (S47-001)."""

from datetime import datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.audit import AuditLog
from app.models.user import UserRole
from tests.task_helpers import auth, register_and_login

AUDIT_URL = "/api/v1/admin/audit"
EXPORT_URL = "/api/v1/admin/audit/export"


async def _admin(
    client: AsyncClient, db: AsyncSession, username: str = "audit_admin"
) -> tuple[str, str]:
    """Токен админа и его id"""
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.ADMIN)
    return token, str(user.id)


def _add_log(
    db: AsyncSession,
    *,
    actor_id: str | None,
    action: str,
    entity_type: str = "user",
    entity_id: str | None = None,
    created_at: datetime | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor_id,
        actor_role="admin",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload={"summary": "x"},
        ip="127.0.0.1",
        created_at=created_at or datetime.utcnow(),
    )
    db.add(log)
    return log


async def test_audit_filters_and_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Действие, тип сущности и поиск по action работают вместе"""
    token, admin_id = await _admin(client, db_session)
    _add_log(db_session, actor_id=admin_id, action="user.updated")
    _add_log(db_session, actor_id=admin_id, action="task.moderated", entity_type="task")
    _add_log(db_session, actor_id=admin_id, action="task.published", entity_type="task")
    await db_session.commit()

    by_action = await client.get(
        AUDIT_URL, params={"action": "user.updated"}, headers=auth(token)
    )
    by_type = await client.get(
        AUDIT_URL, params={"entity_type": "task"}, headers=auth(token)
    )
    by_search = await client.get(
        AUDIT_URL, params={"search": "MODERATED"}, headers=auth(token)
    )

    assert by_action.status_code == 200
    assert by_action.json()["total"] == 1
    assert by_action.json()["items"][0]["action"] == "user.updated"
    assert by_type.json()["total"] == 2
    assert by_search.json()["total"] == 1
    assert by_search.json()["items"][0]["action"] == "task.moderated"


async def test_audit_returns_actor_username(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Имя актора приходит из users; у удалённого аккаунта — null"""
    token, admin_id = await _admin(client, db_session, "audit_actor_admin")
    _add_log(db_session, actor_id=admin_id, action="user.updated")
    _add_log(db_session, actor_id=None, action="user.self_deleted")
    await db_session.commit()

    response = await client.get(
        AUDIT_URL, params={"search": "user."}, headers=auth(token)
    )

    assert response.status_code == 200
    items = {item["action"]: item for item in response.json()["items"]}
    assert items["user.updated"]["actor_username"] == "audit_actor_admin"
    assert items["user.self_deleted"]["actor_username"] is None


async def test_audit_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Пагинация: новые сверху, skip/limit и total"""
    token, admin_id = await _admin(client, db_session, "audit_page_admin")
    base = datetime.utcnow()
    for index in range(5):
        _add_log(
            db_session,
            actor_id=admin_id,
            action=f"test.action_{index}",
            created_at=base + timedelta(seconds=index),
        )
    await db_session.commit()

    first = await client.get(
        AUDIT_URL, params={"search": "test.action_", "limit": 2}, headers=auth(token)
    )
    second = await client.get(
        AUDIT_URL,
        params={"search": "test.action_", "skip": 2, "limit": 2},
        headers=auth(token),
    )

    assert first.json()["total"] == 5
    assert [item["action"] for item in first.json()["items"]] == [
        "test.action_4",
        "test.action_3",
    ]
    assert [item["action"] for item in second.json()["items"]] == [
        "test.action_2",
        "test.action_1",
    ]


async def test_audit_csv_matches_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """CSV отдаёт те же строки, что и список; utf-8-sig"""
    token, admin_id = await _admin(client, db_session, "audit_csv_admin")
    _add_log(db_session, actor_id=admin_id, action="user.updated")
    _add_log(db_session, actor_id=admin_id, action="task.moderated", entity_type="task")
    await db_session.commit()

    listing = await client.get(
        AUDIT_URL, params={"entity_type": "task"}, headers=auth(token)
    )
    exported = await client.get(
        EXPORT_URL, params={"entity_type": "task"}, headers=auth(token)
    )

    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert exported.content.startswith(b"\xef\xbb\xbf")
    text = exported.content.decode("utf-8-sig")
    lines = [line for line in text.splitlines() if line]
    # Заголовок + столько строк, сколько отдал список
    assert len(lines) == listing.json()["total"] + 1
    assert lines[0].startswith("created_at,action,actor_username")
    assert "task.moderated" in text
    assert "audit_csv_admin" in text


async def test_audit_export_is_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Выгрузка журнала пишет audit.exported без текста фильтров-ПДн"""
    token, _ = await _admin(client, db_session, "audit_export_admin")

    await client.get(EXPORT_URL, headers=auth(token))

    response = await client.get(
        AUDIT_URL, params={"action": "audit.exported"}, headers=auth(token)
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    payload = response.json()["items"][0]["payload"]
    assert set(payload) == {"action", "entity_type", "actor_id", "has_search", "limit"}


async def test_audit_forbidden_for_non_admin(client: AsyncClient) -> None:
    """Ученик и аноним не видят журнал и не выгружают его"""
    student = await register_and_login(client, "audit_student")

    listing = await client.get(AUDIT_URL, headers=auth(student))
    export = await client.get(EXPORT_URL, headers=auth(student))
    anonymous = await client.get(AUDIT_URL)

    assert listing.status_code == 403
    assert export.status_code == 403
    assert anonymous.status_code in (401, 403)


async def test_audit_unknown_actor_everything_ok(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Фильтр по случайному actor_id не падает и возвращает пусто"""
    token, _ = await _admin(client, db_session, "audit_random_admin")

    response = await client.get(
        AUDIT_URL, params={"actor_id": str(uuid4())}, headers=auth(token)
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
