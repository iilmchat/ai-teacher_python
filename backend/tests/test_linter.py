"""
Тесты линтера и метрик кода (S6-007).
"""

from app.core.linter import (
    MAX_LINE_LENGTH,
    analyze_code,
    code_stats,
    lint_code,
)


def _codes(code: str) -> list[str]:
    return [issue.code for issue in lint_code(code)]


def test_syntax_error_reported() -> None:
    """Синтаксическая ошибка — единственное замечание"""
    issues = lint_code("if True print(1)")

    assert len(issues) == 1
    assert issues[0].code == "E001"
    assert issues[0].severity == "error"


def test_forbidden_import_flagged() -> None:
    """Запрещённый импорт — ошибка безопасности"""
    issues = lint_code("import os")

    assert "S001" in _codes("import os")
    assert issues[0].severity == "error"


def test_forbidden_call_flagged() -> None:
    """open() — ошибка безопасности"""
    assert "S002" in _codes('open("file.txt")')


def test_dunder_access_flagged() -> None:
    """Dunder-атрибут — ошибка безопасности"""
    assert "S003" in _codes("print((1).__class__)")


def test_bare_except_flagged() -> None:
    """Пустой except — предупреждение"""
    code = "try:\n    x = 1\nexcept:\n    pass"

    assert "W001" in _codes(code)


def test_none_comparison_flagged() -> None:
    """Сравнение с None через == — предупреждение"""
    assert "W002" in _codes("x = 1\nif x == None:\n    pass")


def test_docstring_missing_flagged() -> None:
    """Функция без docstring — информационное замечание"""
    assert "I001" in _codes("def f(x):\n    return x + 1")


def test_docstring_present_not_flagged() -> None:
    """Функция с docstring не даёт замечания"""
    code = 'def f(x):\n    """Вернуть x."""\n    return x + 1'

    assert "I001" not in _codes(code)


def test_long_line_flagged() -> None:
    """Слишком длинная строка — предупреждение"""
    code = "x = " + " + ".join(["1"] * 60)

    assert len(code) > MAX_LINE_LENGTH
    assert "W003" in _codes(code)


def test_clean_code_has_no_issues() -> None:
    """Аккуратный код без замечаний"""
    code = '"""Сумма чисел."""\n\ntotal = sum([1, 2, 3])\nprint(total)\n'

    assert lint_code(code) == []


def test_code_stats_counts_constructs() -> None:
    """Метрики считают функции, циклы, условия, импорты"""
    code = (
        "import math\n"
        "def f(n):\n"
        "    for i in range(n):\n"
        "        if i > 0:\n"
        "            return i\n"
        "    return 0\n"
    )

    stats = code_stats(code)

    assert stats.lines == 6
    assert stats.functions == 1
    assert stats.loops == 1
    assert stats.conditions == 1
    assert stats.imports == 1


def test_code_stats_on_syntax_error_returns_lines() -> None:
    """При синтаксической ошибке метрики не падают"""
    stats = code_stats("if True print(1)")

    assert stats.lines == 1
    assert stats.functions == 0


def test_analyze_returns_issues_and_stats() -> None:
    """analyze_code объединяет линт и метрики"""
    issues, stats = analyze_code("import os\nprint(1)")

    assert any(issue.code == "S001" for issue in issues)
    assert stats.lines == 2
    assert stats.imports == 1
