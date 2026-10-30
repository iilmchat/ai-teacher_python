"""S20-003: endpoint × role access matrix and IDOR audit.

Каждый тест создаёт своих пользователей; БД-сессия conftest откатывается
между тестами, поэтому имена можно переиспользовать без разделения состояния.

Проверяются три класса проблем:
- анонимный доступ к защищённым маршрутам (ожидается 401/403);
- RBAC: student на teacher/admin-маршрутах, teacher на admin-маршрутах;
- IDOR: чужой ресурс (чат, история кода, уведомления, классы, задания,
  версии задач) недоступен, а списки показывают только свои объекты.

Известное расхождение (S20-003 finding): ``GET /tasks/{id}/hints/{index}``
не требует аутентификации — тест помечен ``xfail(strict=True)``; когда
маршрут починят, strict-xfail станет XPASS и напомнит убрать маркер.
"""

from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.main import app
from app.models.code import CodeExecution
from app.models.engagement import Notification
from app.models.user import User, UserRole
from app.services.llm.base import LLMMessage, LLMProvider
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

MISSING_ID = "00000000-0000-0000-0000-000000000000"
CLASSROOMS = "/api/v1/classrooms"
CHAT = "/api/v1/chat"
CODE = "/api/v1/code"
ENGAGEMENT = "/api/v1/me"
SEARCH = "/api/v1/chat/search"


class _FakeLLM(LLMProvider):
    """Минимальный LLM-фейк: тесты матрицы не должны ходить в сеть"""

    name = "fake"
    reply = "Ответ ассистента для проверки доступа."

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self.reply

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        yield self.reply


@pytest.fixture
def fake_llm() -> Iterator[None]:
    """Подменить LLM-провайдер, чтобы чат-маршруты не шли в сеть"""
    from app.api.v1.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: _FakeLLM()
    yield
    app.dependency_overrides.pop(get_llm_provider, None)


# --- Фикстуры ролей ------------------------------------------------------


async def _user(db: AsyncSession, username: str) -> User:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None, f"пользователь {username} не создан"
    return user


@pytest_asyncio.fixture
async def student(client: AsyncClient) -> str:
    """Токен обычного ученика"""
    return await register_and_login(client, "matrix_student")


@pytest_asyncio.fixture
async def other_student(client: AsyncClient) -> str:
    """Токен второго независимого ученика"""
    return await register_and_login(client, "matrix_other")


@pytest_asyncio.fixture
async def teacher(client: AsyncClient, db_session: AsyncSession) -> str:
    """Токен преподавателя"""
    return await teacher_token(client, db_session, "matrix_teacher")


@pytest_asyncio.fixture
async def admin(client: AsyncClient, db_session: AsyncSession) -> str:
    """Токен администратора (роль поднимается напрямую в БД, как в test_admin)"""
    token = await register_and_login(client, "matrix_admin")
    user = await _user(db_session, "matrix_admin")
    await UserRepository(db_session).update_role(user.id, UserRole.ADMIN)
    return token


async def _create_task(client: AsyncClient, token: str) -> dict[str, Any]:
    response = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _create_classroom(
    client: AsyncClient, token: str, name: str = "Матрица доступа"
) -> dict[str, Any]:
    response = await client.post(
        CLASSROOMS, json={"name": name}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


# --- Публичные и анонимные запросы --------------------------------------

PUBLIC_ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/v1/health", None),
    ("GET", "/api/v1/chat/levels", None),
    ("GET", "/api/v1/users/levels", None),
    ("GET", "/api/v1/code/limits", None),
    ("POST", "/api/v1/code/lint", {"code": "print(1)"}),
]

ANON_PROTECTED: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/v1/auth/me", None),
    ("GET", "/api/v1/users/me", None),
    ("GET", CHAT + "/sessions", None),
    ("POST", CHAT + "/sessions", {}),
    ("GET", SEARCH + "?q=x", None),
    ("GET", CODE + "/history", None),
    ("POST", CODE + "/execute", {"code": "print(1)"}),
    ("GET", TASKS_URL, None),
    ("GET", TASKS_URL + "/progress", None),
    ("GET", "/api/v1/teacher/students", None),
    ("GET", "/api/v1/admin/users", None),
    ("GET", CLASSROOMS, None),
    ("GET", ENGAGEMENT + "/notifications", None),
    ("POST", ENGAGEMENT + f"/notifications/{MISSING_ID}/read", None),
]


