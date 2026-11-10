# Шаг 04 / спринт 47: сводка качества LLM

**Дата:** 2026-11-10
**Спринт:** 47 (v0.5.0 «Learning Experience & Teaching Workflow»)
**Задача:** S47-004 — сводка качества LLM и выгрузка негативных оценок
**Статус:** реализовано

---

## 1. Что сделано

1. **`by_level` в `FeedbackService.quality_summary`.** Добавлен join
   `message_feedback → chat_messages → chat_sessions` и группировка по
   уровню. Уровень берётся из сессии (в `message_metadata` его нет):
   `COALESCE(NULLIF(LOWER(TRIM(level)), ''), 'unknown')`. Пустая/пробельная
   строка у старых сессий попадает в `unknown`. Формат среза — как у
   `by_provider`/`by_model`: `{name, total, positive, negative, approval_rate}`.
2. **`top_problem_topics`.** Негативные оценки агрегируются по
   `tasks.category` и `tasks.tags`; для тегов используется
   `jsonb_array_elements_text` через `LATERAL`. Возвращается до 10 тем:
   `{kind: category|tag|none, name, negative}`.
3. **Связка с задачей.** `task_context.task_id` хранится в метаданных
   **вопроса ученика** (S42-006), а оценка привязана к **ответу** ассистента.
   Поэтому контекст ищется в ближайшем предыдущем сообщении ученика той же
   сессии (LATERAL по `created_at`). Это работает и для оценок, созданных до
   S47-004. Нет контекста или задача удалена — `kind="none"`,
   `name="без задачи"` (D-003).
4. **`GET /admin/quality/export?format=csv|json`.** Потоковая выгрузка
   негативных оценок через серверный курсор (`db.stream`), без загрузки
   таблицы в память. Поля: `message_id`, `comment`, `provider`, `model`,
   `level`, `task_id` (или `без задачи`), `created_at`. Лимит —
   `EXPORT_MAX_ROWS`, заголовок `X-Export-Limit`, ответ — вложение
   `quality-negative-<дата>.<format>`. Аудит `quality.exported` пишет
   `format` и `limit`, без текста комментария (D-008).
5. **Схемы и API.** `AdminQualityResponse` дополнен `by_level` и
   `top_problem_topics`; добавлена `QualityTopic`. Роут экспорта — в
   `api/v1/admin.py`; набор `negative_feedback` добавлен в `export_service`.
   Попутно исправлена сериализация экспорта: даты теперь ISO, enum-значения —
   их значениями (раньше результат перезаписывался исходным объектом).
6. **UI.** На странице `AdminPage` в карточке качества:
   - таблица `by_level` (уровень, всего, положительные, отрицательные, доля);
   - таблица топ-тем (тип, тема, число негативных);
   - выбор формата CSV/JSON и кнопка «Скачать негативные оценки» через
     `api.download` + `saveBlob`.
   Уровень `unknown` и группа «без задачи» локализованы.
7. **Тесты.** Backend: `tests/test_quality.py` — 8 тестов (by_level с
   fallback, топ категорий/тегов, связка через `task_context`, «без задачи»,
   CSV/JSON, лимит, аудит, права). Дополнительно прогнаны `test_feedback.py`
   и `test_export_retention.py`. Frontend: 2 новых теста в
   `admin-quality.test.tsx` (срезы и скачивание) — всего 5.
8. **Документация.** `docs/SPEC.md`, `docs/CHANGELOG.md`, `TODO_V0.5.md`,
   этот отчёт, `docs/README.md` (размер entry), OpenAPI-снапшот.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `ruff check app tests` | **0** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 101 файл |
| Backend, новые тесты | `pytest tests/test_quality.py` | **8 passed** |
| Backend, профильные | `pytest tests/test_quality.py tests/test_feedback.py tests/test_export_retention.py` | **31 passed** |
| Backend, полный прогон | `pytest -q` | **725 passed, 1 skipped** (636.55 с) |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend tests | `pnpm test` | **267 passed** (45 файлов) |
| Frontend build | `pnpm build` | **успешно**, entry 69.84 kB gzip |
| i18n | `node scripts/check-i18n.mjs` | **701 ключ, ru/en паритет** |
| OpenAPI | `pytest tests/test_contract_openapi.py` | **12 passed** |

