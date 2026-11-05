"""Проверка, что образы закреплены по digest (S33-001).

Тег — изменяемая ссылка: `python:3.12-slim` сегодня и через месяц могут быть
разными образами. Для воспроизводимой сборки и сканирования нужен digest:
`python:3.12-slim@sha256:<64 hex>`.

Скрипт проверяет Dockerfile'ы (``FROM``) и compose-файлы (``image:``). Запуск:

    python backend/scripts/check_image_pins.py
    python backend/scripts/check_image_pins.py --root /src

Код возврата: 0 — всё закреплено, 1 — есть незакреплённые образы, 2 — ошибка
чтения файлов.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCKERFILES = (
    "backend/Dockerfile",
    "backend/sandbox_runner/Dockerfile",
    "frontend/Dockerfile",
)
COMPOSE_FILES = (
    "docker-compose.yml",
    "docker-compose.prod.yml",
)

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}\b")
FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)", re.IGNORECASE)
IMAGE = re.compile(r"^\s*image:\s*([^\s#]+)", re.IGNORECASE)


def is_pinned(reference: str) -> bool:
    """Есть ли в ссылке на образ digest ``@sha256:<64 hex>``."""
    return DIGEST.search(reference) is not None


def check_dockerfile(text: str) -> list[str]:
    """Проблемы со строками ``FROM`` в Dockerfile."""
    problems: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = FROM.match(line)
        if match is None:
            continue
        reference = match.group(1)
        if reference == "scratch" or is_pinned(reference):
            continue
        problems.append(f"строка {lineno}: FROM {reference} без @sha256")
    return problems


def check_compose(text: str) -> list[str]:
    """Проблемы со строками ``image:`` в compose-файле."""
    problems: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = IMAGE.match(line)
        if match is None:
            continue
        reference = match.group(1).strip("'\"")
        if is_pinned(reference):
            continue
        problems.append(f"строка {lineno}: image {reference} без @sha256")
    return problems


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def check_tree(root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Все незакреплённые образы: ``{путь: [проблема, ...]}``."""
    problems: dict[str, list[str]] = {}
    for relative in DOCKERFILES:
        found = check_dockerfile(_read(root, relative))
        if found:
            problems[relative] = found
    for relative in COMPOSE_FILES:
        found = check_compose(_read(root, relative))
        if found:
            problems[relative] = found
    return problems


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Проверка digest-пиннинга образов")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Корень репозитория")
    args = parser.parse_args(argv)

    try:
        problems = check_tree(args.root)
    except OSError as exc:
        print(f"Не удалось прочитать файлы: {exc}")
        return 2

    if problems:
        print("Незакреплённые образы (нужен @sha256:<digest>):")
        for relative, items in problems.items():
            for item in items:
                print(f"  - {relative}: {item}")
        return 1

    checked = len(DOCKERFILES) + len(COMPOSE_FILES)
    print(f"OK: все образы закреплены по digest ({checked} файлов)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
