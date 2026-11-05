"""Фейковый LLM-провайдер для тестов (не ходим в сеть, RULES §4.4).

Вынесен из `test_chat.py` (S22-001), чтобы контрактные тесты форм ответов
использовали тот же фейк, а не вторую копию.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.main import app
from app.services.llm.base import LLMMessage, LLMProvider


class FakeProvider(LLMProvider):
    """Фейковый провайдер, запоминающий переданные сообщения."""

    name = "fake"

    def __init__(
        self,
        reply: str = "Попробуй проверить условие.\n\n```python\nprint(1)\n```",
    ) -> None:
        self.reply = reply
        self.calls: list[list[LLMMessage]] = []

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(messages)
        return self.reply

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.calls.append(messages)
        for part in ("Привет", ", ", "ученик!"):
            yield part


def install_fake_provider(provider: LLMProvider) -> None:
    """Подменить провайдера в приложении через dependency_overrides."""
    from app.api.v1.chat import get_llm_provider

    app.dependency_overrides[get_llm_provider] = lambda: provider


def uninstall_fake_provider() -> None:
    from app.api.v1.chat import get_llm_provider

    app.dependency_overrides.pop(get_llm_provider, None)


def provider_override() -> dict[str, Any]:
    """Текущие переопределения (для отладки в тестах)."""
    return dict(app.dependency_overrides)
