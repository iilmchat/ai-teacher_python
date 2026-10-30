"""
Тесты Redis-кэша справочных данных (S19-003).

Используется in-memory FakeRedis (как в `test_rate_limit.py`): тесты не
зависят от внешнего Redis и не мешают другим прогонам. Флаг `CACHE_ENABLED`
по умолчанию выключен autouse-фикстурой `conftest.disable_cache`.
"""

import fnmatch
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.cache import (
    CATEGORIES_KEY,
    LEVELS_KEY,
    PREFIX,
    cache_get_json,
    cache_metrics,
    cache_set_json,
    invalidate_tasks_cache,
    reset_cache_state,
    tasks_list_cache_key,
)
from tests.task_helpers import TASK_PAYLOAD, TASKS_URL, auth, teacher_token


class FakeRedis:
    """Минимальная реализация команд Redis, нужных кэшу"""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.data[key] = value
        self.ttls[key] = ttl

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.data.pop(key, None)
            self.ttls.pop(key, None)

    async def scan_iter(
        self, match: str | None = None, count: int = 100
    ) -> AsyncIterator[str]:
        for key in list(self.data):
            if match is None or fnmatch.fnmatch(key, match):
                yield key


class BrokenRedis:
    """Клиент, всегда падающий (Redis недоступен)"""

    async def get(self, key: str) -> None:
        raise ConnectionError("redis is down")

    async def setex(self, key: str, ttl: int, value: str) -> None:
        raise ConnectionError("redis is down")

    async def delete(self, *keys: str) -> None:
        raise ConnectionError("redis is down")

    async def scan_iter(
        self, match: str | None = None, count: int = 100
    ) -> AsyncIterator[str]:
        raise ConnectionError("redis is down")
        yield ""  # pragma: no cover — делает функцию генератором


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeRedis]:
    """Включённый кэш с чистым FakeRedis"""
    from app.db.redis import set_redis_client

    monkeypatch.setattr(settings, "cache_enabled", True)
    redis = FakeRedis()
    set_redis_client(redis)  # type: ignore[arg-type]
    reset_cache_state()
    yield redis
    set_redis_client(None)
    reset_cache_state()


async def _levels(client: AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/v1/chat/levels")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_levels_are_cached_on_second_request(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    """Первый запрос — промах и запись в Redis, второй — попадание"""
    first = await _levels(client)
    second = await _levels(client)

    assert first == second
    assert LEVELS_KEY in fake_redis.data
    assert fake_redis.ttls[LEVELS_KEY] == 60
    snapshot = cache_metrics.snapshot()
    assert snapshot["hits"] >= 1
    assert snapshot["misses"] >= 1
    assert snapshot["hit_rate"] > 0


async def test_cache_disabled_by_flag(client: AsyncClient) -> None:
    """CACHE_ENABLED=false: Redis не используется, API работает"""
    from app.db.redis import set_redis_client

    redis = FakeRedis()
    set_redis_client(redis)  # type: ignore[arg-type]

    response = await client.get("/api/v1/chat/levels")

    assert response.status_code == 200
    assert redis.data == {}


async def test_fail_open_when_redis_is_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redis недоступен → ответ 200, счётчик ошибок растёт"""
    from app.db.redis import set_redis_client

    monkeypatch.setattr(settings, "cache_enabled", True)
    reset_cache_state()
    set_redis_client(BrokenRedis())  # type: ignore[arg-type]

    response = await client.get("/api/v1/chat/levels")

    assert response.status_code == 200
    assert response.json()["levels"]
    assert cache_metrics.snapshot()["errors"] >= 1


async def test_cache_helpers_roundtrip_and_invalidation(fake_redis: FakeRedis) -> None:
    """Базовые операции кэша и инвалидация namespace задач"""
    await cache_set_json("cache:tasks:categories", {"categories": ["a"]})
    await cache_set_json("cache:tasks:list:x", [1])
    await cache_set_json(LEVELS_KEY, {"levels": []})

    assert await cache_get_json("cache:tasks:categories") == {"categories": ["a"]}

    removed = await invalidate_tasks_cache()

    assert removed == 2
    assert "cache:tasks:categories" not in fake_redis.data
    assert "cache:tasks:list:x" not in fake_redis.data
    # Справочник уровней не относится к задачам
    assert LEVELS_KEY in fake_redis.data


async def test_categories_cached_and_invalidated_by_task_create(
    client: AsyncClient, db_session: Any, fake_redis: FakeRedis
) -> None:
    """Категории кэшируются; создание задачи сбрасывает кэш задач"""
    teacher = await teacher_token(client, db_session, "cacheteacher")

    first = await client.get(f"{TASKS_URL}/categories", headers=auth(teacher))
    assert first.status_code == 200, first.text
    assert CATEGORIES_KEY in fake_redis.data

    second = await client.get(f"{TASKS_URL}/categories", headers=auth(teacher))
    assert second.status_code == 200
    assert cache_metrics.snapshot()["hits"] >= 1

    created = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    assert created.status_code == 201, created.text
    assert CATEGORIES_KEY not in fake_redis.data

    after = await client.get(f"{TASKS_URL}/categories", headers=auth(teacher))
    assert after.status_code == 200
    assert TASK_PAYLOAD["category"] in after.json()["categories"]


async def test_tasks_list_cache_key_contains_filters_and_user(
    client: AsyncClient, db_session: Any, fake_redis: FakeRedis
) -> None:
    """Список задач кэшируется с ключом, включающим пользователя и фильтры"""
    teacher = await teacher_token(client, db_session, "cachelist")
    await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))

    key = tasks_list_cache_key(
        "00000000-0000-0000-0000-000000000001",
        difficulty="easy",
        category="input_output",
        tag="python",
        search="сумма",
        skip=0,
        limit=100,
    )
    assert key.startswith(f"{PREFIX}:tasks:list:")
    assert "easy" in key and "python" in key and "сумма" in key

    listed = await client.get(
        TASKS_URL, params={"difficulty": "easy"}, headers=auth(teacher)
    )
    assert listed.status_code == 200
    cached_keys = [k for k in fake_redis.data if k.startswith(f"{PREFIX}:tasks:list:")]
    assert cached_keys
    assert listed.json()


