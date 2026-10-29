"""
Безопасное выполнение Python-кода ученика (S6-001, S6-002, S6-003).

Защита в несколько слоёв:

1. Статический анализ AST — отклоняет запрещённые импорты, `eval`/`exec`/`open`,
   dunder-атрибуты (`find_violations`).
2. `compile_restricted` (RestrictedPython) — ограниченный синтаксис.
3. Ограниченные builtins + guard'ы доступа к атрибутам и записи.
4. Собственный `__import__` с белым списком модулей.
5. Выполнение в отдельном процессе интерпретатора Python: по таймауту процесс
   убивается, поэтому `while True` не «съедает» воркер API.

Почему subprocess, а не multiprocessing: на Windows spawn перезапускает
`__main__`, что конфликтует с uvicorn («Safe importing of main module»).
Отдельный интерпретатор изолирован полностью и не зависит от `__main__`.

Ограничение: лимит памяти (RSS) на Windows не enforced — см. KNOWN_ISSUES.
"""

import ast
import asyncio
import builtins as builtins_module
import contextlib
import io
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from RestrictedPython import PrintCollector, compile_restricted
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safer_getattr,
)

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


def _run_restricted(code: str, stdin_text: str = "") -> dict[str, Any]:
    """Выполнить код в RestrictedPython и вернуть словарь результата.

    Функция вызывается в дочернем процессе, поэтому не использует БД и сеть.
    `stdin_text` подаётся в `input()` построчно; когда строки кончаются,
    возвращается пустая строка (чтобы код не завис).
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
        }
    except Exception as exc:  # noqa: BLE001 — RestrictedPython может бросить своё
        return {
            "success": False,
            "output": "",
            "error": str(exc),
            "error_type": type(exc).__name__,
            "violations": violations,
        }

    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            exec(byte_code, safe_globals)  # noqa: S102 — код ограничен RestrictedPython
    except Exception as exc:  # noqa: BLE001 — любая ошибка ученика
        return {
            "success": False,
            "output": collected_output() + buffer.getvalue(),
            "error": f"{type(exc).__name__}: {exc}",
            "error_type": type(exc).__name__,
            "execution_time": time.perf_counter() - started,
            "violations": violations,
        }

    return {
        "success": True,
        "output": collected_output() + buffer.getvalue(),
        "error": None,
        "error_type": None,
        "execution_time": time.perf_counter() - started,
        "violations": violations,
    }


#: Каталог backend — нужен, чтобы дочерний интерпретатор импортировал `app`
BACKEND_DIR = Path(__file__).resolve().parents[2]

#: Код раннера: читает JSON {code, stdin} из stdin, пишет JSON-результат в stdout
_RUNNER = (
    "import json, sys\n"
    "from app.core.executor import _run_restricted\n"
    "payload = json.loads(sys.stdin.read())\n"
    "result = _run_restricted(payload['code'], payload.get('stdin', ''))\n"
    "sys.stdout.write(json.dumps(result, ensure_ascii=False))\n"
)


class SandboxedExecutor:
    """Песочница для кода ученика"""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def _execute_in_process(self, code: str, stdin_text: str = "") -> ExecutionResult:
        """Запустить код в отдельном интерпретаторе и дождаться результата"""
        env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(BACKEND_DIR),
        }
        payload = json.dumps({"code": code, "stdin": stdin_text}, ensure_ascii=False)
        started = time.perf_counter()

        try:
            completed = subprocess.run(  # noqa: S603 — фиксированная команда
                [sys.executable, "-c", _RUNNER],
                input=payload.encode("utf-8"),
                capture_output=True,
                timeout=self.timeout,
                cwd=str(BACKEND_DIR),
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"Превышен лимит времени выполнения ({self.timeout:.0f} с)",
                error_type="TimeoutError",
                execution_time=time.perf_counter() - started,
            )

        elapsed = time.perf_counter() - started
        stdout = completed.stdout.decode("utf-8", errors="replace").strip()

        try:
            raw: dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            return ExecutionResult(
                success=False,
                error=f"Сбой песочницы: {stderr[-500:] or 'нет ответа'}",
                error_type="SandboxError",
                execution_time=elapsed,
            )

        return ExecutionResult(
            success=bool(raw.get("success")),
            output=str(raw.get("output", "")),
            error=raw.get("error"),
            execution_time=float(raw.get("execution_time") or elapsed),
            error_type=raw.get("error_type"),
            violations=list(raw.get("violations") or []),
        )

    async def execute(self, code: str, stdin_text: str = "") -> ExecutionResult:
        """Выполнить код в песочнице (блокирующая работа — в отдельном потоке)"""
        return await asyncio.to_thread(self._execute_in_process, code, stdin_text)
