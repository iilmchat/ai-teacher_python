"""Тесты инструментов релиза (S21-005): заметки из журнала и сверка версий.

Скрипты лежат в ``backend/scripts`` (не пакет), поэтому путь к ним добавляется
явно — как и для остальных утилит в этом каталоге, тесты не зависят от CWD.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))

import check_version  # noqa: E402
import release_notes  # noqa: E402

JOURNAL = """# Журнал

## Этап v0.2.0 «Classroom» — релиз

Краткое описание этапа.

## Спринт 20: Security Audit

Подробности спринта.

---

## Релиз v0.2.0 «Classroom»

**Дата:** 2026-10-30

- классы и назначения;
- аудит зависимостей.

---

## Шаблон отчёта по спринту

Шаблон.
"""


def test_extract_notes_prefers_release_heading() -> None:
    body = release_notes.extract_notes(JOURNAL, "0.2.0")

    assert body is not None
    assert "классы и назначения" in body
    assert "Краткое описание этапа" not in body


def test_extract_notes_stops_at_next_heading() -> None:
    body = release_notes.extract_notes(JOURNAL, "0.2.0")

    assert body is not None
    assert "Шаблон" not in body
    assert "---" not in body


def test_extract_notes_missing_version_returns_none() -> None:
    assert release_notes.extract_notes(JOURNAL, "9.9.9") is None


def test_extract_notes_does_not_match_version_prefix() -> None:
    journal = "## Релиз v0.2.01\n\n- другое\n\n## Релиз v0.2.0\n\n- наше\n"

    assert release_notes.extract_notes(journal, "0.2.0") == "- наше"


def test_render_notes_has_title_and_available_versions_on_miss() -> None:
    rendered = release_notes.render_notes(JOURNAL, "0.2.0")
    assert rendered.startswith("# v0.2.0")
    assert "классы и назначения" in rendered

    with pytest.raises(LookupError) as excinfo:
        release_notes.render_notes(JOURNAL, "9.9.9")
    assert "0.2.0" in str(excinfo.value)


def test_release_versions_lists_only_release_sections() -> None:
    assert release_notes.release_versions(JOURNAL) == ["0.2.0"]


def test_repository_journal_contains_v020_notes() -> None:
    markdown = (REPO_ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")

    body = release_notes.extract_notes(markdown, "0.2.0")

    assert body is not None
    assert body.strip()
    assert "Шаблон отчёта по спринту" not in body


def _write_project(root: Path, version: str, package_version: str | None = None) -> None:
    (root / "backend" / "app").mkdir(parents=True)
    (root / "frontend").mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "{version}"\n', encoding="utf-8"
    )
    package = {"name": "demo", "version": package_version or version}
    (root / "frontend" / "package.json").write_text(json.dumps(package), encoding="utf-8")
    (root / "backend" / "app" / "config.py").write_text(
        f'class Settings:\n    version: str = "{version}"\n', encoding="utf-8"
    )


def test_collect_versions_reads_all_sources(tmp_path: Path) -> None:
    _write_project(tmp_path, "1.2.3")

    versions = check_version.collect_versions(tmp_path)

    assert versions == {
        "pyproject.toml": "1.2.3",
        "frontend/package.json": "1.2.3",
        "backend/app/config.py": "1.2.3",
    }
    assert check_version.mismatches(versions) == []


def test_collect_versions_detects_mismatch_and_expected(tmp_path: Path) -> None:
    _write_project(tmp_path, "1.2.3", package_version="1.2.4")

    versions = check_version.collect_versions(tmp_path)
    problems = check_version.mismatches(versions)

    assert any("package.json" in problem for problem in problems)
    assert check_version.mismatches(versions, "2.0.0")


def test_cli_strict_fails_on_mismatch(tmp_path: Path) -> None:
    _write_project(tmp_path, "1.2.3", package_version="1.2.4")

    assert check_version.main(["--root", str(tmp_path)]) == 0
    assert check_version.main(["--root", str(tmp_path), "--strict"]) == 1
    assert check_version.main(["--root", str(tmp_path), "--expected", "1.2.3", "--strict"]) == 1


def test_cli_reports_broken_config(tmp_path: Path) -> None:
    _write_project(tmp_path, "1.2.3")
    (tmp_path / "backend" / "app" / "config.py").write_text("x = 1\n", encoding="utf-8")

    assert check_version.main(["--root", str(tmp_path)]) == 2


def test_repository_versions_are_consistent() -> None:
    versions = check_version.collect_versions(REPO_ROOT)

    assert check_version.mismatches(versions) == []


def test_release_notes_cli_writes_file(tmp_path: Path) -> None:
    journal = tmp_path / "RELEASES.md"
    journal.write_text(JOURNAL, encoding="utf-8")
    output = tmp_path / "notes.md"

    written = release_notes.main(
        ["--version", "0.2.0", "--file", str(journal), "--output", str(output)]
    )
    assert written == 0
    assert output.read_text(encoding="utf-8").startswith("# v0.2.0")

    assert release_notes.main(["--version", "9.9.9", "--file", str(journal)]) == 1
    assert release_notes.main(["--list", "--file", str(journal)]) == 0
    assert release_notes.main(["--version", "0.2.0", "--file", str(tmp_path / "none.md")]) == 2
