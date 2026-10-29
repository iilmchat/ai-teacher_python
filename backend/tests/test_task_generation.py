"""
Тесты генерации задач через LLM (S14-003).

LLM и песочница подменяются: реальная модель и интерпретатор не нужны.
"""

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.executor import ExecutionResult, SandboxedExecutor
from app.main import app
from app.services.llm.base import LLMMessage, LLMProvider, LLMUsage
from tests.task_helpers import (
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)

GENERATED_TASK: dict[str, Any] = {
    "title": "Сумма двух чисел",
    "description": "Считайте два числа и выведите их сумму.",
    "category": "input_output",
    "tags": ["sum", "input"],
    "test_cases": [
        {"input": "2\n3\n", "expected_output": "5", "description": "Сложить"}
    ],
    "hints": ["int(input())", "Сложите", "Проверьте вывод"],
    "solution_template": "a = int(input())\nb = int(input())\nprint(a + b)\n",
}


class FakeLLM(LLMProvider):
    """Провайдер с заданным ответом и usage"""

    name = "fake"
    model = "fake-model"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.closed = False

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.last_usage = LLMUsage(prompt_tokens=100, completion_tokens=50)
        return self.reply

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        yield self.reply

    async def close(self) -> None:
        self.closed = True


class ExpectedOutputExecutor(SandboxedExecutor):
    """Песочница, возвращающая ожидаемый вывод по stdin"""

    def __init__(self, outputs: dict[str, str]) -> None:
        super().__init__(timeout=1)
        self.outputs = outputs

    async def execute(  # type: ignore[override]
        self, code: str, stdin_text: str = ""
    ) -> ExecutionResult:
        return ExecutionResult(
            success=True, output=self.outputs.get(stdin_text, "неверно")
        )


@pytest.fixture
def fake_llm() -> Iterator[FakeLLM]:
    """Подменить провайдера и песочницу в Tasks API"""
    from app.api.v1.tasks import get_executor, get_llm_provider

    provider = FakeLLM(json.dumps([GENERATED_TASK], ensure_ascii=False))
    executor = ExpectedOutputExecutor({"2\n3\n": "5"})
    app.dependency_overrides[get_llm_provider] = lambda: provider
    app.dependency_overrides[get_executor] = lambda: executor
    yield provider
    app.dependency_overrides.pop(get_llm_provider, None)
    app.dependency_overrides.pop(get_executor, None)


async def test_generate_creates_validated_task(
    client: AsyncClient, db_session: AsyncSession, fake_llm: FakeLLM
) -> None:
    """Валидная задача сохраняется, usage попадает в ответ"""
    token = await teacher_token(client, db_session, "gentteacher")

    response = await client.post(
        f"{TASKS_URL}/generate",
        json={"topic": "сложение", "difficulty": "easy", "count": 1},
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    assert len(data["created"]) == 1
    assert data["created"][0]["title"] == "Сумма двух чисел"
    assert data["created"][0]["tags"] == ["sum", "input"]
    assert data["rejected"] == []
    assert data["prompt_tokens"] == 100
    assert data["completion_tokens"] == 50
    assert fake_llm.closed is True


async def test_generate_rejects_task_with_broken_solution(
    client: AsyncClient, db_session: AsyncSession, fake_llm: FakeLLM
) -> None:
    """Если эталон не проходит тесты — задача не сохраняется"""
    from app.api.v1.tasks import get_executor

    app.dependency_overrides[get_executor] = lambda: ExpectedOutputExecutor({})
    token = await teacher_token(client, db_session, "genbroken")

    response = await client.post(
        f"{TASKS_URL}/generate",
        json={"topic": "сложение", "difficulty": "easy", "count": 1},
        headers=auth(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == []
    assert len(data["rejected"]) == 1
    assert "не прошло тесты" in data["rejected"][0]["reason"]


async def test_generate_rejects_malformed_json(
    client: AsyncClient, db_session: AsyncSession, fake_llm: FakeLLM
) -> None:
    """Не-JSON ответ модели не создаёт задач"""
    fake_llm.reply = "Вот задачи: (но это не JSON)"
    token = await teacher_token(client, db_session, "genjson")

    response = await client.post(
        f"{TASKS_URL}/generate",
        json={"topic": "сложение", "difficulty": "easy", "count": 1},
        headers=auth(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == []
    assert "Не удалось разобрать" in data["rejected"][0]["reason"]


async def test_generate_count_limit(
    client: AsyncClient, db_session: AsyncSession, fake_llm: FakeLLM
) -> None:
    """Больше 5 задач за вызов — 422"""
    token = await teacher_token(client, db_session, "genlimit")

    response = await client.post(
        f"{TASKS_URL}/generate",
        json={"topic": "сложение", "difficulty": "easy", "count": 6},
        headers=auth(token),
    )

    assert response.status_code == 422


async def test_generate_requires_teacher(client: AsyncClient) -> None:
    """Ученик не может генерировать задачи"""
    token = await register_and_login(client, "genstudent")

    response = await client.post(
        f"{TASKS_URL}/generate",
        json={"topic": "сложение", "difficulty": "easy", "count": 1},
        headers=auth(token),
    )

    assert response.status_code == 403
