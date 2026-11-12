"""Проверка паритета CI и гейтов (S37-002/003/004).

Stdlib-only: запускается в CI-контейнере без зависимостей.

Проверяет:
- базовые проверки Lint/Test/Frontend/Security есть на GitHub и GitFlic;
- backend coverage gate `--cov-fail-under=70` задан во всех пайплайнах;
- frontend использует `test:coverage` (порог в vite.config.ts);
- preflight раннера присутствует в каждом self-hosted job и в GitFlic;
- release-workflow содержит preflight.

Код возврата: 0 — паритет соблюдён; 1 — расхождения; 2 — ошибка чтения.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GITHUB_SELFHOSTED = ".github/workflows/ci-selfhosted.yml"
GITHUB_HOSTED = ".github/workflows/ci.yml"
GITHUB_RELEASE = ".github/workflows/release.yml"
GITFLIC = "gitflic-ci.yaml"
FRONTEND_SCRIPT = "scripts/ci/frontend.sh"
BACKEND_TEST_SCRIPT = "scripts/ci/backend-test.sh"

BASE_CHECKS = ("lint", "test", "frontend", "security")
JOB_RE = re.compile(r"(?m)^  ([A-Za-z0-9_-]+):\s*$")
GITFLIC_JOB_RE = re.compile(r"(?m)^([A-Za-z0-9_-]+):\s*$")
GITFLIC_NON_JOBS = {"stages", "variables", "workflow", "include", "default"}
NON_JOBS = {
    "pull_request",
    "push",
    "run",
    "workflow_call",
    "workflow_dispatch",
    "permissions",
    "concurrency",
    "defaults",
    "env",
    "on",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def jobs(text: str) -> set[str]:
    return set(JOB_RE.findall(text)) - NON_JOBS


def parse_gitflic_jobs(text: str) -> set[str]:
    return set(GITFLIC_JOB_RE.findall(text)) - GITFLIC_NON_JOBS


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    try:
        selfhosted = read(GITHUB_SELFHOSTED)
        hosted = read(GITHUB_HOSTED)
        release = read(GITHUB_RELEASE)
        gitflic = read(GITFLIC)
        frontend_script = read(FRONTEND_SCRIPT)
        backend_test = read(BACKEND_TEST_SCRIPT)
    except OSError as exc:
        print(f"ERROR: не удалось прочитать конфигурацию: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    selfhosted_jobs = jobs(selfhosted)
    hosted_jobs = jobs(hosted)
    gitflic_jobs = parse_gitflic_jobs(gitflic)

    # 1. Базовые проверки: GitHub self-hosted и hosted.
    for check in BASE_CHECKS:
        require(check in selfhosted_jobs, f"{GITHUB_SELFHOSTED}: нет job '{check}'", errors)
        require(check in hosted_jobs, f"{GITHUB_HOSTED}: нет job '{check}'", errors)

    # 2. GitFlic: security разнесён на несколько job'ов.
    for check in ("lint", "test", "frontend"):
        require(check in gitflic_jobs, f"{GITFLIC}: нет job '{check}'", errors)
    gitflic_security = {name for name in gitflic_jobs if name.startswith("security")}
    require(bool(gitflic_security), f"{GITFLIC}: нет security-job'ов", errors)
    require("gitleaks" in gitflic_jobs, f"{GITFLIC}: нет job 'gitleaks'", errors)

    # 3. Coverage gate (backend 70%, frontend test:coverage).
    require(
        "--cov-fail-under=70" in selfhosted
        or "--cov-fail-under=70" in backend_test
        or 'COVERAGE_MIN:-70' in backend_test,
        "backend coverage gate не найден в self-hosted CI",
        errors,
    )
    require(
        "--cov-fail-under=70" in hosted,
        f"{GITHUB_HOSTED}: нет --cov-fail-under=70",
        errors,
    )
    require(
        "--cov-fail-under=70" in gitflic,
        f"{GITFLIC}: нет --cov-fail-under=70",
        errors,
    )
    require(
        "test:coverage" in hosted,
        f"{GITHUB_HOSTED}: frontend не использует test:coverage",
        errors,
    )
    require(
        "test:coverage" in gitflic,
        f"{GITFLIC}: frontend не использует test:coverage",
        errors,
    )
    require(
        "test:coverage" in frontend_script,
        f"{FRONTEND_SCRIPT}: frontend не использует test:coverage",
        errors,
    )

    # 4. Preflight: в каждом self-hosted job (9) + release + GitFlic.
    require(
        selfhosted.count("preflight.ps1") >= 9,
        f"{GITHUB_SELFHOSTED}: preflight меньше чем в 9 job'ах",
        errors,
    )
    require(
        "preflight.ps1" in release,
        f"{GITHUB_RELEASE}: нет preflight",
        errors,
    )
    require(
        gitflic.count("preflight.") >= 6,
        f"{GITFLIC}: preflight меньше чем в 6 job'ах",
        errors,
    )

    # 5. Обязательные файлы preflight-скриптов.
    for script in ("scripts/ci/preflight.ps1", "scripts/ci/preflight.sh"):
        require((ROOT / script).is_file(), f"нет {script}", errors)

    # 6. Единый локальный прогон гейтов (S37-005).
    for script in ("scripts/ci/gates.ps1", "scripts/ci/gates.sh"):
        require((ROOT / script).is_file(), f"нет {script}", errors)

    if errors:
        print("CI parity FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("CI parity OK")
    print(f"  GitHub self-hosted jobs: {', '.join(sorted(selfhosted_jobs))}")
    print(f"  GitHub hosted jobs:      {', '.join(sorted(hosted_jobs))}")
    print(f"  GitFlic jobs:            {', '.join(sorted(gitflic_jobs))}")
    print("  coverage: backend 70%, frontend test:coverage")
    print("  preflight: все self-hosted job'ы и GitFlic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
