"""Проверка дрейфа `.env.example` и `Settings` (S40-003).

Парсит AST `backend/app/config.py` (без импорта pydantic) и активные
`KEY=VALUE` из `.env.example`. Падает, если:

- в `Settings` есть поле без соответствующей переменной в `.env.example`;
- в `.env.example` есть переменная, которой нет в `Settings`.

Исключения:
- `version` — намеренно задаётся кодом, не ENV (см. комментарий в файле);
- `UVICORN_WORKERS` — переменная compose/uvicorn, не `Settings`.

Запуск:
    python scripts/check_env_drift.py
    python scripts/check_env_drift.py --root /src
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

#: Поля Settings, которые осознанно не задаются через `.env.example`.
CODE_ONLY = frozenset({"version"})
#: Переменные `.env.example`, которые читает не Settings (compose/uvicorn).
ENV_ONLY = frozenset({"uvicorn_workers"})


def settings_fields(config_path: Path) -> set[str]:
    """Имена аннотированных полей класса Settings (snake_case)."""
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            fields: set[str] = set()
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    name = item.target.id
                    if not name.startswith("_"):
                        fields.add(name)
            return fields
    raise SystemExit(f"ERROR: класс Settings не найден в {config_path}")


def env_keys(env_path: Path) -> set[str]:
    """Активные ключи из env-файла (комментарии и пустые строки игнорируются)."""
    keys: set[str] = set()
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key.lower())
    return keys


def check(root: Path) -> tuple[set[str], set[str]]:
    """Вернуть (missing_in_env, unknown_in_env) в терминах snake_case."""
    fields = settings_fields(root / "backend" / "app" / "config.py")
    keys = env_keys(root / ".env.example")

    expected_env = {field for field in fields if field not in CODE_ONLY}
    missing = expected_env - keys
    unknown = keys - expected_env - ENV_ONLY
    return missing, unknown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Env drift: Settings ↔ .env.example")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args(argv)

    try:
        missing, unknown = check(args.root)
    except (OSError, SyntaxError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if missing or unknown:
        print("ENV DRIFT обнаружен:", file=sys.stderr)
        if missing:
            print("  в Settings есть, в .env.example нет:", file=sys.stderr)
            for name in sorted(missing):
                print(f"    - {name.upper()}", file=sys.stderr)
        if unknown:
            print("  в .env.example есть, в Settings нет:", file=sys.stderr)
            for name in sorted(unknown):
                print(f"    - {name.upper()}", file=sys.stderr)
        print(
            "Обновите .env.example (или исключения в scripts/check_env_drift.py).",
            file=sys.stderr,
        )
        return 1

    field_count = len(settings_fields(args.root / "backend" / "app" / "config.py"))
    print(f"OK: Settings ({field_count} полей) и .env.example согласованы")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
