"""
Импорт и экспорт задач (S14-001).

Формат — JSON или YAML: массив задач либо `{"tasks": [...]}`. Каждая запись
валидируется схемой `TaskCreate`; дубликаты по заголовку пропускаются,
ошибки не мешают импорту остальных записей.
"""

import json
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskCreate,
    TaskExportItem,
    TaskImportError,
    TaskImportPreview,
    TaskImportResponse,
)


class TaskImportFormatError(ValueError):
    """Файл не является массивом задач"""


def parse_task_payload(text: str) -> list[Any]:
    """Разобрать JSON/YAML в список записей задач"""
    stripped = text.strip()
    if not stripped:
        raise TaskImportFormatError("Пустой файл")

    data: Any
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            data = yaml.safe_load(stripped)
        except yaml.YAMLError as exc:
            raise TaskImportFormatError(f"Не удалось разобрать JSON/YAML: {exc}") from exc

    if isinstance(data, dict):
        data = data.get("tasks")
    if not isinstance(data, list):
        raise TaskImportFormatError(
            "Ожидается массив задач или объект с ключом 'tasks'"
        )
    return data


def _validation_message(error: PydanticValidationError) -> str:
    """Короткое описание первой ошибки схемы"""
    first = error.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    return f"{location}: {first.get('msg', 'некорректное значение')}"


def preview_import(text: str) -> TaskImportPreview:
    """Проверить файл без сохранения: сколько задач валидны и где ошибки"""
    items = parse_task_payload(text)
    valid = 0
    errors: list[TaskImportError] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(
                TaskImportError(
                    index=index, message="Запись должна быть объектом"
                )
            )
            continue
        raw_title = item.get("title")
        title = str(raw_title)[:255] if raw_title is not None else None
        try:
            TaskCreate.model_validate(item)
        except PydanticValidationError as exc:
            errors.append(
                TaskImportError(
                    index=index, title=title, message=_validation_message(exc)
                )
            )
            continue
        valid += 1
    return TaskImportPreview(tasks=valid, errors=errors)


async def import_tasks(
    session: AsyncSession,
    items: list[Any],
    author: User | None = None,
) -> TaskImportResponse:
    """Импортировать задачи; вернуть отчёт created/skipped/errors"""
    existing = set((await session.execute(select(Task.title))).scalars().all())
    created = 0
    skipped = 0
    errors: list[TaskImportError] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(
                TaskImportError(
                    index=index, message="Запись должна быть объектом"
                )
            )
            continue

        raw_title = item.get("title")
        title = str(raw_title)[:255] if raw_title is not None else None
        try:
            payload = TaskCreate.model_validate(item)
        except PydanticValidationError as exc:
            errors.append(
                TaskImportError(
                    index=index, title=title, message=_validation_message(exc)
                )
            )
            continue

        if payload.title in existing:
            skipped += 1
            continue

        session.add(
            Task(
                title=payload.title,
                description=payload.description,
                difficulty=payload.difficulty,
                category=payload.category,
                tags=list(payload.tags),
                test_cases=[case.model_dump() for case in payload.test_cases],
                hints=list(payload.hints),
                solution_template=payload.solution_template,
                created_by=author.id if author is not None else None,
            )
        )
        existing.add(payload.title)
        created += 1

    await session.commit()
    return TaskImportResponse(created=created, skipped=skipped, errors=errors)


def export_tasks(tasks: list[Task]) -> list[TaskExportItem]:
    """Сериализовать задачи в формат, пригодный для повторного импорта"""
    return [
        TaskExportItem.model_validate(
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "difficulty": task.difficulty,
                "category": task.category,
                "tags": list(task.tags or []),
                "test_cases": list(task.test_cases or []),
                "hints": list(task.hints or []),
                "solution_template": task.solution_template,
            }
        )
        for task in tasks
    ]


def export_to_yaml(tasks: list[Task]) -> str:
    """Выгрузка в YAML (для CLI и ручной правки)"""
    payload = [item.model_dump(mode="json") for item in export_tasks(tasks)]
    dumped = yaml.safe_dump(
        {"tasks": payload}, allow_unicode=True, sort_keys=False
    )
    return str(dumped)
