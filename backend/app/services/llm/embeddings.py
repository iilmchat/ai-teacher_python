"""
Провайдеры эмбеддингов для RAG-lite (S19-005).

Эмбеддинги не обязательны для работы приложения: если `RAG_ENABLED=false`
или LM Studio недоступен, поиск по истории чата работает через ILIKE, а
отправка сообщений — без вектора.

Провайдер отвечает только за транспорт: текст → вектор. Проверка размерности
и обработка ошибок живут в `app/services/rag.py`, чтобы сбой провайдера не
ломал ни отправку сообщения, ни поиск (fail-open).
"""

import asyncio
from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import is_placeholder_secret


class EmbeddingError(Exception):
    """Провайдер эмбеддингов недоступен или вернул некорректный ответ"""


class EmbeddingProvider(ABC):
    """Интерфейс провайдера эмбеддингов"""

    name: str = "base"
    model: str = "unknown"

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Вернуть вектор для одного текста"""

    async def close(self) -> None:
        """Освободить ресурсы клиента (по умолчанию — ничего)"""
        return None


class LMStudioEmbeddingProvider(EmbeddingProvider):
    """Эмбеддинги через OpenAI-совместимый endpoint LM Studio"""

    name = "lm_studio"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model = model or settings.rag_embedding_model
        self._base_url = base_url or settings.lm_studio_url
        self._timeout = timeout or settings.rag_embedding_timeout
        # LM Studio не проверяет ключ, но OpenAI-клиент требует непустой
        self._client = AsyncOpenAI(api_key="lm-studio", base_url=self._base_url)

    def is_configured(self) -> bool:
        """URL локального endpoint задан и не является заглушкой"""
        return bool(self._base_url.strip()) and not is_placeholder_secret(
            self._base_url
        )

    async def embed(self, text: str) -> list[float]:
        """Получить вектор текста; ошибки оборачиваются в `EmbeddingError`"""
        try:
            response = await asyncio.wait_for(
                self._client.embeddings.create(model=self.model, input=text),
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 — сеть/таймаут/модель
            raise EmbeddingError(f"LM Studio embeddings недоступны: {exc}") from exc

        if not response.data:
            raise EmbeddingError("Провайдер вернул пустой список эмбеддингов")
        return list(response.data[0].embedding)

    async def close(self) -> None:
        await self._client.close()


def create_embedding_provider() -> EmbeddingProvider | None:
    """Создать провайдер эмбеддингов из настроек или ``None``.

    Возвращает ``None``, если RAG выключен или endpoint не настроен: вызывающий
    код обязан уметь работать без эмбеддингов (ILIKE-поиск).
    """
    if not settings.rag_enabled:
        return None
    provider = LMStudioEmbeddingProvider()
    if not provider.is_configured():
        return None
    return provider
