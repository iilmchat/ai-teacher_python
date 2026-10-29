"""
Сборка промптов для трёх уровней ассистента (S4-003, S5-001).

Промпты лежат в файлах `prompts/<level>.txt`, а не в коде: изменение
текста инструкций — отдельный PR с тестом (RULES §8.1).
"""

from functools import lru_cache
from pathlib import Path

from app.models.user import UserLevel
from app.services.llm.base import LLMMessage

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

#: Сколько последних сообщений диалога попадает в контекст
MAX_CONTEXT_MESSAGES = 20

#: Ограничение длины одного сообщения в контексте (символов)
MAX_MESSAGE_CHARS = 4000


class PromptError(ValueError):
    """Ошибка сборки промпта"""


@lru_cache(maxsize=8)
def load_system_prompt(level: UserLevel | str) -> str:
    """Прочитать системный промпт уровня из файла"""
    level_value = level.value if isinstance(level, UserLevel) else level
    path = PROMPTS_DIR / f"{level_value}.txt"
    if not path.is_file():
        raise PromptError(f"Промпт для уровня '{level_value}' не найден: {path}")
    return path.read_text(encoding="utf-8").strip()


def build_messages(
    level: UserLevel | str,
    history: list[LLMMessage] | list[tuple[str, str]],
    user_message: str,
) -> list[LLMMessage]:
    """Собрать список сообщений для LLM с учётом уровня и истории.

    history — предыдущие сообщения диалога (LLMMessage или пары role/content).
    В контекст попадают только последние MAX_CONTEXT_MESSAGES сообщений,
    каждое обрезается до MAX_MESSAGE_CHARS символов.
    """
    normalized: list[LLMMessage] = []
    for item in history:
        if isinstance(item, LLMMessage):
            normalized.append(item)
        else:
            role, content = item
            normalized.append(LLMMessage(role=role, content=content))

    tail = normalized[-MAX_CONTEXT_MESSAGES:]

    messages = [LLMMessage(role="system", content=load_system_prompt(level))]
    for message in tail:
        messages.append(
            LLMMessage(role=message.role, content=message.content[:MAX_MESSAGE_CHARS])
        )

    messages.append(
        LLMMessage(role="user", content=user_message[:MAX_MESSAGE_CHARS])
    )
    return messages


def available_levels() -> list[UserLevel]:
    """Уровни, для которых есть файл промпта"""
    return [
        level
        for level in UserLevel
        if (PROMPTS_DIR / f"{level.value}.txt").is_file()
    ]
