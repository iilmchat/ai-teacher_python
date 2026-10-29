"""
Healthcheck LLM-провайдера (S12-001).

Проверка лёгкая и кэшируется на 60 секунд: `/health` не должен бить по API
провайдера на каждый запрос мониторинга. `reachable` проверяется только у
настроенного провайдера — иначе статус `not_configured`, а не `ok`
(именно эта ошибка была в соседнем проекте: health показывал `ok`, хотя
ключ не задан).
"""

import time
from dataclasses import dataclass
from typing import Any, Literal

from app.services.llm.base import LLMProvider

ProviderStatus = Literal["ok", "degraded", "not_configured"]

#: Сколько секунд держим результат проверки провайдера
CACHE_TTL_SECONDS = 60.0

#: Кэш: ключ `name:model` → (момент проверки, результат)
_CACHE: dict[str, tuple[float, "ProviderHealth"]] = {}


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Состояние LLM-провайдера для `/health`"""

    provider: str
    model: str
    configured: bool
    reachable: bool
    status: ProviderStatus
    fallback: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "configured": self.configured,
            "reachable": self.reachable,
            "status": self.status,
            "fallback": self.fallback,
        }


def reset_health_cache() -> None:
    """Сбросить кэш (тесты и смена настроек без перезапуска)"""
    _CACHE.clear()


async def check_provider_health(
    provider: LLMProvider, *, now: float | None = None
) -> ProviderHealth:
    """Проверить провайдера с кэшем на `CACHE_TTL_SECONDS`"""
    key = f"{provider.name}:{provider.model}"
    current = time.monotonic() if now is None else now

    cached = _CACHE.get(key)
    if cached is not None and current - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    configured = provider.is_configured()
    reachable = await provider.ping() if configured else False
    if not configured:
        status: ProviderStatus = "not_configured"
    elif reachable:
        status = "ok"
    else:
        status = "degraded"

    health = ProviderHealth(
        provider=provider.name,
        model=provider.model,
        configured=configured,
        reachable=reachable,
        status=status,
        fallback=provider.fallback_name or None,
    )
    _CACHE[key] = (current, health)
    return health
