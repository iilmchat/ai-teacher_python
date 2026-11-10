# Спринт 47 — Admin Console v2

**Дата:** 2026-11-10
**Этап:** v0.5.0 «Learning Experience & Teaching Workflow»
**Задачи:** S47-001…S47-005
**Статус:** завершён

---

## 1. Файлы (+/-)

**Backend:**

- `backend/app/api/v1/admin.py` — очередь модерации, действия модератора,
  выгрузка качества.
- `backend/app/api/v1/engagement.py` — `read-all`, фильтр `type`.
- `backend/app/schemas/admin.py` — `ModerationMetrics`, `AdminTaskReviewItem`,
  `TaskModerateRequest/Response`, `QualityTopic`, `by_level`,
  `top_problem_topics`.
- `backend/app/schemas/engagement.py` — `NotificationsReadAllResponse`.
- `backend/app/services/moderation_service.py` — очередь и действия модератора.
- `backend/app/services/quality_queries.py` — связка оценки с `task_context`
  через предыдущий вопрос.
- `backend/app/services/feedback_service.py` — `by_level`,
  `top_problem_topics`.
- `backend/app/services/engagement_service.py` — `mark_all_read`, фильтр
  `type`, безопасные `link`/`task_id`.
- `backend/app/services/export_service.py` — dataset `negative_feedback`,
  корректная сериализация дат/enum.
- `backend/app/services/task_service.py`, `task_import.py` — `source`.
- `backend/app/services/classroom_service.py` — `task_id` в уведомлениях.
- `backend/alembic/versions/20261110_0022_task_moderation.py` — миграция 022.
- `backend/scripts/task_moderation_metrics.sql` — SQL спайка.
- `backend/scripts/seed_e2e.py` — админ для e2e.
- `backend/tests/test_moderation.py`, `test_quality.py`,
  `test_notifications.py`; дополнены `test_task_generation.py`,
  `test_task_import.py`, `test_migrations.py`, `test_engagement.py`,
  `test_sandbox_batch_security.py`.
- `backend/tests/contracts/openapi.json` — снапшот.

**Frontend:**

- `frontend/src/pages/AdminModerationPage.tsx` — очередь модерации.
- `frontend/src/pages/AdminAuditPage.tsx` — журнал аудита.
- `frontend/src/pages/NotificationsPage.tsx` — центр уведомлений.
- `frontend/src/store/notifications.ts` — общий стейт и бейдж.
- `frontend/src/lib/notifications.ts` — безопасные ссылки и fallback.
- `frontend/src/pages/AdminPage.tsx` — сводка качества, выгрузка аналитики.
- `frontend/src/pages/DashboardPage.tsx` — общий стейт уведомлений.
- `frontend/src/components/layout/AppLayout.tsx` — навигация и бейдж.
- `frontend/src/App.tsx`, `types/api.ts`, `i18n/locales/ru.json`,
  `en.json`.
- `frontend/src/test/admin-moderation.test.tsx`, `admin-quality.test.tsx`,
  `notifications.test.tsx`, `dashboard.test.tsx`.
- `frontend/e2e/sprint47-admin.spec.ts` — e2e админки.

**Документация:**

- `docs/SPEC.md`, `docs/CHANGELOG.md`, `TODO_V0.5.md`, `docs/README.md`.
- `docs/reports/sprint-47/STEP-03_MODERATION.md`,
  `STEP-04_QUALITY.md`, `STEP-05_NOTIFICATIONS.md`, этот отчёт.

---

## 2. Покрытие

- **S47-001 (аудит):** экран `/admin/audit` с фильтрами по действию и типу
  сущности, пагинацией, ссылками на задачу/класс; e2e-проверка записи
  `task.created`.
- **S47-002 (выгрузка):** блок выгрузки аналитики на `/admin` (набор
  `users|tasks|attempts|activity`, CSV/JSON), скачивание через `api.download`;
  e2e проверяет файл `analytics-users-YYYY-MM-DD.csv`.
