"""
Провайдер DeepSeek (OpenAI-совместимый API).
"""

import asyncio
from collections.abc import AsyncIterator
from typing import cast

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_stream_options_param import (
    ChatCompletionStreamOptionsParam,
)

from app.config import settings
from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
    is_placeholder_secret,
)


class DeepSeekProvider(LLMProvider):
    """Облачный провайдер DeepSeek"""

    name = "deepseek"
    #: Таймаут healthcheck: не держим `/health` дольше этого значения
    PING_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "deepseek-chat",
    ) -> None:
        self.model = model
        self._api_key = api_key if api_key is not None else settings.deepseek_api_key
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=base_url or settings.deepseek_base_url,
        )

    def is_configured(self) -> bool:
        """Ключ задан и не является заглушкой из `.env.example`"""
        return not is_placeholder_secret(self._api_key)

    def _payload(self, messages: list[LLMMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def ping(self) -> bool:
        """Проверить доступ к API списком моделей (без генерации токенов)"""
        if not self.is_configured():
            return False
        try:
            await asyncio.wait_for(
                self._client.models.list(), timeout=self.PING_TIMEOUT_SECONDS
            )
        except Exception:  # noqa: BLE001 — любая ошибка транспорта = недоступен
            return False
        return True

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=self._payload(messages),  # type: ignore[arg-type]
                temperature=settings.llm_temperature if temperature is None else temperature,
                max_tokens=settings.llm_max_tokens if max_tokens is None else max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — транспортные ошибки клиента
            raise LLMUnavailableError(f"DeepSeek недоступен: {exc}") from exc

        usage = response.usage
        self.last_usage = (
            LLMUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            )
            if usage is not None
            else None
        )

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMUnavailableError("DeepSeek вернул пустой ответ")
        return content

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.last_usage = None
        stream_options: ChatCompletionStreamOptionsParam = {"include_usage": True}
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=self._payload(messages),  # type: ignore[arg-type]
                temperature=settings.llm_temperature if temperature is None else temperature,
                max_tokens=settings.llm_max_tokens if max_tokens is None else max_tokens,
                stream=True,
                # Последний чанк приходит с usage и пустым choices
                stream_options=stream_options,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailableError(f"DeepSeek недоступен: {exc}") from exc

        # create(stream=True) возвращает поток, но тип в SDK — объединение
        stream = cast("AsyncStream[ChatCompletionChunk]", response)
        async for chunk in stream:
            if chunk.usage is not None:
                self.last_usage = LLMUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                )
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def close(self) -> None:
        await self._client.close()
