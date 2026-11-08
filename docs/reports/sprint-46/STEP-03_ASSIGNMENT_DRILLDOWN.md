# Шаг 03 / спринт 46: drill-down по назначению

**Дата:** 2026-11-08
**Спринт:** 46 (v0.5.0 «Learning Experience & Teaching Workflow»)
**Задача:** S46-003 — аналитика одного назначения
**Статус:** реализовано

---

## 1. Что сделано

1. **`GET /classrooms/{id}/assignments/{assignment_id}/analytics`.**
   Аналитика назначения: `total_students`, `completed`, `in_progress`,
   `not_started`, `overdue`, `attempts_total`, распределение попыток
   (`attempts → students`), «проблемные» ученики и полный список учеников
   со статусом, числом попыток, временем завершения и флагом просрочки.
2. **Порог «проблемных».** Параметр `problem_threshold` (по умолчанию 3,
   0…100): ученик попадает в список, если сделал больше попыток, чем порог.
3. **Совпадение с матрицей прогресса.** Аналитика читает те же
   `UserTaskProgress`, что и `/classrooms/{id}/progress`; тест сверяет
   статусы и попытки по каждому ученику.
4. **Права.** Только владелец класса; чужой учитель и ученик получают 403.
   Несуществующее назначение (или назначение другого класса) — 404.
5. **UI.** Клик по названию назначения на странице класса открывает панель
   «Кто как справился»: сводка, распределение попыток, проблемные ученики и
   таблица учеников со ссылкой «Открыть работы».
6. **Переход к работам.** Ссылка ведёт на
   `/teacher/students?student=<id>&tab=works`; `TeacherStudentsPage` читает
   параметры и сразу открывает карточку ученика на вкладке «Работы».
7. **Тесты.** Backend — 5 (агрегаты и сверка с матрицей, свой порог, права,
   404, пустой класс). Frontend — 3 (панель, ссылка на работы, авто-открытие
   работ по query-параметрам).

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest tests/test_assignment_analytics.py` | **5 passed** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 99 файлов |
| Frontend unit | `pnpm vitest run src/test/classroom-analytics.test.tsx src/test/teacher-works.test.tsx` | **9 passed** |
| Frontend typecheck / lint | `pnpm typecheck`, `pnpm lint` | **0 / 0** |
| i18n | `node scripts/check-i18n.mjs` | **583 ключа, OK** |

---

## 3. Файлы

**Backend:**

- `backend/app/services/classroom_service.py` — `assignment_analytics` и
  dataclass-структуры.
- `backend/app/api/v1/classrooms.py` — endpoint аналитики.
- `backend/app/schemas/classroom.py` — `AssignmentAnalytics`,
  `AssignmentAnalyticsStudent`, `AssignmentAttemptBucket`.
- `backend/tests/test_assignment_analytics.py` — 5 тестов (новый файл).

**Frontend:**

- `frontend/src/pages/ClassroomDetailPage.tsx` — кликабельное назначение и
  панель drill-down.
- `frontend/src/pages/TeacherStudentsPage.tsx` — автопереход из query-строки.
- `frontend/src/types/api.ts` — типы аналитики.
- `frontend/src/test/classroom-analytics.test.tsx` — 2 теста (новый файл).
- `frontend/src/test/teacher-works.test.tsx` — тест автоперехода.
- `frontend/src/i18n/locales/ru.json`, `en.json` — `classrooms.analytics*`.

---

## 4. Проблемы и отклонения

- **Порог «проблемности» — параметр, а не константа.** Разным классам нужен
  разный порог; значение по умолчанию 3 сохраняет предсказуемость.
- **Проблемные считаются по числу попыток, без фильтра по статусу.**
  Ученик, решивший задачу с четвёртой попытки, тоже интересен учителю как
  «проблемный» — он вошёл в список.
- **Список учеников отдаётся целиком.** Пагинация здесь не нужна: это один
  класс, а матрица прогресса уже отдаёт все ячейки.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Считать аналитику из `UserTaskProgress` | **Да** | Те же данные, что в матрице: расхождений не будет. |
| Отдельный endpoint | **Да** | Drill-down нужен по клику, а не в общем прогрессе класса. |
| Ссылка на работы через query | **Да** | Не добавляет новый маршрут; страница учителя уже умеет открывать ученика. |
| Порог в ответе | **Да** | UI показывает, по какому правилу построен список. |

---

## 6. Что дальше

Шаг 04: управление назначениями — перенос срока и снятие с уведомлениями и
сохранением прогресса.
