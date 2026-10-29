# Sprint 15: Teacher Console — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён

---

## 1. Файлы (+/-)

### Backend
```
+ app/api/v1/teacher.py                  — /teacher: задачи, ученики, прогресс
+ app/schemas/teacher.py                 — схемы кабинета
+ tests/test_teacher.py                  — 6 тестов
~ app/main.py                           — роутер teacher
~ app/api/v1/tasks.py                    — import/preview и import/file
~ app/services/task_import.py            — preview_import
~ app/schemas/task.py                    — TaskImportPreview/Content
```

### Frontend
```
+ components/TeacherRoute.tsx            — доступ teacher/admin
+ components/teacher/TaskForm.tsx        — форма с конструктором кейсов
+ components/teacher/taskFormTypes.ts    — типы формы (без react-refresh warning)
+ pages/TeacherTasksPage.tsx             — таблица, CRUD, импорт
+ pages/TeacherStudentsPage.tsx          — ученики и прогресс
+ test/teacher.test.tsx                  — 6 тестов
~ lib/api.ts                             — postFile (multipart)
~ App.tsx                                — маршруты /teacher/*
~ layout/AppLayout.tsx                   — ссылка «Кабинет»
~ types/api.ts                           — типы Teacher API
~ i18n locales                           — раздел teacher
```

### Документы
```
~ USER_GUIDE, SPEC, ARCHITECTURE, RULES, MANUAL_TESTING_GUIDE
~ README, docs/README, TODO_V0.2, RELEASES, CHANGELOG
+ docs/reports/sprint-15/SPRINT-15.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Backend тесты | 250 | **256** (+6) |
| Frontend unit | 65 | **71** (+6) |
| Backend покрытие | 83% | **82%** |

Новые тесты:

- backend: список учеников с агрегатами, прогресс, неактивные задачи,
  403 ученику, 404, предпросмотр+файл импорта
- frontend: TeacherRoute (teacher/admin/student), TaskForm (добавление/удаление
  кейса, валидация, отправка), загрузка задач и открытие формы

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend | `pytest -q` | **256 passed, 1 skipped** |
| Ruff / MyPy | `ruff check`, `mypy app` | 0 / 0 |
| Frontend | `pnpm typecheck && lint && test && build` | 71 passed, 0/0 |
| Alembic | `alembic check` | без расхождений |

---

## 4. Smoke

1. Учитель открывает `/teacher/tasks`: таблица задач, включая неактивные.
2. «Новая задача»: заполнение полей и 2 кейсов → POST `/tasks`, задача в таблице.
3. «Изменить»: PATCH, затем `/tasks/{id}/versions` содержит снимок.
4. Импорт: выбор файла → preview (валидные/ошибки) → подтверждение → отчёт
   `created/skipped/errors`, задачи в каталоге.
5. `/teacher/students`: агрегаты; клик по ученику — прогресс по задачам.
6. Ученик открывает `/teacher/tasks` → «Доступ только для преподавателя»;
   API `/teacher/*` → 403.

---

## 5. Что не так

- Предпросмотр эталона в форме (кнопка «прогнать») не сделан: проверка
  эталонного решения выполняется при LLM-генерации (S14-003), в ручной форме
  её нет.
- Список учеников не пагинирован в UI (backend поддерживает `skip/limit`).
- Импорт в UI читает файл целиком в память; ограничение 2 МБ на preview.

---

## 6. Новые KI

Нет.

---

## 7. Обоснование

- **Отдельный `/teacher` API, а не переиспользование `/admin`.** Учитель не
  должен получать доступ к пользователям/ролям; отдельные схемы и роль
  `teacher/admin` минимизируют права.
- **Агрегаты одним запросом.** `outerjoin` + `count(filter(...))`/`sum` в SQL
  вместо N+1 по ученикам.
- **Импорт через preview + upload.** Предпросмотр показывает ошибки до записи
  в БД, а загрузка файла не требует парсить YAML в браузере.
- **Форма отдельным компонентом.** `TaskForm` тестируется без страницы;
  типы вынесены из `.tsx`, чтобы не нарушать react-refresh.
- **`TeacherRoute` по образцу `AdminRoute`.** Единый паттерн защиты маршрутов.
