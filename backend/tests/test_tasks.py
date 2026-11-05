"""
Тесты Task API и прогресса (S7-005, S7-006, S7-007).

Песочница подменяется зависимостью: тесты не запускают интерпретатор,
но проверяют весь путь проверки решения и обновления прогресса.
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.executor import ExecutionResult, SandboxedExecutor
from app.db.repositories.user import UserRepository
from app.main import app
from app.models.user import UserRole

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
TASKS_URL = "/api/v1/tasks"


class CaseAwareExecutor(SandboxedExecutor):
    """Песочница: возвращает ожидаемый вывод, если решение «правильное»"""

    def __init__(self, expected: dict[str, str], *, correct: bool = True) -> None:
        super().__init__(timeout=1)
        self.expected = expected
        self.correct = correct
        self.calls: list[str] = []

    async def execute(  # type: ignore[override]
        self, code: str, stdin_text: str = ""
    ) -> ExecutionResult:
        self.calls.append(code)
        output = self.expected.get(stdin_text, "")
        return ExecutionResult(success=True, output=output if self.correct else "неверно\n")

    async def execute_many(  # type: ignore[override]
        self, code: str, stdins: list[str]
    ) -> list[ExecutionResult]:
        """Фейк не ходит в песочницу: батч — это цикл по `execute`"""
        return [await self.execute(code, stdin) for stdin in stdins]


@pytest.fixture
def executor() -> Iterator[CaseAwareExecutor]:
    """Подменить песочницу в Tasks API"""
    from app.api.v1.tasks import get_executor

    fake = CaseAwareExecutor({"2\n3\n": "5\n", "-5\n5\n": "0\n"})
    app.dependency_overrides[get_executor] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_executor, None)


async def _register_and_login(client: AsyncClient, username: str) -> str:
    await client.post(
        REGISTER_URL,
        json={
            "email": f"{username}@example.com",
            "username": username,
            "password": "password123",
        },
    )
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": "password123"}
    )
    token: str = response.json()["access_token"]
    return token


async def _make_teacher(db: AsyncSession, username: str) -> None:
    """Повысить роль пользователя напрямую в БД (adмин-эндпоинт недоступен без админа)"""
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.TEACHER)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


TASK_PAYLOAD: dict[str, Any] = {
    "title": "Сумма двух чисел",
    "description": "Считайте два числа и выведите их сумму.",
    "difficulty": "easy",
    "category": "input_output",
    "test_cases": [
        {"input": "2\n3\n", "expected_output": "5", "description": "Положительные"},
        {"input": "-5\n5\n", "expected_output": "0", "description": "С минусом"},
    ],
    "hints": ["Используйте int(input())", "Сложите два числа"],
    "solution_template": "a = int(input())\nb = int(input())\nprint(a + b)\n",
}


async def _create_teacher_token(
    client: AsyncClient, db: AsyncSession, username: str
) -> str:
    """Зарегистрировать пользователя, выдать роль teacher и вернуть токен.

    Роль читается из БД при каждом запросе, поэтому токен перевыпускать не нужно.
    """
    token = await _register_and_login(client, username)
    await _make_teacher(db, username)
    return token


async def _create_task(
    client: AsyncClient, db: AsyncSession, teacher_name: str = "teacher1"
) -> dict[str, Any]:
    """Создать задачу от имени преподавателя"""
    token = await _create_teacher_token(client, db, teacher_name)
    response = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=_auth(token))
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


# --- Создание и чтение --------------------------------------------------


async def test_student_cannot_create_task(
    client: AsyncClient, executor: CaseAwareExecutor
) -> None:
    """Студент не может создать задачу"""
    token = await _register_and_login(client, "plainstudent")

    response = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=_auth(token))

    assert response.status_code == 403


async def test_teacher_creates_task(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Преподаватель создаёт задачу с тест-кейсами"""
    task = await _create_task(client, db_session)

    assert task["title"] == TASK_PAYLOAD["title"]
    assert task["test_cases_count"] == 2
    assert task["is_active"] is True
    assert len(task["test_cases"]) == 2


