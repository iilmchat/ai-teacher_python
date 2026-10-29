"""Общие помощники тестов задач (S14)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user import UserRepository
from app.models.user import UserRole

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
TASKS_URL = "/api/v1/tasks"

TASK_PAYLOAD: dict[str, Any] = {
    "title": "Сумма двух чисел",
    "description": "Считайте два числа и выведите их сумму.",
    "difficulty": "easy",
    "category": "input_output",
    "tags": ["python", "basics"],
    "test_cases": [
        {"input": "2\n3\n", "expected_output": "5", "description": "Положительные"},
        {"input": "-5\n5\n", "expected_output": "0", "description": "С минусом"},
    ],
    "hints": ["Используйте int(input())", "Сложите два числа"],
    "solution_template": "a = int(input())\nb = int(input())\nprint(a + b)\n",
}


async def register_and_login(client: AsyncClient, username: str) -> str:
    """Зарегистрировать пользователя и вернуть access-токен"""
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


async def make_teacher(db: AsyncSession, username: str) -> None:
    """Повысить роль пользователя напрямую в БД"""
    user = await UserRepository(db).get_by_username(username)
    assert user is not None
    await UserRepository(db).update_role(user.id, UserRole.TEACHER)


async def teacher_token(
    client: AsyncClient, db: AsyncSession, username: str
) -> str:
    """Токен преподавателя"""
    token = await register_and_login(client, username)
    await make_teacher(db, username)
    return token


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
