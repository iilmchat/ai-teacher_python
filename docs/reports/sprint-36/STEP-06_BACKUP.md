# S36-006 — бэкапы

**Дата:** 2026-11-12
**Спринт:** 36
**Статус:** завершено

## backup.sh

- Контейнер БД определяется через
  `docker compose -f $COMPOSE_FILE ps -q postgres` (имя не хардкодится);
  fallback — `-c CONTAINER`.
- `pg_dump -Fc` → проверка `pg_restore -l` → gzip.
- `AGE_RECIPIENT` → `age -r` (файл `*.dump.gz.age`).
- `AWS_ACCESS_KEY_ID` + `S3_BUCKET` → `aws s3 cp` (или `s3cmd`),
  `S3_ENDPOINT_URL` для Selectel; иначе локально.
- `sha256`, retention 14 дней (настраивается), `--dry-run`, `--no-s3`.
- `TEXTFILE_DIR` → `backup_last_success_timestamp` и `backup_size_bytes` для
  node-exporter (`BackupStale`).
- ENV загружается безопасно (`scripts/lib/env.sh`), без `source` — значения с
  пробелами не ломают скрипт.

## systemd

`deploy/systemd/`:

- `ai-teacher-backup.service` — oneshot, `EnvironmentFile=/etc/ai-teacher/backup.env`;
- `ai-teacher-backup.timer` — `OnCalendar=*-*-* 03:00:00`, `Persistent=true`,
  случайная задержка до 5 минут;
- `backup.env.example` — шаблон окружения (права 0600).

## node-exporter

В `docker-compose.monitoring.yml` добавлен `node-exporter` (digest-pinned),
Prometheus scrape'ит `node-exporter:9100`, textfile-коллектор читает
`/var/lib/node_exporter/textfile` — алерт `BackupStale` теперь получает данные.

## Проверки (реальный запуск, dev-БД)

```
COMPOSE_FILE=docker-compose.yml ENV_FILE=.env bash scripts/backup.sh
[backup] pg_dump -Fc
[backup] Проверка архива (pg_restore -l)
[backup] S3: ключи/бакет не заданы — бэкап остаётся локально
[backup] OK: .../ai_teacher_20261112T075927Z.dump.gz (20K); retention 14 дн.
```

S3/age не запускались (нет ключей/age в окружении); ветки покрыты
конфигурационными тестами и документированы в RUNBOOK §5.
