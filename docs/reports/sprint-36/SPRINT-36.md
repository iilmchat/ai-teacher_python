# Спринт 36 — Registry, Deploy, TLS & Backup/DR

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening»
**Задачи:** S36-001…S36-009 (группы 004/005 и 006/007)
**Статус:** завершён (без реального GHCR/сервера — конфигурации проверены локально)

---

## 1. Итоги

| Задача | Результат |
|--------|-----------|
| S36-001 | `docker-publish.yml`: backend/frontend/sandbox-runner → GHCR по тегу `v*` |
| S36-002 | prod-compose без `build:`, GHCR-образы через ENV; `pin_images.sh` фиксирует digest в `.env.prod` |
| S36-003 | `deploy/caddy/Caddyfile`: TLS/ACME, frontend + `/api/*` + WebSocket, HSTS; Caddy — единственный публичный вход |
| S36-004 | one-shot `migrate`; backend `SKIP_MIGRATIONS=true` |
| S36-005 | `deploy.sh` (бэкап→миграции→pull→up→health→авто-откат), `rollback.sh` |
| S36-006 | `backup.sh`: авто-контейнер, gzip, age, S3, retention, метрика; systemd 03:00 |
| S36-007 | `restore_drill.sh` в scratch-БД; `restore.sh` понимает `*.age` |
| S36-008/009 | `RUNBOOK.md`, ARCHITECTURE/GETTING_STARTED/SECURITY, CI-гейт |

---

## 2. Файлы

**Инфраструктура:**
- `.github/workflows/docker-publish.yml`
- `docker-compose.prod.yml` (GHCR, Caddy, migrate, сети, TRUSTED_PROXIES)
- `deploy/caddy/Caddyfile`
- `deploy/systemd/{ai-teacher-backup.service,ai-teacher-backup.timer,backup.env.example}`
- `.env.prod.example`, `.gitignore`

**Скрипты:**
- `scripts/pin_images.sh`
- `scripts/deploy.sh`, `scripts/rollback.sh`
- `scripts/backup.sh` (расширен), `scripts/restore.sh` (+age), `scripts/restore_drill.sh`
- `scripts/lib/env.sh` (безопасная загрузка ENV)

**Код/тесты:**
- `backend/scripts/check_image_pins.py` (ENV/алиасы, monitoring compose)
- `backend/tests/test_deploy_config.py` (8 тестов)
- CI job **Deploy config** в `ci.yml` / `ci-selfhosted.yml`

**Документация:**
- `docs/RUNBOOK.md` (новый), `ARCHITECTURE.md`, `GETTING_STARTED.md`,
  `SECURITY.md`, `README.md`, `docs/README.md`, `CHANGELOG.md`,
  `RELEASES.md`, `TODO_V0.4.md`, отчёты `docs/reports/sprint-36/`.

---

## 3. Проверки

### Конфигурация

```
docker compose --env-file .env.prod.example -f docker-compose.prod.yml config --quiet
docker compose ... -f docker-compose.monitoring.yml --profile monitoring config --quiet
# OK

caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
# Valid configuration

python backend/scripts/check_image_pins.py
# OK: все образы закреплены по digest (6 файлов)

bash -n scripts/*.sh scripts/lib/env.sh
# OK (7 скриптов)
```

### Скрипты

```
bash scripts/pin_images.sh --tag v0.6.0 --digest ...   # .env.prod обновлён
bash scripts/deploy.sh --dry-run                       # config валиден
bash scripts/rollback.sh --dry-run                     # план отката
```

### Бэкап и DR (реально, dev-БД)

```
bash scripts/backup.sh
# OK: ai_teacher_20261112T075927Z.dump.gz (20K); retention 14 дн.

bash scripts/restore_drill.sh
# Таблиц: 17; users: 32; alembic_version: OK
# OK: restore drill успешен; scratch-БД удалена
```

### Тесты

```
cd backend && pytest tests/test_deploy_config.py -q          # 8 passed
cd backend && pytest tests/test_monitoring_config.py \
  tests/test_metrics_export.py tests/test_sentry.py -q       # 26 passed
```

Полный прогон: **780 passed, 1 skipped**.

---

## 4. Ограничения (нет доступа к GHCR/серверу)

- Реальная публикация образов и ACME-выпуск не выполнялись; workflow и
  Caddyfile валидированы статически.
- `deploy.sh` проверен в `--dry-run` и `rollback.sh` в `--dry-run`; health-gate
  и авто-откат исполняются на сервере с реальными образами.
- S3/age-бэкапы не запускались (нет ключей/`age`); локальный бэкап и полный
  restore drill — успешно.

---

## 5. Следующий шаг

**S37 — CI Gates & GitFlic** (required checks, паритет CI, coverage-гейт),
затем S38 Security & Privacy. `KI-023` (merge-gate) по-прежнему требует
действия владельца.