---

## 3. Файлы

**Backend:**

- `backend/app/services/quality_queries.py` — общие SQL-выражения:
  `level_column`, `negative_contexts_cte` (поиск контекста в предыдущем
  вопросе).
- `backend/app/services/feedback_service.py` — `by_level`,
  `top_problem_topics`.
- `backend/app/services/export_service.py` — набор `negative_feedback`,
  исправление `_serialize`.
- `backend/app/schemas/admin.py` — `QualityTopic`, поля
  `AdminQualityResponse`.
- `backend/app/api/v1/admin.py` — `GET /admin/quality/export`, аудит.
- `backend/tests/test_quality.py` — 8 тестов.
- `backend/tests/test_sandbox_batch_security.py` — стабилизация
  `test_sandbox_recovers_after_timeout` (холодный старт >1 с на Windows).
- `backend/tests/contracts/openapi.json` — снапшот OpenAPI.

**Frontend:**

- `frontend/src/pages/AdminPage.tsx` — таблицы уровней и тем, экспорт.
- `frontend/src/types/api.ts` — `QualityTopic`, новые поля сводки.
- `frontend/src/i18n/locales/ru.json`, `en.json` — ключи S47-004.
- `frontend/src/test/admin-quality.test.tsx` — 2 новых теста.

**Документация:**

- `docs/SPEC.md`, `docs/CHANGELOG.md`, `TODO_V0.5.md`, `docs/README.md`,
  `docs/reports/sprint-47/STEP-04_QUALITY.md`.

---

## 4. Проблемы и отклонения

- **Контекст задачи лежит не на том сообщении, к которому привязана оценка.**
  Литеральное `message_feedback → chat_messages.message_metadata` дало бы
  «без задачи» для всех оценок: `task_context` пишется в метаданные вопроса
  (S42-006), а feedback — на ответ. Реализован поиск ближайшего предыдущего
  вопроса в сессии; это сохраняет контракт S42-006 и работает для старых
  данных.
- **Группа «без задачи» — `kind="none"`.** В API `name="без задачи"` для
  машинной однозначности, в UI показывается локализованная подпись; тип
  отделён от `category`, чтобы не дублировать счётчик.
- **Топ тем ограничен 10.** Это «топ», а не полный список; при необходимости
  лимит меняется одной константой.
- **Полный backend-прогон.** Первый прогон упал на существующем flaky-тесте
  песочницы: холодный старт интерпретатора на Windows занимал больше 1 с.
  Тест стабилизирован (проверяется восстановление, а не скорость старта);
  повторные прогоны — зелёные.
- **Миграции нет.** S47-004 не меняет схему БД; Alembic не затрагивался.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Контекст задачи искать в предыдущем вопросе | **Да** | Оценка привязана к ответу, а `task_context` хранится на вопросе (S42-006); прямой join давал бы пустую связку. |
| `by_level` — join к `chat_sessions` | **Да** | Уровень — свойство сессии; в метаданных сообщения его нет. |
| Топ тем — SQL-агрегация, а не Python | **Да** | Негативных оценок может быть много; `jsonb_array_elements_text` и `GROUP BY` считают на стороне БД. |
| Выгрузка — новый dataset в `export_service` | **Да** | Переиспользует серверный курсор, лимит и формат CSV/JSON; не дублирует потоковую логику. |
| UI — блок в существующей карточке качества | **Да** | Сводка качества уже живёт на `AdminPage`; отдельная страница не нужна. |
| `QualityTopic.kind` | **Да** | UI различает категорию, тег и «без задачи» без парсинга строки. |

---

## 6. Что дальше

Шаг 05 (S47-005): центр уведомлений и бейдж непрочитанного. После него —
общий e2e админки, отчёт спринта 47 и релиз v0.5.0 (спринт 48).
