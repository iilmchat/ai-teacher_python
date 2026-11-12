# S36-001 — GHCR: сборка и публикация

**Дата:** 2026-11-12
**Спринт:** 36 (Registry, Deploy, TLS & Backup/DR)
**Статус:** завершено

## Что сделано

`.github/workflows/docker-publish.yml`:

- триггер **только** `push` тега `v*`; теги `v*-dryrun` пропускаются
  (`if: !contains(github.ref_name, 'dryrun')`);
- matrix: `backend`, `frontend`, `sandbox-runner` (контекст `backend`,
  Dockerfile `sandbox_runner/Dockerfile`);
- образы:
  - `ghcr.io/<owner>/ai-teacher-backend:<tag>`
  - `ghcr.io/<owner>/ai-teacher-frontend:<tag>`
  - `ghcr.io/<owner>/ai-teacher-sandbox-runner:<tag>`
  плюс `sha-<short>`; `latest` не публикуется;
- auth: `username: ${{ github.actor }}`, `password: ${{ secrets.GITHUB_TOKEN }}`;
- `permissions: packages: write`; SBOM и provenance включены;
- digest и теги пишутся в Step Summary и artifact `digest-<name>`;
- схема кэша `type=gha` по каждому образу.

## Ограничение

Реальной публикации в GHCR в этом окружении не было (нет доступа к registry/
тегу). Workflow валидируется как YAML тестом `test_deploy_config.py`; логика
соответствует стандартному `docker/build-push-action`.
