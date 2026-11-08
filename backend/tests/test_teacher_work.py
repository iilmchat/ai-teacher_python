"""Тесты спринта 46: работы учеников и комментарии учителя (S46-001, S46-002)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.executor import ExecutionResult, SandboxedExecutor
from app.db.repositories.user import UserRepository
from app.main import app
from app.models.audit import AuditLog
from app.models.user import UserRole
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

CLASSROOMS = "/api/v1/classrooms"
TEACHER = "/api/v1/teacher"


class CorrectExecutor(SandboxedExecutor):
    """Песочница, которая всегда возвращает ожидаемый вывод"""

    def __init__(self, expected: dict[str, str]) -> None:
        super().__init__(timeout=1)
        self.expected = expected

    async def execute(  # type: ignore[override]
        self, code: str, stdin_text: str = ""
    ) -> ExecutionResult:
        return ExecutionResult(
            success=True, output=self.expected.get(stdin_text, "")
        )

    async def execute_many(  # type: ignore[override]
        self, code: str, stdins: list[str]
    ) -> list[ExecutionResult]:
        return [await self.execute(code, stdin) for stdin in stdins]


@pytest.fixture
def executor() -> Iterator[CorrectExecutor]:
    """Подменить песочницу: попытки ученика проходят все тест-кейсы"""
    from app.api.v1.tasks import get_executor

    fake = CorrectExecutor({"2\n3\n": "5\n", "-5\n5\n": "0\n"})
    app.dependency_overrides[get_executor] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_executor, None)


async def _role_token(
    client: AsyncClient,
    db: AsyncSession,
    username: str,
    role: UserRole = UserRole.ADMIN,
) -> str:
    token = await register_and_login(client, username)
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, role)
    return token


async def _classroom(client: AsyncClient, token: str, name: str) -> dict[str, Any]:
    response = await client.post(
        CLASSROOMS, json={"name": name}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _task(
    client: AsyncClient, token: str, title: str = "Сумма"
) -> dict[str, Any]:
    payload = dict(TASK_PAYLOAD)
    payload["title"] = title
    response = await client.post(TASKS_URL, json=payload, headers=auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _join(
    client: AsyncClient, student: str, classroom: dict[str, Any]
) -> None:
    response = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(student),
    )
    assert response.status_code == 200, response.text


async def _submit(
    client: AsyncClient, student: str, task_id: str, code: str | None = None
) -> dict[str, Any]:
    response = await client.post(
        f"{TASKS_URL}/{task_id}/submit",
        json={"code": code or "a = int(input())\nb = int(input())\nprint(a + b)"},
        headers=auth(student),
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def _student_with_attempt(
    client: AsyncClient, db: AsyncSession, teacher_name: str, student_name: str
) -> tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Учитель, ученик в его классе, задача и одна засчитанная попытка"""
    teacher = await teacher_token(client, db, teacher_name)
    student = await register_and_login(client, student_name)
    classroom = await _classroom(client, teacher, f"Класс {teacher_name}")
    await _join(client, student, classroom)
    task = await _task(client, teacher, f"Задача {student_name}")
    attempt = await _submit(client, student, task["id"])
    return teacher, student, classroom, task, attempt


# --- S46-001: просмотр работ ученика ---------------------------------------


async def test_teacher_lists_student_attempts(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Владелец класса видит попытки ученика с названием задачи и счётом"""
    teacher, student, _, task, _ = await _student_with_attempt(
        client, db_session, "t46_teacher", "t46_student"
    )
    student_user = await UserRepository(db_session).get_by_username("t46_student")
    assert student_user is not None

    response = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts", headers=auth(teacher)
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["task_id"] == task["id"]
    assert item["task_title"] == task["title"]
    assert item["passed"] is True
    assert item["passed_count"] == 2
    assert student


async def test_teacher_reads_attempt_detail(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Детальная работа содержит код и разбор по тест-кейсам"""
    teacher, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_detail_teacher", "t46_detail_student"
    )
    student_user = await UserRepository(db_session).get_by_username(
        "t46_detail_student"
    )
    assert student_user is not None
    listing = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts", headers=auth(teacher)
    )
    attempt_id = listing.json()["items"][0]["id"]

    response = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts/{attempt_id}",
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["student_id"] == str(student_user.id)
    assert "print(a + b)" in data["code"]
    assert len(data["results"]) == 2
    assert all(result["passed"] for result in data["results"])


