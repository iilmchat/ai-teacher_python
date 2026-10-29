"""
Политика уровней поверх промпта (S12-005).

Промпт задаёт правила, но модель не обязана им следовать. Для базового
уровня ответ с готовым кодом — нарушение политики, поэтому такие ответы
помечаются предупреждением. Мы не блокируем ответ: ученик всё равно его
увидит, а преподаватель/метрики узнают о нарушении.
"""

import re

from app.models.user import UserLevel

#: Регулярное выражение для блоков кода в markdown
CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.+?)```", re.DOTALL)

#: Фразы, которыми модель выдаёт готовое решение
READY_SOLUTION_RE = re.compile(
    r"(вот\s+(?:готовое\s+)?(?:решение|код|программа))"
    r"|((?:готовое|полное)\s+решение)"
    r"|(полный\s+код)",
    re.IGNORECASE,
)

#: Сколько строк кода уже считается «решением», а не иллюстрацией синтаксиса
FULL_CODE_MIN_LINES = 4

#: Порог «полной программы» по числу строк
FULL_PROGRAM_MIN_LINES = 6

INPUT_RE = re.compile(r"\binput\s*\(")
PRINT_RE = re.compile(r"\bprint\s*\(")
DEF_RE = re.compile(r"^\s*def\s+\w+", re.MULTILINE)
RETURN_RE = re.compile(r"^\s*return\b", re.MULTILINE)


def extract_code_blocks(text: str) -> list[str]:
    """Извлечь блоки кода из markdown-ответа модели"""
    return [block.strip() for block in CODE_BLOCK_RE.findall(text) if block.strip()]


def _is_full_program(block: str) -> bool:
    """Похож ли блок на законченную программу, а не на фрагмент синтаксиса"""
    lines = [line for line in block.splitlines() if line.strip()]
    if len(lines) >= FULL_PROGRAM_MIN_LINES:
        return True
    has_io = bool(INPUT_RE.search(block) and PRINT_RE.search(block))
    has_function = bool(DEF_RE.search(block) and RETURN_RE.search(block))
    return has_io or has_function


def detect_level_policy_violations(
    level: UserLevel | str, answer: str
) -> list[str]:
    """Коды нарушений политики уровня для готового ответа модели.

    Проверяется только базовый уровень: средний может показывать короткие
    примеры синтаксиса, продвинутый обязан давать решение.
    """
    level_value = level.value if isinstance(level, UserLevel) else level
    if level_value != UserLevel.BASIC.value:
        return []

    blocks = extract_code_blocks(answer)
    codes: list[str] = []

    if any(len([line for line in block.splitlines() if line.strip()]) >= FULL_CODE_MIN_LINES
           for block in blocks):
        codes.append("basic_code_block")

    if any(_is_full_program(block) for block in blocks):
        codes.append("basic_full_solution")

    if READY_SOLUTION_RE.search(answer):
        codes.append("basic_ready_solution_phrase")

    return codes