async def test_public_endpoints_available_anonymous(client: AsyncClient) -> None:
    """Справочные/служебные маршруты доступны без токена (осознанно публичные)"""
    failures = []
    for method, url, body in PUBLIC_ENDPOINTS:
        response = await client.request(method, url, json=body)
        if response.status_code != 200:
            failures.append(f"{method} {url} -> {response.status_code}")
    assert not failures, "публичные маршруты: " + "; ".join(failures)


async def test_anonymous_requests_rejected(client: AsyncClient) -> None:
    """Без токена защищённые маршруты не выполняются (401/403)"""
    failures = []
    for method, url, body in ANON_PROTECTED:
        response = await client.request(method, url, json=body)
        if response.status_code not in (401, 403):
            failures.append(f"{method} {url} -> {response.status_code}")
    assert not failures, "анонимный доступ: " + "; ".join(failures)


async def test_missing_credentials_403_and_invalid_token_401(
    client: AsyncClient,
) -> None:
    """Нет заголовка — 403 (FastAPI HTTPBearer), битый токен — 401"""
    no_header = await client.get("/api/v1/auth/me")
    bad_token = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert no_header.status_code == 403
    assert bad_token.status_code == 401


# --- RBAC: student против teacher/admin ---------------------------------

STUDENT_FORBIDDEN: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/v1/teacher/students", None),
    ("GET", "/api/v1/teacher/tasks", None),
    ("GET", "/api/v1/admin/users", None),
    ("GET", "/api/v1/admin/tasks", None),
    ("GET", "/api/v1/admin/analytics", None),
    ("GET", f"/api/v1/users/{MISSING_ID}", None),
    ("PATCH", f"/api/v1/users/{MISSING_ID}/role?role=teacher", None),
    ("POST", TASKS_URL, TASK_PAYLOAD),
    ("PATCH", f"{TASKS_URL}/{MISSING_ID}", {"title": "Взлом"}),
    ("DELETE", f"{TASKS_URL}/{MISSING_ID}", None),
    ("POST", f"{TASKS_URL}/import", {"tasks": []}),
    ("GET", f"{TASKS_URL}/{MISSING_ID}/versions", None),
    ("POST", f"{TASKS_URL}/{MISSING_ID}/versions/1/restore", None),
    ("POST", CLASSROOMS, {"name": "Чужой класс"}),
    ("GET", f"{CLASSROOMS}/{MISSING_ID}/progress", None),
]


@pytest.mark.parametrize(("method", "url", "body"), STUDENT_FORBIDDEN)
async def test_student_forbidden_on_privileged_endpoints(
    client: AsyncClient,
    student: str,
    method: str,
    url: str,
    body: dict[str, Any] | None,
) -> None:
    """Ученик получает 403 на teacher/admin-маршрутах (роль проверяется до БД)"""
    response = await client.request(method, url, json=body, headers=auth(student))

    assert response.status_code == 403, response.text


# --- RBAC: teacher против admin -----------------------------------------

TEACHER_FORBIDDEN: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/v1/admin/users", None),
    ("GET", "/api/v1/admin/tasks", None),
    ("GET", "/api/v1/admin/analytics", None),
    ("GET", f"/api/v1/users/{MISSING_ID}", None),
    ("PATCH", f"/api/v1/users/{MISSING_ID}/role?role=teacher", None),
]


@pytest.mark.parametrize(("method", "url", "body"), TEACHER_FORBIDDEN)
async def test_teacher_forbidden_on_admin_endpoints(
    client: AsyncClient,
    teacher: str,
    method: str,
    url: str,
    body: dict[str, Any] | None,
) -> None:
    """Преподаватель получает 403 на admin-маршрутах"""
    response = await client.request(method, url, json=body, headers=auth(teacher))

    assert response.status_code == 403, response.text