async def test_foreign_teacher_gets_403(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Учитель чужого класса не видит работы ученика"""
    _, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_owner", "t46_foreign_student"
    )
    outsider = await teacher_token(client, db_session, "t46_outsider")
    student_user = await UserRepository(db_session).get_by_username(
        "t46_foreign_student"
    )
    assert student_user is not None

    listing = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts", headers=auth(outsider)
    )
    detail = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts/"
        "00000000-0000-0000-0000-000000000000",
        headers=auth(outsider),
    )

    assert listing.status_code == 403
    assert detail.status_code == 403


async def test_unknown_student_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Несуществующий ученик — 404, а не 403"""
    teacher = await teacher_token(client, db_session, "t46_no_student")

    response = await client.get(
        f"{TEACHER}/students/00000000-0000-0000-0000-000000000000/attempts",
        headers=auth(teacher),
    )

    assert response.status_code == 404


async def test_admin_sees_any_student(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Администратор не привязан к классам"""
    _, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_admin_teacher", "t46_admin_student"
    )
    admin = await _role_token(client, db_session, "t46_admin")
    student_user = await UserRepository(db_session).get_by_username(
        "t46_admin_student"
    )
    assert student_user is not None

    response = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts", headers=auth(admin)
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_best_solution_returned_in_progress(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """`best_solution` читается: последнее успешное решение в карточке"""
    teacher, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_best_teacher", "t46_best_student"
    )
    student_user = await UserRepository(db_session).get_by_username(
        "t46_best_student"
    )
    assert student_user is not None

    response = await client.get(
        f"{TEACHER}/students/{student_user.id}/progress", headers=auth(teacher)
    )

    assert response.status_code == 200, response.text
    completed = [
        item
        for item in response.json()["items"]
        if item["status"] == "completed"
    ]
    assert completed
    assert "print(a + b)" in completed[0]["best_solution"]


# --- S46-002: комментарий учителя к попытке ---------------------------------


async def _first_attempt_id(
    client: AsyncClient, db: AsyncSession, teacher: str, student_name: str
) -> tuple[str, str]:
    """Id ученика и его единственной попытки"""
    student_user = await UserRepository(db).get_by_username(student_name)
    assert student_user is not None
    listing = await client.get(
        f"{TEACHER}/students/{student_user.id}/attempts", headers=auth(teacher)
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert items
    return str(student_user.id), items[0]["id"]


async def test_teacher_feedback_visible_to_student(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Комментарий учителя виден ученику в истории и детали попытки"""
    teacher, student, _, task, _ = await _student_with_attempt(
        client, db_session, "t46_fb_teacher", "t46_fb_student"
    )
    student_user = await UserRepository(db_session).get_by_username(
        "t46_fb_student"
    )
    assert student_user is not None
    attempt_id = (
        await client.get(
            f"{TEACHER}/students/{student_user.id}/attempts",
            headers=auth(teacher),
        )
    ).json()["items"][0]["id"]

    response = await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "Молодец, но добавь проверку ввода"},
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    created = response.json()
    assert created["comment"] == "Молодец, но добавь проверку ввода"
    assert created["teacher_name"] == "t46_fb_teacher"

    history = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=auth(student)
    )
    assert history.status_code == 200, history.text
    feedback = history.json()["items"][0]["feedback"]
    assert len(feedback) == 1
    assert feedback[0]["comment"] == "Молодец, но добавь проверку ввода"
    assert feedback[0]["teacher_name"] == "t46_fb_teacher"

    detail = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts/{attempt_id}", headers=auth(student)
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["feedback"][0]["comment"] == created["comment"]


