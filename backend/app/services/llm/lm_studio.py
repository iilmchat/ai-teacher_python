"""
Провайдер LM Studio (локальная модель, OpenAI-совместимый endpoint).
"""

from collections.abc import AsyncIterator
from typing import cast

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk

from app.config import settings
from app.services.llm.base import LLMMessage, LLMProvider, LLMUnavailableError


class LMStudioProvider(LLMProvider):
    """Локальный провайдер LM Studio"""

    name = "lm_studio"

    def __init__(
        self,
        base_url: str | None = None,
        model: str = "local-model",
    ) -> None:
        # LM Studio не проверяет ключ, но OpenAI-клиент требует непустое значение
        self.model = model
        self._client = AsyncOpenAI(
            api_key="lm-studio",
            base_url=base_url or settings.lm_studio_url,
        )

    def _payload(self, messages: list[LLMMessage]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

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
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailableError(f"LM Studio недоступен: {exc}") from exc

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
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def close(self) -> None:
        await self._client.close()
