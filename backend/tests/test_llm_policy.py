"""
Тесты детектора «готового решения» для базового уровня (S12-005).
"""

import pytest

from app.services.llm.policy import (
    FULL_CODE_MIN_LINES,
    detect_level_policy_violations,
    extract_code_blocks,
)

SHORT_SYNTAX = "```python\nx = 1\n```"
FULL_PROGRAM = """```python
n = int(input("N: "))
total = 0
for i in range(1, n + 1):
    total += i
print(total)
```"""


def test_short_syntax_example_is_allowed() -> None:
    """Короткая иллюстрация синтаксиса — не решение задачи"""
    assert detect_level_policy_violations("basic", f"Посмотри на синтаксис:\n{SHORT_SYNTAX}") == []


def test_long_code_block_flagged() -> None:
    codes = detect_level_policy_violations("basic", f"Вот фрагмент:\n{FULL_PROGRAM}")

    assert "basic_code_block" in codes


def test_full_program_flagged() -> None:
    codes = detect_level_policy_violations("basic", FULL_PROGRAM)

    assert "basic_full_solution" in codes


def test_ready_solution_phrase_flagged() -> None:
    codes = detect_level_policy_violations("basic", "Вот готовое решение задачи, спиши его.")

    assert codes == ["basic_ready_solution_phrase"]


def test_code_without_input_and_print_not_full_solution() -> None:
    block = "\n".join(["a = 1", "b = 2", "c = a + b", "d = c * 2"])
    assert len(block.splitlines()) >= FULL_CODE_MIN_LINES

    codes = detect_level_policy_violations("basic", f"```python\n{block}\n```")

    assert "basic_code_block" in codes
    assert "basic_full_solution" not in codes


@pytest.mark.parametrize("level", ["intermediate", "advanced"])
def test_non_basic_levels_are_not_checked(level: str) -> None:
    """Средний показывает примеры, продвинутый обязан давать решение"""
    assert detect_level_policy_violations(level, FULL_PROGRAM) == []


def test_text_answer_has_no_warnings() -> None:
    assert detect_level_policy_violations("basic", "Где у тебя объявлена переменная?") == []


def test_extract_code_blocks_reused_by_policy() -> None:
    text = "```python\nprint(1)\n```\nи ещё:\n```\nx = 2\n```"

    assert extract_code_blocks(text) == ["print(1)", "x = 2"]
