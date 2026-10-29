"""
Метаданные уровней ассистента (S5-002, S5-004).

Описания уровней нужны API (`GET /chat/levels`) и документации. Тексты
промптов живут отдельно — в `app/services/llm/prompts/`.
"""

from dataclasses import dataclass

from app.models.user import UserLevel
from app.services.llm.prompt_builder import PROMPTS_DIR


@dataclass(frozen=True, slots=True)
class LevelInfo:
    """Публичное описание уровня помощи"""

    level: UserLevel
    title: str
    description: str
    audience: str
    gives_ready_code: bool


LEVELS: tuple[LevelInfo, ...] = (
    LevelInfo(
        level=UserLevel.BASIC,
        title="Базовый",
        description=(
            "Наводящие вопросы и подсказки. Ассистент указывает, где ошибка, "
            "но не исправляет её и не даёт готовых решений."
        ),
        audience="Начинающие: первые шаги в Python",
        gives_ready_code=False,
    ),
    LevelInfo(
        level=UserLevel.INTERMEDIATE,
        title="Средний",
        description=(
            "Объяснение причины ошибки и правильного синтаксиса на коротких "
            "примерах, с мини-упражнением для закрепления."
        ),
        audience="Ученики, знающие основы: циклы, условия, функции",
        gives_ready_code=False,
    ),
    LevelInfo(
        level=UserLevel.ADVANCED,
        title="Продвинутый",
        description=(
            "Полное решение с комментариями, разбор сложности, "
            "альтернативные подходы и рекомендации по стилю."
        ),
        audience="Уверенные ученики и подготовка к олимпиадам",
        gives_ready_code=True,
    ),
)


def get_level_info(level: UserLevel | str) -> LevelInfo:
    """Описание уровня по значению enum"""
    normalized = level if isinstance(level, UserLevel) else UserLevel(level)
    for info in LEVELS:
        if info.level == normalized:
            return info
    raise ValueError(f"Неизвестный уровень: {level}")


def list_levels() -> list[LevelInfo]:
    """Все уровни в порядке возрастания сложности"""
    return list(LEVELS)


def has_prompt(level: UserLevel | str) -> bool:
    """Есть ли файл промпта для уровня (fallback-проверка)"""
    normalized = level.value if isinstance(level, UserLevel) else level
    return (PROMPTS_DIR / f"{normalized}.txt").is_file()


def resolve_level(level: UserLevel | str) -> UserLevel:
    """Вернуть уровень, для которого гарантированно есть промпт.

    Если файл промпта отсутствует — откатываемся на базовый уровень,
    чтобы чат продолжал работать (fallback из S5-003).
    """
    normalized = level if isinstance(level, UserLevel) else UserLevel(level)
    return normalized if has_prompt(normalized) else UserLevel.BASIC
