# ADR-001 — GHCR и digest-пиннинг для деплоя

**Статус:** Accepted
**Дата:** 2026-11-12
**Контекст:** До v0.6.0 prod собирался на сервере (`build:` в compose):
артефакт невоспроизводим, сборка зависит от машины и сети, нет трассируемости
«что именно задеплоено». Аудит v0.5.0 требовал registry/CD и проверяемый
откат. GitHub-hosted минуты ограничены (KI-014), self-hosted runner —
основная площадка.

## Решение

- Публиковать `backend`, `frontend`, `sandbox-runner` в **GHCR** workflow
  `docker-publish.yml` по тегу `v*` (GitHub Actions, `GITHUB_TOKEN`,
  `github.actor`, `packages: write`).
- Теги: `:<version>` и `:sha-<short>`, без `latest` в prod.
- Prod-compose не содержит `build:`; образы подставляются через
  `BACKEND_IMAGE`/`FRONTEND_IMAGE`/`SANDBOX_IMAGE` (полная ссылка с digest)
  или `IMAGE_TAG`.
- После публикации `scripts/pin_images.sh` получает digest
  (`buildx imagetools inspect`, fallback `docker pull` + `RepoDigests`) и
  пишет ссылки в `.env.prod`; deploy использует их.

## Последствия

**Плюсы:**
- воспроизводимый артефакт, immutable digest, честный rollback;
- SBOM/provenance и трассируемость версии;
- сборка не нагружает VPS, деплой — только pull.

**Минусы/риски:**
- нужен доступ к GHCR и PAT/токен для приватных пакетов;
- digest нужно обновлять после каждого релиза (скрипт автоматизирует);
- GHCR rate limits/видимость пакетов — эксплуатационная ответственность.

**Ссылки:** `docker-compose.prod.yml`, `.github/workflows/docker-publish.yml`,
`scripts/pin_images.sh`, `docs/RUNBOOK.md` §1–2.
