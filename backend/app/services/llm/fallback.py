"""
Fallback LLM-провайдеров (S12-002).

Если основной провайдер недоступен, один раз пробуем резервный
(`LLM_FALLBACK_PROVIDER`, например `lm_studio`). Если недоступны оба —
`LLMUnavailableError`, который API отдаёт как 503 с понятным текстом,
а не «тихий» пустой ответ.
"""

from collections.abc import AsyncIterator

import structlog

from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
)
from app.services.llm.metrics import llm_metrics

logger = structlog.get_logger(__name__)

#: Понятное пользователю сообщение, когда оба провайдера недоступны
UNAVAILABLE_DETAIL = (
    "Ассистент временно недоступен: не отвечает ни основной, ни резервный "
    "провайдер. Попробуйте повторить вопрос через минуту."
)


class FallbackProvider(LLMProvider):
    """Провайдер с одним повтором через резервную модель"""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.model = primary.model
        self.fallback_name = fallback.name
        self.last_usage: LLMUsage | None = None
        self._active_name = primary.name

    @property
    def used_provider(self) -> str:
        return self._active_name

    def is_configured(self) -> bool:
        """Достаточно, чтобы был настроен хотя бы один из провайдеров"""
        return self.primary.is_configured() or self.fallback.is_configured()

    async def ping(self) -> bool:
        """Healthcheck отражает состояние основного провайдера"""
        return await self.primary.ping()

    def _switch_to_fallback(self, error: LLMUnavailableError) -> None:
        logger.warning(
            "llm_fallback_used",
            primary=self.primary.name,
            fallback=self.fallback.name,
            error=str(error),
        )
        llm_metrics.record_fallback(primary=self.primary.name)

    def _remember(self, provider: LLMProvider) -> None:
        self._active_name = provider.name
        self.last_usage = provider.last_usage

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        try:
            result = await self.primary.generate(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        except LLMUnavailableError as exc:
            self._switch_to_fallback(exc)
            try:
                result = await self.fallback.generate(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
            except LLMUnavailableError as fallback_error:
                logger.error(
                    "llm_all_providers_failed",
                    primary=self.primary.name,
                    fallback=self.fallback.name,
                    error=str(fallback_error),
                )
                raise LLMUnavailableError(UNAVAILABLE_DETAIL) from fallback_error
            self._remember(self.fallback)
            return result

        self._remember(self.primary)
        return result

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Поток с fallback только до первого токена.

        Если основной провайдер упал посреди ответа, переключение невозможно:
        ученик уже увидел часть текста, поэтому ошибка пробрасывается.
        """
        iterator = self.primary.stream(
            messages, temperature=temperature, max_tokens=max_tokens
        )
        try:
            first = await anext(iterator)
        except StopAsyncIteration:
            self._remember(self.primary)
            return
        except LLMUnavailableError as exc:
            self._switch_to_fallback(exc)
            try:
                async for delta in self.fallback.stream(
                    messages, temperature=temperature, max_tokens=max_tokens
                ):
                    yield delta
            except LLMUnavailableError as fallback_error:
                logger.error(
                    "llm_all_providers_failed",
                    primary=self.primary.name,
                    fallback=self.fallback.name,
                    error=str(fallback_error),
                )
                raise LLMUnavailableError(UNAVAILABLE_DETAIL) from fallback_error
            self._remember(self.fallback)
            return

        yield first
        async for delta in iterator:
            yield delta
        self._remember(self.primary)

    async def close(self) -> None:
        await self.primary.close()
        await self.fallback.close()
