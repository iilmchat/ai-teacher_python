"""
Тесты прогона тест-кейсов (S7-004).
"""


from app.core.executor import ExecutionResult, SandboxedExecutor
from app.core.test_runner import (
    normalize_output,
    outputs_match,
    run_test_cases,
)


class StubExecutor(SandboxedExecutor):
    """Песочница, возвращающая вывод по подставленному stdin"""

    def __init__(self, mapping: dict[str, str]) -> None:
        super().__init__(timeout=1)
        self.mapping = mapping
        self.calls: list[tuple[str, str]] = []

    async def execute(  # type: ignore[override]
        self, code: str, stdin_text: str = ""
    ) -> ExecutionResult:
        self.calls.append((code, stdin_text))
        if stdin_text not in self.mapping:
            return ExecutionResult(
                success=False, error="KeyError: неожиданный ввод", error_type="KeyError"
            )
        return ExecutionResult(success=True, output=self.mapping[stdin_text])


def test_normalize_strips_trailing_newlines() -> None:
    """Хвостовые пустые строки не влияют на сравнение"""
    assert normalize_output("5\n\n") == "5"


def test_normalize_unifies_line_endings() -> None:
    """CRLF приводится к LF"""
    assert normalize_output("a\r\nb") == "a\nb"


def test_outputs_match_ignores_trailing_spaces() -> None:
    """Пробелы в конце строк не считаются ошибкой"""
    assert outputs_match("5\n", "5   \n") is True


def test_outputs_match_detects_difference() -> None:
    """Разный вывод не совпадает"""
    assert outputs_match("5", "6") is False


async def test_run_all_cases_pass() -> None:
    """Все кейсы пройдены"""
    executor = StubExecutor({"2\n3\n": "5\n", "-5\n5\n": "0\n"})
    cases = [
        {"input": "2\n3\n", "expected_output": "5"},
        {"input": "-5\n5\n", "expected_output": "0"},
    ]

    outcome = await run_test_cases(executor, "code", cases)

    assert outcome.passed is True
    assert outcome.passed_count == 2
    assert outcome.total_count == 2
    assert [item.index for item in outcome.results] == [1, 2]


async def test_run_partial_failure() -> None:
    """Часть кейсов провалена — итог не пройден"""
    executor = StubExecutor({"2\n3\n": "5\n", "1\n1\n": "3\n"})
    cases = [
        {"input": "2\n3\n", "expected_output": "5"},
        {"input": "1\n1\n", "expected_output": "2"},
    ]

    outcome = await run_test_cases(executor, "code", cases)

    assert outcome.passed is False
    assert outcome.passed_count == 1
    assert outcome.results[1].passed is False
    assert outcome.results[1].expected_output == "2"
    assert outcome.results[1].actual_output == "3\n"


async def test_runtime_error_marks_case_failed() -> None:
    """Ошибка выполнения помечает кейс проваленным"""

    class FailingExecutor(StubExecutor):
        async def execute(  # type: ignore[override]
            self, code: str, stdin_text: str = ""
        ) -> ExecutionResult:
            return ExecutionResult(
                success=False, error="ZeroDivisionError: division by zero"
            )

    outcome = await run_test_cases(
        FailingExecutor({}), "code", [{"input": "", "expected_output": "x"}]
    )

    assert outcome.passed is False
    assert outcome.results[0].error is not None
    assert "ZeroDivisionError" in (outcome.results[0].error or "")


async def test_stdin_is_passed_to_executor() -> None:
    """Данные кейса передаются как stdin"""
    executor = StubExecutor({"hello\n": "hi\n"})

    await run_test_cases(
        executor, "print(input())", [{"input": "hello\n", "expected_output": "hi"}]
    )

    assert executor.calls == [("print(input())", "hello\n")]


async def test_cases_limited_by_max_cases() -> None:
    """Число кейсов за прогон ограничено"""
    executor = StubExecutor({})
    cases = [{"input": str(i), "expected_output": "x"} for i in range(30)]

    outcome = await run_test_cases(executor, "code", cases, max_cases=3)

    assert outcome.total_count == 3
    assert len(executor.calls) == 3


async def test_empty_cases_trivially_pass() -> None:
    """Без тест-кейсов прогон считается успешным (задачу проверяет API)"""
    outcome = await run_test_cases(StubExecutor({}), "code", [])

    assert outcome.passed is True
    assert outcome.total_count == 0


async def test_violations_are_collected() -> None:
    """Нарушения песочницы собираются в итог"""

    class ViolationExecutor(StubExecutor):
        async def execute(  # type: ignore[override]
            self, code: str, stdin_text: str = ""
        ) -> ExecutionResult:
            return ExecutionResult(
                success=False,
                error="Импорт запрещённого модуля: os",
                error_type="SecurityError",
                violations=["Импорт запрещённого модуля: os"],
            )

    outcome = await run_test_cases(
        ViolationExecutor({}), "import os", [{"input": "", "expected_output": "x"}]
    )

    assert outcome.violations == ["Импорт запрещённого модуля: os"]
