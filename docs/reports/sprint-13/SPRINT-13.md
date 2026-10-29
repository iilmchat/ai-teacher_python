# Sprint 13: Sandbox Hardening — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён (S13-006 — опционально, отложен)

---

## 1. Файлы (+/-)

### Backend
```
+ app/core/sandbox_limits.py              — RLIMIT_AS / Job Object, обрезка вывода
+ tests/test_sandbox_limits.py            — 20 тестов (атаки, обходы, вывод)
+ tests/test_executor_memory.py           — 5 тестов (память, вывод, лимиты)
+ tests/test_executor_concurrency.py      — 3 теста (503, параллелизм, слот)
~ app/core/executor.py                    — лимиты в раннере, семафор, поля результата
~ app/config.py                           — memory/output/concurrency/queue
~ app/errors.py                           — ServiceUnavailableError (503)
~ app/api/v1/code.py                      — новые поля ответа и /code/limits
~ app/schemas/code.py                     — memory_limit_enforced/output_truncated
~ tests/test_code_api.py                  — лимиты и 503
+ app/services/llm/prompts/versions.json  — intermediate v2 (по итогам живого прогона)
~ app/services/llm/prompts/intermediate.txt — запрет полной программы в Q2
~ app/services/llm/lm_studio.py           — модель из LM_STUDIO_MODEL
~ app/config.py                           — lm_studio_model
+ docs/reports/llm-eval/2026-10-29/       — 15 ответов, REVIEW.md, Q2-prompt-v2.md
```

