# UPGRADE.md — обновление v0.2.0 → v0.3.0

> Дата: 2026-11-01. Релиз «Ops & Scale»: CI/релиз-процесс, зависимости, песочница,
> наблюдаемость, приватность, поиск и инструменты учителя.

## 1. Что меняется для эксплуатации

| Область | Изменение | Действие |
|---------|-----------|----------|
| БД | 3 новые миграции: `011` (audit_log), `012` (users.is_active), `013` (assignment_templates) | `alembic upgrade head` |
| Песочница | контейнерный режим `EXECUTOR_MODE=container` (опция) + пул воркеров | по желанию: собрать образ и включить |
| Метрики | `GET /metrics` (Prometheus) и `/health/live`/`/health/ready` | открыть только внутренней сети |
| Логи | JSON по умолчанию, `X-Request-ID` сквозной | настроить сбор логов |
| Аудит | журнал действий teacher/admin + `GET /admin/audit` | проверить доступ admin |
| Экспорт/ПДн | CSV/JSON-экспорт, retention-скрипт, `DELETE /auth/me` | задать `RETENTION_*`, прочитать `docs/PRIVACY.md` |
| Поиск | `RAG_MIN_SCORE`, backfill эмбеддингов | при включённом RAG — запустить backfill |
| Email | `NOTIFICATIONS_EMAIL_ENABLED` (по умолчанию off) | включить при готовом SMTP |

**Ломающие изменения:** отсутствующий `Authorization` теперь даёт **401** (было
403 — поведение Starlette 1.x); `users.is_active=false` блокирует вход;
`/metrics` не публикуется через nginx (404).

## 2. Порядок обновления

```bash
git fetch && git checkout v0.3.0

# 1) Бэкап
bash scripts/backup.sh            # pg_dump в backups/

# 2) Новые переменные окружения (.env) — см. таблицу ниже
cp .env.example .env && $EDITOR .env

# 3) Миграции (с 010 до 013)
cd backend && alembic upgrade head && alembic check && cd ..

# 4) Пересборка и запуск
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 5) Проверка
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS -H 'X-Request-ID: upgrade-check' http://127.0.0.1:8000/health/live
docker compose -f docker-compose.prod.yml ps
```

Опционально (изоляция песочницы):

```bash
docker build -f backend/sandbox_runner/Dockerfile -t ai-teacher-sandbox-runner:latest backend
docker run --rm -i --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 65534:65534 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m --memory 128m --pids-limit 64 \
  --pull never ai-teacher-sandbox-runner:latest --self-check
# затем EXECUTOR_MODE=container в .env
```

## 3. Новые переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `EXECUTOR_MODE` | `native` | `native` или `container` (раннер в Docker) |
| `EXECUTOR_IMAGE` | `ai-teacher-sandbox-runner:latest` | образ раннера |
| `EXECUTOR_POOL_SIZE` | `2` | тёплые воркеры (0 — выключить) |
| `EXECUTOR_POOL_MAX_TASKS` | `50` | задач на воркер до перезапуска |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | логи (`console` — для dev) |
| `METRICS_ENABLED` / `METRICS_PATH` | `true` / `/metrics` | Prometheus-эндпоинт |
| `RETENTION_CHAT_MESSAGES_DAYS` | `90` | хранение сообщений чата (0 — off) |
| `RETENTION_CODE_EXECUTIONS_DAYS` | `90` | хранение запусков кода |
| `RETENTION_NOTIFICATIONS_DAYS` | `180` | хранение уведомлений |
| `RETENTION_AUDIT_LOG_DAYS` | `365` | хранение журнала аудита |
| `EXPORT_MAX_ROWS` | `100000` | лимит строк одного экспорта |
| `RAG_MIN_SCORE` | `0.0` | порог семантического поиска (0 — без порога) |
| `NOTIFICATIONS_EMAIL_ENABLED` | `false` | email-уведомления |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | — | SMTP |
| `NOTIFICATIONS_DEADLINE_HOURS` | `72` | окно напоминаний о дедлайне |

Полный список — `.env.example`.

## 4. После обновления

1. `/health/ready` → `status: ready`; `/metrics` отдаёт метрики.
2. Аудит: действие учителя (создание задачи) видно в `GET /api/v1/admin/audit`.
3. Retention: `python backend/scripts/apply_retention.py --dry-run` (ничего не удаляет).
4. RAG (если включён): `python backend/scripts/backfill_embeddings.py --dry-run`, затем без флага.
5. Email (если включён): назначить задачу классу — письмо в SMTP/MailHog.

## 5. Откат

```bash
# вернуть код
git checkout v0.2.0
# откатить миграции (011–013 аддитивные, данные новых таблиц будут удалены)
cd backend && alembic downgrade 010 && cd ..
docker compose -f docker-compose.prod.yml up -d --build
```

`010 → 009` и ниже не требуется: новые таблицы/колонки не использовались старой
версией. Перед откатом сделайте бэкап: `bash scripts/backup.sh`.

## 6. Известные ограничения v0.3.0

См. [KNOWN_ISSUES.md](KNOWN_ISSUES.md): KI-023 (branch protection на GitHub Free),
KI-018 (`.format()` в песочнице), KI-024 (метрики LLM/кэша — на процесс),
KI-025 (retention запускается вручную/по cron).
