# S36-008/009 — документация и runbook

**Дата:** 2026-11-12
**Спринт:** 36
**Статус:** завершено

## Документы

- `docs/RUNBOOK.md` — новый: быстрый доступ, деплой, откат, падения БД/Redis/
  backend/Caddy, TLS, бэкап/восстановление/DR, ротация секретов, алерты,
  эскалация, постмортем.
- `docs/ARCHITECTURE.md` §9.3/§10 — GHCR, digest, Caddy/TLS, миграции job'ом,
  deploy/rollback, age/S3/systemd, restore drill.
- `docs/GETTING_STARTED.md` §7/§8 — prod через GHCR + `deploy.sh`, Caddy,
  `migrate`, бэкапы/шифрование/S3/DR, установка systemd.
- `SECURITY.md` — TLS обязателен, автоматические бэкапы, образы по digest,
  `latest` запрещён.
- `docs/README.md`, `README.md` — ссылки на RUNBOOK.
- `.env.prod.example` — все production-переменные (домен, GHCR, digest,
  Caddy-порты, бэкапы/age/S3, Grafana).
- `docs/CHANGELOG.md`, `docs/RELEASES.md`, `TODO_V0.4.md` — S36 отмечен.

## CI

- Job **Deploy config** добавлен в `ci.yml` и `ci-selfhosted.yml`:
  `compose config` (prod + monitoring), `caddy validate`, `bash -n` всех
  скриптов, `check_image_pins.py`.
- `backend/tests/test_deploy_config.py` (8 тестов) проверяет compose/GHCR/
  Caddy/systemd/скрипты/ENV и digest-пиннинг без registry.

## i18n

Новых пользовательских строк нет — изменения инфраструктурные.
