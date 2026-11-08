"""Тесты объявлений класса (S46-006)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.classroom import ClassroomAnnouncement
from tests.task_helpers import auth, register_and_login, teacher_token

CLASSROOMS = "/api/v1/classrooms"


async def _classroom(
    client: AsyncClient, token: str, name: str = "7А класс"
) -> dict[str, Any]:
    response = await client.post(
        CLASSROOMS, json={"name": name}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _join(
    client: AsyncClient, token: str, classroom: dict[str, Any]
) -> None:
    response = await client.post(
        f"{CLASSROOMS}/join",
        json={"join_code": classroom["join_code"]},
        headers=auth(token),
    )
    assert response.status_code == 200, response.text


async def _setup(
    client: AsyncClient, db: AsyncSession, prefix: str
) -> tuple[str, str, dict[str, Any]]:
    """Учитель, класс с одним учеником"""
    teacher = await teacher_token(client, db, f"{prefix}_teacher")
    student = await register_and_login(client, f"{prefix}_student")
    classroom = await _classroom(client, teacher, f"Класс {prefix}")
    await _join(client, student, classroom)
    return teacher, student, classroom


async def _publish(
    client: AsyncClient,
    token: str,
    classroom: dict[str, Any],
    *,
    title: str = "Контрольная в пятницу",
    body: str = "Повторите циклы и функции.",
) -> dict[str, Any]:
    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": title, "body": body},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_announcement_visible_to_students(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Учитель публикует, ученик видит объявление в классе и в ленте"""
    teacher, student, classroom = await _setup(client, db_session, "s4606v")

    created = await _publish(client, teacher, classroom)

    assert created["title"] == "Контрольная в пятницу"
    assert created["author_name"] == "s4606v_teacher"
    assert created["can_delete"] is True

    listing = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        headers=auth(student),
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["body"] == "Повторите циклы и функции."
    assert items[0]["can_delete"] is False

    feed = await client.get("/api/v1/me/announcements", headers=auth(student))
    assert feed.status_code == 200, feed.text
    feed_items = feed.json()["items"]
    assert len(feed_items) == 1
    assert feed_items[0]["classroom_name"] == "Класс s4606v"


async def test_announcement_notifies_every_student(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Публикация порождает уведомление каждому ученику класса"""
    teacher, student, classroom = await _setup(client, db_session, "s4606n")
    second = await register_and_login(client, "s4606n_student2")
    await _join(client, second, classroom)

    announcement = await _publish(
        client, teacher, classroom, title="Перенос занятия"
    )

    for token in (student, second):
        response = await client.get(
            "/api/v1/me/notifications", headers=auth(token)
        )
        assert response.status_code == 200, response.text
        items = [
            item
            for item in response.json()["items"]
            if item["type"] == "announcement"
        ]
        assert len(items) == 1
        payload = items[0]["payload"]
        assert payload["announcement_id"] == announcement["id"]
        assert payload["classroom_id"] == classroom["id"]
        assert payload["classroom_name"] == "Класс s4606n"
        assert payload["title"] == "Перенос занятия"

    owner_notifications = await client.get(
        "/api/v1/me/notifications", headers=auth(teacher)
    )
    assert [
        item
        for item in owner_notifications.json()["items"]
        if item["type"] == "announcement"
    ] == []


async def test_announcement_rights(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Публиковать может только владелец; чужой не читает объявления"""
    teacher, student, classroom = await _setup(client, db_session, "s4606r")
    outsider = await teacher_token(client, db_session, "s4606r_outsider")

    by_student = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": "Текст", "body": "Текст"},
        headers=auth(student),
    )
    by_outsider = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": "Текст", "body": "Текст"},
        headers=auth(outsider),
    )
    read_by_outsider = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        headers=auth(outsider),
    )

    assert by_student.status_code == 403
    assert by_outsider.status_code == 403
    assert read_by_outsider.status_code == 403
    assert teacher


async def test_announcement_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Автор удаляет объявление; повторное удаление — 404"""
    teacher, student, classroom = await _setup(client, db_session, "s4606d")
    announcement = await _publish(client, teacher, classroom)

    removed = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/announcements/{announcement['id']}",
        headers=auth(teacher),
    )
    again = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/announcements/{announcement['id']}",
        headers=auth(teacher),
    )
    listing = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        headers=auth(student),
    )

    assert removed.status_code == 204, removed.text
    assert again.status_code == 404
    assert listing.json()["items"] == []


async def test_announcement_delete_foreign_teacher(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Чужой учитель не удаляет чужое объявление"""
    teacher, _, classroom = await _setup(client, db_session, "s4606f")
    outsider = await teacher_token(client, db_session, "s4606f_outsider")
    announcement = await _publish(client, teacher, classroom)

    response = await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/announcements/{announcement['id']}",
        headers=auth(outsider),
    )

    assert response.status_code == 403


async def test_announcement_validation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Пустые и слишком длинные поля — 422"""
    teacher, _, classroom = await _setup(client, db_session, "s4606x")

    empty_title = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": "", "body": "Текст"},
        headers=auth(teacher),
    )
    empty_body = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": "Тема", "body": ""},
        headers=auth(teacher),
    )
    long_title = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": "x" * 201, "body": "Текст"},
        headers=auth(teacher),
    )
    long_body = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        json={"title": "Тема", "body": "x" * 5001},
        headers=auth(teacher),
    )

    assert empty_title.status_code == 422
    assert empty_body.status_code == 422
    assert long_title.status_code == 422
    assert long_body.status_code == 422


async def test_announcement_audit(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Публикация и удаление попадают в аудит"""
    from sqlalchemy import select

    from app.models.audit import AuditLog

    teacher, _, classroom = await _setup(client, db_session, "s4606a")
    announcement = await _publish(client, teacher, classroom)
    await client.delete(
        f"{CLASSROOMS}/{classroom['id']}/announcements/{announcement['id']}",
        headers=auth(teacher),
    )

    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.entity_id == announcement["id"],
                AuditLog.action.in_(
                    ["announcement.created", "announcement.deleted"]
                ),
            )
        )
    ).scalars().all()

    assert {row.action for row in rows} == {
        "announcement.created",
        "announcement.deleted",
    }


async def test_announcement_ordering(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Список объявлений — новые сверху"""
    teacher, _, classroom = await _setup(client, db_session, "s4606o")
    first = await _publish(client, teacher, classroom, title="Первое")
    second = await _publish(client, teacher, classroom, title="Второе")
    row = await db_session.get(ClassroomAnnouncement, second["id"])
    assert row is not None
    row.created_at = datetime.utcnow() + timedelta(minutes=1)
    await db_session.commit()

    listing = await client.get(
        f"{CLASSROOMS}/{classroom['id']}/announcements",
        headers=auth(teacher),
    )

    titles = [item["title"] for item in listing.json()["items"]]
    assert titles == ["Второе", "Первое"]
    assert first
