"""
Тесты тегов, поиска и категорий задач (S14-004).
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.task_helpers import (
    TASK_PAYLOAD,
    TASKS_URL,
    auth,
    register_and_login,
    teacher_token,
)


async def test_tags_are_normalized_on_create(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Теги приводятся к нижнему регистру и без дублей"""
    token = await teacher_token(client, db_session, "tagsteacher")
    payload = {**TASK_PAYLOAD, "tags": [" Python ", "loops", "python"]}

    response = await client.post(TASKS_URL, json=payload, headers=auth(token))

    assert response.status_code == 201, response.text
    assert response.json()["tags"] == ["python", "loops"]


async def test_filter_by_tag_and_search(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Фильтр по тегу и поиск по заголовку/описанию"""
    token = await teacher_token(client, db_session, "searchteacher")
    await client.post(
        TASKS_URL,
        json={**TASK_PAYLOAD, "tags": ["loops"], "title": "Циклы и суммы"},
        headers=auth(token),
    )
    await client.post(
        TASKS_URL,
        json={
            **TASK_PAYLOAD,
            "title": "Строки и срезы",
            "description": "Перевернуть строку и вывести результат.",
            "tags": ["strings"],
        },
        headers=auth(token),
    )

    by_tag = await client.get(TASKS_URL, params={"tag": "loops"}, headers=auth(token))
    by_query = await client.get(
        TASKS_URL, params={"q": "строк"}, headers=auth(token)
    )

    assert [item["title"] for item in by_tag.json()] == ["Циклы и суммы"]
    assert [item["title"] for item in by_query.json()] == ["Строки и срезы"]


async def test_categories_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Категории активных задач"""
    token = await teacher_token(client, db_session, "catteacher")
    await client.post(
        TASKS_URL,
        json={**TASK_PAYLOAD, "category": "loops"},
        headers=auth(token),
    )

    response = await client.get(f"{TASKS_URL}/categories", headers=auth(token))

    assert response.status_code == 200
    assert "loops" in response.json()["categories"]


async def test_student_sees_tags_in_list_and_detail(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Теги доступны ученику в каталоге и карточке"""
    teacher = await teacher_token(client, db_session, "tagviewteacher")
    created: dict[str, Any] = (
        await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    ).json()
    student = await register_and_login(client, "tagviewstudent")

    listing = await client.get(TASKS_URL, headers=auth(student))
    detail = await client.get(
        f"{TASKS_URL}/{created['id']}", headers=auth(student)
    )

    assert listing.json()[0]["tags"] == ["python", "basics"]
    assert detail.json()["tags"] == ["python", "basics"]