async def test_teacher_allowed_on_teacher_endpoints(
    client: AsyncClient, teacher: str
) -> None:
    """Преподаватель: CRUD задач и кабинет учителя доступны"""
    task = await _create_task(client, teacher)

    students = await client.get("/api/v1/teacher/students", headers=auth(teacher))
    all_tasks = await client.get("/api/v1/teacher/tasks", headers=auth(teacher))
    detail = await client.get(
        f"/api/v1/teacher/tasks/{task['id']}", headers=auth(teacher)
    )
    patched = await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"description": "Обновлено преподавателем в матрице доступа."},
        headers=auth(teacher),
    )
    versions = await client.get(
        f"{TASKS_URL}/{task['id']}/versions", headers=auth(teacher)
    )

    assert students.status_code == 200
    assert all_tasks.status_code == 200
    assert detail.status_code == 200
    assert patched.status_code == 200
    assert versions.status_code == 200


async def test_admin_allowed_everywhere(
    client: AsyncClient, admin: str, student: str
) -> None:
    """Администратор проходит и admin-, и teacher-маршруты"""
    task = await _create_task(client, admin)
    student_user = await _user_from_token(client, student)

    users = await client.get("/api/v1/admin/users", headers=auth(admin))
    tasks = await client.get("/api/v1/admin/tasks", headers=auth(admin))
    analytics = await client.get("/api/v1/admin/analytics", headers=auth(admin))
    teacher_view = await client.get("/api/v1/teacher/students", headers=auth(admin))
    profile = await client.get(
        f"/api/v1/users/{student_user['id']}", headers=auth(admin)
    )

    assert users.status_code == 200
    assert tasks.status_code == 200
    assert analytics.status_code == 200
    assert teacher_view.status_code == 200
    assert profile.status_code == 200
    assert task["title"] == TASK_PAYLOAD["title"]


async def _user_from_token(client: AsyncClient, token: str) -> dict[str, Any]:
    """Профиль владельца токена через /auth/me (id нужен для admin-маршрутов)"""
    response = await client.get("/api/v1/auth/me", headers=auth(token))
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


# --- IDOR ---------------------------------------------------------------


async def test_chat_session_idor(
    client: AsyncClient, fake_llm: None
) -> None:
    """Чужую сессию нельзя прочитать, дополнить сообщением или удалить"""
    owner = await register_and_login(client, "chat_idor_owner")
    intruder = await register_and_login(client, "chat_idor_intruder")
    session = (
        await client.post(CHAT + "/sessions", json={}, headers=auth(owner))
    ).json()

    foreign_get = await client.get(
        f"{CHAT}/sessions/{session['id']}", headers=auth(intruder)
    )
    foreign_post = await client.post(
        f"{CHAT}/sessions/{session['id']}/messages",
        json={"content": "чужой вопрос"},
        headers=auth(intruder),
    )
    foreign_delete = await client.delete(
        f"{CHAT}/sessions/{session['id']}", headers=auth(intruder)
    )
    owner_history = await client.get(
        f"{CHAT}/sessions/{session['id']}", headers=auth(owner)
    )
    missing = await client.get(
        f"{CHAT}/sessions/{MISSING_ID}", headers=auth(intruder)
    )
    intruder_list = await client.get(CHAT + "/sessions", headers=auth(intruder))

    assert foreign_get.status_code == 403
    assert foreign_post.status_code == 403
    assert foreign_delete.status_code == 403
    assert owner_history.status_code == 200
    assert missing.status_code == 404
    assert intruder_list.json() == []


async def test_chat_search_only_own_messages(
    client: AsyncClient, fake_llm: None
) -> None:
    """GET /chat/search (S19-005) не отдаёт чужие сообщения и сессии"""
    owner = await register_and_login(client, "search_idor_owner")
    intruder = await register_and_login(client, "search_idor_intruder")
    owner_session = (
        await client.post(CHAT + "/sessions", json={}, headers=auth(owner))
    ).json()
    await client.post(
        f"{CHAT}/sessions/{owner_session['id']}/messages",
        json={"content": "секретная кошка владельца"},
        headers=auth(owner),
    )
    intruder_session = (
        await client.post(CHAT + "/sessions", json={}, headers=auth(intruder))
    ).json()
    await client.post(
        f"{CHAT}/sessions/{intruder_session['id']}/messages",
        json={"content": "моя собака"},
        headers=auth(intruder),
    )

    foreign = await client.get(
        SEARCH, params={"q": "секретная"}, headers=auth(intruder)
    )
    own = await client.get(SEARCH, params={"q": "секретная"}, headers=auth(owner))

    assert foreign.status_code == 200
    assert foreign.json()["total"] == 0
    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert own.json()["items"][0]["session_id"] == owner_session["id"]


