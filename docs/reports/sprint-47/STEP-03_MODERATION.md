# Шаг 03 / спринт 47: модерация задач

**Дата:** 2026-11-10
**Спринт:** 47 (v0.5.0 «Learning Experience & Teaching Workflow»)
**Задача:** S47-003 — модерация задач (только LLM-генерация и импорт)
**Статус:** реализовано

---

## 1. Что сделано

1. **Спайк метрик «застревания».** Добавлен воспроизводимый SQL
   `backend/scripts/task_moderation_metrics.sql`: очередь из
   `generated|imported`, агрегаты по `task_attempts` и
   `user_task_progress`, сортировка «сначала проблемные». Метрики:
   `attempts`, `passed_attempts`, `success_rate`, `avg_attempts`, `students`,
   `stuck_students` (попыток больше порога и задача не завершена).
   - Корректность проверена на детерминированном наборе: 3 ученика, 11
     попыток, 3 успешных, 2 застрявших → `0.2727 / 3.67 / 3 / 2`; ручная
     задача с 15 попытками в выдачу не попала.
   - Скорость: на 1 006 задачах очереди, 200 000 попыток и 200 000 строк
     прогресса — ~290 мс (PostgreSQL 17, локальный контейнер). На 1 000 000
     попыток — ~300 мс. Вариант с `LATERAL` на тот же набор дал ~2 000 мс,
     поэтому выбран CTE-агрегат.
2. **Проверка `ChatMessage.message_metadata`.** `task_context.task_id`
   действительно сохраняется: `app/services/llm/task_context.py` →
   `task_context_metadata()`, оба пути (REST и WebSocket) вызывают его в
   `chat_service`. Тесты `test_chat.py::test_task_context_in_metadata_not_content`
   и `::test_task_context_not_leaked_into_history` подтверждают запись
   `metadata = {"task_context": {"task_id": ..., "title": ...}}`. Для S47-004
   этого достаточно; менять контракт не потребовалось.
3. **Миграция `022` (additive).** `tasks.source` —
   `VARCHAR(20) NOT NULL DEFAULT 'manual'`, `tasks.moderation_comment` —
   `TEXT NULL`, индекс `idx_tasks_source_created(source, created_at)`.
   Существующие задачи получают `manual`; downgrade удаляет индекс и обе
   колонки. Тест миграции проверяет upgrade → вставку «старой» задачи →
   upgrade head → `source='manual'` → downgrade → повторный upgrade.
4. **Проставление `source`.** `TaskService.create_task` → `manual`,
   `TaskService.create_many` (LLM-генерация) → `generated`,
   `task_import.import_tasks` → `imported`. Seed и прямые вставки без поля
   получают `manual` через default модели/БД.
5. **`GET /admin/tasks/review`.** Только `generated|imported`; фильтры
   `source`, `difficulty`, `threshold` (1…20, default 3), `skip`, `limit`;
   сортировка по `stuck_students` ↓, `success_rate` ↑, `attempts` ↓,
   `created_at` ↓. В ответе — метрики и последние 5 попыток на задачу
   (один запрос на страницу, без N+1).
6. **`POST /admin/tasks/{id}/moderate`.** `publish` → `is_active=true` и
   очистка комментария; `unpublish` → `is_active=false`; `return_to_revision`
   → обязательный комментарий 1…1000 символов, `is_active=false`,
   сохранение в `moderation_comment`. Для `manual` разрешён только
   `unpublish` (остальное — 422). Аудит `task.moderated` содержит `action`
   и, для возврата, `comment_length`; текст комментария не пишется. Действия
   инвалидируют кэш каталога.
7. **UI `/admin/moderation`.** Очередь с фильтрами источника, сложности и
   порога; карточка выбранной задачи с описанием, метриками, последними
   попытками и кнопками «Опубликовать», «Снять с публикации», «Вернуть в
   доработку». Возврат — модалка с комментарием, счётчиком символов и
   валидацией. Добавлены ссылка в навигацию администратора, route-level
   lazy-чанк и i18n ru/en.
8. **Тесты.** Backend: `tests/test_moderation.py` — 11 тестов (очередь,
   метрики, фильтры, publish/unpublish/return, валидация, права, каталог
   ученика, `source='manual'` при создании). Дополнены тесты генерации и
   импорта проверкой `source`. Миграция — отдельный тест. Frontend:
   `admin-moderation.test.tsx` — 4 теста.
9. **Документация.** `docs/SPEC.md` (контракты, схема БД, миграция 022),
   `docs/CHANGELOG.md`, `TODO_V0.5.md`, этот отчёт. OpenAPI-снапшот
   перегенерирован: проверка «старый снапшот → текущая схема» дала 0
   breaking-изменений, +16 путей (2 из S47-003, остальные — ранее
   добавленные маршруты S45/S46, не попадавшие в снапшот).

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff (изменённые файлы) | `ruff check app tests` | **0** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 100 файлов |
| Backend, профильные тесты | `pytest tests/test_moderation.py tests/test_task_generation.py tests/test_task_import.py` | **24 passed** |
| Backend, регрессия | `pytest tests/test_contract_openapi.py tests/test_admin.py tests/test_tasks.py tests/test_chat.py tests/test_moderation.py tests/test_task_generation.py tests/test_task_import.py tests/test_migrations.py` | **135 passed** |
| Backend, полный прогон | `pytest -q` | **717 passed, 1 skipped** (545.94 с) |
| Миграции | `pytest tests/test_migrations.py` | **5 passed** |
| Alembic upgrade | `alembic upgrade head` | **022 applied** |
| Alembic check (чистая БД) | `alembic upgrade head && alembic check` на scratch-БД | **No new upgrade operations detected** |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend tests (полный) | `pnpm test` | **265 passed** (45 файлов) |
| Frontend build | `pnpm build` | **успешно**, entry 69.84 kB gzip |
| i18n | `node scripts/check-i18n.mjs` | **687 ключей, OK** |
| Спайк SQL | `psql -v threshold=3 -v limit=50 -f scripts/task_moderation_metrics.sql` | **11 / 0.2727 / 3.67 / 3 / 2**; manual отсутствует |

