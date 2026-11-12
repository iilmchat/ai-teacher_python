"""Конфигурация деплоя/бэкапов как код (S36).

Проверяем без реального registry/сервера:
- prod compose использует GHCR-образы и не собирает приложение на хосте;
- Caddy — edge с WebSocket и TLS, без публикации frontend/backend;
- workflow публикует три образа по тегу `v*`;
- systemd-таймер бэкапа и обязательные ENV на месте;
- digest-пиннинг проходит (`check_image_pins.py`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _yaml(relative: str) -> dict[str, Any]:
    data = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(data, dict), relative
    return data


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_prod_compose_uses_ghcr_images_without_build() -> None:
    compose = _yaml("docker-compose.prod.yml")
    services = compose["services"]

    for name in ("backend", "frontend"):
        assert "build" not in services[name], name
        assert "ghcr.io" in services[name]["image"], name

    assert services["backend"]["image"].startswith("${BACKEND_IMAGE:-ghcr.io/")
    assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
    assert services["backend"]["environment"]["SKIP_MIGRATIONS"] == "true"
    assert "8000" in services["backend"]["expose"]
    assert "ports" not in services["frontend"]
    assert services["frontend"]["expose"] == ["80"]


def test_caddy_is_only_public_entrypoint() -> None:
    compose = _yaml("docker-compose.prod.yml")
    caddy = compose["services"]["caddy"]

    assert "${CADDY_HTTP_PORT:-80}:80" in caddy["ports"]
    assert "${CADDY_HTTPS_PORT:-443}:443" in caddy["ports"]
    assert "DOMAIN" in caddy["environment"]
    assert "build" not in compose["services"]["postgres"]

    caddyfile = _text("deploy/caddy/Caddyfile")
    assert "reverse_proxy backend:8000" in caddyfile
    assert "reverse_proxy frontend:80" in caddyfile
    assert "{$DOMAIN" in caddyfile
    # Метрики и health остаются внутренними.
    assert "/metrics" not in caddyfile


def test_trusted_proxies_match_docker_subnet() -> None:
    compose = _yaml("docker-compose.prod.yml")
    subnet = compose["networks"]["edge"]["ipam"]["config"][0]["subnet"]
    env = compose["services"]["backend"]["environment"]["TRUSTED_PROXIES"]

    assert "${DOCKER_SUBNET:-10.77.0.0/16}" == subnet
    assert "${TRUSTED_PROXIES:-10.77.0.0/16}" == env


def test_caddy_security_headers_and_docs_off() -> None:
    """S38-003: строгие заголовки на edge, HSTS только в TLS-блоке."""
    caddyfile = _text("deploy/caddy/Caddyfile")
    for header in (
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Strict-Transport-Security",
        "Cross-Origin-Opener-Policy",
        "worker-src 'self' blob:",
        "https://*.ingest.sentry.io",
    ):
        assert header in caddyfile, header

    # S39-004: лимит тела и таймауты upstream.
    assert "max_size 10MB" in caddyfile
    assert "read_timeout 600s" in caddyfile
    assert "flush_interval -1" in caddyfile

    compose = _yaml("docker-compose.prod.yml")
    assert compose["services"]["backend"]["environment"]["DOCS_ENABLED"] == "false"


def test_publish_workflow_tags_and_images() -> None:
    workflow = _yaml(".github/workflows/docker-publish.yml")

    # PyYAML трактует ключ `on` как boolean True — это нормально.
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers["push"]["tags"] == ["v*"]
    assert workflow["permissions"]["packages"] == "write"

    text = _text(".github/workflows/docker-publish.yml")
    assert "username: ${{ github.actor }}" in text
    assert "password: ${{ secrets.GITHUB_TOKEN }}" in text
    for image in ("backend", "frontend", "sandbox-runner"):
        assert image in text
    assert "type=raw,value=latest" not in text
    assert ":latest" not in text


def test_systemd_timer_runs_backup_daily() -> None:
    timer = _text("deploy/systemd/ai-teacher-backup.timer")
    unit = _text("deploy/systemd/ai-teacher-backup.service")

    assert "OnCalendar=*-*-* 03:00:00" in timer
    assert "Persistent=true" in timer
    assert "scripts/backup.sh" in unit
    assert "EnvironmentFile=/etc/ai-teacher/backup.env" in unit


def test_backup_and_deploy_scripts_cover_s36_features() -> None:
    backup = _text("scripts/backup.sh")
    deploy = _text("scripts/deploy.sh")
    rollback = _text("scripts/rollback.sh")

    assert "compose" in backup and "ps -q postgres" in backup
    assert "age -r" in backup
    assert 's3 cp' in backup
    assert "backup_last_success_timestamp" in backup

    assert "alembic upgrade head" in deploy
    assert "--no-deps --remove-orphans" in deploy
    assert "health/ready" in deploy
    assert "rollback.sh" in deploy
    assert "last_deploy" in rollback


def test_secret_files_are_supported() -> None:
    """S38-002: compose и пример override поддерживают *_FILE/Docker secrets."""
    compose = _yaml("docker-compose.prod.yml")
    postgres_env = compose["services"]["postgres"]["environment"]
    backend_env = compose["services"]["backend"]["environment"]

    assert "POSTGRES_PASSWORD_FILE" in postgres_env
    assert "SECRET_KEY_FILE" in backend_env
    assert "DEEPSEEK_API_KEY_FILE" in backend_env
    assert "SENTRY_DSN_FILE" in backend_env

    override = _yaml("deploy/docker-compose.secrets.example.yml")
    assert {"postgres_password", "secret_key", "deepseek_api_key"} <= set(
        override["secrets"]
    )
    assert "secret_key" in override["services"]["backend"]["secrets"]


def test_env_prod_example_has_required_keys() -> None:
    env = _text(".env.prod.example")
    for key in (
        "DOMAIN=",
        "SECRET_KEY=",
        "POSTGRES_PASSWORD=",
        "GHCR_OWNER=",
        "IMAGE_TAG=",
        "CADDY_HTTP_PORT=",
        "BACKUP_DIR=",
        "AGE_RECIPIENT=",
        "S3_BUCKET=",
    ):
        assert key in env, key


def test_image_pinning_passes() -> None:
    result = subprocess.run(
        [sys.executable, "backend/scripts/check_image_pins.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
