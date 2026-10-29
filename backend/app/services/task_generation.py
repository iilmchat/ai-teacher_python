"""
Генерация задач через LLM с проверкой в песочнице (S14-003).

Модель возвращает JSON-массив задач; каждая задача валидируется схемой и
обязательно проверяется: эталонное решение прогоняется на всех тест-кейсах.
Невалидные задачи не сохраняются и попадают в отчёт `rejected`.
"""

import json
from typing import Any

import structlog
from pydantic import ValidationError as PydanticValidationError

from app.core.executor import SandboxedExecutor
from app.core.test_runner import run_test_cases
from app.schemas.task import (
    TaskCreate,
    TaskGenerateError,
    TaskGenerateRequest,
)
from app.services.llm.base import LLMMessage, LLMProvider, LLMUsage

logger = structlog.get_logger(__name__)

GENERATION_SYSTEM_PROMPT = """Ты — методист и преподаватель Python для школьников 10–17 лет.
Ты создаёшь учебные задачи с автопроверкой.

Верни ТОЛЬКО JSON-массив задач (без markdown и пояснений). Каждый элемент:
{{
  "title": "краткое название",
  "description": "условие задачи, что подаётся на вход и что вывести",
  "category": "категория (например, loops, strings, lists)",
  "tags": ["2-4 тега"],
  "test_cases": [
    {{"input": "данные", "expected_output": "ответ", "description": "что проверяем"}}
  ],
  "hints": ["подсказка 1", "подсказка 2", "подсказка 3"],
  "solution_template": "полный код на Python, который читает input() и печатает ответ"
}}

Требования:
- ровно {count} задач по теме «{topic}»;
- сложность: {difficulty};
- 2–4 тест-кейса на задачу, входные данные соответствуют input();
- эталонное решение должно проходить все тест-кейсы и выводить только ответ;
- без сторонних модулей, только стандартные средства Python;
- текст для школьника, без взрослых формулировок.
"""


def build_generation_messages(
    request: TaskGenerateRequest,
) -> list[LLMMessage]:
    """Сообщения для генерации задач"""
    return [
        LLMMessage(
            role="system",
            content=GENERATION_SYSTEM_PROMPT.format(
                topic=request.topic,
                difficulty=request.difficulty.value,
                count=request.count,
            ),
        ),
        LLMMessage(
            role="user",
            content=(
                f"Сгенерируй {request.count} задач по теме «{request.topic}» "
                f"уровня {request.difficulty.value}."
            ),
        ),
    ]


def extract_json_array(text: str) -> list[Any]:
    """Достать JSON-массив из ответа модели (снимая markdown-обёртку)"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("В ответе модели нет JSON-массива")
    data: Any = json.loads(cleaned[start : end + 1])
    if not isinstance(data, list):
        raise ValueError("Ожидался JSON-массив задач")
    return data


def _reject(reason: str, title: str | None = None) -> TaskGenerateError:
    return TaskGenerateError(title=title, reason=reason)


async def validate_generated_tasks(
    raw_items: list[Any],
    request: TaskGenerateRequest,
    executor: SandboxedExecutor,
) -> tuple[list[TaskCreate], list[TaskGenerateError]]:
    """Провалидировать задачи и прогнать эталонные решения в песочнице"""
    accepted: list[TaskCreate] = []
    rejected: list[TaskGenerateError] = []

    for raw in raw_items[: request.count]:
        if not isinstance(raw, dict):
            rejected.append(_reject("Задача должна быть объектом"))
            continue

        candidate = {**raw, "difficulty": request.difficulty.value}
        title = str(candidate.get("title", ""))[:255] or None
        try:
            payload = TaskCreate.model_validate(candidate)
        except PydanticValidationError as exc:
            first = exc.errors()[0]
            location = ".".join(str(part) for part in first.get("loc", ()))
            rejected.append(
                _reject(f"{location}: {first.get('msg', 'некорректно')}", title)
            )
            continue

        if not payload.solution_template or not payload.solution_template.strip():
            rejected.append(_reject("Нет эталонного решения", payload.title))
            continue

        outcome = await run_test_cases(
            executor,
            payload.solution_template,
            [case.model_dump() for case in payload.test_cases],
        )
        if not outcome.passed:
            detail = (
                outcome.results[0].error
                if outcome.results and outcome.results[0].error
                else f"пройдено {outcome.passed_count} из {outcome.total_count}"
            )
            rejected.append(
                _reject(f"Эталонное решение не прошло тесты: {detail}", payload.title)
            )
            continue

        accepted.append(payload)

    return accepted, rejected


async def generate_tasks(
    provider: LLMProvider,
    request: TaskGenerateRequest,
    executor: SandboxedExecutor,
) -> tuple[list[TaskCreate], list[TaskGenerateError], LLMUsage | None]:
    """Сгенерировать и проверить задачи; вернуть принятые, отказы и usage"""
    answer = await provider.generate(build_generation_messages(request))
    usage = provider.last_usage

    try:
        raw_items = extract_json_array(answer)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("task_generation_parse_failed", error=str(exc))
        return [], [_reject(f"Не удалось разобрать ответ модели: {exc}")], usage

    accepted, rejected = await validate_generated_tasks(raw_items, request, executor)
    logger.info(
        "task_generation_completed",
        topic=request.topic,
        difficulty=request.difficulty.value,
        accepted=len(accepted),
        rejected=len(rejected),
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )
    return accepted, rejected, usage