async def test_feedback_sends_notification(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Ученик получает in-app уведомление о комментарии"""
    teacher, student, _, task, _ = await _student_with_attempt(
        client, db_session, "t46_fb_notify_teacher", "t46_fb_notify_student"
    )
    student_id, attempt_id = await _first_attempt_id(
        client, db_session, teacher, "t46_fb_notify_student"
    )
    assert student_id
    await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "Разбери второй тест"},
        headers=auth(teacher),
    )

    response = await client.get("/api/v1/me/notifications", headers=auth(student))

    assert response.status_code == 200, response.text
    feedback_items = [
        item for item in response.json()["items"]
        if item["type"] == "attempt_feedback"
    ]
    assert len(feedback_items) == 1
    payload = feedback_items[0]["payload"]
    assert payload["attempt_id"] == attempt_id
    assert payload["task_id"] == task["id"]
    assert payload["teacher"] == "t46_fb_notify_teacher"
    assert payload["title"] == task["title"]


async def test_feedback_validation(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Пустой и слишком длинный комментарий — 422"""
    teacher, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_fb_val_teacher", "t46_fb_val_student"
    )
    _, attempt_id = await _first_attempt_id(
        client, db_session, teacher, "t46_fb_val_student"
    )

    empty = await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": ""},
        headers=auth(teacher),
    )
    too_long = await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "x" * 2001},
        headers=auth(teacher),
    )

    assert empty.status_code == 422
    assert too_long.status_code == 422


async def test_feedback_upsert_updates_comment(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Повторный комментарий того же учителя обновляет текст, не дублирует"""
    teacher, student, _, task, _ = await _student_with_attempt(
        client, db_session, "t46_fb_up_teacher", "t46_fb_up_student"
    )
    _, attempt_id = await _first_attempt_id(
        client, db_session, teacher, "t46_fb_up_student"
    )

    first = await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "Первый вариант"},
        headers=auth(teacher),
    )
    second = await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "Уточнённый вариант"},
        headers=auth(teacher),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    history = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=auth(student)
    )
    feedback = history.json()["items"][0]["feedback"]
    assert len(feedback) == 1
    assert feedback[0]["comment"] == "Уточнённый вариант"


async def test_feedback_access_denied_for_foreign_teacher(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Чужой учитель не комментирует попытку: 403, неизвестная — 404"""
    owner, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_fb_owner", "t46_fb_foreign"
    )
    _, attempt_id = await _first_attempt_id(
        client, db_session, owner, "t46_fb_foreign"
    )
    outsider = await teacher_token(client, db_session, "t46_fb_outsider")

    forbidden = await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "Текст"},
        headers=auth(outsider),
    )
    unknown = await client.post(
        f"{TEACHER}/attempts/00000000-0000-0000-0000-000000000000/feedback",
        json={"comment": "Текст"},
        headers=auth(outsider),
    )

    assert forbidden.status_code == 403
    assert unknown.status_code == 404


async def test_feedback_writes_audit(
    client: AsyncClient, db_session: AsyncSession, executor: CorrectExecutor
) -> None:
    """Комментарий учителя попадает в журнал аудита"""
    teacher, _, _, _, _ = await _student_with_attempt(
        client, db_session, "t46_fb_audit_teacher", "t46_fb_audit_student"
    )
    _, attempt_id = await _first_attempt_id(
        client, db_session, teacher, "t46_fb_audit_student"
    )
    await client.post(
        f"{TEACHER}/attempts/{attempt_id}/feedback",
        json={"comment": "Аудит"},
        headers=auth(teacher),
    )

    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "attempt.feedback_added",
                AuditLog.entity_id == attempt_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["length"] == len("Аудит")

