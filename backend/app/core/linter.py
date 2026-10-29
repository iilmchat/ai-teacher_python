"""
Статический анализ кода ученика (S6-006).

Линтер не выполняет код: он разбирает AST и сообщает о безопасности,
синтаксисе и типичных ошибках новичков. Внешние линтеры не используются,
чтобы не тянуть зависимости (RULES §3.3).
"""

import ast
from dataclasses import dataclass

from app.core.executor import FORBIDDEN_CALLS, FORBIDDEN_MODULES

#: Максимальная рекомендуемая длина строки
MAX_LINE_LENGTH = 100


@dataclass(slots=True)
class LintIssue:
    """Одно замечание линтера"""

    line: int
    column: int
    code: str
    message: str
    severity: str  # 'error' | 'warning' | 'info'


@dataclass(slots=True)
class CodeStats:
    """Простые метрики кода для блока «анализ»"""

    lines: int = 0
    functions: int = 0
    classes: int = 0
    loops: int = 0
    conditions: int = 0
    imports: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "lines": self.lines,
            "functions": self.functions,
            "classes": self.classes,
            "loops": self.loops,
            "conditions": self.conditions,
            "imports": self.imports,
        }


def lint_code(code: str) -> list[LintIssue]:
    """Проверить код и вернуть список замечаний"""
    issues: list[LintIssue] = []

    # Синтаксис проверяем отдельно: дальше AST недоступен
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        issues.append(
            LintIssue(
                line=exc.lineno or 0,
                column=exc.offset or 0,
                code="E001",
                message=f"Синтаксическая ошибка: {exc.msg}",
                severity="error",
            )
        )
        return issues

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    issues.append(
                        LintIssue(
                            line=node.lineno,
                            column=node.col_offset,
                            code="S001",
                            message=f"Импорт запрещённого модуля: {root}",
                            severity="error",
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in FORBIDDEN_MODULES:
                issues.append(
                    LintIssue(
                        line=node.lineno,
                        column=node.col_offset,
                        code="S001",
                        message=f"Импорт запрещённого модуля: {root}",
                        severity="error",
                    )
                )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                issues.append(
                    LintIssue(
                        line=node.lineno,
                        column=node.col_offset,
                        code="S002",
                        message=f"Вызов запрещённой функции: {node.func.id}",
                        severity="error",
                    )
                )
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            issues.append(
                LintIssue(
                    line=node.lineno,
                    column=node.col_offset,
                    code="S003",
                    message=f"Обращение к служебному атрибуту: {node.attr}",
                    severity="error",
                )
            )
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(
                LintIssue(
                    line=node.lineno,
                    column=node.col_offset,
                    code="W001",
                    message="Пустой `except:` перехватывает все ошибки — укажите тип",
                    severity="warning",
                )
            )
        elif isinstance(node, ast.Compare):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    if any(isinstance(op, ast.Eq | ast.NotEq) for op in node.ops):
                        issues.append(
                            LintIssue(
                                line=node.lineno,
                                column=node.col_offset,
                                code="W002",
                                message="Сравнение с None: используйте `is None` / `is not None`",
                                severity="warning",
                            )
                        )
                        break
        elif isinstance(node, ast.FunctionDef) and ast.get_docstring(node) is None:
            issues.append(
                LintIssue(
                    line=node.lineno,
                    column=node.col_offset,
                    code="I001",
                    message=f"У функции `{node.name}` нет docstring",
                    severity="info",
                )
            )

    for index, line in enumerate(code.splitlines(), start=1):
        if len(line) > MAX_LINE_LENGTH:
            issues.append(
                LintIssue(
                    line=index,
                    column=MAX_LINE_LENGTH,
                    code="W003",
                    message=f"Строка длиннее {MAX_LINE_LENGTH} символов",
                    severity="warning",
                )
            )

    return issues


def code_stats(code: str) -> CodeStats:
    """Посчитать простые метрики кода"""
    stats = CodeStats(lines=len(code.splitlines()))
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return stats

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            stats.functions += 1
        elif isinstance(node, ast.ClassDef):
            stats.classes += 1
        elif isinstance(node, ast.For | ast.While | ast.AsyncFor):
            stats.loops += 1
        elif isinstance(node, ast.If):
            stats.conditions += 1
        elif isinstance(node, ast.Import | ast.ImportFrom):
            stats.imports += 1
    return stats


def analyze_code(code: str) -> tuple[list[LintIssue], CodeStats]:
    """Линт + метрики для эндпоинта анализа"""
    return lint_code(code), code_stats(code)
