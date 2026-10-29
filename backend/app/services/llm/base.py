"""
Контракт LLM-провайдеров.

Провайдер отвечает только за транспорт к модели: собрать сообщения,
отправить запрос, вернуть текст или поток токенов. Образовательная логика
(уровни, контекст, валидация) живёт в `chat_service` и `prompt_builder`.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """Сообщение в формате chat-модели"""

    role: str  # 'system' | 'user' | 'assistant'
    content: str


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Расход токенов одного вызова (из поля `usage` ответа провайдера)"""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMError(Exception):
    """Базовая ошибка LLM-слоя"""


class LLMUnavailableError(LLMError):
    """Провайдер недоступен (сеть, ключ, таймаут)"""


#: Значения-заглушки из `.env.example` — считаются «ключ не настроен».
PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        "change_me_api_key",
        "your_deepseek_api_key_here",
        "change_me_password",
    }
)


def is_placeholder_secret(value: str) -> bool:
    """Похоже ли значение на заглушку, а не на реальный секрет"""
    normalized = value.strip().lower()
    return normalized in PLACEHOLDER_SECRETS or normalized.startswith("change_me")


class LLMProvider(ABC):
    """Интерфейс провайдера LLM"""

    name: str = "base"
    #: Имя модели для healthcheck и метрик
    model: str = "unknown"
    #: Имя fallback-провайдера, если он настроен (S12-002)
    fallback_name: str = ""
    #: Расход токенов последнего вызова; None, если провайдер не отдаёт `usage`
    last_usage: LLMUsage | None = None

    def is_configured(self) -> bool:
        """Настроен ли провайдер (ключ, URL). Не ходит в сеть."""
        return True

    @property
    def used_provider(self) -> str:
        """Имя провайдера, который фактически обслужил последний вызов"""
        return self.name

    async def ping(self) -> bool:
        """Лёгкая проверка доступности провайдера.

        По умолчанию провайдер считается доступным: локальные и тестовые
        реализации не требуют сетевого вызова.
        """
        return True

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Вернуть полный ответ модели"""

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Вернуть поток текстовых дельт ответа модели"""

    async def close(self) -> None:
        """Освободить ресурсы клиента (по умолчанию — ничего)"""
        return None
