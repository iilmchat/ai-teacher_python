# S40-003 — Env-drift: Settings ↔ `.env.example`

**Дата:** 2026-11-12
**Спринт:** 40
**Шаг:** S40-004 (по плану — дрейф `.env.example` ↔ `Settings`)
**Статус:** завершено

## 1. Задача

Не допускать расхождения кода и шаблона окружения: новая переменная в
`Settings` без `.env.example` (или наоборот) должна ломать локальный гейт и CI.

## 2. Что сделано

- `scripts/check_env_drift.py`:
  - парсит AST `backend/app/config.py` (класс `Settings`, аннотированные
    поля) — **без импорта pydantic**, работает до установки зависимостей;
  - читает только активные `KEY=VALUE` из `.env.example` (комментарии и
    пустые строки игнорируются);
  - сравнивает в snake_case; exit 1 при missing/extra, exit 2 при ошибке
    чтения/парсинга.
- Исключения: `version` (задаётся кодом) и `uvicorn_workers`
  (compose/uvicorn, не `Settings`).
- `.env.example` синхронизирован: добавлены `LOG_*`, `*_FILE`,
  `RATE_LIMIT_ENABLED`, `NOTIFICATIONS_*`, `SMTP_*`, `EXPORT_MAX_ROWS`,
  `RAG_*`, `MAX_UPLOAD_BYTES` — итого **76 полей**.
- `backend/tests/test_env_drift.py` — 4 теста: синхронность репозитория,
  missing, unknown, исключение `version`.
- Гейты: `scripts/ci/gates.sh`/`gates.ps1` (`--fast`), `backend-lint.sh`,
  `.github/workflows/ci.yml`, `gitflic-ci.yaml`.
- Документация: `CONTRIBUTING.md` §4, `RULES.md` §11.52.

## 3. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Синхронность | `python scripts/check_env_drift.py` | `OK: Settings (76 полей) и .env.example согласованы` |
| Негативный кейс | удалить `RATE_LIMIT_ENABLED=` → скрипт | exit **1**, `ENV DRIFT обнаружен` |
| После восстановления | `python scripts/check_env_drift.py` | exit 0 |
| Тесты | `pytest tests/test_env_drift.py -q` | **4 passed** |
| Линтер | `ruff check scripts` | All checks passed |

## 4. Риски

- Скрипт сравнивает имена, но не типы/дефолты: если ENV переименован с
  сохранением ключа — это не поймается. Для типов есть pydantic при старте.
- `UVICORN_WORKERS` и `PROMETHEUS_MULTIPROC_DIR` — compose-only; первый в
  allowlist, второй не входит в `Settings` и в `.env.example` не добавлялся
  (задаётся в prod-compose). При добавлении в `.env.example` — расширить
  `ENV_ONLY`.

## 5. Проблемы и открытия

Дрейф был реальным: в `.env.example` отсутствовали 22 переменные (включая
`RATE_LIMIT_ENABLED`, `*_FILE`, `RAG_*`). Исправлено; новые поля теперь
обязаны попадать в шаблон.

## 6. Дальнейшие шаги

- При добавлении `PROMETHEUS_MULTIPROC_DIR`/`BACKUP_*` в `.env.example`
  обновить allowlist осознанно.
- Возможное расширение: проверка, что ключи в `.env.prod.example` —
  подмножество `Settings` (отдельная задача, не блокирует S40).

## 7. Итог шага

Env-drift ловится локально и в CI; негативный сценарий проверен вручную.
Следующий шаг — актуализация документации (S40-005).
