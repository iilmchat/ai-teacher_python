# Шаг 02 / спринт 46: комментарий учителя к попытке

**Дата:** 2026-11-08
**Спринт:** 46 (v0.5.0 «Learning Experience & Teaching Workflow»)
**Задача:** S46-002 — комментарий к попытке и уведомление ученику
**Статус:** реализовано

---

## 1. Что сделано

1. **Модель `AttemptFeedback`** (`backend/app/models/task.py`): один
   комментарий учителя на попытку. Уникальная пара (`attempt_id`,
   `teacher_id`), поэтому повторная отправка обновляет текст, а не создаёт
   дубль. Удаляется каскадом вместе с попыткой.
2. **Миграция `020`** (`20261108_0020_attempt_feedback.py`): аддитивная
   таблица `attempt_feedback` с индексами и внешними ключами.
3. **`POST /teacher/attempts/{attempt_id}/feedback`.** Учитель оставляет
   комментарий (1…2000 символов). Доступ — тот же, что к работам ученика:
   владелец класса или администратор. Действие пишется в аудит
   (`attempt.feedback_added`, длина комментария без текста).
4. **Уведомление ученику.** `create_feedback_notification` создаёт
   `Notification(type="attempt_feedback")` с payload `{attempt_id, task_id,
   title, teacher}`. Ученик видит его на дашборде как «Учитель … оставил
   комментарий к работе …».
5. **Ученический API.** `GET /tasks/{id}/attempts` и деталь попытки отдают
   `feedback: list[{id, comment, teacher_name, created_at}]`; история
   загружается одним запросом на страницу (без N+1).
6. **Teacher API.** Детальная работа содержит `feedback` — учитель видит
   комментарии коллег и свой.
7. **UI.** В карточке работы появилась форма комментария и список уже
   оставленных; ученик видит комментарии прямо в истории попыток на
   странице задачи.
8. **Тесты.** Backend — 6 новых (видимость ученику, уведомление, 422,
   upsert, права/404, аудит), всего 12 в файле. Frontend — 3 новых
   (показ комментария учителю и ученику, отправка).

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest tests/test_teacher_work.py` | **12 passed** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 99 файлов |
| Frontend unit | `pnpm vitest run src/test/teacher-works.test.tsx src/test/task-detail.test.tsx` | **11 passed** |
| Frontend typecheck / lint | `pnpm typecheck`, `pnpm lint` | **0 / 0** |
| i18n | `node scripts/check-i18n.mjs` | **567 ключей, OK** |

---

## 3. Файлы

**Backend:**

- `backend/app/models/task.py` — `AttemptFeedback`, экспорт в `models/__init__.py`.
- `backend/alembic/versions/20261108_0020_attempt_feedback.py` — миграция 020.
- `backend/app/services/teacher_service.py` — `list_feedback`, `add_feedback`.
- `backend/app/services/task_service.py` — `_feedback_map`, `feedback` в истории.
- `backend/app/services/engagement_service.py` — `create_feedback_notification`.
- `backend/app/api/v1/teacher.py` — POST комментария, `feedback` в детали.
- `backend/app/schemas/task.py`, `teacher.py` — `AttemptFeedbackItem`,
  `AttemptFeedbackCreate`.
- `backend/tests/test_teacher_work.py` — 6 тестов S46-002.

**Frontend:**

- `frontend/src/pages/TeacherStudentsPage.tsx` — форма и список комментариев.
- `frontend/src/pages/TaskDetailPage.tsx` — комментарии в истории попыток.
- `frontend/src/pages/DashboardPage.tsx` — текст уведомления.
- `frontend/src/types/api.ts` — `AttemptFeedbackItem`, `feedback`.
- `frontend/src/test/teacher-works.test.tsx`, `task-detail.test.tsx` — тесты.
- `frontend/src/i18n/locales/ru.json`, `en.json` — ключи комментариев.

---

## 4. Проблемы и отклонения

- **Один комментарий на пару «попытка — учитель».** Обсуждение в ветке не
  поддерживается: для разбора достаточно одного актуального комментария,
  а история изменений остаётся в аудите.
- **`updated_at` нет.** Комментарий — короткая заметка; дата создания
  сохраняется, повторная отправка не меняет её. Это осознанно: сортировка
  комментариев остаётся стабильной.
- **Уведомление уходит и при обновлении.** Ученик должен узнать, что
  учитель уточнил замечание; подавление повторных уведомлений усложнило бы
  логику без пользы.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Отдельная таблица `attempt_feedback` | **Да** | Комментариев может быть несколько (разные учителя), и они не должны перезаписывать попытку. |
| Upsert по (`attempt_id`, `teacher_id`) | **Да** | Учитель исправляет формулировку одной кнопкой, без удаления. |
| Комментарии в списке попыток | **Да, батчем** | Ученик видит разбор сразу; один запрос на страницу. |
| Аудит без текста комментария | **Да** | Текст — персональная обратная связь, в журнал пишем только факт и длину. |

---

## 6. Что дальше

Шаг 03: drill-down по назначению — переход из журнала/прогресса к работам
конкретной задачи и ученика.
