# Sprint 6: Code Execution — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён (кроме лимита памяти — KI-009)

---

## 1. Файлы (+/-)

### Созданные
```
+ backend/app/core/executor.py                 — песочница (RestrictedPython + процесс)
+ backend/app/core/linter.py                   — AST-линтер и метрики кода
+ backend/app/models/code.py                   — модель CodeExecution
+ backend/app/schemas/code.py                  — схемы выполнения/линта/анализа
+ backend/app/db/repositories/code.py          — история запусков
+ backend/app/api/v1/code.py                   — Code API
+ backend/alembic/versions/20261029_0002_code_executions.py
+ backend/tests/test_executor.py               — 12 тестов
+ backend/tests/test_linter.py                 — 13 тестов
+ backend/tests/test_code_api.py               — 9 тестов
```

### Изменённые
```
~ backend/app/models/__init__.py   — экспорт CodeExecution
~ backend/app/main.py              — подключён code-роутер
~ pyproject.toml                   — RestrictedPython в mypy overrides
```

---

## 2. Покрытие

| Файл | Тестов | Что проверяет |
|------|--------|----------------|
| `test_executor.py` | 12 | print, math, циклы, запрет os/open/dunder, ошибки, timeout |
| `test_linter.py` | 13 | S001–S003, W001–W003, I001, метрики, чистый код |
| `test_code_api.py` | 9 | execute + история, линт, анализ, изоляция истории, лимиты |
| **Итого** | **34** | всего в проекте — **101** |

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Линтер | `ruff check app tests` | `All checks passed!` |
| Типы | `mypy app --config-file ../pyproject.toml` | `Success: no issues found in 40 source files` |
| Тесты | `pytest -q` | `101 passed in 43.89s` |
| Миграция | `alembic upgrade head` | `Running upgrade 001 -> 002` |
| Схема | `alembic check` | `No new upgrade operations detected` |

---

## 4. Smoke

```
POST /auth/register → 201
POST /auth/login    → 200
POST /code/execute {"code":"total = sum(range(5))\nprint(total)"}
  → {"success":true,"output":"10\n","execution_time":0.0077}
POST /code/execute {"code":"import os\nprint(1)"}
  → {"success":false,"error":"Импорт запрещённого модуля: os","error_type":"SecurityError"}
POST /code/lint {"code":"x = 1\nif x == None:\n    pass"}
  → W002 «Сравнение с None: используйте is None»
```

---

## 5. Что не так

1. **KI-009:** лимит памяти 128 МБ не применяется (на Windows нет `resource`,
   `subprocess` не умеет ограничивать RSS кроссплатформенно).
2. **KI-008:** реальные ответы LLM по-прежнему не проверены.
3. **Запрет импорта возвращает HTTP 200** с `success=false` — это осознанно
   (результат выполнения), но фронтенду нужно явно показывать `violations`.
4. Логирование попыток нарушения безопасности (S6-002) пока не выполнено —
   сообщения возвращаются клиенту, но не пишутся в структурный лог.

---

## 6. Новые KI

| ID | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-009 | Open | Med | Лимит памяти песочницы не enforced |

---

## 7. Обоснование

- **Процесс вместо потока.** Первая версия выполняла код в потоке:
  `asyncio.wait_for` отменял задачу, но поток продолжал крутить `while True`,
  и процесс API не завершался. Отдельный интерпретатор решает это: таймаут
  убивает процесс.
- **subprocess вместо multiprocessing.** На Windows `spawn` перезапускает
  `__main__` и конфликтует с uvicorn («Safe importing of main module»).
  Отдельный интерпретатор не зависит от `__main__`.
- **Два уровня проверки.** Статический AST-анализ отсекает очевидно опасное
  до запуска (быстро, понятные сообщения), RestrictedPython — второй барьер
  на уровне семантики.
- **Собственный линтер.** pylint/flake8 — тяжёлые зависимости ради нескольких
  правил; для учебных подсказок достаточно AST-проверок (RULES §3.3).
- **`_print_ = PrintCollector` + `_inplacevar_`.** RP 7 инстанцирует коллектор
  сам (`_print = _print_(_getattr_)`), а `+=` транслируется в `_inplacevar_` —
  оба контракта пришлось реализовать явно (проверено дизассемблированием).
- **История запусков в БД.** Нужна для прогресса ученика и разбора ошибок
  в следующих спринтах.

---

**Дата:** 2026-10-29