async def test_code_history_idor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """История запусков кода: список только свои, чужой id — 403, нет id — 404"""
    await register_and_login(client, "code_idor_owner")
    intruder = await register_and_login(client, "code_idor_intruder")
    owner_user = await _user(db_session, "code_idor_owner")
    record = CodeExecution(
        user_id=owner_user.id,
        code="print('secret')",
        output="secret",
        success=True,
        execution_time=0.01,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    listing = await client.get(CODE + "/history", headers=auth(intruder))
    foreign = await client.get(
        f"{CODE}/history/{record.id}", headers=auth(intruder)
    )
    missing = await client.get(
        f"{CODE}/history/{MISSING_ID}", headers=auth(intruder)
    )

    assert listing.status_code == 200
    assert all(item["id"] != str(record.id) for item in listing.json())
    assert foreign.status_code == 403
    assert missing.status_code == 404


async def test_notifications_idor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Уведомления: чужое не читается (404), список — только свои"""
    owner = await register_and_login(client, "notify_idor_owner")
    intruder = await register_and_login(client, "notify_idor_intruder")
    owner_user = await _user(db_session, "notify_idor_owner")
    notification = Notification(
        user_id=owner_user.id,
        type="assignment",
        payload={"title": "Секретное назначение"},
    )
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)

    listing = await client.get(
        ENGAGEMENT + "/notifications", headers=auth(intruder)
    )
    foreign_read = await client.post(
        f"{ENGAGEMENT}/notifications/{notification.id}/read",
        headers=auth(intruder),
    )
    missing_read = await client.post(
        f"{ENGAGEMENT}/notifications/{MISSING_ID}/read",
        headers=auth(intruder),
    )
    owner_read = await client.post(
        f"{ENGAGEMENT}/notifications/{notification.id}/read",
        headers=auth(owner),
    )

    assert listing.status_code == 200
    assert all(
        item["id"] != str(notification.id) for item in listing.json()["items"]
    )
    assert foreign_read.status_code == 404
    assert missing_read.status_code == 404
    assert owner_read.status_code == 200
    assert owner_read.json()["read_at"] is not None


async def test_my_assignments_isolated(
    client: AsyncClient, teacher: str, student: str, other_student: str
) -> None:
    """«Мои задания» видят только участники класса; чужой класс — 403"""
    task = await _create_task(client, teacher)
    classroom = await _create_classroom(client, teacher)
    joined = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    assigned = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"], "due_at": datetime(2030, 1, 1).isoformat()},
        headers=auth(teacher),
    )

    mine = await client.get(ENGAGEMENT + "/assignments", headers=auth(student))
    other_mine = await client.get(
        ENGAGEMENT + "/assignments", headers=auth(other_student)
    )
    foreign_assignments = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        headers=auth(other_student),
    )

    assert joined.status_code == 200, joined.text
    assert assigned.status_code == 201, assigned.text
    assert len(mine.json()["items"]) == 1
    assert mine.json()["items"][0]["task_id"] == task["id"]
    assert other_mine.json()["items"] == []
    assert foreign_assignments.status_code == 403


async def test_classroom_outsider_forbidden(
    client: AsyncClient, teacher: str, other_student: str
) -> None:
    """Класс и его ресурсы недоступны не-участнику"""
    classroom = await _create_classroom(client, teacher)

    listing = await client.get(CLASSROOMS, headers=auth(other_student))
    detail = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(other_student)
    )
    assignments = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        headers=auth(other_student),
    )
    progress = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/progress",
        headers=auth(other_student),
    )

    assert listing.status_code == 200
    assert listing.json()["items"] == []
    assert detail.status_code == 403
    assert assignments.status_code == 403
    assert progress.status_code == 403


async def test_classroom_non_owner_teacher_forbidden(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Другой преподаватель не управляет чужим классом (только владелец)"""
    owner = await teacher_token(client, db_session, "class_owner_teacher")
    outsider = await teacher_token(client, db_session, "class_outsider_teacher")
    classroom = await _create_classroom(client, owner)
    task = await _create_task(client, owner)
    owner_user = await _user(db_session, "class_owner_teacher")

    detail = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(outsider)
    )
    assignments = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/assignments", headers=auth(outsider)
    )
    progress = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/progress", headers=auth(outsider)
    )
    assign = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/assignments",
        json={"task_id": task["id"]},
        headers=auth(outsider),
    )
    remove = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/members/{owner_user.id}",
        headers=auth(outsider),
    )

    assert detail.status_code == 403
    assert assignments.status_code == 403
    assert progress.status_code == 403
    assert assign.status_code == 403
    assert remove.status_code == 403


