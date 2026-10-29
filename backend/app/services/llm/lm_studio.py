"""
Провайдер LM Studio (локальная модель, OpenAI-совместимый endpoint).
"""

import asyncio
from collections.abc import AsyncIterator
from typing import cast

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk

from app.config import settings
from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
    is_placeholder_secret,
)


class LMStudioProvider(LLMProvider):
    """Локальный провайдер LM Studio"""

    name = "lm_studio"
    PING_TIMEOUT_SECONDS = 3.0

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        # LM Studio не проверяет ключ, но OpenAI-клиент требует непустое значение
        self.model = model or settings.lm_studio_model
        self._base_url = base_url or settings.lm_studio_url
        self._client = AsyncOpenAI(
            api_key="lm-studio",
            base_url=self._base_url,
        )

    def is_configured(self) -> bool:
        """URL локального endpoint задан и не является заглушкой"""
        return bool(self._base_url.strip()) and not is_placeholder_secret(self._base_url)

    async def ping(self) -> bool:
        """Проверить, что LM Studio отвечает на /models"""
        if not self.is_configured():
            return False
        try:
            await asyncio.wait_for(
                self._client.models.list(), timeout=self.PING_TIMEOUT_SECONDS
            )
        except Exception:  # noqa: BLE001 — локальный сервер может быть не запущен
            return False
        return True

    def _payload(self, messages: list[LLMMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def _remember_usage(self, usage: object | None) -> None:
        """Сохранить usage, если провайдер его вернул (LM Studio — опционально)"""
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            self.last_usage = LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.last_usage = None
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=self._payload(messages),  # type: ignore[arg-type]
                temperature=settings.llm_temperature if temperature is None else temperature,
                max_tokens=settings.llm_max_tokens if max_tokens is None else max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailableError(f"LM Studio недоступен: {exc}") from exc

        self._remember_usage(response.usage)
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMUnavailableError("LM Studio вернул пустой ответ")
        return content

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.last_usage = None
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=self._payload(messages),  # type: ignore[arg-type]
                temperature=settings.llm_temperature if temperature is None else temperature,
                max_tokens=settings.llm_max_tokens if max_tokens is None else max_tokens,
                stream=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailableError(f"LM Studio недоступен: {exc}") from exc

        # create(stream=True) возвращает поток, но тип в SDK — объединение
        stream = cast("AsyncStream[ChatCompletionChunk]", response)
        async for chunk in stream:
            self._remember_usage(getattr(chunk, "usage", None))
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def close(self) -> None:
        await self._client.close()
