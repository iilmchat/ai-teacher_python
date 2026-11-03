# SPRINT-32.md — Ops hardening: встроенный retention-планировщик (v0.3.2)

**Период:** 2026-11-03  
**Задачи:** S32-001…S32-003 (закрытие KI-025)  
**Статус:** ✅ завершён: планировщик, метрики, 18 тестов, документация,
версия 0.3.2 в трёх источниках

---

## 1. Что сделано

1. `app/services/scheduler.py` — планировщик retention: одна asyncio-задача в
   lifespan, время запуска `RETENTION_SCHEDULER_AT` (UTC), флаг
   `RETENTION_SCHEDULER_ENABLED` (по умолчанию off; в
   `docker-compose.prod.yml` — on), `RETENTION_SCHEDULER_BATCH_SIZE`.
2. Advisory-lock PostgreSQL (`pg_try_advisory_lock`, ключ `0x41495452`) на время
   прогона: второй инстанс получает `retention_scheduler_skipped` и ничего не
   удаляет; lock отпускается в `finally` даже при ошибке.
3. Graceful stop: `asyncio.Event` + `stop_scheduler` — при остановке приложения
   текущий прогон доигрывается (таймаут 30 с), новый не начинается.
4. Prometheus: `retention_rows_deleted_total{table}`,
   `retention_runs_total{table,result}` — считаются и в планировщике, и в CLI
   (`apply_retention`).
5. `.env.example`: блок `RETENTION_*`; убрана переменная `VERSION` (перекрывала
   версию из `config.py` и устаревала: в `.env` было `0.1.0` при релизе 0.3.1).
6. Документация: CHANGELOG `[0.3.2]`, RELEASES (спринт 32 + «Релиз v0.3.2»),
   KNOWN_ISSUES (KI-025 → Resolved), UPGRADE §0, PRIVACY §4,
   DESIGN_ADMIN_AND_OPS §11, README, TODO/TODO_V0.3 (актуализированы чекбоксы),
   MANUAL_TESTING_GUIDE §19.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| ruff | `ruff check app tests` (из `backend/`) | 0 |
| mypy strict | `mypy app --config-file ../pyproject.toml` | 0 (92 файла) |
| pytest (полный) | `pytest -q` | 496 passed, 22 skipped, 2 failed — оба падения **воспроизводятся на чистом дереве** (stale venv: fastapi 0.115.5 / starlette 0.41.3 вместо запиненных 0.162 / 1.10) |
| pytest (затронутое) | `pytest tests/test_scheduler.py tests/test_export_retention.py` | 29 passed |
| версия | `python backend/scripts/check_version.py` | 0.3.2 во всех трёх источниках |
| заметки релиза | `python backend/scripts/release_notes.py --version 0.3.2` | раздел найден |
| frontend | не трогался (кроме `package.json`), CI-гейты — на PR | — |

**Про 2 локальных падения:** `test_access_matrix::test_missing_credentials…`
(403 вместо 401) и `test_contract_openapi::test_openapi_matches_snapshot` —
следствие старого venv: в нём `fastapi 0.115.5` / `starlette 0.41.3`, а
`backend/requirements.txt` пинует `0.162.0` / `1.10.0` (S22-002). Проверено
`git stash` → те же два теста падают на исходном коде без изменений спринта.
CI гоняет зависимости из `requirements.txt` в `python:3.12-slim`, поэтому там
ожидается 519 passed + 1 skipped.

---

## 3. Файлы

```
+ backend/app/services/scheduler.py        — планировщик (lock, цикл, stop)
+ backend/tests/test_scheduler.py          — 18 тестов
+ docs/reports/sprint-32/SPRINT-32.md     — этот отчёт
~ backend/app/config.py                    — RETENTION_SCHEDULER_*, версия 0.3.2
~ backend/app/core/metrics.py              — retention-счётчики, reset_metrics
~ backend/app/services/retention.py        — инкремент счётчиков
~ backend/app/main.py                      — запуск/остановка планировщика в lifespan
~ docker-compose.prod.yml                  — планировщик включён в production
~ .env.example                             — блок RETENTION_*, убрана VERSION
~ pyproject.toml / frontend/package.json   — 0.3.2
~ docs/CHANGELOG.md                        — [0.3.2]
~ docs/RELEASES.md                         — шапка, спринт 32, «Релиз v0.3.2»
~ docs/KNOWN_ISSUES.md                     — KI-025 закрыта, KI-024 в «Активные»
~ docs/UPGRADE.md                          — §0: обновление v0.3.1 → v0.3.2
~ docs/PRIVACY.md / DESIGN_ADMIN_AND_OPS.md / MANUAL_TESTING_GUIDE.md
~ README.md / TODO.md / TODO_V0.3.md / docs/README.md
```

---

## 4. Проблемы и отклонения

1. **Локальный venv устарел** (fastapi/starlette из S22 не установлены — PyPI
   с хоста заблокирован, KI-017). Полный локальный pytest не может быть
   «зелёным» без пересоздания venv через wheelhouse/Docker; атрибуция
   падений подтверждена baseline-прогоном. Пересоздание venv — отдельная
   задача окружения, не код спринта.
2. **KI-024 не трогали** (метрики LLM/кэша на процесс) — осознанно вынесено в
   v0.4.0 вместе с переходом на несколько воркеров: в одном процессе значения
   корректны, переделка scrape-пути сейчас — риск без пользы.

---

## 5. Обоснование решений

- **Advisory-lock PostgreSQL, а не Redis-lock:** PostgreSQL уже обязателен для
  retention; `pg_try_advisory_lock` не требует TTL/продления и не оставляет
  «мёртвый» lock дольше сессии. Redis-lock пришлось бы делать с истечением и
  повторной проверкой.
- **`asyncio.Event`, а не `task.cancel()` при остановке:** отмена может
  прервать удаление между батчами; событие позволяет доиграть прогон (батчи
  коммитятся), а таймаут 30 с страхует shutdown.
- **Флаг по умолчанию `false` в коде, `true` в prod-compose:** dev/тесты не
  получают фоновых задач в БД; production получает поведение из коробки.
  Внешний cron остаётся документированной альтернативой.
- **Счётчики, а не gauge:** `retention_rows_deleted_total` — Counter, поэтому
  суммируется между инстансами и scrape'ами (в отличие от gauge'ов LLM/кэша,
  KI-024).
- **Удаление `VERSION` из `.env.example`:** это был второй источник истины,
  который уже разошёлся с кодом (0.1.0 в `.env` при версии 0.3.1); версия
  остаётся в `config.py` + `check_version.py` для релиза.
- **Чекбоксы TODO 26/28:** UI-остатки (кнопка отчёта, мультивыбор, страница
  журнала) сделаны ещё в S30 — чекбоксы были не актуализированы; код проверен
  (`ClassroomDetailPage`, `GradebookPage`, `gradebook.test.tsx`).

---

## 6. Что дальше

- PR → зелёный CI (self-hosted runner) → merge в `main`.
- Релиз: `gh workflow run release.yml -f version=0.3.2 -f dry_run=false`
  (заметки — раздел «Релиз v0.3.2» в RELEASES).
- v0.4.0: KI-024 (мультипроцессные метрики — Redis-счётчики или
  `PROMETHEUS_MULTIPROC_DIR`), планировщик напоминаний о дедлайнах с
  дедупликацией, runbook масштабирования; завести `TODO_V0.4.md`.
- KI-023 — запрос владельцу (GitHub Pro или GitFlic-токен/агент).
