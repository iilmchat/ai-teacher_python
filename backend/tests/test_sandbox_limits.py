"""
Тесты лимитов песочницы без запуска дочернего процесса (S13-004, S13-005).

Проверяем статические и рантайм-запреты, обрезку вывода и таблицу
«вектор атаки → отказ». Лимит памяти проверяется отдельно в
`test_executor_memory.py` — его нельзя ставить процессу pytest.
"""

# Для проверки записи файла используем tmp_path, но код не должен её создать
from pathlib import Path

import pytest

from app.core.executor import _run_restricted
from app.core.sandbox_limits import truncate_output


def test_truncate_output_keeps_short_text() -> None:
    text, truncated = truncate_output("короткий вывод\n", 100)

    assert text == "короткий вывод\n"
    assert truncated is False


def test_truncate_output_cuts_long_text() -> None:
    text, truncated = truncate_output("x" * 5000, 1000)

    assert truncated is True
    assert len(text) <= 1000
    assert "вывод обрезан" in text


def test_restricted_output_is_truncated() -> None:
    result = _run_restricted("print('x' * 5000)", max_output_chars=1000)

    assert result["success"] is True
    assert result["output_truncated"] is True
    assert len(result["output"]) <= 1000


def test_restricted_output_not_truncated_when_small() -> None:
    result = _run_restricted("print('ok')", max_output_chars=1000)

    assert result["success"] is True
    assert result["output_truncated"] is False
    assert result["output"].strip() == "ok"


ATTACKS = [
    ("import socket", "SecurityError"),
    ("import urllib.request", "SecurityError"),
    ("import http.client", "SecurityError"),
    ("import os", "SecurityError"),
    ("import subprocess", "SecurityError"),
    ('open("x.txt", "w")', "SecurityError"),
    ("eval('1+1')", "SecurityError"),
    ("exec('print(1)')", "SecurityError"),
    ("globals()", "SecurityError"),
    ("(1).__class__", "SecurityError"),
    ("[].__class__.__bases__", "SecurityError"),
]


@pytest.mark.parametrize(("code", "error_type"), ATTACKS)
def test_attack_vectors_are_rejected(code: str, error_type: str) -> None:
    """Опасные конструкции блокируются до выполнения"""
    result = _run_restricted(code)

    assert result["success"] is False
    assert result["error_type"] == error_type


@pytest.mark.parametrize(
    "code",
    [
        "getattr(1, '__class__')",  # getattr не входит в ограниченные builtins
        "__builtins__['open']",  # open отсутствует в словаре builtins
        "__import__('os')",  # вызов запрещён, импорт не выполняется
    ],
)
def test_bypass_attempts_do_not_execute(code: str) -> None:
    """Обходные трюки не дают доступа к опасным функциям"""
    result = _run_restricted(code)

    assert result["success"] is False


def test_file_is_not_created(tmp_path: Path) -> None:
    """Запись в файл невозможна — open заблокирован"""
    target = tmp_path / "student.txt"
    code = f'open(r"{target}", "w").write("pwned")'

    result = _run_restricted(code)

    assert result["success"] is False
    assert target.exists() is False