- **S47-003 (модерация):** миграция `022` (`source`, `moderation_comment`),
  очередь только `generated|imported`, метрики застревания, `publish`/
  `unpublish`/`return_to_revision`, аудит `task.moderated`, UI `/admin/moderation`.
- **S47-004 (качество LLM):** `by_level`, `top_problem_topics`, потоковая
  выгрузка негативных оценок с лимитом и аудитом `quality.exported`.
- **S47-005 (уведомления):** `read-all`, фильтр `type`, безопасные `link`/
  `task_id`, страница `/notifications`, бейдж через общий Zustand-стор.
- **E2E:** `frontend/e2e/sprint47-admin.spec.ts` — админ создаёт задачу
  (аудит), импортирует задачу, видит аудит, скачивает аналитику и снимает
  задачу с публикации.

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| **Build** | **0 ошибок**; frontend entry **70.57 kB gzip** (лимит 80) |
| **Backend tests** | **728 passed, 1 skipped** (`pytest -q`) |
| **Frontend tests** | **274 passed**, 46 файлов |
| **E2E** | **1 passed** (`sprint47-admin.spec.ts`) |
| Ruff | **0** |
| MyPy strict | **0**, 101 файл |
| Frontend typecheck / lint | **0 / 0** |
| i18n | **747 ключей**, ru/en паритет |
| Alembic | миграция `022` upgrade/downgrade; `alembic check` на чистой БД — зелёный |

---

## 4. Smoke

Ручной сценарий (и e2e):

1. Войти администратором (`e2e_admin` в e2e-БД).
2. Открыть `/admin/audit` — видна запись `task.created`, работают фильтры и
   пагинация.
3. На `/admin` выбрать набор `users`, формат `csv`, нажать «Скачать
   аналитику» — скачивается файл.
4. Открыть `/admin/moderation`, выбрать импортированную задачу, нажать
   «Снять с публикации» — задача уходит из каталога, появляется уведомление
   об успехе.
5. Ученик открывает `/notifications`, фильтрует по типу, переходит по ссылке,
   нажимает «Прочитать все»; бейдж в шапке обнуляется.

---

## 5. Что не так

- S47-001/S47-002 приняты владельцем; в этом проходе добавлены экран аудита,
  выгрузка аналитики и e2e-проверка пути «аудит → выгрузка → модерация».
- Бейдж уведомлений обновляется после read/read-all и при загрузке страницы;
  отдельного WebSocket/polling-пуша новых уведомлений нет.
- Ссылки уведомлений валидируются на клиенте; сервер хранит относительный
  `link`, но не проверяет его повторно — контракт D-007 закрыт на UI-слое.
- `alembic check` на локальной dev-БД показывает исторический дрейф индексов
  0009 (известный артефакт); на чистой БД проверка зелёная.

---

## 6. Новые KI

Нет. Все выявленные ограничения либо закрыты в спринте, либо уже
зафиксированы в существующих KI/бэклоге v0.6.0.

---

## 7. Обоснование

- **Модерация только LLM/импорта** (D-002/D-003): ручные задачи публикуются
  сразу; очередь и метрики не смешивают источники.
- **Связка качества с задачей** идёт через предыдущий вопрос, потому что
  `task_context` хранится на вопросе, а оценка — на ответе; прямой join давал
  бы «без задачи».
- **Экспорт — серверный курсор**: `EXPORT_MAX_ROWS` защищает API и БД,
  формат CSV/JSON переиспользует `export_service`.
- **Уведомления — общий Zustand-стор**: бейдж, дашборд и страница не
  расходятся после read/read-all.
- **Безопасные ссылки**: разрешены только внутренние пути; небезопасный
  `link` игнорируется, fallback — только для старых уведомлений без ссылки.
- **E2E на реальном UI**: аудит, выгрузка и модерация проверяются в одном
  сценарии, а не только unit-тестами.
