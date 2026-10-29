"""
Пакет LLM-провайдеров и фабрика выбора провайдера по настройкам.
"""

from app.config import settings
from app.services.llm.base import (
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
)
from app.services.llm.deepseek import DeepSeekProvider
from app.services.llm.echo import EchoProvider
from app.services.llm.lm_studio import LMStudioProvider

__all__ = [
    "DeepSeekProvider",
    "EchoProvider",
    "LLMError",
    "LLMMessage",
    "LLMProvider",
    "LLMUnavailableError",
    "LMStudioProvider",
    "create_llm_provider",
]


def create_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Создать провайдер по имени из настроек (`LLM_PROVIDER`).

    `echo` — детерминированный провайдер для e2e-тестов и демо без ключа.
    """
    name = (provider_name or settings.llm_provider).strip().lower()

    if name in {"deepseek", "openai"}:
        return DeepSeekProvider()
    if name in {"lm_studio", "lmstudio", "local"}:
        return LMStudioProvider()
    if name == "echo":
        return EchoProvider()

    raise LLMError(f"Неизвестный LLM_PROVIDER: {name}")
