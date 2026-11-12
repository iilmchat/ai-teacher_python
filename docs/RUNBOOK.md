# RUNBOOK.md — эксплуатация, инциденты и восстановление (S36)

> Оперативный документ для пилота v0.6.0: что делать, если что-то упало.
> Метрики/алерты — `docs/MONITORING.md`, SLO — `docs/SLO.md`, деплой —
> `docs/GETTING_STARTED.md` §7. Секреты и `.env.prod` не коммитить.

## 0. Быстрый доступ

```bash
cd /opt/ai-teacher
export ENV_FILE=.env.prod
COMPOSE="docker compose --env-file $ENV_FILE -f docker-compose.prod.yml"

$COMPOSE ps                       # состояние сервисов
$COMPOSE logs --tail=200 backend  # логи backend
$COMPOSE exec backend python -c \
  "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health/ready')"
curl -fsS https://<DOMAIN>/       # SPA через Caddy
```

- Caddy — единственный публичный слушатель (80/443; на пилоте 8080/8443).
- `backend`, `frontend`, `postgres`, `redis` — только внутри Docker-сети.
- Мониторинг: `docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml --profile monitoring up -d`; UI только на 127.0.0.1 (SSH-туннель).

## 1. Деплой

```bash
bash scripts/pin_images.sh --tag v0.6.0   # зафиксировать digest из GHCR
bash scripts/deploy.sh                   # бэкап → миграции → up → health
```

`deploy.sh` сохраняет предыдущее состояние в `.last_deploy`. При неудачном
healthcheck автоматически вызывает `rollback.sh`. `--dry-run` проверяет
конфиг без изменений; `--no-backup`/`--no-pull`/`--skip-migrations` — для
отладки.

## 2. Откат

```bash
bash scripts/rollback.sh              # на .last_deploy
bash scripts/rollback.sh --dry-run
bash scripts/rollback.sh --to .deploy-state.backup
```

Откатывается **код/образы**, не схема БД: миграции аддитивные, старый backend
совместим. Если данные повреждены — см. §5.

## 3. Если упала БД (`DatabaseDown`, 5xx)

1. `$COMPOSE ps postgres`; `docker logs <pg-container> --tail=200`.
2. Свободное место: `df -h`; память: `docker stats --no-stream`.
3. `pg_isready -U $POSTGRES_USER` внутри контейнера.
4. Рестарт: `$COMPOSE restart postgres`; backend переподключится сам.
5. Если БД не поднимается или повреждена:
   - остановить backend: `$COMPOSE stop backend`;
   - восстановить последний бэкап (§5) в рабочую БД;
   - поднять backend и проверить `/health/ready`.

## 4. Backend/Caddy/Redis

- **BackendDown:** `$COMPOSE logs backend`; проверить `SECRET_KEY` (fail-fast
  при `DEBUG=false`), миграции (`$COMPOSE --profile tools run --rm migrate`),
  память. Рестарт: `$COMPOSE restart backend`.
- **Caddy/TLS:** `$COMPOSE logs caddy`; проверить DNS A/AAAA → VPS, доступность
  портов 80/443 (на пилоте — 8080/8443 и upstream proxy). Сертификаты:
  `docker exec <caddy> ls /data/caddy/certificates`. Не удаляйте volume
  `caddy_data` без необходимости — иначе ACME-лимиты.
- **RedisDown:** не критично (лимиты/кэш fail-open); `$COMPOSE restart redis`.
- **Диск заполнен:** `docker system df`; старые бэкапы/логи; `journalctl
  --vacuum-time=7d`. Логи Docker ограничены 10 МБ × 3.

## 5. Бэкап и восстановление

Ежедневно в 03:00 UTC: `ai-teacher-backup.timer` → `scripts/backup.sh`.
Локально: `$BACKUP_DIR`; S3 — при заданных ключах; `age` — при `AGE_RECIPIENT`;
метрика `backup_last_success_timestamp` для `BackupStale`.

```bash
# Ручной бэкап
bash scripts/backup.sh
# С шифрованием и S3 (ключи в /etc/ai-teacher/backup.env)
AGE_RECIPIENT=age1... bash scripts/backup.sh

# Восстановление в рабочую БД (осознанно; сервис остановить)
$COMPOSE stop backend
bash scripts/restore.sh -f backups/ai_teacher_<stamp>.dump.gz \
  -t ai_teacher --force -y --clean
$COMPOSE start backend

# Проверка бэкапа без риска: restore drill в scratch-БД
bash scripts/restore_drill.sh            # последний бэкап
bash scripts/restore_drill.sh -f backups/...
```

`*.age` требует `--age-identity /etc/ai-teacher/age.key` (или ENV
`AGE_IDENTITY`). Scratch-БД удаляется автоматически; `--keep` — оставить для
разбора.

## 6. Секреты

- `SECRET_KEY`, `POSTGRES_PASSWORD`, `S3_*`, `AGE_IDENTITY`, `DEEPSEEK_API_KEY`
  — в `.env.prod` / `/etc/ai-teacher/*.env`, права `0600`, не в git.
- Ротация `SECRET_KEY` разлогинивает всех (refresh-токены невалидны) —
  предупредить пользователей.
- Ротация `POSTGRES_PASSWORD`: обновить `.env.prod`, `$COMPOSE up -d postgres
  backend` (пароль меняется в БД отдельно, см. PostgreSQL docs).

## 7. Мониторинг и алерты

- `docs/MONITORING.md` §6 — действия по каждому алерту.
- `High5xxRate`/`BackendDown`/`DatabaseDown` — critical; сначала health и
  логи, затем откат (§2).
- `BackupStale` — проверить timer (`systemctl status ai-teacher-backup.timer`)
  и место; сделать бэкап вручную.
- `RetentionStale` — `RETENTION_SCHEDULER_ENABLED`/логи.

## 8. Контакты и эскалация

1. Дежурный инженер: владелец проекта (`info@ruchating.com`).
2. Провайдер VPS/сети — при недоступности хоста или DNS.
3. LLM-провайдер — при массовых ошибках; включить fallback (`LLM_FALLBACK_PROVIDER`).

## 9. Постмортем

После инцидента: запись в `docs/KNOWN_ISSUES.md` (если нужен фикс), краткий
разбор в `docs/reports/` (что случилось, почему, что меняем), обновление
RUNBOOK/MONITORING, проверка, что бэкап и restore drill снова зелёные.
