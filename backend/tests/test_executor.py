"""
Тесты песочницы (S6-007).

Каждый тест запускает отдельный интерпретатор, поэтому набор помечен `slow`:
быстрый прогон — `pytest -m "not slow"`, полный — `pytest`.
"""

import pytest

from app.core.executor import SandboxedExecutor, find_violations

pytestmark = pytest.mark.slow


@pytest.fixture
def executor() -> SandboxedExecutor:
    return SandboxedExecutor(timeout=3)


async def test_print_output(executor: SandboxedExecutor) -> None:
    """print попадает в вывод"""
    result = await executor.execute('print("привет")')

    assert result.success is True
    assert result.output.strip() == "привет"
    assert result.error is None


async def test_allowed_import_math(executor: SandboxedExecutor) -> None:
    """Разрешённый модуль доступен"""
    result = await executor.execute("import math\nprint(math.sqrt(16))")

    assert result.success is True
    assert result.output.strip() == "4.0"


async def test_loop_and_augmented_assignment(executor: SandboxedExecutor) -> None:
    """Циклы и `+=` работают (guard `_inplacevar_`)"""
    code = "total = 0\nfor i in range(5):\n    total += i\nprint(total)"

    result = await executor.execute(code)

    assert result.success is True
    assert result.output.strip() == "10"


async def test_forbidden_import_os(executor: SandboxedExecutor) -> None:
    """Импорт os блокируется до выполнения"""
    result = await executor.execute("import os\nprint(os.getcwd())")

    assert result.success is False
    assert result.error_type == "SecurityError"
    assert "os" in (result.error or "")


async def test_forbidden_import_subprocess(executor: SandboxedExecutor) -> None:
    """Импорт subprocess блокируется"""
    result = await executor.execute("import subprocess")

    assert result.success is False
    assert result.error_type == "SecurityError"


async def test_forbidden_open(executor: SandboxedExecutor) -> None:
    """open() блокируется"""
    result = await executor.execute('open("secret.txt", "r")')

    assert result.success is False
    assert result.error_type == "SecurityError"


async def test_forbidden_dunder_access(executor: SandboxedExecutor) -> None:
    """Обращение к dunder-атрибутам блокируется"""
    result = await executor.execute("print((1).__class__)")

    assert result.success is False
    assert result.error_type == "SecurityError"


async def test_fstring_formatting_works(executor: SandboxedExecutor) -> None:
    """f-строки — безопасная замена .format() в RP 8.x"""
    result = await executor.execute("x = 5\nprint(f'x = {x:>3}')")

    assert result.success is True
    assert result.output.strip() == "x =   5"


@pytest.mark.parametrize(
    "code",
    [
        "print('{0.__class__}'.format(1))",
        "print('{0}'.format(1))",
        "print('{0}'.format_map({'0': 1}))",
        "import string\nprint(string.Formatter)",
    ],
)
async def test_str_format_is_blocked_with_hint(
    executor: SandboxedExecutor, code: str
) -> None:
    """RP 8.x блокирует format-методы строки (GHSA-hp3v-5vw7-fx9w)

    Ученику возвращается понятная подсказка вместо `NotImplementedError`.
    """
    result = await executor.execute(code)

    assert result.success is False
    assert result.error_type == "RestrictedFeatureError"
    assert "f-строки" in (result.error or "")


async def test_runtime_error_reported(executor: SandboxedExecutor) -> None:
    """Ошибка времени выполнения возвращается с типом"""
    result = await executor.execute("print(1 / 0)")

    assert result.success is False
    assert result.error_type == "ZeroDivisionError"
    assert "division by zero" in (result.error or "")


async def test_syntax_error_reported(executor: SandboxedExecutor) -> None:
    """Синтаксическая ошибка возвращается с типом"""
    result = await executor.execute("if True print(1)")

    assert result.success is False
    assert result.error_type == "SyntaxError"


async def test_infinite_loop_is_killed() -> None:
    """Бесконечный цикл прерывается по таймауту"""
    executor = SandboxedExecutor(timeout=1.5)

    result = await executor.execute("while True:\n    pass")

    assert result.success is False
    assert result.error_type == "TimeoutError"


def test_find_violations_detects_dangerous_code() -> None:
    """Статический анализ находит запрещённые конструкции"""
    code = "import os\nopen('x')\nprint((1).__class__)"
    violations = find_violations(code)

    assert any("os" in item for item in violations)
    assert any("open" in item for item in violations)
    assert any("__class__" in item for item in violations)


def test_find_violations_ignores_safe_code() -> None:
    """Безопасный код не даёт нарушений"""
    assert find_violations("print(sum([1, 2, 3]))") == []
