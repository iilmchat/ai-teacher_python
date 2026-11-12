"""Env drift: Settings ↔ .env.example (S40-003)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(root: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_env_drift.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode


def _make_tree(tmp_path: Path, env_text: str) -> Path:
    config = tmp_path / "backend" / "app" / "config.py"
    config.parent.mkdir(parents=True)
    config.write_text(
        "class Settings:\n"
        "    app_name: str = 'x'\n"
        "    secret_key: str = 'x'\n"
        "    version: str = '0.6.0'\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text(env_text, encoding="utf-8")
    return tmp_path


def test_repo_env_example_is_in_sync() -> None:
    assert _run(ROOT) == 0


def test_missing_variable_fails(tmp_path: Path) -> None:
    root = _make_tree(tmp_path, "APP_NAME=x\n# SECRET_KEY commented\n")

    assert _run(root) == 1


def test_unknown_variable_fails(tmp_path: Path) -> None:
    root = _make_tree(tmp_path, "APP_NAME=x\nSECRET_KEY=x\nUNKNOWN_FLAG=1\n")

    assert _run(root) == 1


def test_version_is_exempt(tmp_path: Path) -> None:
    root = _make_tree(tmp_path, "APP_NAME=x\nSECRET_KEY=x\n")

    assert _run(root) == 0
