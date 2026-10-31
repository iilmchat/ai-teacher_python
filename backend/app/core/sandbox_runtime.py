"""Чистое ядро песочницы: RestrictedPython-выполнение без зависимостей приложения (S24-001).

Модуль специально не импортирует app.config / app.errors / БД: его копируют в
образ контейнера-раннера (backend/sandbox_runner), где нет ни pydantic, ни
sqlalchemy. Всё, что нужно — stdlib, RestrictedPython и sandbox_limits.

Публичные функции:

* find_violations(code) — статический анализ AST (до выполнения);
* run_restricted(code, stdin, ...) — выполнить код и вернуть dict-результат
  (используется и нативным раннером, и контейнерным).

executor.py реэкспортирует run_restricted как _run_restricted и
find_violations, чтобы остальной код и тесты не менялись.
"""

from __future__ import annotations

import ast
import builtins as builtins_module
import contextlib
import io
import time
from dataclasses import dataclass, field
from typing import Any

from RestrictedPython.compile import compile_restricted

# RP 8.x: `__init__` реэкспортирует имена без `__all__` — mypy(strict) считает
# их неэкспортированными, поэтому импортируем из подмодулей явно.
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector

from app.core.sandbox_limits import apply_memory_limit, truncate_output

#: Модули, доступные ученику в песочнице
ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "math",
        "random",
        "datetime",
        "collections",
        "itertools",
        "functools",
        "string",
        "re",
        "statistics",
        "decimal",
        "fractions",
        "json",
    }
)

#: Модули, импорт которых всегда отклоняется (для понятного сообщения)
FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "shutil",
        "pathlib",
        "importlib",
        "builtins",
        "ctypes",
        "multiprocessing",
        "threading",
        "sqlite3",
        "http",
        "urllib",
        "requests",
        "pickle",
        "marshal",
    }
)

#: Функции, вызов которых запрещён.
#: `input` разрешён: он читает только переданный stdin, а не терминал.
FORBIDDEN_CALLS: frozenset[str] = frozenset(
    {"eval", "exec", "compile", "open", "__import__", "globals", "locals"}
)


@dataclass(slots=True)
class ExecutionResult:
    """Результат выполнения кода"""

    success: bool
    output: str = ""
    error: str | None = None
    execution_time: float = 0.0
    error_type: str | None = None
    violations: list[str] = field(default_factory=list)
    #: Удалось ли применить лимит памяти (S13-001, S13-002)
    memory_limit_enforced: bool = False
    #: Был ли вывод обрезан по лимиту (S13-005)
    output_truncated: bool = False


class _OutputCollector:
    """Сборщик `print` для RestrictedPython.

    RestrictedPython вызывает `_print_` напрямую в одних версиях и
    `_print_._call_print(...)` в других, поэтому поддерживаем оба варианта.
    """

    def __init__(self) -> None:
        self._parts: list[str] = []

    def __call__(self, *objects: object, **kwargs: object) -> None:
        self._call_print(*objects, **kwargs)

    def write(self, text: str) -> None:
        self._parts.append(str(text))

    def _call_print(self, *objects: object, **kwargs: object) -> None:
        sep = str(kwargs.get("sep", " "))
        end = str(kwargs.get("end", "\n"))
        self._parts.append(sep.join(str(obj) for obj in objects) + end)

    def getvalue(self) -> str:
        return "".join(self._parts)