async def test_list_tasks_filters(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Список задач фильтруется по сложности и категории"""
    await _create_task(client, db_session)
    token = await _register_and_login(client, "liststudent")

    easy = await client.get(
        TASKS_URL, params={"difficulty": "easy"}, headers=_auth(token)
    )
    hard = await client.get(
        TASKS_URL, params={"difficulty": "hard"}, headers=_auth(token)
    )
    by_category = await client.get(
        TASKS_URL, params={"category": "input_output"}, headers=_auth(token)
    )

    assert easy.status_code == 200
    assert len(easy.json()) >= 1
    assert hard.json() == []
    assert all(item["category"] == "input_output" for item in by_category.json())


async def test_get_task_detail_and_hints(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Карточка задачи и подсказки по индексу"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "hintstudent")

    detail = await client.get(f"{TASKS_URL}/{task['id']}", headers=_auth(token))
    hint = await client.get(f"{TASKS_URL}/{task['id']}/hints/0", headers=_auth(token))
    bad_hint = await client.get(f"{TASKS_URL}/{task['id']}/hints/99", headers=_auth(token))

    assert detail.status_code == 200
    assert detail.json()["hints"] == TASK_PAYLOAD["hints"]
    assert detail.json()["status"] == "not_started"

    assert hint.status_code == 200
    assert hint.json()["hint"] == TASK_PAYLOAD["hints"][0]
    assert hint.json()["total"] == 2

    assert bad_hint.status_code == 422


async def test_missing_task_returns_404(
    client: AsyncClient, executor: CaseAwareExecutor
) -> None:
    """Несуществующая задача — 404"""
    token = await _register_and_login(client, "missingstudent")

    response = await client.get(
        f"{TASKS_URL}/00000000-0000-0000-0000-000000000000", headers=_auth(token)
    )

    assert response.status_code == 404


# --- Проверка решения ---------------------------------------------------


async def test_submit_correct_solution_completes_task(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Правильное решение: все тесты пройдены, задача завершена"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "solver1")

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/submit",
        json={"code": "a = int(input())\nb = int(input())\nprint(a + b)"},
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["passed"] is True
    assert data["passed_count"] == 2
    assert data["status"] == "completed"
    assert data["attempts"] == 1
    assert "решена" in data["message"]

    progress = await client.get(f"{TASKS_URL}/progress", headers=_auth(token))
    assert progress.json()["completed"] == 1


async def test_submit_wrong_solution_marks_in_progress(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Неправильное решение: задача в процессе, попытка учтена"""
    from app.api.v1.tasks import get_executor

    fake = CaseAwareExecutor({"2\n3\n": "5\n", "-5\n5\n": "0\n"}, correct=False)
    app.dependency_overrides[get_executor] = lambda: fake
    try:
        task = await _create_task(client, db_session)
        token = await _register_and_login(client, "solver2")

        response = await client.post(
            f"{TASKS_URL}/{task['id']}/submit",
            json={"code": "print('неверно')"},
            headers=_auth(token),
        )
    finally:
        app.dependency_overrides.pop(get_executor, None)

    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False
    assert data["passed_count"] == 0
    assert data["status"] == "in_progress"
    assert data["results"][0]["actual_output"] == "неверно\n"


async def test_attempts_accumulate(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Каждая отправка увеличивает счётчик попыток"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "solver3")

    for _ in range(3):
        await client.post(
            f"{TASKS_URL}/{task['id']}/submit",
            json={"code": "print(1)"},
            headers=_auth(token),
        )

    progress = await client.get(f"{TASKS_URL}/progress", headers=_auth(token))
    item = next(
        entry for entry in progress.json()["items"] if entry["task_id"] == task["id"]
    )
    assert item["attempts"] == 3


async def test_progress_summary_structure(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Сводка прогресса содержит счётчики и разбивку по сложности"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "solver4")
    await client.post(
        f"{TASKS_URL}/{task['id']}/submit",
        json={"code": "print(5)"},
        headers=_auth(token),
    )

    response = await client.get(f"{TASKS_URL}/progress", headers=_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] >= 1
    assert data["completed"] == 1
    assert "easy" in data["by_difficulty"]
    assert isinstance(data["completion_rate"], float)


async def test_stats_endpoint(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Статистика отдаёт разбивку по сложности и категориям"""
    await _create_task(client, db_session)
    token = await _register_and_login(client, "solver5")

    response = await client.get(f"{TASKS_URL}/stats", headers=_auth(token))

    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] >= 1
    assert "easy" in data["by_difficulty"]
    assert "input_output" in data["by_category"]


async def test_progress_is_per_user(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Прогресс одного ученика не влияет на другого"""
    task = await _create_task(client, db_session)
    first = await _register_and_login(client, "progress1")
    second = await _register_and_login(client, "progress2")

    await client.post(
        f"{TASKS_URL}/{task['id']}/submit",
        json={"code": "print(5)"},
        headers=_auth(first),
    )

    first_progress = await client.get(f"{TASKS_URL}/progress", headers=_auth(first))
    second_progress = await client.get(f"{TASKS_URL}/progress", headers=_auth(second))

    assert first_progress.json()["completed"] == 1
    assert second_progress.json()["completed"] == 0


async def test_submit_requires_auth(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Без токена отправка решения недоступна"""
    task = await _create_task(client, db_session)

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/submit", json={"code": "print(1)"}
    )

    assert response.status_code in (401, 403)


# --- История попыток (S42-002) -------------------------------------------


async def test_submit_creates_attempt(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Каждая засчитанная отправка попадает в историю попыток"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "history1")

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/submit",
        json={"code": "a = int(input())\nb = int(input())\nprint(a + b)"},
        headers=_auth(token),
    )

    assert response.status_code == 200

    attempts = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=_auth(token)
    )
    assert attempts.status_code == 200, attempts.text
    data = attempts.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["passed"] is True
    assert data["items"][0]["passed_count"] == 2
    assert data["items"][0]["total_count"] == 2


async def test_attempt_history_is_ordered_newest_first(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Новые попытки идут первыми"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "history2")

    for _ in range(3):
        await client.post(
            f"{TASKS_URL}/{task['id']}/submit",
            json={"code": "print(1)"},
            headers=_auth(token),
        )

    attempts = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=_auth(token)
    )
    data = attempts.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    created = [item["created_at"] for item in data["items"]]
    assert created == sorted(created, reverse=True)


async def test_check_does_not_create_attempt(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Пробная проверка не попадает в историю (попытка не засчитана)"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "history3")

    await client.post(
        f"{TASKS_URL}/{task['id']}/check",
        json={"code": "print(1)"},
        headers=_auth(token),
    )

    attempts = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=_auth(token)
    )
    assert attempts.json()["total"] == 0
    assert attempts.json()["items"] == []


async def test_attempt_detail_contains_code_and_results(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Детальная попытка хранит код и разбор по кейсам"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "history4")
    code = "a = int(input())\nb = int(input())\nprint(a + b)"

    await client.post(
        f"{TASKS_URL}/{task['id']}/submit",
        json={"code": code},
        headers=_auth(token),
    )

    listing = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=_auth(token)
    )
    attempt_id = listing.json()["items"][0]["id"]

    detail = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts/{attempt_id}", headers=_auth(token)
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()
    assert data["code"] == code
    assert data["passed"] is True
    assert len(data["results"]) == 2
    assert data["results"][0]["passed"] is True


async def test_attempts_are_private_to_user(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Чужая попытка недоступна: и в списке, и по прямой ссылке"""
    task = await _create_task(client, db_session)
    owner_token = await _register_and_login(client, "history_owner")
    other_token = await _register_and_login(client, "history_other")

    await client.post(
        f"{TASKS_URL}/{task['id']}/submit",
        json={"code": "print(1)"},
        headers=_auth(owner_token),
    )

    owner_list = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=_auth(owner_token)
    )
    attempt_id = owner_list.json()["items"][0]["id"]

    other_list = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts", headers=_auth(other_token)
    )
    assert other_list.json()["total"] == 0
    assert other_list.json()["items"] == []

    other_detail = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts/{attempt_id}",
        headers=_auth(other_token),
    )
    assert other_detail.status_code == 404


async def test_attempts_require_auth(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Без токена история попыток недоступна"""
    task = await _create_task(client, db_session)

    response = await client.get(f"{TASKS_URL}/{task['id']}/attempts")

    assert response.status_code in (401, 403)


async def test_attempts_of_unknown_task_return_404(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """История несуществующей задачи — 404"""
    token = await _register_and_login(client, "history5")

    response = await client.get(
        f"{TASKS_URL}/{uuid4()}/attempts", headers=_auth(token)
    )

    assert response.status_code == 404


async def test_attempts_pagination(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Список попыток постраничный"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "history6")

    for _ in range(3):
        await client.post(
            f"{TASKS_URL}/{task['id']}/submit",
            json={"code": "print(1)"},
            headers=_auth(token),
        )

    page = await client.get(
        f"{TASKS_URL}/{task['id']}/attempts?skip=1&limit=1", headers=_auth(token)
    )
    data = page.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1


# --- Пробная проверка без траты попытки (S42-001) -------------------------


async def test_check_does_not_count_attempt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Пробная проверка не увеличивает счётчик попыток и не меняет статус"""
    from app.api.v1.tasks import get_executor

    fake = CaseAwareExecutor({"2\n3\n": "5\n", "-5\n5\n": "0\n"}, correct=False)
    app.dependency_overrides[get_executor] = lambda: fake
    try:
        task = await _create_task(client, db_session)
        token = await _register_and_login(client, "checker1")

        response = await client.post(
            f"{TASKS_URL}/{task['id']}/check",
            json={"code": "print('неверно')"},
            headers=_auth(token),
        )
    finally:
        app.dependency_overrides.pop(get_executor, None)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["practice"] is True
    assert data["passed"] is False
    assert data["attempts"] == 0
    assert data["status"] == "not_started"

    progress = await client.get(f"{TASKS_URL}/progress", headers=_auth(token))
    item = next(
        entry
        for entry in progress.json()["items"]
        if entry["task_id"] == task["id"]
    )
    assert item["attempts"] == 0
    assert item["status"] == "not_started"


async def test_check_does_not_create_progress_record(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Пробная проверка не создаёт запись прогресса (иначе задача «начата»)"""
    from app.db.repositories.task import ProgressRepository
    from app.db.repositories.user import UserRepository

    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "checker2")

    await client.post(
        f"{TASKS_URL}/{task['id']}/check",
        json={"code": "print(1)"},
        headers=_auth(token),
    )

    user = await UserRepository(db_session).get_by_username("checker2")
    assert user is not None
    record = await ProgressRepository(db_session).get_by_user_and_task(
        user.id, task["id"]
    )
    assert record is None


async def test_check_keeps_existing_attempts(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Пробная проверка не меняет уже набранные попытки"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "checker3")

    for _ in range(2):
        await client.post(
            f"{TASKS_URL}/{task['id']}/submit",
            json={"code": "print(1)"},
            headers=_auth(token),
        )

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/check",
        json={"code": "print(1)"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["attempts"] == 2


async def test_check_result_matches_submit(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Результат пробы совпадает с результатом отправки того же кода"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "checker4")
    code = "a = int(input())\nb = int(input())\nprint(a + b)"

    checked = await client.post(
        f"{TASKS_URL}/{task['id']}/check", json={"code": code}, headers=_auth(token)
    )
    submitted = await client.post(
        f"{TASKS_URL}/{task['id']}/submit", json={"code": code}, headers=_auth(token)
    )

    assert checked.status_code == 200
    assert submitted.status_code == 200
    checked_data = checked.json()
    submitted_data = submitted.json()

    assert checked_data["passed"] == submitted_data["passed"]
    assert checked_data["passed_count"] == submitted_data["passed_count"]
    assert checked_data["total_count"] == submitted_data["total_count"]
    assert checked_data["results"] == submitted_data["results"]
    assert checked_data["practice"] is True
    assert submitted_data["practice"] is False


async def test_check_requires_auth(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Без токена пробная проверка недоступна"""
    task = await _create_task(client, db_session)

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/check", json={"code": "print(1)"}
    )

    assert response.status_code in (401, 403)


async def test_check_unknown_task_returns_404(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Пробная проверка несуществующей задачи — 404"""
    token = await _register_and_login(client, "checker5")

    response = await client.post(
        f"{TASKS_URL}/{uuid4()}/check",
        json={"code": "print(1)"},
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_check_rejects_empty_code(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Пустой код отклоняется валидацией"""
    task = await _create_task(client, db_session)
    token = await _register_and_login(client, "checker6")

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/check", json={"code": ""}, headers=_auth(token)
    )

    assert response.status_code == 422


async def test_teacher_updates_and_deletes_task(
    client: AsyncClient, db_session: AsyncSession, executor: CaseAwareExecutor
) -> None:
    """Преподаватель обновляет и удаляет задачу"""
    task = await _create_task(client, db_session)
    token = await _create_teacher_token(client, db_session, "updateteacher")

    updated = await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"title": "Сумма двух чисел (обновлено)"},
        headers=_auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Сумма двух чисел (обновлено)"

    deleted = await client.delete(f"{TASKS_URL}/{task['id']}", headers=_auth(token))
    assert deleted.status_code == 204

    gone = await client.get(f"{TASKS_URL}/{task['id']}", headers=_auth(token))
    assert gone.status_code == 404


async def test_register_ignores_requested_role(client: AsyncClient) -> None:
    """Регистрация не даёт запросить роль teacher/admin"""
    response = await client.post(
        REGISTER_URL,
        json={
            "email": "sneaky@example.com",
            "username": "sneaky",
            "password": "password123",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "student"
