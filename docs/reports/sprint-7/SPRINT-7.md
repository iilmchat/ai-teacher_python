# Sprint 7: Task System — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён

---

## 1. Файлы (+/-)

### Созданные
```
+ backend/app/models/task.py                    — Task, UserTaskProgress, enums
+ backend/app/schemas/task.py                   — схемы задач, submit, прогресса
+ backend/app/db/repositories/task.py           — TaskRepository, ProgressRepository
+ backend/app/core/test_runner.py               — прогон тест-кейсов
+ backend/app/services/task_service.py          — логика задач и прогресса
+ backend/app/api/v1/tasks.py                   — Task API
+ backend/alembic/versions/20261029_0003_tasks.py
+ backend/scripts/seed_tasks.py                 — 6 учебных задач
+ backend/tests/test_tasks.py                   — 14 тестов
+ backend/tests/test_runner.py                  — 11 тестов
```

### Изменённые
```
~ backend/app/core/executor.py      — stdin для input(), input разрешён
~ backend/app/schemas/code.py       — поле stdin в CodeRequest
~ backend/app/api/v1/code.py        — передача stdin в песочницу
~ backend/app/api/v1/auth.py        — регистрация игнорирует role/level (KI-011)
~ backend/app/models/__init__.py    — экспорт моделей задач
~ backend/app/main.py               — подключён tasks-роутер
~ backend/tests/test_code_api.py    — сигнатура FakeExecutor с stdin
```

---

## 2. Покрытие

| Файл | Тестов | Что проверяет |
|------|--------|----------------|
| `test_tasks.py` | 14 | CRUD преподавателем, фильтры, подсказки, submit (верно/неверно), попытки, прогресс по пользователям, эскалация роли |
| `test_runner.py` | 11 | нормализация вывода, частичный провал, ошибки выполнения, stdin, лимит кейсов, нарушения |
| **Итого новых** | **25** | всего в проекте — **126** |

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Линтер | `ruff check app tests` | `All checks passed!` |
| Типы | `mypy app --config-file ../pyproject.toml` | `Success: no issues found in 46 source files` |
| Тесты | `pytest -q` | `126 passed in 56.45s` |
| Миграции | `alembic upgrade head` | `Running upgrade 002 -> 003` |
| Схема | `alembic check` | `No new upgrade operations detected` |
| Seed | `python scripts/seed_tasks.py` | добавлено 6 задач |

---

## 4. Smoke

```
GET  /api/v1/tasks → 6 задач (Сумма двух чисел, Чётное/нечётное, Сумма 1..N,
                             Максимум из трёх, Таблица умножения, Реверс числа)
POST /api/v1/tasks/{id}/submit  (верное решение)
  → passed=true, 3/3, attempts=1, status="completed"
POST /api/v1/tasks/{id}/submit  (print(0))
  → passed=false, 1/3
GET  /api/v1/tasks/progress
  → completed=1, total_tasks=6, completion_rate=16.7
```

---

## 5. Что не так

1. **KI-010:** seed запускается вручную — на чистой базе каталог пуст.
2. Генерация задач через LLM не реализована (перенесено): сначала ручной набор.
3. Проверка решения запускает до 20 подпроцессов подряд — на слабой машине
   отправка может занимать несколько секунд.
4. Прогресс считается по всем активным задачам без пагинации.

---

## 6. Новые KI

| ID | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-010 | Open | Low | Задачи наполняются вручную |
| KI-011 | Resolved | Critical | Эскалация роли через регистрацию |

---

## 7. Обоснование

- **`stdin` вместо реального терминала.** `input()` в песочнице читает
  подготовленные строки: тесты детерминированы, ученик не может «подвесить»
  программу ожиданием ввода.
- **Мягкое сравнение вывода.** Лишний `\n` от `print` — не ошибка ученика;
  нормализуем `\r\n`, хвостовые пробелы и пустые строки.
- **Лимит 20 кейсов за прогон.** Ограничивает время и стоимость проверки;
  остальные кейсы игнорируются осознанно.
- **Прогресс отдельной таблицей.** `UserTaskProgress` с уникальным
  `(user_id, task_id)` позволяет считать попытки и статусы без пересчёта
  истории выполнений.
- **Мягкое удаление задач с прогрессом.** Ученик не теряет статистику, если
  преподаватель удалил задачу.
- **Регистрация без role.** Критичная уязвимость: любой мог стать админом.
  Роль меняется только администратором; добавлен регрессионный тест.

---

**Дата:** 2026-10-29