---

## 3. Файлы

**Backend:**

- `backend/app/models/task.py` — `TaskSource`, `source`, `moderation_comment`,
  индекс `idx_tasks_source_created`.
- `backend/app/models/__init__.py` — экспорт `TaskSource`.
- `backend/alembic/versions/20261110_0022_task_moderation.py` — миграция 022.
- `backend/app/schemas/admin.py` — схемы очереди, метрик и действий.
- `backend/app/services/moderation_service.py` — очередь, метрики, действия.
- `backend/app/services/task_service.py` — `source` в `create_task`/`create_many`.
- `backend/app/services/task_import.py` — `source='imported'`.
- `backend/app/api/v1/admin.py` — `GET /admin/tasks/review`,
  `POST /admin/tasks/{id}/moderate`, аудит.
- `backend/scripts/task_moderation_metrics.sql` — SQL спайка.
- `backend/tests/test_moderation.py` — 11 тестов.
- `backend/tests/test_migrations.py` — тест 022.
- `backend/tests/test_task_generation.py`, `test_task_import.py` — проверки
  `source`.
- `backend/tests/contracts/openapi.json` — снапшот OpenAPI.

**Frontend:**

- `frontend/src/pages/AdminModerationPage.tsx` — страница модерации.
- `frontend/src/App.tsx` — маршрут `/admin/moderation`.
- `frontend/src/components/layout/AppLayout.tsx` — ссылка в навигации.
- `frontend/src/types/api.ts` — типы очереди и действий.
- `frontend/src/i18n/locales/ru.json`, `en.json` — ключи модерации.
- `frontend/src/test/admin-moderation.test.tsx` — 4 теста.

**Документация:**

- `docs/SPEC.md`, `docs/CHANGELOG.md`, `TODO_V0.5.md`,
  `docs/README.md` (размер entry после сборки),
  `docs/reports/sprint-47/STEP-03_MODERATION.md`.

---

## 4. Проблемы и отклонения

- **Определение «застревания».** Считаются ученики с `attempts > threshold`
  и незавершённой задачей (`status != completed`). Ученик, который решил
  задачу с 5-й попытки, застрявшим не считается — иначе метрика наказывала
  бы за трудную, но решённую задачу.
- **Доля успешных — на уровне попыток, а не учеников.** `success_rate =
  passed_attempts / attempts`. Это отвечает на вопрос «какая доля отправок
  проходит тесты», а не «какая доля учеников справилась»; последнее видно по
  `students` и `stuck_students`.
- **`manual` и действия.** Публикация и возврат в доработку для ручных задач
  запрещены (422): они не входят в область модерации по D-002/D-003.
  Снятие с публикации разрешено для любой задачи, как требует постановка.
  Вернуть ручную задачу в каталог можно обычной правкой задачи учителем.
- **E2E-сценарий не добавлялся.** Шаг закрыт интеграционными тестами API и
  unit-тестами страницы; сквозной сценарий админки остаётся на уровень
  спринта (S47-004/005 и sprint-level e2e).
- **Снапшот OpenAPI был устаревшим.** В нём не было маршрутов S45/S46
  (экспорт данных, сессии, работы ученика, объявления). Перегенерация
  добавила их вместе с S47-003; `diff_openapi(old, current)` — 0 problems,
  то есть изменение только аддитивное.
- **`alembic check` на локальной dev-БД** показывает исторический дрейф
  индексов 0009 (следствие правки уже применённой миграции), не связанный с
  022. На чистой БД, поднятой с нуля, `alembic check` зелёный; это и
  зафиксировано в проверках.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| CTE-агрегат против `LATERAL` по каждой задаче | **CTE** | На 1 006 задачах и 200 000 попыток CTE ~290 мс, `LATERAL` ~2 000 мс: коррелированные подзапросы дают по bitmap-heap scan на задачу. |
| Сортировка по «проблемности» | **stuck ↓, success ↑, attempts ↓** | Сначала задачи, где больше всего учеников не могут пройти; при равенстве — где ниже доля успеха и больше попыток. |
| `source` — `VARCHAR` + enum-константы | **Да** | Постановка требует строку; enum в БД усложнил бы additive-миграцию и сравнения. Значения закрыты `TaskSource` и `Literal` в API. |
| Отдельная страница `/admin/moderation` | **Да** | Очередь — самостоятельный рабочий экран с фильтрами и карточкой; админ-дашборд не разрастается. |
| Комментарий хранится в `tasks.moderation_comment` | **Да** | Комментарий относится к текущему состоянию задачи; история изменений и так фиксируется в аудите. |
| Аудит без текста комментария | **Да** | Текст — обратная связь автору, а не PII-сводка; в журнал пишем действие и длину (RULES §7.2). |

---

## 6. Что дальше

Шаг 04 (S47-004): сводка качества LLM. `task_context.task_id` из
`message_metadata` уже подтверждён — можно связывать негативные оценки
ответов с задачами и строить топ проблемных тем. После S47-004/005 — общий
e2e админки и отчёт спринта 47.
