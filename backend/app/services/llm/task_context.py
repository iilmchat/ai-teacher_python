"""Контекст учебной задачи для чата (S42-006).

В контекст попадает только условие задачи: название, сложность, описание
и входные данные тест-кейсов. Эталонное решение (`solution_template`) и
ожидаемые выводы (`test_cases[].expected_output`) не передаются: ассистент
должен помогать ученику разобраться, а не выдавать готовый ответ.

Контекст добавляется отдельным системным сообщением (не текстом вопроса)
и не сохраняется в `content` сообщения — в истории остаётся только вопрос
ученика, а идентификатор задачи — в `message_metadata`.
"""

from typing import Any

from app.models.task import Task

#: Сколько символов условия задачи попадает в системное сообщение
MAX_TASK_CONTEXT_CHARS = 4000

#: Сколько тест-кейсов перечисляем в контексте
MAX_CONTEXT_TEST_CASES = 20


def task_context_metadata(task: Task) -> dict[str, Any]:
    """Метаданные сообщения ученика: чем задача была в контексте.

    Храним только идентификатор и название — этого достаточно, чтобы в
    истории было видно, о какой задаче шла речь, и при этом в метаданные
    не попадают ни код ученика, ни эталонное решение.
    """
    return {
        "task_context": {
            "task_id": str(task.id),
            "title": task.title,
        }
    }


def build_task_context_message(task: Task) -> str:
    """Собрать системное сообщение с условием задачи (без решения)."""
    lines = [
        "Контекст учебной задачи (только условие, без эталонного решения):",
        f"Название: {task.title}",
        f"Сложность: {task.difficulty.value}",
        f"Категория: {task.category}",
        "Описание:",
        task.description.strip(),
    ]

    cases = list(task.test_cases or [])[:MAX_CONTEXT_TEST_CASES]
    if cases:
        lines.append(
            f"Проверяется на {len(task.test_cases or [])} тест-кейсах. "
            "Входные данные:"
        )
        for index, case in enumerate(cases, start=1):
            raw_input = str(case.get("input", "")).strip()
            input_text = raw_input if raw_input else "(без ввода)"
            description = str(case.get("description") or "").strip()
            suffix = f" — {description}" if description else ""
            lines.append(f"{index}. {input_text}{suffix}")

    lines.append(
        "Помоги ученику разобраться с этой задачей, опираясь на её условие."
    )
    return "\n".join(lines)[:MAX_TASK_CONTEXT_CHARS]
