"""
Асинхронный клиент Redis (S11-003).

Клиент создаётся лениво: приложение должно стартовать, даже если Redis ещё не
поднят. Если Redis недоступен, защитные механизмы работают в режиме fail-open
(см. `app/core/rate_limiter.py`), а healthcheck показывает `degraded`.
"""

from typing import Any

import redis.asyncio as redis
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_client: "redis.Redis[Any] | None" = None


def get_redis() -> "redis.Redis[Any]":
    """Вернуть общий клиент Redis (создаётся при первом обращении)"""
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client


async def ping_redis() -> bool:
    """Проверить доступность Redis, не бросая исключение"""
    try:
        return bool(await get_redis().ping())
    except Exception as exc:  # noqa: BLE001 — Redis может быть недоступен
        logger.warning("redis_unavailable", error=str(exc))
        return False


async def close_redis() -> None:
    """Закрыть соединение при остановке приложения"""
    global _client
    if _client is not None:
        try:
            # В redis 5.x метод называется `aclose`; стабы типизируют `close`
            await _client.aclose()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis_close_failed", error=str(exc))
        finally:
            _client = None


def set_redis_client(client: "redis.Redis[Any] | None") -> None:
    """Подменить клиент (для тестов)"""
    global _client
    _client = client