async def test_task_versions_restore_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Версии задачи: ученику 403; каталог задач общий — правка другому teacher ок.

    SPEC §2: задачи — общий каталог, отдельного владения нет, поэтому
    преподаватель B может смотреть/откатывать задачу преподавателя A
    (это осознанное поведение, не IDOR: данные задач не приватны).
    """
    author = await teacher_token(client, db_session, "versions_author")
    colleague = await teacher_token(client, db_session, "versions_colleague")
    student = await register_and_login(client, "versions_student")
    task = await _create_task(client, author)
    await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"description": "Изменение для создания версии 1 в матрице."},
        headers=auth(author),
    )

    student_versions = await client.get(
        f"{TASKS_URL}/{task['id']}/versions", headers=auth(student)
    )
    student_restore = await client.post(
        f"{TASKS_URL}/{task['id']}/versions/1/restore", headers=auth(student)
    )
    colleague_versions = await client.get(
        f"{TASKS_URL}/{task['id']}/versions", headers=auth(colleague)
    )
    colleague_restore = await client.post(
        f"{TASKS_URL}/{task['id']}/versions/1/restore", headers=auth(colleague)
    )

    assert student_versions.status_code == 403
    assert student_restore.status_code == 403
    assert colleague_versions.status_code == 200
    assert colleague_restore.status_code == 200


async def test_user_profile_only_self_or_admin(
    client: AsyncClient, teacher: str, admin: str
) -> None:
    """Свой профиль — всем; чужой — только admin"""
    student = await register_and_login(client, "profile_student")
    teacher_profile = await _user_from_token(client, teacher)
    student_profile = await _user_from_token(client, student)

    own = await client.get("/api/v1/auth/me", headers=auth(student))
    foreign = await client.get(
        f"/api/v1/users/{teacher_profile['id']}", headers=auth(student)
    )
    admin_view = await client.get(
        f"/api/v1/users/{student_profile['id']}", headers=auth(admin)
    )

    assert own.status_code == 200
    assert own.json()["username"] == "profile_student"
    assert foreign.status_code == 403
    assert admin_view.status_code == 200


# --- Регрессия S20-003: auth на подсказках -------------------------------


async def test_task_hints_require_auth(
    client: AsyncClient, teacher: str, student: str
) -> None:
    """Подсказки к задаче доступны только авторизованным (S20-003 fix).

    Найденный дефект: маршрут не имел auth-зависимости и отдавал подсказку
    анонимно (200). Теперь аноним получает 401/403 (фактически 403 —
    стандартное поведение ``HTTPBearer`` для отсутствующего заголовка,
    как и на остальных защищённых маршрутах).
    """
    task = await _create_task(client, teacher)

    anonymous = await client.get(f"{TASKS_URL}/{task['id']}/hints/0")
    authorized = await client.get(
        f"{TASKS_URL}/{task['id']}/hints/0", headers=auth(student)
    )

    assert anonymous.status_code in (401, 403)
    assert "hint" not in anonymous.text
    assert authorized.status_code == 200
    assert authorized.json()["hint"] == TASK_PAYLOAD["hints"][0]
