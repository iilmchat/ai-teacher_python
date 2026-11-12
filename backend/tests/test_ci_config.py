"""CI-гейты и паритет платформ (S37).

Без запуска CI проверяем:
- preflight есть в каждом self-hosted job и в release;
- покрытие: backend `--cov-fail-under=70`, frontend `test:coverage`;
- базовые проверки Lint/Test/Frontend/Security есть в GitHub и GitFlic;
- скрипт паритета `check_ci_parity.py` проходит;
- YAML-файлы валидны.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
SELFHOSTED = ROOT / ".github" / "workflows" / "ci-selfhosted.yml"
HOSTED = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
GITFLIC = ROOT / "gitflic-ci.yaml"


def _yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), path
    return data


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_workflows_are_valid_yaml() -> None:
    for path in (
        SELFHOSTED,
        HOSTED,
        RELEASE,
        GITFLIC,
        ROOT / ".github" / "workflows" / "docker-publish.yml",
    ):
        _yaml(path)


def test_preflight_runs_in_every_selfhosted_job_and_release() -> None:
    data = _yaml(SELFHOSTED)
    jobs = data["jobs"]

    expected = {
        "lint",
        "test",
        "frontend",
        "security",
        "e2e",
        "docker",
        "perf",
        "monitoring",
        "deploy-config",
    }
    assert expected <= set(jobs)
    for name, job in jobs.items():
        steps = job.get("steps", [])
        assert any(
            "preflight.ps1" in str(step.get("run", "")) for step in steps
        ), f"нет preflight в job {name}"

    release_text = _text(RELEASE)
    assert "preflight.ps1" in release_text


def test_backend_coverage_gate_is_70_percent() -> None:
    assert "--cov-fail-under=70" in _text(HOSTED)
    assert "--cov-fail-under=70" in _text(GITFLIC)
    backend_test = _text(ROOT / "scripts" / "ci" / "backend-test.sh")
    assert (
        "--cov-fail-under=70" in backend_test
        or 'COVERAGE_MIN:-70' in backend_test
    )


def test_frontend_coverage_runs_in_ci() -> None:
    assert "test:coverage" in _text(HOSTED)
    assert "test:coverage" in _text(GITFLIC)
    assert "test:coverage" in _text(ROOT / "scripts" / "ci" / "frontend.sh")


def test_base_checks_exist_on_both_platforms() -> None:
    hosted_jobs = set(_yaml(HOSTED)["jobs"])
    selfhosted_jobs = set(_yaml(SELFHOSTED)["jobs"])
    for check in ("lint", "test", "frontend", "security"):
        assert check in hosted_jobs
        assert check in selfhosted_jobs

    gitflic_text = _text(GITFLIC)
    for job in ("lint:", "test:", "frontend:", "security-backend:", "security-frontend:"):
        assert f"\n{job}" in f"\n{gitflic_text}"


def test_gitflic_pipeline_has_required_merge_checks() -> None:
    text = _text(GITFLIC)
    for job in ("lint", "test", "frontend", "security-backend", "security-frontend", "gitleaks"):
        assert f"\n{job}:" in f"\n{text}"
    assert (ROOT / "scripts" / "ci" / "gitflic-gate.ps1").is_file()


def test_local_gates_scripts_exist() -> None:
    assert (ROOT / "scripts" / "ci" / "gates.sh").is_file()
    assert (ROOT / "scripts" / "ci" / "gates.ps1").is_file()
    assert "release-check" in _text(ROOT / "Makefile")


def test_ci_parity_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/ci/check_ci_parity.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
