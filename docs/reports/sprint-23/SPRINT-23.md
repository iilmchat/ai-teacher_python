# SPRINT-23.md — Sandbox Throughput (v0.3.0)

**Период:** 2026-10-31  
**Задачи:** S23-001…S23-005  
**Статус:** ✅ завершён: submit 5 RPS — p95 **48.9 мс** (бюджет 2000 мс;
до спринта 2219.7 мс); knee не найден до 40 RPS; `KI-022` закрыт

---

## 1. Файлы (+/-)

```
~ backend/app/core/executor.py            — _BATCH_RUNNER/_POOL_WORKER,
                                            execute_many, пул, таймаут на кейс
~ backend/app/core/test_runner.py         — батчевый путь по умолчанию
+ backend/app/core/runner_pool.py         — пул тёплых интерпретаторов (S23-002)
+ backend/app/config.py                   — EXECUTOR_POOL_SIZE/MAX_TASKS
~ backend/app/main.py                     — закрытие пула в lifespan
+ backend/tests/test_batch_executor.py    — 16 тестов батча
+ backend/tests/test_runner_pool.py       — 11 тестов пула
+ backend/tests/test_sandbox_batch_security.py — 36 тестов безопасности
~ backend/tests/test_runner.py            — фейк поддерживает execute_many
~ backend/tests/test_tasks.py, test_task_generation.py — фейки: execute_many
+ scripts/ci/perf.ps1                     — perf-smoke (backend + load test)
+ .github/workflows/perf-nightly.yml      — ночной прогон 2 RPS
~ .github/workflows/ci-selfhosted.yml     — job `Perf smoke (submit)` (0.5 RPS)
+ docs/reports/sprint-23/LOAD_TEST-SUBMIT.md
+ docs/reports/sprint-23/load-test.json   — сырые цифры
+ docs/reports/sprint-23/SPRINT-23.md     — этот отчёт
~ docs/ARCHITECTURE.md                    — слой 5: раннер и пул
~ docs/RULES.md                           — §11.8 п. 12–15
~ docs/SPEC.md                            — лимиты, батч, пул, throughput
~ .env.example                            — EXECUTOR_POOL_*
~ docs/CHANGELOG.md, docs/KNOWN_ISSUES.md — KI-022 → Resolved
~ docs/RELEASES.md, TODO_V0.3.md          — журнал и статусы
```

---

## 2. Покрытие

- **Батч (16):** все кейсы одним процессом, изоляция переменных между кейсами,
  ошибка в середине не ломает остальные, таймаут на кейс, `SystemExit` не
  убивает батч, обрезка вывода, UTF-8, лимит памяти, пустой список, fallback
  при недоступном subprocess, `run_test_cases` использует батч (patch
  `execute` → падение, если вызван), 1/5/20 кейсов.
- **Пул (11):** переиспользование (1 процесс на 3 батча), перезапуск после
  таймаута и после `max_tasks`, выключение `pool_size=0`, изоляция задач,
  блокировка импортов, закрытие пула, 1/3/8 кейсов, отсутствие циклического
  импорта.
- **Безопасность (36):** 14 атакующих векторов × 2 режима (батч/пул),
  отсутствие файловых побочных эффектов, восстановление после
  `MemoryError`/`TimeoutError`, отсутствие переиспользования «отравленного»
  процесса, корректные результаты при ошибке в середине батча.
- **Непокрытое:** `scripts/ci/perf.ps1` — инфраструктурный скрипт (проверен
  запуском), нагрузочный harness проверяется самим прогоном.

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | **0** |
| `mypy app` (strict) | **0** |
| `pytest -q` | **430 passed, 1 skipped** (142 с) |
| submit 5 RPS (пул 2) | p50 34.8 мс, **p95 48.9 мс**, 0 ошибок → **PASS** |
| knee (пул) | 15/25/40 RPS → p95 48.9/54.3/94.8 мс, 0 ошибок |
| health 50 RPS / tasks 20 RPS | p95 7.3 / 19.3 мс → PASS |
| perf-smoke скрипт локально | submit 0.5 RPS — PASS (p95 50.7 мс) |
| e2e / frontend | без изменений (12/12, 80/80) |

Build: 0/0; Tests: 430/431 (1 skip — Windows-only).

---

## 4. Smoke

1. `pytest -q tests/test_batch_executor.py tests/test_runner_pool.py
   tests/test_sandbox_batch_security.py` → 63 passed.
2. Backend с `EXECUTOR_POOL_SIZE=2`; `load_test.py --scenario submit --rps 5`
   → p95 48.9 мс.
3. Тот же прогон с `pool_size=0` → p95 395 мс (эффект пула виден).
4. `scripts/ci/perf.ps1 -Rps 0.5 -Duration 10` → «PERF SMOKE OK».
5. Атака `import os` в батче → `SecurityError` для каждого кейса, файл не
   создаётся; после `MemoryError`/таймаута следующая задача проходит.

---

## 5. Что не так

1. **Фейковые исполнители ломали батч.** `CaseAwareExecutor`/`ExpectedOutputExecutor`
   переопределяли только `execute`, а `run_test_cases` вызывает `execute_many` —
   батч уходил в настоящую песочницу, два теста прогресса «покраснели».
   Исправлено в фейках; урок — RULES §11.8 п. 14.
2. **Лимит памяти — на процесс пула.** RLIMIT_AS/Job Object нельзя ослабить
   или навесить дважды, поэтому значение фиксируется при первом кейсе процесса.
   Для задач с разными лимитами пул придётся выключать (`EXECUTOR_POOL_SIZE=0`).
3. **p99 ≈ 338 мс** — «холодные» первые запросы (пул поднимает процессы);
   медиана и p95 стабильны.
4. **Конкурентность клиента 5** ограничивает knee-замеры: при 15 RPS без пула
   достигнуто 12.5. Для точного knee нужен прогон с большей конкурентностью.
5. **Ночной perf-прогон** запускается только при включённой машине
   (self-hosted runner) — это ограничение инфраструктуры, а не теста.

---

## 6. Новые KI

- **Новых KI нет.** `KI-022` → `Resolved`.
- Активны: `KI-018` (accepted, `.format()` в песочнице), `KI-023` (merge-gate).

---

## 7. Обоснование

1. **Батч — самое дешёвое ускорение.** 2 из 3 стартов интерпретатора просто
   выбрасывались; один процесс на задачу снижает latency втрое без изменения
   модели изоляции (свежие globals на кейс).
2. **Таймаут на кейс, а не на батч.** Иначе один `while True` съедал бюджет
   всех кейсов и клиент не понимал, какой кейс виноват. Построчный протокол
   даёт точную диагностику и позволяет убить процесс, не теряя результаты
   предыдущих кейсов.
3. **Пул — опция, а не догма.** `EXECUTOR_POOL_SIZE=0` возвращает прежнюю
   модель «процесс на задачу»; это нужно, если у задач разные лимиты памяти или
   требуется гарантированная чистота модульного состояния. По умолчанию 2 —
   компромисс между скоростью и памятью (2 × 128 МБ).
4. **Гейт в CI, а не «на глаз».** Perf-smoke ловит регресс submit при мерже
   (0.5 RPS достаточно, чтобы поймать повторное появление per-case процессов),
   ночной 2 RPS — запас по стабильности.
5. **Безопасность проверяем в том же режиме, что и прод.** Атакующие тесты
   идут и в батче, и в пуле: изоляция не должна зависеть от оптимизации.
