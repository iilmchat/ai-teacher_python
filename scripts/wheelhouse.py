"""Wheelhouse: офлайн-установка зависимостей backend (S22-005, KI-017).

PyPI с машины разработки недоступен/нестабилен, а CI должен ставиться
предсказуемо. Скрипт скачивает **все пины** из `backend/requirements.txt` в
каталог (или в Docker-том) и умеет ставить их без сети.

Примеры:

    # скачать колёса в .wheelhouse (локальный pip; нужен доступ к индексу)
    python scripts/wheelhouse.py build --out .wheelhouse

    # то же, но скачивание делает контейнер (PyPI/зеркало видно из Docker)
    python scripts/wheelhouse.py build --out .wheelhouse --docker \
        --index-url https://mirrors.aliyun.com/pypi/simple/

    # поставить пакеты из каталога в venv (без сети)
    python scripts/wheelhouse.py install --from .wheelhouse --python backend/venv/Scripts/python.exe

    # что лежит в каталоге
    python scripts/wheelhouse.py list --from .wheelhouse

Важно: колёса скачиваются под **платформу того интерпретатора**, который
запускает pip. Для CI (Linux-контейнеры) используйте `--docker` — иначе
Windows-колёса в Linux-образ не установятся.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = REPO_ROOT / "backend" / "requirements.txt"
DEFAULT_OUT = REPO_ROOT / ".wheelhouse"
DOCKER_IMAGE = "python:3.12-slim"


def _run(command: list[str], *, cwd: Path | None = None) -> int:
    print("+", " ".join(command))
    return subprocess.call(command, cwd=str(cwd) if cwd else None)


def build_local(requirements: Path, out: Path, index_url: str | None) -> int:
    out.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "pip", "download", "-r", str(requirements), "-d", str(out)]
    if index_url:
        command += ["--index-url", index_url]
    return _run(command)


def build_docker(requirements: Path, out: Path, index_url: str | None) -> int:
    if shutil.which("docker") is None:
        print("docker не найден в PATH", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    command = [
        "docker", "run", "--rm",
        "-v", f"{REPO_ROOT}:/src:ro",
        "-v", f"{out}:/wheelhouse",
        DOCKER_IMAGE,
        "python", "/src/scripts/wheelhouse.py", "build",
        "--requirements", f"/src/{requirements.relative_to(REPO_ROOT).as_posix()}",
        "--out", "/wheelhouse",
    ]
    if index_url:
        command += ["--index-url", index_url]
    return _run(command)


def install(requirements: Path, source: Path, python: str | None) -> int:
    wheels = sorted(source.glob("*.whl"))
    if not wheels:
        print(f"в {source} нет .whl — сначала build", file=sys.stderr)
        return 2
    executable = python or sys.executable
    command = [
        executable, "-m", "pip", "install",
        "--no-index", "--find-links", str(source),
        "-r", str(requirements),
    ]
    return _run(command)


def list_wheels(source: Path) -> int:
    if not source.is_dir():
        print(f"каталог не найден: {source}", file=sys.stderr)
        return 2
    wheels = sorted(source.glob("*.whl"))
    total = sum(path.stat().st_size for path in wheels)
    print(f"wheelhouse: {source}")
    print(f"  колёс: {len(wheels)}, размер: {total / 1024 / 1024:.1f} МБ")
    for path in wheels:
        print(f"  {path.name}")
    return 0 if wheels else 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Wheelhouse для офлайн-установки (S22-005)")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="скачать все пины в каталог")
    build_parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    build_parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    build_parser.add_argument("--index-url", default=os.environ.get("CI_PYPI_MIRROR"))
    build_parser.add_argument(
        "--docker",
        action="store_true",
        help="скачивать контейнером python:3.12-slim (Linux-колёса, PyPI виден из Docker)",
    )

    install_parser = sub.add_parser("install", help="поставить зависимости из каталога без сети")
    install_parser.add_argument("--from", dest="source", type=Path, default=DEFAULT_OUT)
    install_parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    install_parser.add_argument(
        "--python",
        default=None,
        help="интерпретатор-цель (по умолчанию текущий); пример — backend/venv/Scripts/python.exe",
    )

    list_parser = sub.add_parser("list", help="показать содержимое каталога")
    list_parser.add_argument("--from", dest="source", type=Path, default=DEFAULT_OUT)

    args = parser.parse_args(argv)

    if args.command == "build":
        requirements = args.requirements.resolve()
        if not requirements.is_file():
            print(f"requirements не найден: {requirements}", file=sys.stderr)
            return 2
        out = args.out.resolve()
        if args.docker:
            return build_docker(requirements, out, args.index_url)
        return build_local(requirements, out, args.index_url)

    if args.command == "install":
        return install(args.requirements.resolve(), args.source.resolve(), args.python)

    return list_wheels(args.source.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
