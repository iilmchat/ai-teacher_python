"""
Тесты оптимизации запросов и пагинации (S19-004).

Проверяют: индексы под фильтры/сортировки реально создаются моделью,
N+1 в списках классов и назначений устранён (число SQL-запросов не растёт
с числом объектов), пагинация additive-параметров работает.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.repositories.user import UserRepository
from app.models.engagement import Notification
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

CLASSROOMS = "/api/v1/classrooms"

EXPECTED_INDEXES: dict[str, set[str]] = {
    "tasks": {"idx_tasks_active_created"},
    "users": {"idx_users_role_last_active"},
    "notifications": {"idx_notifications_user_created"},
    "assignments": {"idx_assignments_due_at"},
    "chat_messages": {
        "idx_chat_messages_session_created",
        "idx_chat_messages_embedding_hnsw",
    },
}


class QueryCounter:
    """Счётчик SQL-запросов, выполненных во время блока"""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.statements: list[str] = []

    def _record(
        self,
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        self.statements.append(statement)

    def __enter__(self) -> "QueryCounter":
        event.listen(self.engine.sync_engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(self.engine.sync_engine, "before_cursor_execute", self._record)

    def matching(self, *needles: str) -> list[str]:
        """Запросы, содержащие все указанные подстроки (без учёта регистра)"""

        def matches(statement: str) -> bool:
            lowered = statement.lower()
            return all(needle.lower() in lowered for needle in needles)

        return [statement for statement in self.statements if matches(statement)]


async def _make_task(
    client: AsyncClient, token: str, title: str = "Задача"
) -> dict[str, Any]:
    payload = dict(TASK_PAYLOAD)
    payload["title"] = title
    response = await client.post(TASKS_URL, json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _make_classroom(
    client: AsyncClient, token: str, name: str
) -> dict[str, Any]:
    response = await client.post(CLASSROOMS, json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _index_names(db: AsyncSession, table: str) -> set[str]:
    result = await db.execute(
        text("select indexname from pg_indexes where tablename = :table"),
        {"table": table},
    )
    return {str(row[0]) for row in result.all()}


async def test_query_indexes_exist(db_session: AsyncSession) -> None:
    """Индексы миграций 0009/0010 присутствуют в схеме (create_all из моделей)"""
    for table, expected in EXPECTED_INDEXES.items():
        names = await _index_names(db_session, table)
        missing = expected - names
        assert not missing, f"{table}: нет индексов {missing}"


async def test_classrooms_list_does_not_scale_queries(
    client: AsyncClient, db_session: AsyncSession, test_engine: AsyncEngine
) -> None:
    """Список классов считается одним запросом, а не N+1 по members_count"""
    teacher = await teacher_token(client, db_session, "nplusteacher")
    for index in range(3):
        await _make_classroom(client, teacher, f"Класс {index}")

    counter = QueryCounter(test_engine)
    with counter:
        response = await client.get(CLASSROOMS, headers=auth(teacher))

    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 3
    # Один aggregate-запрос с JOIN и GROUP BY вместо 1 + N запросов
    assert len(counter.matching("classroom_members")) == 1


async def test_assignments_list_uses_single_count_query(
    client: AsyncClient, db_session: AsyncSession, test_engine: AsyncEngine
) -> None:
    """Счётчики выполнения назначений считаются одним GROUP BY-запросом"""
    teacher = await teacher_token(client, db_session, "assignnplus")
    student = await register_and_login(client, "assignnplusstudent")
    classroom = await _make_classroom(client, teacher, "7Н класс")
    await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    for index in range(2):
        task = await _make_task(client, teacher, f"Задача {index}")
        created = await client.post(
            f"{CLASSROOMS}/{classroom['id']}/assignments",
            json={"task_id": task["id"]},
            headers=auth(teacher),
        )
        assert created.status_code == 201, created.text

    counter = QueryCounter(test_engine)
    with counter:
        response = await client.get(
            f"{CLASSROOMS}/{classroom['id']}/assignments", headers=auth(teacher)
        )

    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 2
    assert len(counter.matching("user_task_progress", "count")) == 1


async def test_tasks_list_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /tasks: skip/limit возвращают разные страницы (порядок created_at)"""
    teacher = await teacher_token(client, db_session, "pagetasks")
    first = await _make_task(client, teacher, "Задача A")
    second = await _make_task(client, teacher, "Задача B")

    page_one = await client.get(TASKS_URL, params={"limit": 1}, headers=auth(teacher))
    page_two = await client.get(
        TASKS_URL, params={"skip": 1, "limit": 1}, headers=auth(teacher)
    )

    assert page_one.status_code == 200 and page_two.status_code == 200
    assert [item["id"] for item in page_one.json()] == [first["id"]]
    assert [item["id"] for item in page_two.json()] == [second["id"]]


async def test_teacher_tasks_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /teacher/tasks: limit и total считаются по всей таблице"""
    teacher = await teacher_token(client, db_session, "pageteacher")
    for index in range(3):
        await _make_task(client, teacher, f"Учительская {index}")

    response = await client.get(
        "/api/v1/teacher/tasks", params={"limit": 2}, headers=auth(teacher)
    )

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3


async def test_notifications_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /me/notifications: skip/limit, unread — по всем непрочитанным"""
    token = await register_and_login(client, "pagenotify")
    user = await UserRepository(db_session).get_by_username("pagenotify")
    assert user is not None
    for index in range(3):
        db_session.add(
            Notification(
                user_id=user.id,
                type="system",
                payload={"index": index},
            )
        )
    await db_session.commit()

    first_page = await client.get(
        "/api/v1/me/notifications", params={"limit": 2}, headers=auth(token)
    )
    second_page = await client.get(
        "/api/v1/me/notifications",
        params={"skip": 2, "limit": 2},
        headers=auth(token),
    )

    assert first_page.status_code == 200, first_page.text
    assert len(first_page.json()["items"]) == 2
    assert first_page.json()["unread"] == 3
    assert len(second_page.json()["items"]) == 1


async def test_classrooms_list_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /classrooms: skip/limit (additive)"""
    teacher = await teacher_token(client, db_session, "pageclasses")
    for index in range(3):
        await _make_classroom(client, teacher, f"Класс {index}")

    response = await client.get(CLASSROOMS, params={"limit": 2}, headers=auth(teacher))
    second = await client.get(
        CLASSROOMS, params={"skip": 2, "limit": 2}, headers=auth(teacher)
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert len(second.json()["items"]) == 1
