"""Сверка версии проекта по всем источникам (S21-005).

Версия живёт в трёх местах, и релиз обязан обновить все:

* ``pyproject.toml`` — ``[project] version`` (пакет Python);
* ``frontend/package.json`` — ``version`` (npm-пакет);
* ``backend/app/config.py`` — ``Settings.version`` (то, что отдаёт ``/health``).

Скрипт используется release-workflow (``dry-run`` — предупреждения, реальный
релиз — жёсткая проверка) и локально: ``python backend/scripts/check_version.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_VERSION = re.compile(r'^\s*version:\s*str\s*=\s*"([^"]+)"', re.MULTILINE)


def read_pyproject_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def read_package_version(root: Path) -> str:
    data = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))
    return str(data["version"])


def read_config_version(root: Path) -> str:
    text = (root / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    match = CONFIG_VERSION.search(text)
    if match is None:
        raise LookupError("в backend/app/config.py нет поля version: str")
    return match.group(1)


def collect_versions(root: Path = REPO_ROOT) -> dict[str, str]:
    """Версии по источникам: ``{'pyproject.toml': '0.2.0', ...}``."""
    return {
        "pyproject.toml": read_pyproject_version(root),
        "frontend/package.json": read_package_version(root),
        "backend/app/config.py": read_config_version(root),
    }


def mismatches(versions: dict[str, str], expected: str | None = None) -> list[str]:
    """Расхождения между источниками и (опционально) ожидаемой версией."""
    problems: list[str] = []
    target = expected or next(iter(versions.values()))
    for source, value in versions.items():
        if value != target:
            problems.append(f"{source}: {value} ≠ {target}")
    return problems


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Сверка версии проекта по источникам")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Корень репозитория")
    parser.add_argument("--expected", help="Ожидаемая версия (например, из тега)")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Ненулевой код возврата при любом расхождении (для реального релиза)",
    )
    args = parser.parse_args(argv)

    try:
        versions = collect_versions(args.root)
    except (OSError, KeyError, LookupError, json.JSONDecodeError) as exc:
        print(f"Не удалось прочитать версии: {exc}")
        return 2

    for source, value in versions.items():
        print(f"  {source}: {value}")

    problems = mismatches(versions, args.expected)
    if problems:
        print("Расхождение версий:")
        for problem in problems:
            print(f"  - {problem}")
        return 1 if args.strict else 0

    target = args.expected or next(iter(versions.values()))
    print(f"OK: версия {target} согласована во всех источниках")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
