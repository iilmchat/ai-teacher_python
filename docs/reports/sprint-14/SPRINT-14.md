# Sprint 14: Tasks v2 — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён

---

## 1. Файлы (+/-)

### Backend
```
+ app/data/seed_tasks.py                  — стартовый набор задач (перенос из CLI)
+ app/services/seed_service.py            — идемпотентный seed
+ app/services/task_import.py             — JSON/YAML, импорт и экспорт
+ app/services/task_generation.py         — LLM-генерация с проверкой в песочнице
+ alembic/versions/20261029_0005_task_tags.py
+ alembic/versions/20261029_0006_task_versions.py
+ scripts/import_tasks.py                 — CLI импорта
+ tests/task_helpers.py                   — общие помощники тестов
+ tests/test_task_tags.py                 — 4 теста
+ tests/test_task_import.py               — 8 тестов
+ tests/test_seed_service.py              — 2 теста
+ tests/test_task_generation.py           — 5 тестов
+ tests/test_task_versions.py             — 4 теста
~ app/models/task.py                      — tags, TaskVersion
~ app/db/repositories/task.py             — фильтры, категории, версии
~ app/services/task_service.py            — теги, версии, create_many/export
~ app/schemas/task.py                     — tags, импорт/генерация/версии
~ app/api/v1/tasks.py                     — import/export/generate/categories/versions
~ app/config.py                           — SEED_ON_START
~ app/main.py                             — seed в lifespan
~ scripts/seed_tasks.py                   — использует общий сервис
~ requirements.txt                        — PyYAML
```

### Frontend
```
~ src/types/api.ts                        — tags в задачах
```

### Документы
```
~ docs/USER_GUIDE.md, ARCHITECTURE.md, SPEC.md, RULES.md,
  MANUAL_TESTING_GUIDE.md, GETTING_STARTED.md
~ docs/KNOWN_ISSUES.md                    — KI-010 Resolved
~ docs/RELEASES.md, CHANGELOG.md, README.md, docs/README.md, TODO_V0.2.md
+ docs/reports/sprint-14/SPRINT-14.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Backend тесты | 227 | **250** (+23; +1 skip на Windows) |
| Backend покрытие | 84% | **83%** (порог 70) |
| Frontend unit | 65 | 65 |

Новые тесты:

- `test_task_import.py` — 8: JSON/YAML, пустой/битый файл, created/skipped/errors,
  round-trip экспорта, YAML-выгрузка, права
- `test_seed_service.py` — 2: идемпотентность, существующий заголовок
- `test_task_generation.py` — 5: валидная задача, провал эталона, битый JSON,
  лимит count, права
- `test_task_tags.py` — 4: нормализация, фильтр/поиск, категории, выдача ученику
- `test_task_versions.py` — 4: снимок при правке, откат, права, 404

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest -q` | **250 passed, 1 skipped** за ~135 с |
| Покрытие | `pytest --cov=app` | **83%** |
| Ruff / MyPy | `ruff check app tests scripts`, `mypy app` | 0 / 0 |
| Миграции | `alembic upgrade head`, `alembic check` | 005–006, без расхождений |
| Frontend | `pnpm typecheck && lint && test && build` | 65 passed, 0/0 |
| Импорт CLI | smoke на тестовом файле | отчёт created/skipped/errors |

---

## 4. Smoke

1. **Импорт.** `import_tasks.py` с валидным YAML создаёт задачи; повторный
   запуск — `created=0`, `skipped=N`; битая запись — в `errors`, остальные
   импортируются.
2. **Экспорт.** `GET /tasks/export` отдаёт test_cases/tags; повторный импорт
   выгрузки не создаёт дублей; `format=yaml` — YAML с ключом `tasks`.
3. **Seed.** На чистой БД с `SEED_ON_START=true` появляется 6 задач; повторный
   старт не дублирует; ошибка seed не мешает приложению подняться.
4. **Генерация.** Валидный ответ LLM → задача сохранена; эталон не проходит
   тесты → только `rejected`; битый JSON → `rejected` без 500; `count=6` → 422.
5. **Теги/поиск.** `?tag=loops&q=сумма` фильтрует; `tags` приходят в списке и
   карточке; категории — отдельным эндпоинтом.
6. **Версии.** PATCH создаёт версию 1; повторный PATCH — версию 2; откат к 1
   возвращает тест-кейсы и сохраняет текущее состояние как версию 3.

---

## 5. Что не так

- **UI преподавателя отсутствует:** импорт/генерация/версии доступны через API
  и CLI; интерфейс — спринт 15.
- **Генерация без повторов:** если все задачи отклонены, повторного запроса к
  LLM нет (предсказуемость стоимости); преподаватель запускает ещё раз.
- **Дубликаты — по точному заголовку:** регистр/пробелы не нормализуются;
  при массовом импорте это осознанно, чтобы не склеить разные задачи.
- **YAML — новая зависимость** (`PyYAML`), добавлена в requirements.
- CI не стартовал (KI-014, биллинг); мерж по временному разрешению владельца.

---

## 6. Новые KI

Нет. **KI-010 закрыт** (Resolved): `SEED_ON_START` + общий seed-сервис.
Открыты: KI-013 (Monaco CDN), KI-014 (CI/биллинг).

---

## 7. Обоснование

- **Импорт через сервис, а не route handler.** Один и тот же код используют API
  и CLI; отчёт и правила валидации не дублируются.
- **Поштучная валидация.** Массовый импорт не должен падать целиком из-за одной
  записи; `errors` с индексом позволяют исправить файл точечно.
- **Seed в lifespan, а не в миграции.** Данные — не схема: их можно менять без
  Alembic, а `SEED_ON_START` управляет поведением в контейнере. Ошибка seed не
  валит приложение — иначе пустая/занятая БД блокирует старт.
- **Генерация с обязательным прогоном эталона.** LLM может вернуть
  правдоподобный, но неверный код; единственный надёжный фильтр — выполнить
  его в песочнице на всех кейсах. Невалидное не сохраняется.
- **Один LLM-вызов на запрос.** Ретраи внутри генерации умножают стоимость и
  непредсказуемы; лучше вернуть отчёт и дать преподавателю решить.
- **Версии — полный снимок JSONB.** Восстановление не зависит от текущей схемы
  и не требует join; история небольшого объёма (правки задач редки).
- **Теги JSONB + GIN.** Не нужна отдельная таблица связей; `@>` по GIN-индексу
  закрывает фильтр, а нормализация в схеме гарантирует единый вид.
