"""
Детерминированный провайдер `echo` для e2e-тестов и демо без ключа.

Не обращается к сети: ответ зависит от уровня и содержит маркеры политики
уровня (базовый не даёт готовый код, продвинутый даёт решение с блоком кода).
Включается через `LLM_PROVIDER=echo`; в продакшене не используется.
"""

from collections.abc import AsyncIterator

from app.services.llm.base import LLMMessage, LLMProvider

#: Маркеры уровней для e2e: по ним тесты проверяют, что промпт выбран верно
LEVEL_MARKERS = {
    "базовый": "basic",
    "средний": "intermediate",
    "продвинутый": "advanced",
}


class EchoProvider(LLMProvider):
    """Провайдер-заглушка с предсказуемым ответом"""

    name = "echo"
    model = "echo"

    def _detect_level(self, messages: list[LLMMessage]) -> str:
        system = next((m.content for m in messages if m.role == "system"), "").lower()
        if "продвинутый" in system:
            return "advanced"
        if "средний" in system:
            return "intermediate"
        return "basic"

    def _last_question(self, messages: list[LLMMessage]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content.strip()
        return ""

    def build_reply(self, messages: list[LLMMessage]) -> str:
        """Собрать ответ по уровню"""
        level = self._detect_level(messages)
        question = self._last_question(messages)
        short = question[:120]

        if level == "basic":
            return (
                f"Давай разберёмся вместе. Ты спросил: «{short}».\n\n"
                "Какая строка кода, по-твоему, выполняется не так, как ожидается?"
            )
        if level == "intermediate":
            return (
                f"Причина обычно в типе данных или операторе. По вопросу «{short}»:\n\n"
                "```python\nvalue = int(input())\nprint(value + 1)\n```\n\n"
                "Попробуй применить этот приём к своей задаче."
            )
        return (
            f"Разбор вопроса «{short}».\n\n"
            "```python\ntotal = sum(range(5))\nprint(total)  # 10\n```\n\n"
            "Альтернатива: цикл `for` с накопителем. Итог тот же, но нагляднее."
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self.build_reply(messages)

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        reply = self.build_reply(messages)
        # Отдаём кусками, чтобы e2e видел именно стриминг
        for index in range(0, len(reply), 20):
            yield reply[index : index + 20]
