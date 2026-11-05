"""Тесты проверки digest-пиннинга образов (S33-001)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND / "scripts"))

import check_image_pins  # noqa: E402

PINNED = "python:3.12-slim@sha256:" + "a" * 64


def test_is_pinned_accepts_sha256_digest() -> None:
    assert check_image_pins.is_pinned(PINNED)
    assert check_image_pins.is_pinned("nginx:1.27-alpine@sha256:" + "b" * 64)
    assert not check_image_pins.is_pinned("python:3.12-slim")
    assert not check_image_pins.is_pinned("python:3.12-slim@sha256:short")


def test_check_dockerfile_reports_only_unpinned_from() -> None:
    text = "\n".join(
        [
            "# FROM redis:7-alpine",
            f"FROM {PINNED} AS build",
            "FROM nginx:1.27-alpine",
            "RUN echo ok",
        ]
    )

    problems = check_image_pins.check_dockerfile(text)

    assert len(problems) == 1
    assert "nginx:1.27-alpine" in problems[0]


def test_check_dockerfile_allows_scratch() -> None:
    assert check_image_pins.check_dockerfile("FROM scratch") == []


def test_check_compose_reports_only_unpinned_image() -> None:
    text = "\n".join(
        [
            "services:",
            "  db:",
            f"    image: {PINNED}",
            "  cache:",
            "    image: 'redis:7-alpine'  # без digest",
        ]
    )

    problems = check_image_pins.check_compose(text)

    assert len(problems) == 1
    assert "redis:7-alpine" in problems[0]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_tree_collects_problems_by_file(tmp_path: Path) -> None:
    for relative in check_image_pins.DOCKERFILES:
        _write(tmp_path, relative, f"FROM {PINNED}\n")
    _write(tmp_path, check_image_pins.DOCKERFILES[0], "FROM python:3.12-slim\n")
    for relative in check_image_pins.COMPOSE_FILES:
        _write(tmp_path, relative, f"services:\n  app:\n    image: {PINNED}\n")

    problems = check_image_pins.check_tree(tmp_path)

    assert list(problems) == [check_image_pins.DOCKERFILES[0]]


def test_cli_returns_codes(tmp_path: Path) -> None:
    for relative in (*check_image_pins.DOCKERFILES, *check_image_pins.COMPOSE_FILES):
        _write(tmp_path, relative, f"FROM {PINNED}\n")

    assert check_image_pins.main(["--root", str(tmp_path)]) == 0

    _write(tmp_path, check_image_pins.COMPOSE_FILES[0], "services:\n  db:\n    image: redis:7\n")
    assert check_image_pins.main(["--root", str(tmp_path)]) == 1

    _write(tmp_path, check_image_pins.COMPOSE_FILES[0], "")
    (tmp_path / check_image_pins.COMPOSE_FILES[0]).unlink()
    assert check_image_pins.main(["--root", str(tmp_path)]) == 2


def test_repository_images_are_pinned() -> None:
    assert check_image_pins.check_tree(REPO_ROOT) == {}
