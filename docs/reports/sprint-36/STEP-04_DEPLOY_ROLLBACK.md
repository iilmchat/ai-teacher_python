# S36-004/005 — миграции, deploy и rollback

**Дата:** 2026-11-12
**Спринт:** 36
**Статус:** завершено

## Миграции (S36-004)

- В prod-compose добавлен one-shot сервис `migrate` (profile `tools`):
  `command: alembic upgrade head`, тот же backend-образ, зависит от healthy
  postgres.
- Backend запускается с `SKIP_MIGRATIONS=true`, чтобы entrypoint не дублировал
  миграции.
- `deploy.sh` выполняет `compose --profile tools run --rm migrate` до `up`.

## deploy.sh (S36-005)

Порядок:

1. Проверка `docker`, `.env.prod`, обязательных переменных (`SECRET_KEY` ≥32,
   `POSTGRES_PASSWORD`, `DOMAIN` не placeholder) и `compose config`.
2. Сохранение текущего `.deploy-state` в `.last_deploy`.
3. Бэкап (`scripts/backup.sh`) — если не `--no-backup`.
4. `compose up -d --wait postgres redis`.
5. Миграции (`migrate`).
6. `compose pull` backend/frontend (по тегу/digest) и
   `compose up -d --no-deps --remove-orphans backend frontend caddy`.
7. Healthcheck `/health/ready` (через `compose exec backend`; можно задать
   `DEPLOY_HEALTHCHECK_URL`), 30 попыток × 2 с.
8. Запись `.deploy-state` (фактические `Config.Image` + tag + время).
9. При любом сбое — `rollback.sh --to .last_deploy`.

Флаги: `--dry-run`, `--no-backup`, `--no-pull`, `--skip-migrations`,
`--env-file`, `--compose-file`.

## rollback.sh

- Читает `.last_deploy` (или `--to FILE`), экспортирует
  `BACKEND_IMAGE`/`FRONTEND_IMAGE`/`SANDBOX_IMAGE`;
- `compose pull` (если не `--no-pull`) и
  `up -d --no-deps --remove-orphans backend frontend caddy`;
- тот же healthcheck; при успехе обновляет `.deploy-state`;
- схема БД не откатывается — миграции аддитивные; данные — через restore.

## Проверки

```
bash scripts/deploy.sh --dry-run
# [deploy] Проверка compose-конфигурации
# [deploy] DRY-RUN: config валиден; бэкап/миграции/up/healthcheck не выполнялись

bash scripts/rollback.sh --dry-run
# [rollback] backend/frontend @sha256:...
# [rollback] DRY-RUN: откат не выполнялся
```

Полноценный deploy в GHCR/сервер не выполнялся (нет доступа); dry-run и
`compose config` подтверждают конфигурацию, healthcheck-логика идентична
production.
