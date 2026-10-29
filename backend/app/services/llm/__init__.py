"""
Пакет LLM-провайдеров и фабрика выбора провайдера по настройкам.
"""

from app.config import settings
from app.services.llm.base import (
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
)
from app.services.llm.deepseek import DeepSeekProvider
from app.services.llm.echo import EchoProvider
from app.services.llm.fallback import FallbackProvider
from app.services.llm.lm_studio import LMStudioProvider
from app.services.llm.metrics import MetricsProvider

__all__ = [
    "DeepSeekProvider",
    "EchoProvider",
    "FallbackProvider",
    "LLMError",
    "LLMMessage",
    "LLMProvider",
    "LLMUnavailableError",
    "LLMUsage",
    "LMStudioProvider",
    "MetricsProvider",
    "create_llm_provider",
]


def _create_single(provider_name: str) -> LLMProvider:
    """Создать один провайдер по имени без fallback-обёртки"""
    if provider_name in {"deepseek", "openai"}:
        return DeepSeekProvider()
    if provider_name in {"lm_studio", "lmstudio", "local"}:
        return LMStudioProvider()
    if provider_name == "echo":
        return EchoProvider()
    raise LLMError(f"Неизвестный LLM_PROVIDER: {provider_name}")


def create_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Создать провайдер по имени из настроек (`LLM_PROVIDER`).

    `echo` — детерминированный провайдер для e2e-тестов и демо без ключа.
    Если задан `LLM_FALLBACK_PROVIDER`, основной провайдер оборачивается в
    `FallbackProvider` (S12-002). Каждый вызов попадает в метрики (S12-003).
    """
    name = (provider_name or settings.llm_provider).strip().lower()
    primary: LLMProvider = MetricsProvider(_create_single(name))

    fallback_name = settings.llm_fallback_provider.strip().lower()
    if not fallback_name or fallback_name == name:
        return primary

    fallback = MetricsProvider(_create_single(fallback_name))
    return FallbackProvider(primary, fallback)
