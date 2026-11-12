# S36-007 — restore drill (DR)

**Дата:** 2026-11-12
**Спринт:** 36
**Статус:** завершено

## restore.sh

Добавлена поддержка `*.age`:

- `--age-identity FILE` (или `AGE_IDENTITY`), расшифровка во временный gzip;
- дальше — прежняя логика: `--create`, `--clean`, `--force`, `--verify`,
  защита системных БД и рабочей БД без `--force`.

## restore_drill.sh

- Берёт последний бэкап (`BACKUP_DIR`) или `-f FILE`;
- создаёт scratch-БД `ai_teacher_drill_<UTC>`;
- вызывает `restore.sh --create -y --verify`;
- проверяет: таблиц > 0, `alembic_version` = 1, `users` читается;
- удаляет scratch-БД (если не `--keep`);
- пишет лог в `${BACKUP_DIR}/dr-reports/` (gitignored);
- `--dry-run`.

## Реальный прогон (dev-БД)

```
COMPOSE_FILE=docker-compose.yml ENV_FILE=.env BACKUP_DIR=./backups \
  bash scripts/restore_drill.sh

...
users 32
OK: восстановление в ai_teacher_drill_20261112T075935Z завершено.
[drill] Проверки после восстановления
[drill] Таблиц: 17; users: 32; alembic_version: OK
[drill] OK: restore drill успешен
[drill] Scratch-БД ai_teacher_drill_20261112T075935Z удалена
```

## Ограничение

Восстановление из S3 и `age`-файла не выполнялось (нет ключей/age); логика
описана и покрыта синтаксической/конфигурационной проверкой. Для пилота
рекомендуется еженедельный restore drill (systemd timer или cron).
