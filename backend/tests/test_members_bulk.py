"""Тесты массовых операций с учениками (S46-005)."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
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


async def _user_id(db: AsyncSession, username: str) -> str:
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    return str(user.id)


async def test_bulk_add_partial_success(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Существующий — skipped, новый — added, неизвестный — unknown"""
    teacher = await teacher_token(client, db_session, "s4605_teacher")
    classroom = await _classroom(client, teacher, "Класс S4605")
    existing = await register_and_login(client, "s4605_existing")
    await _join(client, existing, classroom)
    await register_and_login(client, "s4605_new")

    response = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={
            "usernames": [
                "s4605_existing",
                "s4605_new",
                "s4605_missing",
                " s4605_new ",
            ]
        },
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["added"] == ["s4605_new"]
    assert data["skipped"] == ["s4605_existing"]
    assert data["unknown"] == ["s4605_missing"]

    detail = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(teacher)
    )
    usernames = {member["username"] for member in detail.json()["members"]}
    assert "s4605_new" in usernames
    assert "s4605_missing" not in usernames


async def test_bulk_add_limit_and_rights(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Больше 100 логинов — 422; чужой учитель — 403"""
    teacher = await teacher_token(client, db_session, "s4605_owner")
    outsider = await teacher_token(client, db_session, "s4605_outsider")
    classroom = await _classroom(client, teacher, "Класс S4605 limit")

    too_many = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={"usernames": [f"user{i}" for i in range(101)]},
        headers=auth(teacher),
    )
    foreign = await client.post(
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={"usernames": ["someone"]},
        headers=auth(outsider),
    )

    assert too_many.status_code == 422
    assert foreign.status_code == 403


async def test_bulk_remove_partial_success(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Снимаются участники, владелец и неизвестные — skipped"""
    teacher = await teacher_token(client, db_session, "s4605_rm_teacher")
    student1 = await register_and_login(client, "s4605_rm1")
    student2 = await register_and_login(client, "s4605_rm2")
    classroom = await _classroom(client, teacher, "Класс S4605 remove")
    await _join(client, student1, classroom)
    await _join(client, student2, classroom)
    owner_id = await _user_id(db_session, "s4605_rm_teacher")
    id1 = await _user_id(db_session, "s4605_rm1")
    id2 = await _user_id(db_session, "s4605_rm2")

    response = await client.request(
        "DELETE",
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={"user_ids": [id1, owner_id, "00000000-0000-0000-0000-000000000000"]},
        headers=auth(teacher),
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["removed"] == [id1]
    assert len(data["skipped"]) == 2

    detail = await client.get(
        f"{CLASSROOMS}/{classroom['id']}", headers=auth(teacher)
    )
    usernames = {member["username"] for member in detail.json()["members"]}
    assert "s4605_rm1" not in usernames
    assert "s4605_rm2" in usernames
    assert id2


async def test_bulk_remove_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Повторное снятие — не ошибка, все id в skipped"""
    teacher = await teacher_token(client, db_session, "s4605_idem_teacher")
    student = await register_and_login(client, "s4605_idem_student")
    classroom = await _classroom(client, teacher, "Класс S4605 idem")
    await _join(client, student, classroom)
    student_id = await _user_id(db_session, "s4605_idem_student")

    first = await client.request(
        "DELETE",
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={"user_ids": [student_id]},
        headers=auth(teacher),
    )
    second = await client.request(
        "DELETE",
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={"user_ids": [student_id]},
        headers=auth(teacher),
    )

    assert first.status_code == 200
    assert first.json()["removed"] == [student_id]
    assert second.status_code == 200
    assert second.json()["removed"] == []
    assert second.json()["skipped"] == [student_id]


async def test_bulk_remove_requires_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Чужой учитель не снимает участников"""
    teacher = await teacher_token(client, db_session, "s4605_rmo_teacher")
    outsider = await teacher_token(client, db_session, "s4605_rmo_outsider")
    student = await register_and_login(client, "s4605_rmo_student")
    classroom = await _classroom(client, teacher, "Класс S4605 rm owner")
    await _join(client, student, classroom)
    student_id = await _user_id(db_session, "s4605_rmo_student")

    response = await client.request(
        "DELETE",
        f"{CLASSROOMS}/{classroom['id']}/members/bulk",
        json={"user_ids": [student_id]},
        headers=auth(outsider),
    )

    assert response.status_code == 403
