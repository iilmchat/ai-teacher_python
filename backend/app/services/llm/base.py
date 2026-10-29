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


class LLMError(Exception):
    """Базовая ошибка LLM-слоя"""


class LLMUnavailableError(LLMError):
    """Провайдер недоступен (сеть, ключ, таймаут)"""


class LLMProvider(ABC):
    """Интерфейс провайдера LLM"""

    name: str = "base"

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
