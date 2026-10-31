"""Заметки релиза из ``docs/RELEASES.md`` (S21-005).

Release-workflow (GitHub ``release.yml`` и GitFlic-джоб ``release``) берёт
описание релиза не из коммитов, а из раздела журнала::

    ## Релиз v0.2.0 «Classroom»

Скрипт работает только со stdlib, не обращается к сети и поэтому запускается
и в контейнере ``python:3.12-slim``, и на Windows-runner'е.

Примеры::

    python backend/scripts/release_notes.py --version 0.2.0
    python backend/scripts/release_notes.py --version 0.2.0 --output notes.md
    python backend/scripts/release_notes.py --list
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOURNAL = REPO_ROOT / "docs" / "RELEASES.md"

# Заголовки второго уровня: «## Релиз v0.2.0 «Classroom»», «## Спринт 20: ...».
HEADING = re.compile(r"^##[ \t]+(?P<title>\S.*)$", re.MULTILINE)
# Разделитель между разделами журнала — строка из трёх и более дефисов.
SEPARATOR = re.compile(r"^[ \t]*-{3,}[ \t]*$", re.MULTILINE)


def _version_pattern(version: str) -> re.Pattern[str]:
    """Совпадение по версии, но не по её префиксу (0.2.0 ≠ 0.2.01)."""
    return re.compile(rf"v{re.escape(version)}(?![\w.])")


def iter_sections(markdown: str) -> list[tuple[str, str]]:
    """Все разделы второго уровня: список ``(заголовок, тело)``.

    Тело начинается со строки после заголовка, заканчивается перед следующим
    заголовком второго уровня и очищается от хвостовых разделителей ``---``.
    """
    headings = list(HEADING.finditer(markdown))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        body = markdown[match.end() : end]
        body = SEPARATOR.sub("", body).strip()
        sections.append((match.group("title").strip(), body))
    return sections


def release_versions(markdown: str) -> list[str]:
    """Версии, для которых в журнале есть раздел «Релиз vX.Y.Z»."""
    versions: list[str] = []
    for title, _ in iter_sections(markdown):
        match = re.search(r"v\d+\.\d+\.\d+(?:-[\w.]+)?", title)
        if match and title.lower().startswith("релиз"):
            versions.append(match.group(0).lstrip("v"))
    return versions


def extract_notes(markdown: str, version: str) -> str | None:
    """Тело раздела релиза ``version`` или ``None``, если раздела нет.

    Приоритет — заголовок, начинающийся с «Релиз»: в журнале есть и
    «## Этап v0.2.0 ... — релиз», который тоже содержит версию.
    """
    pattern = _version_pattern(version)
    candidates = [
        (title, body) for title, body in iter_sections(markdown) if pattern.search(title)
    ]
    if not candidates:
        return None
    for title, body in candidates:
        if title.lower().startswith("релиз"):
            return body
    return candidates[0][1]


def render_notes(markdown: str, version: str) -> str:
    """Заметки с заголовком релиза — готовый текст для Release/артефакта."""
    body = extract_notes(markdown, version)
    if body is None:
        available = ", ".join(release_versions(markdown)) or "нет"
        raise LookupError(
            f"в журнале нет раздела «## Релиз v{version}» "
            f"(есть релизы: {available}) — добавьте раздел в docs/RELEASES.md"
        )
    return f"# v{version}\n\n{body}\n"


def _configure_stdout() -> None:
    """UTF-8 для вывода: в заметках есть «→» и «ё», cp1251 их не кодирует."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Заметки релиза из docs/RELEASES.md")
    parser.add_argument("--version", help="Версия без префикса v, например 0.3.0")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_JOURNAL,
        help=f"Журнал (по умолчанию {DEFAULT_JOURNAL})",
    )
    parser.add_argument("--output", type=Path, help="Записать заметки в файл")
    parser.add_argument("--list", action="store_true", help="Список версий с разделом релиза")
    args = parser.parse_args(argv)

    if not args.file.is_file():
        print(f"Журнал не найден: {args.file}", file=sys.stderr)
        return 2

    markdown = args.file.read_text(encoding="utf-8")

    if args.list:
        for version in release_versions(markdown):
            print(version)
        return 0

    if not args.version:
        parser.error("нужен --version (или --list)")

    try:
        notes = render_notes(markdown, args.version)
    except LookupError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(notes, encoding="utf-8")
        print(f"Заметки записаны: {args.output} ({len(notes)} символов)")
    else:
        print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
