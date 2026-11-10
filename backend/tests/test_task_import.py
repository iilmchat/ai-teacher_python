"""
Тесты импорта/экспорта задач (S14-001).
"""

import json
from typing import Any

import pytest
import yaml
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.services.task_import import TaskImportFormatError, parse_task_payload
from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)


def test_parse_json_and_yaml() -> None:
    """Поддерживаются JSON-массив и YAML-объект с ключом tasks"""
    payload = {**TASK_PAYLOAD, "id": "ignored"}
    json_text = json.dumps([payload])
    yaml_text = yaml.safe_dump({"tasks": [payload]}, allow_unicode=True)

    assert parse_task_payload(json_text)[0]["title"] == TASK_PAYLOAD["title"]
    assert parse_task_payload(yaml_text)[0]["title"] == TASK_PAYLOAD["title"]


@pytest.mark.parametrize("text", ["", "не json и не yaml", "[]"])
def test_parse_rejects_empty_or_not_a_list(text: str) -> None:
    """Пустой/некорректный файл отклоняется"""
    if text == "[]":
        assert parse_task_payload(text) == []
        return
    with pytest.raises(TaskImportFormatError):
        parse_task_payload(text)


async def test_import_reports_created_skipped_errors(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Импорт: валидная задача создаётся, дубликат пропускается, битая — ошибка"""
    token = await teacher_token(client, db_session, "importteacher")
    broken = {**TASK_PAYLOAD, "title": "Битая", "test_cases": []}
    payload = {"tasks": [TASK_PAYLOAD, TASK_PAYLOAD, broken]}

    response = await client.post(
        f"{TASKS_URL}/import", json=payload, headers=auth(token)
    )

    assert response.status_code == 200, response.text
    report: dict[str, Any] = response.json()
    assert report["created"] == 1
    assert report["skipped"] == 1
    assert len(report["errors"]) == 1
    assert report["errors"][0]["index"] == 2
    imported = (
        await db_session.execute(
            select(Task).where(Task.title == TASK_PAYLOAD["title"])
        )
    ).scalar_one()
    assert imported.source == "imported"


async def test_export_round_trip_skips_existing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Экспорт можно импортировать обратно без дублей"""
    token = await teacher_token(client, db_session, "exportteacher")
    await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(token))

    exported = await client.get(f"{TASKS_URL}/export", headers=auth(token))
    assert exported.status_code == 200
    items = exported.json()
    assert len(items) == 1
    assert items[0]["tags"] == ["python", "basics"]
    assert items[0]["test_cases"][0]["expected_output"] == "5"

    reimport = await client.post(
        f"{TASKS_URL}/import", json={"tasks": items}, headers=auth(token)
    )

    assert reimport.json()["created"] == 0
    assert reimport.json()["skipped"] == 1


async def test_export_yaml_round_trip(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """YAML-выгрузка парсится и содержит задачи"""
    token = await teacher_token(client, db_session, "exportyaml")
    await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(token))

    response = await client.get(
        f"{TASKS_URL}/export", params={"format": "yaml"}, headers=auth(token)
    )

    assert response.status_code == 200
    assert "yaml" in response.headers["content-type"]
    data = yaml.safe_load(response.text)
    assert data["tasks"][0]["title"] == TASK_PAYLOAD["title"]


async def test_import_and_export_require_teacher(
    client: AsyncClient,
) -> None:
    """Ученик не может импортировать или выгружать задачи"""
    token = await register_and_login(client, "importstudent")

    import_response = await client.post(
        f"{TASKS_URL}/import", json={"tasks": [TASK_PAYLOAD]}, headers=auth(token)
    )
    export_response = await client.get(
        f"{TASKS_URL}/export", headers=auth(token)
    )

    assert import_response.status_code == 403
    assert export_response.status_code == 403