### Инфраструктура и документы
```
~ .env.example                            — EXECUTOR_MAX_OUTPUT/CONCURRENCY/QUEUE
~ docs/ARCHITECTURE.md                    — слои песочницы и таблица лимитов
~ docs/DESIGN_ADMIN_AND_OPS.md            — guardrails, таблица лимитов
~ docs/RULES.md                           — §11.8: ловушки лимитов и семафора
~ docs/SPEC.md                            — контракты /code/*
~ docs/MANUAL_TESTING_GUIDE.md            — кейсы 4.9–4.11
~ docs/KNOWN_ISSUES.md                    — KI-009 Resolved, KI-014 waiver
~ docs/RELEASES.md, CHANGELOG.md, README.md, docs/README.md, TODO_V0.2.md
+ docs/reports/sprint-13/SPRINT-13.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Backend тесты | 200 | **227** (+27; +1 skip на Windows) |
| Backend покрытие | 83% | **84%** |
| Frontend | 65 | 65 (не менялся) |

Новые тесты:

- `test_sandbox_limits.py` — 20: обрезка вывода (5), 11 атакующих векторов
  (`socket`, `urllib`, `http`, `os`, `subprocess`, `open`, `eval`, `exec`,
  `globals`, dunder), 3 обхода (`getattr`, `__builtins__`, `__import__`),
  проверка отсутствия файла
- `test_executor_memory.py` — 5: лимит по умолчанию из настроек, обычный код
  под лимитом, обрезка 1 МБ вывода, Windows Job Object, POSIX RLIMIT_AS
- `test_executor_concurrency.py` — 3: 503 при занятом слоте, 10 запусков при
  лимите 3, освобождение слота после ошибки
- `test_code_api.py` — +2: новые поля `/code/limits`, 503 при перегрузке

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты (Windows) | `pytest -q` | **227 passed, 1 skipped** за ~113 с |
| Покрытие backend | `pytest --cov=app` | **84%** (порог 70) |
| Ruff / MyPy | `ruff check app tests`, `mypy app` | 0 / 0 |
| Linux-контейнер, память | `python:3.12-slim`, `SandboxedExecutor` | лимит применён, huge → `MemoryError` |
| Linux-контейнер, обычный код | тот же прогон | `45`, `enforced=True` |
| Frontend | `pnpm typecheck && lint && test && build` | без изменений, 65 passed |

---

## 4. Smoke

1. **Windows, память.** `SandboxedExecutor().execute("x = [0] * 10**9")` →
   `success=false`, `error_type=MemoryError`, `memory_limit_enforced=true`,
   процесс Python/API жив.
2. **Linux, память.** В `python:3.12-slim` с RestrictedPython:
   обычный код `45` (`enforced=true`), `[0]*10**9` → `MemoryError`.
3. **Вывод.** `print("x" * 1_000_000)` при `max_output_chars=1000` →
   `output_truncated=true`, длина ≤ 1000, в конце «вывод обрезан».
4. **Перегрузка.** `max_concurrency=1`, `queue_timeout=0.1`: второй запуск →
   `ServiceUnavailableError` → HTTP 503; после освобождения слота работа идёт.
5. **Атаки.** `import socket`, `open(...)`, `(1).__class__`, `globals()` →
   `SecurityError`; `getattr`, `__builtins__['open']` — не выполняются;
   файл на диске не создан.
6. **LLM_EVAL (живой, DeepSeek).** `scripts/run_llm_eval.py --provider deepseek`:
   15 ответов, баллы basic 0.99 / intermediate 0.93 / advanced 0.96; найдено
   нарушение `intermediate/Q2`, промпт исправлен до v2, целевой ответ проверен.
7. **LM Studio.** `qwen/qwen3-4b-2507` на `127.0.0.1:8034` — ping ok,
   используется как fallback.

---

## 5. Что не так

- **Job Object зависит от окружения.** Если процесс уже находится в
  несовместимом Job Object (некоторые CI-обёртки/терминалы), назначение
  падает → `memory_limit_enforced=false`, остаётся таймаут. Это видно в
  ответе API; на локальном Windows и в Linux-контейнере лимит работает.
- **POSIX-путь проверен в контейнере, а не в CI:** CI заблокирован (KI-014),
  поэтому Linux-тест на этой машине пропускается (`skipif win32`).
- **S13-006 (раннер-контейнер) не делался:** нативные лимиты покрывают обе
  платформы; контейнер остаётся кандидатом на спринт 20.
- **CPU-время отдельно не ограничено:** от бесконечного цикла защищает
  таймаут; лимит параллелизма не даёт забить все воркеры.
- CI не стартовал (KI-014, биллинг GitHub); мерж разрешён владельцем на 5 дней.

---

## 6. Новые KI

Нет. **KI-009 закрыт** (Resolved): лимит памяти enforced на Windows и Linux,
тесты и документация обновлены. Дополнительно **KI-008 закрыт**: выполнен
живой прогон LLM_EVAL на DeepSeek, оценки зафиксированы
(`docs/reports/llm-eval/2026-10-29/REVIEW.md`), промпт `intermediate`
исправлен до v2. **KI-014** остаётся открытым (CI/биллинг).

---

## 7. Обоснование

- **Лимит ставится в дочернем процессе, а не в родителе.** На Windows Job
  Object назначается после старта процесса — код уже мог начать выполняться.
  Самоназначение (`GetCurrentProcess` + `AssignProcessToJobObject`) убирает
  гонку, а POSIX-путь после импортов не мешает загрузке RestrictedPython.
- **ctypes вместо pywin32.** Не тянем зависимость ради двух вызовов WinAPI;
  структуры `JOBOBJECT_*` описаны локально, handle job держится глобально.
- **`threading.BoundedSemaphore`, а не `asyncio.Semaphore`.** Семафор asyncio
  привязан к event loop, а pytest создаёт новый на каждый тест; общий
  threading-примитив работает и в API, и в тестах, и в фоновых задачах.
- **503 вместо очереди без границ.** Очередь без отказа копит потоки и
  превращает перегрузку в зависание; явный отказ с понятным текстом лучше.
- **Обрезка до JSON.** Если отдать 1 МБ stdout, родитель заплатит памятью и
  трафиком; обрезка в ребёнке дешевле и не ломает протокол.
- **Контейнер-раннер не обязателен.** Job Object и `RLIMIT_AS` дают реальный
  лимит без Docker-сокета в backend-контейнере (docker-in-docker — отдельный
  риск), поэтому S13-006 отложен, а не подменяет рабочие лимиты.