def _safe_import(
    name: str,
    globals_: dict[str, Any] | None = None,
    locals_: dict[str, Any] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> Any:
    """Разрешённый импорт: только из белого списка"""
    root = name.split(".")[0]
    if root in FORBIDDEN_MODULES:
        raise ImportError(f"Модуль '{root}' запрещён в песочнице")
    if root not in ALLOWED_MODULES:
        raise ImportError(
            f"Модуль '{root}' недоступен. "
            f"Разрешены: {', '.join(sorted(ALLOWED_MODULES))}"
        )
    return __import__(name, globals_, locals_, fromlist, level)


def _build_builtins() -> dict[str, Any]:
    """Ограниченные builtins: safe_builtins + безопасные встроенные функции"""
    from RestrictedPython.Guards import safe_builtins

    builtins_copy: dict[str, Any] = dict(safe_builtins)
    builtins_copy["__import__"] = _safe_import
    for name in (
        "abs",
        "all",
        "any",
        "bool",
        "chr",
        "dict",
        "divmod",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "ord",
        "pow",
        "range",
        "reversed",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    ):
        builtins_copy[name] = getattr(builtins_module, name)
    return builtins_copy


def _inplace_var(op: str, left: Any, right: Any) -> Any:
    """Guard для расширенных присваиваний (`+=`, `-=`, ...).

    RestrictedPython заменяет `n += 1` на `n = _inplacevar_("+=", n, 1)`,
    поэтому операцию нужно реализовать явно.
    """
    operations: dict[str, Any] = {
        "+=": lambda a, b: a + b,
        "-=": lambda a, b: a - b,
        "*=": lambda a, b: a * b,
        "/=": lambda a, b: a / b,
        "//=": lambda a, b: a // b,
        "%=": lambda a, b: a % b,
        "**=": lambda a, b: a**b,
        "&=": lambda a, b: a & b,
        "|=": lambda a, b: a | b,
        "^=": lambda a, b: a ^ b,
        "<<=": lambda a, b: a << b,
        ">>=": lambda a, b: a >> b,
    }
    operation = operations.get(op)
    if operation is None:
        raise SyntaxError(f"Неподдерживаемая операция: {op}")
    return operation(left, right)


def _restricted_feature_error(exc: Exception) -> tuple[str, str] | None:
    """Понятное сообщение для ограничений RestrictedPython 8.x (S20-001).

    RP 8.x полностью блокирует `str.format`/`str.format_map` и
    `string.Formatter`: через них происходил обход песочницы
    (GHSA-hp3v-5vw7-fx9w, GHSA-ffg3-p8fm-mjx2). Ученику вместо
    `NotImplementedError: Using the format*() methods of `str` is not safe`
    показываем подсказку про f-строки и `%`.
    """
    message = str(exc)
    if isinstance(exc, NotImplementedError) and "format" in message.lower():
        return (
            "RestrictedFeatureError",
            "Форматирование через .format()/.format_map() недоступно в "
            "песочнице: используйте f-строки (f\"{x}\") или оператор %.",
        )
    return None


def find_violations(code: str) -> list[str]:
    """Статически найти опасные конструкции (без выполнения)"""
    violations: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    violations.append(f"Импорт запрещённого модуля: {root}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in FORBIDDEN_MODULES:
                violations.append(f"Импорт запрещённого модуля: {root}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                violations.append(f"Вызов запрещённой функции: {node.func.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            violations.append(f"Обращение к служебному атрибуту: {node.attr}")
    return violations


def run_restricted(
    code: str,
    stdin_text: str = "",
    *,
    memory_limit_mb: int | None = None,
    max_output_chars: int | None = None,
    apply_limits: bool = False,
) -> dict[str, Any]:
    """Выполнить код в RestrictedPython и вернуть словарь результата.

    Функция вызывается в дочернем процессе, поэтому не использует БД и сеть.
    `stdin_text` подаётся в `input()` построчно; когда строки кончаются,
    возвращается пустая строка (чтобы код не завис).

    `apply_limits=True` ставит лимит памяти на текущий процесс (только в
    дочернем интерпретаторе; в тестах `_run_restricted` вызывается напрямую,
    чтобы не ограничивать сам pytest).
    """
    violations = find_violations(code)
    if violations:
        return {
            "success": False,
            "output": "",
            "error": "; ".join(violations),
            "error_type": "SecurityError",
            "violations": violations,
        }

    memory_enforced = False
    limits_warning: str | None = None
    if apply_limits and memory_limit_mb:
        memory_enforced, limits_warning = apply_memory_limit(memory_limit_mb)

    stdin_lines = iter(stdin_text.splitlines())

    def _safe_input(prompt: str = "") -> str:
        try:
            return next(stdin_lines)
        except StopIteration:
            return ""

    builtins_for_run = _build_builtins()
    builtins_for_run["input"] = _safe_input

    # RP 7 инстанцирует PrintCollector сам: `_print = _print_(_getattr_)`.
    # Собранный вывод доступен после exec в globals['_print'].
    safe_globals: dict[str, Any] = {
        "__builtins__": builtins_for_run,
        "__name__": "student_script",
        "_print_": PrintCollector,
        "_getattr_": safer_getattr,
        "_getitem_": lambda obj, key: obj[key],
        "_getiter_": iter,
        "_write_": full_write_guard,
        "_inplacevar_": _inplace_var,
        "_unpack_sequence_": guarded_unpack_sequence,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
    }

    def collected_output() -> str:
        """Вывод, собранный PrintCollector (если он создан)"""
        printer = safe_globals.get("_print")
        if callable(printer):
            try:
                return str(printer())
            except Exception:  # noqa: BLE001 — не ломаем отчёт о результате
                return ""
        return ""

    started = time.perf_counter()
    try:
        byte_code = compile_restricted(code, "<student_code>", "exec")
    except SyntaxError as exc:
        return {
            "success": False,
            "output": "",
            "error": f"{exc.msg} (строка {exc.lineno})",
            "error_type": "SyntaxError",
            "violations": violations,
            "memory_limit_enforced": memory_enforced,
            "limits_warning": limits_warning,
        }
    except Exception as exc:  # noqa: BLE001 — RestrictedPython может бросить своё
        restricted = _restricted_feature_error(exc)
        return {
            "success": False,
            "output": "",
            "error": restricted[1] if restricted else str(exc),
            "error_type": restricted[0] if restricted else type(exc).__name__,
            "violations": violations,
            "memory_limit_enforced": memory_enforced,
            "limits_warning": limits_warning,
        }

    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(byte_code, safe_globals)  # noqa: S102 — код ограничен RestrictedPython
    except Exception as exc:  # noqa: BLE001 — любая ошибка ученика
        output, truncated = truncate_output(
            collected_output() + buffer.getvalue(), max_output_chars
        )
        restricted = _restricted_feature_error(exc)
        return {
            "success": False,
            "output": output,
            "error": restricted[1] if restricted else f"{type(exc).__name__}: {exc}",
            "error_type": restricted[0] if restricted else type(exc).__name__,
            "execution_time": time.perf_counter() - started,
            "violations": violations,
            "memory_limit_enforced": memory_enforced,
            "output_truncated": truncated,
            "limits_warning": limits_warning,
        }

    output, truncated = truncate_output(
        collected_output() + buffer.getvalue(), max_output_chars
    )
    return {
        "success": True,
        "output": output,
        "error": None,
        "error_type": None,
        "execution_time": time.perf_counter() - started,
        "violations": violations,
        "memory_limit_enforced": memory_enforced,
        "output_truncated": truncated,
        "limits_warning": limits_warning,
    }


#: Совместимость: до S24 функция называлась `_run_restricted`
_run_restricted = run_restricted

