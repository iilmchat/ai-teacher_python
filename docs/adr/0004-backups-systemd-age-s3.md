# ADR-004 — Бэкапы: systemd + age + S3

**Статус:** Accepted
**Дата:** 2026-11-12
**Контекст:** Аудит: бэкапы запускались вручную, имя контейнера БД было
захардкожено (`ai_teacher_postgres`), не было off-site/шифрования, restore
drill — вручную. Для пилота нужен предсказуемый ежедневный бэкап и проверка
восстановления.

## Решение

- `scripts/backup.sh`:
  - находит контейнер через `docker compose ps -q postgres` (fallback ENV);
  - `pg_dump -Fc` → проверка `pg_restore -l` → gzip;
  - `age`-шифрование при `AGE_RECIPIENT` (публичный ключ; приватный — только
    у владельца);
  - выгрузка в S3 при `AWS_ACCESS_KEY_ID` + `S3_BUCKET` (aws-cli/s3cmd,
    Selectel endpoint), иначе локально;
  - sha256, retention 14 дней, `TEXTFILE_DIR` → `backup_last_success_timestamp`.
- systemd `ai-teacher-backup.service` + `.timer` (03:00 UTC, Persistent).
- `scripts/restore.sh` (+ `*.age`), `scripts/restore_drill.sh` — восстановление
  в scratch-БД с проверками и удалением.
- Алерт `BackupStale` (Prometheus + node-exporter textfile).

## Последствия

**Плюсы:**
- ежедневный автоматический бэкап без ручного участия;
- off-site и шифрование снижают риск компрометации/потери VPS;
- restore drill доказывает, что бэкап читается, а не просто создаётся.

**Минусы/риски:**
- нужен age-ключ и S3-креды; потеря приватного ключа = потеря архива;
- S3 lifecycle/retention нужно настроить у провайдера;
- systemd-таймер требует Linux-VPS (на Windows — Task Scheduler / ручной запуск).

**Ссылки:** `scripts/backup.sh`, `scripts/restore.sh`,
`scripts/restore_drill.sh`, `deploy/systemd/`, `docs/RUNBOOK.md` §5.