async def test_update_and_delete_task_invalidate_cache(
    client: AsyncClient, db_session: Any, fake_redis: FakeRedis
) -> None:
    """Правка, деактивация и удаление задачи сбрасывают кэш задач"""
    teacher = await teacher_token(client, db_session, "cachecrud")
    created = await client.post(TASKS_URL, json=TASK_PAYLOAD, headers=auth(teacher))
    task_id = created.json()["id"]

    # Наполняем кэш категориями
    await client.get(f"{TASKS_URL}/categories", headers=auth(teacher))
    assert CATEGORIES_KEY in fake_redis.data

    patched = await client.patch(
        f"{TASKS_URL}/{task_id}", json={"title": "Новое имя"}, headers=auth(teacher)
    )
    assert patched.status_code == 200, patched.text
    assert CATEGORIES_KEY not in fake_redis.data

    await client.get(f"{TASKS_URL}/categories", headers=auth(teacher))
    assert CATEGORIES_KEY in fake_redis.data

    deleted = await client.delete(f"{TASKS_URL}/{task_id}", headers=auth(teacher))
    assert deleted.status_code == 204
    assert CATEGORIES_KEY not in fake_redis.data


async def test_seed_invalidates_task_cache(
    db_session: Any, fake_redis: FakeRedis
) -> None:
    """Seed задач сбрасывает кэш (даже если задачи уже есть — операция безопасна)"""
    from app.services.seed_service import seed_tasks

    await cache_set_json(CATEGORIES_KEY, {"categories": ["old"]})

    created = await seed_tasks(db_session)

    assert created > 0
    assert CATEGORIES_KEY not in fake_redis.data


async def _admin_token(
    client: AsyncClient, db_session: Any, username: str
) -> str:
    """Зарегистрировать пользователя и выдать ему роль администратора"""
    from app.db.repositories.user import UserRepository
    from app.models.user import UserRole

    token = await teacher_token(client, db_session, username)
    user = await UserRepository(db_session).get_by_username(username)
    assert user is not None
    await UserRepository(db_session).update_role(user.id, UserRole.ADMIN)
    return token


async def test_admin_analytics_exposes_cache_metrics(
    client: AsyncClient, db_session: Any, fake_redis: FakeRedis
) -> None:
    """GET /admin/analytics отдаёт hits/misses/hit_rate кэша (S19-003)"""
    admin = await _admin_token(client, db_session, "cacheadmin")
    await _levels(client)
    await _levels(client)

    response = await client.get("/api/v1/admin/analytics", headers=auth(admin))

    assert response.status_code == 200, response.text
    cache = response.json()["cache"]
    assert cache["enabled"] is True
    assert cache["hits"] >= 1
    assert cache["misses"] >= 1
    assert 0.0 < cache["hit_rate"] <= 1.0
