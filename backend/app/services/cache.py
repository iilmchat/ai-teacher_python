"""
Redis-кэш справочных данных (S19-003).

Кэшируются только «дешёвые» и редко меняющиеся ответы:
- `GET /chat/levels` — статический справочник;
- `GET /tasks/categories` — уникальные категории активных задач;
- `GET /tasks` — список задач (ключ включает пользователя и все фильтры).

TTL — 60 секунд (`CACHE_TTL_SECONDS`). Любая мутация задач инвалидирует
namespace `cache:tasks:*` через SCAN: и категории, и списки.

Принципы:
- **fail-open.** Redis недоступен/вернул мусор — приложение работает без
  кэша; ошибки логируются, но не пробрасываются в API. После первого сбоя
  кэш «остывает» `CACHE_COOLDOWN_SECONDS`, чтобы каждый запрос не ждал
  таймаут соединения.
- **метрики.** Hits/misses/sets/errors копятся в памяти процесса и отдаются
  в `GET /admin/analytics` (секция `cache`); те же события уходят в
  Prometheus (`cache_*_total`, KI-024). Каждое событие — structlog.
- **флаг.** `CACHE_ENABLED=false` полностью выключает кэш (как
  `RATE_LIMIT_ENABLED` у лимитов). В тестах флаг выключен autouse-фикстурой.
"""

import json
import time
from threading import Lock
from typing import Any

import structlog

from app.config import settings
from app.core.metrics import cache_observed

logger = structlog.get_logger(__name__)

#: Префикс всех ключей кэша
PREFIX = "cache"
#: Namespace задач: любая мутация задачи чистит его целиком
TASKS_NAMESPACE = f"{PREFIX}:tasks:"

LEVELS_KEY = f"{PREFIX}:chat:levels"
CATEGORIES_KEY = f"{PREFIX}:tasks:categories"
TASKS_LIST_PREFIX = f"{PREFIX}:tasks:list:"

#: Сколько секунд не трогать Redis после сбоя (fail-open без ожидания таймаута)
CACHE_COOLDOWN_SECONDS = 10.0

_disabled_until: float = 0.0


class CacheMetrics:
    """Потокобезопасные счётчики попаданий/промахов кэша"""

    def __init__(self) -> None:
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._invalidations = 0
        self._errors = 0
        self._lock = Lock()

    def record_hit(self) -> None:
        with self._lock:
            self._hits += 1
        cache_observed("hit")

    def record_miss(self) -> None:
        with self._lock:
            self._misses += 1
        cache_observed("miss")

    def record_set(self) -> None:
        with self._lock:
            self._sets += 1
        cache_observed("set")

    def record_invalidation(self) -> None:
        with self._lock:
            self._invalidations += 1
        cache_observed("invalidation")

    def record_error(self) -> None:
        with self._lock:
            self._errors += 1
        cache_observed("error")

    def reset(self) -> None:
        """Обнулить счётчики (тесты, рестарт)"""
        with self._lock:
            self._hits = self._misses = 0
            self._sets = self._invalidations = self._errors = 0

    def snapshot(self) -> dict[str, Any]:
        """Снимок для админ-аналитики"""
        with self._lock:
            hits, misses = self._hits, self._misses
            sets, invalidations, errors = self._sets, self._invalidations, self._errors
        total = hits + misses
        return {
            "enabled": settings.cache_enabled,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / total, 3) if total else 0.0,
            "sets": sets,
            "invalidations": invalidations,
            "errors": errors,
        }


#: Глобальный реестр, который читает `/admin/analytics`
cache_metrics = CacheMetrics()


def reset_cache_state() -> None:
    """Сбросить метрики и «остывание» Redis (autouse-фикстура тестов)"""
    global _disabled_until
    cache_metrics.reset()
    _disabled_until = 0.0


def _client() -> Any:
    """Ленивый клиент Redis; ``None``, если кэш выключен или остывает"""
    if not settings.cache_enabled:
        return None
    if time.monotonic() < _disabled_until:
        return None
    from app.db.redis import get_redis

    return get_redis()


def _mark_unavailable(error: Exception, event: str) -> None:
    """Зафиксировать сбой Redis: счётчик, лог и пауза обращений"""
    global _disabled_until
    _disabled_until = time.monotonic() + CACHE_COOLDOWN_SECONDS
    cache_metrics.record_error()
    logger.warning(event, error=str(error), cooldown_seconds=CACHE_COOLDOWN_SECONDS)


async def cache_get_json(key: str) -> Any | None:
    """Прочитать JSON из кэша; ``None`` при промахе или недоступном Redis"""
    try:
        client = _client()
        if client is None:
            return None
        raw = await client.get(key)
    except Exception as exc:  # noqa: BLE001 — кэш не должен ломать запрос
        _mark_unavailable(exc, "cache_get_failed")
        return None

    if raw is None:
        cache_metrics.record_miss()
        logger.debug("cache_miss", key=key)
        return None

    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        cache_metrics.record_error()
        logger.warning("cache_decode_failed", key=key, error=str(exc))
        return None

    cache_metrics.record_hit()
    logger.debug("cache_hit", key=key)
    return value


async def cache_set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """Положить JSON в кэш; ошибки только логируются"""
    if not settings.cache_enabled:
        return
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as exc:
        cache_metrics.record_error()
        logger.warning("cache_encode_failed", key=key, error=str(exc))
        return

    try:
        client = _client()
        if client is None:
            return
        await client.setex(key, ttl or settings.cache_ttl_seconds, payload)
    except Exception as exc:  # noqa: BLE001
        _mark_unavailable(exc, "cache_set_failed")
        return

    cache_metrics.record_set()
    logger.debug("cache_set", key=key, ttl=ttl or settings.cache_ttl_seconds)


async def cache_invalidate_prefix(prefix: str) -> int:
    """Удалить все ключи с префиксом; вернуть число удалённых (fail-open)"""
    if not settings.cache_enabled:
        return 0
    try:
        client = _client()
        if client is None:
            return 0
        keys = [key async for key in client.scan_iter(match=f"{prefix}*", count=100)]
        if not keys:
            return 0
        await client.delete(*keys)
    except Exception as exc:  # noqa: BLE001
        _mark_unavailable(exc, "cache_invalidate_failed")
        return 0

    cache_metrics.record_invalidation()
    logger.info("cache_invalidated", prefix=prefix, keys=len(keys))
    return len(keys)


async def invalidate_tasks_cache() -> int:
    """Инвалидация всего, что зависит от задач (категории + списки)"""
    return await cache_invalidate_prefix(TASKS_NAMESPACE)


# --- Ключи ---------------------------------------------------------------


def levels_cache_key() -> str:
    """Ключ справочника уровней (статический, без параметров)"""
    return LEVELS_KEY


def categories_cache_key() -> str:
    """Ключ категорий задач"""
    return CATEGORIES_KEY


def tasks_list_cache_key(
    user_id: Any,
    *,
    difficulty: str | None,
    category: str | None,
    tag: str | None,
    search: str | None,
    skip: int,
    limit: int,
) -> str:
    """Ключ списка задач: пользователь (прогресс!) + все фильтры"""
    normalized_search = (search or "").strip().lower()
    return (
        f"{TASKS_LIST_PREFIX}{user_id}:"
        f"{difficulty or '-'}:"
        f"{category or '-'}:"
        f"{(tag or '').strip().lower() or '-'}:"
        f"{normalized_search or '-'}:"
        f"{skip}:{limit}"
    )
