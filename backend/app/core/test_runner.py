"""
Прогон тест-кейсов задачи (S7-004, S23-001).

Каждый кейс выполняется в песочнице с подставленным `stdin`. С S23-001 все
кейсы задачи выполняются **одним** дочерним интерпретатором (батч): на задачах
с 2–20 кейсами это убирает повторный старт интерпретатора на каждый кейс и
даёт кратный рост throughput submit (KI-022). Изоляция между кейсами
сохраняется: `_run_restricted` создаёт свежие globals/builtins на каждый вызов,
а лимиты (память/таймаут) действуют на процесс и на кейс соответственно.

Сравнение вывода мягкое: сравниваются строки без завершающих пробелов и
переводов строк — так ученик не наказывается за лишний `\n` от `print`.
"""

from dataclasses import dataclass, field

from app.core.executor import ExecutionResult, SandboxedExecutor

#: Больше кейсов за один прогон не запускаем (стоимость и время)
MAX_CASES_PER_RUN = 20


@dataclass(slots=True)
class CaseOutcome:
    """Результат одного тест-кейса"""

    index: int
    passed: bool
    input: str
    expected_output: str
    actual_output: str
    description: str | None = None
    error: str | None = None


@dataclass(slots=True)
class CaseRunOutcome:
    """Итог прогона всех кейсов"""

    passed: bool
    passed_count: int
    total_count: int
    results: list[CaseOutcome] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


def normalize_output(text: str) -> str:
    """Привести вывод к сравнимому виду"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    # Убираем пустые строки в конце (лишние переводы строк)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def outputs_match(expected: str, actual: str) -> bool:
    """Сравнить ожидаемый и фактический вывод"""
    return normalize_output(expected) == normalize_output(actual)


async def run_test_cases(
    executor: SandboxedExecutor,
    code: str,
    test_cases: list[dict[str, object]],
    *,
    max_cases: int = MAX_CASES_PER_RUN,
) -> CaseRunOutcome:
    """Прогнать код ученика по тест-кейсам задачи"""
    if not test_cases:
        return CaseRunOutcome(
            passed=True,
            passed_count=0,
            total_count=0,
            results=[],
        )

    results: list[CaseOutcome] = []
    violations: list[str] = []

    selected = test_cases[:max_cases]
    inputs = [str(case.get("input", "")) for case in selected]

    # Один дочерний интерпретатор на все кейсы (S23-001); fallback внутри
    # execute_many, если батчевый протокол недоступен.
    executions: list[ExecutionResult] = await executor.execute_many(code, inputs)

    for index, (case, case_input, result) in enumerate(
        zip(selected, inputs, executions, strict=True)
    ):
        expected = str(case.get("expected_output", ""))
        description = case.get("description")
        description_text = str(description) if description is not None else None

        violations.extend(result.violations)

        actual = result.output
        if result.success:
            passed = outputs_match(expected, actual)
            error = None
        else:
            passed = False
            error = result.error

        results.append(
            CaseOutcome(
                index=index + 1,
                passed=passed,
                input=case_input,
                expected_output=expected,
                actual_output=actual,
                description=description_text,
                error=error,
            )
        )

    passed_count = sum(1 for item in results if item.passed)
    return CaseRunOutcome(
        passed=passed_count == len(results),
        passed_count=passed_count,
        total_count=len(results),
        results=results,
        violations=sorted(set(violations)),
    )
