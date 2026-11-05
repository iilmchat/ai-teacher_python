# Шаг 02 / спринт 42: история попыток ученика

**Дата:** 2026-11-05  
**Спринт:** 42 (v0.5.0 «Learning Experience & Teaching Workflow»)  
**Задача:** S42-002 — история попыток ученика по задаче  
**Статус:** реализовано

---

## 1. Что сделано

1. **Таблица `task_attempts`** (миграция `014`, additive). Хранит каждую
   засчитанную отправку: код, результат по каждому тест-кейсу
   (`results` JSONB), счётчики пройденных тестов, время. Индексы
   `(user_id, task_id, created_at)` и `(task_id, created_at)` — подбор
   истории и разбор по задаче. `user_task_progress` остаётся сводкой
   (статус и счётчик попыток): история и сводка не дублируют друг друга.
2. **Запись истории при отправке.** `TaskService.submit_solution()` создаёт
   запись `TaskAttempt` в той же транзакции, что и обновление прогресса.
   Пробная проверка (S42-001) попытку не засчитывает — и в историю не
   пишется: это осознанное поведение, а не пропуск.
3. **API.** `GET /tasks/{id}/attempts` — постраничный список попыток
   текущего ученика (новые сверху, `skip`/`limit`); `GET
   /tasks/{id}/attempts/{attempt_id}` — детальная попытка с кодом и разбором
   по кейсам. Попытка принадлежит ученику: чужая недоступна (404) — по
   идентификатору нельзя проверить существование чужой записи.
4. **Retention.** Таблица включена в политику S26:
   `RETENTION_TASK_ATTEMPTS_DAYS` (по умолчанию 90, `0` — не удалять).
   В `docs/PRIVACY.md` добавлена строка о новых персональных данных.
5. **UI.** На странице задачи — блок «История попыток»: дата, результат,
   кнопка «Подробнее» (код попытки и разбор по кейсам) и «Вернуть код в
   редактор» — вернуть решение в редактор, чтобы продолжить с него.
   После отправки список перечитывается, новая попытка видна сразу.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `ruff check app tests scripts` (в `backend/`) | **0** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 92 файла |
| Миграция | `alembic upgrade head` → `downgrade 013` → `upgrade head` → `check` | **чисто**, `No new upgrade operations detected` |
| Тесты миграций | `pytest -q tests/test_migrations.py -m migrations` | **4 passed** |
| Backend-тесты задач | `pytest -q tests/test_tasks.py` | **29 passed** (было 21) |
| Retention-тесты | `pytest -q tests/test_export_retention.py` | **12 passed** (было 11) |
| Backend в образе (полный набор) | `docker run ai-teacher-backend:step42b … pytest -q tests` | **532 passed, 22 skipped** (было 523+22) |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend unit | `pnpm test` | **103 passed** (было 99) |
| Frontend build | `pnpm build` | **OK**, entry **69.52 kB** gzip |
| i18n-аудит | `node scripts/check-i18n.mjs` | **OK**, 350 ключей в ru/en |
| E2E (полный набор) | `pnpm exec playwright test` | **19 passed**, 1 skipped (было 18) |

---

## 3. Файлы

**Backend:**

- `backend/app/models/task.py` — модель `TaskAttempt`.
- `backend/app/models/__init__.py` — регистрация модели (иначе Alembic не
  увидит таблицу).
- `backend/alembic/versions/20261105_0014_task_attempts.py` — миграция `014`.
- `backend/app/db/repositories/task.py` — `TaskAttemptRepository`
  (список по ученику и задаче, счётчик).
- `backend/app/schemas/task.py` — `AttemptItem`, `AttemptDetail`,
  `AttemptList`.
- `backend/app/services/task_service.py` — запись попытки при submit,
  `list_attempts()`, `get_attempt()`.
- `backend/app/api/v1/tasks.py` — эндпоинты `GET /tasks/{id}/attempts` и
  `GET /tasks/{id}/attempts/{attempt_id}`.
- `backend/app/services/retention.py` — таблица `task_attempts` в политике
  retention.
- `backend/app/config.py`, `.env.example` — `RETENTION_TASK_ATTEMPTS_DAYS`.
- `backend/tests/test_tasks.py` — 8 тестов истории попыток.
- `backend/tests/test_export_retention.py` — таблица в retention и её
  настройка.

**Frontend:**

- `frontend/src/types/api.ts` — `AttemptItem`, `AttemptDetail`,
  `AttemptList`.
- `frontend/src/store/tasks.ts` — `attempts`, `attemptDetail`,
  `loadAttempts()`, `loadAttempt()`.
- `frontend/src/pages/TaskDetailPage.tsx` — компонент `AttemptsHistory`,
  перечитывание истории после отправки.
- `frontend/src/i18n/locales/ru.json`, `en.json` — ключи истории попыток.
- `frontend/src/test/tasks-store.test.ts` — 3 теста стора.
- `frontend/src/test/task-detail.test.tsx` — тест истории и возврата кода.
- `frontend/e2e/tasks.spec.ts` — сценарий «история попыток сохраняется и
  показывает разбор».

**Документация:** `docs/SPEC.md` §3.5, `docs/PRIVACY.md` §1,
`docs/USER_GUIDE.md` §5, `docs/RULES.md` §11.30, `docs/RELEASES.md`,
`docs/CHANGELOG.md`, `TODO_V0.5.md`.

---

## 4. Проблемы и отклонения

- **Локальный venv отстаёт от `requirements.txt`** (fastapi 0.115.5 против
  0.162.0) — контрактные тесты OpenAPI падают на нём и без этих правок.
  Полный прогон backend выполнен в образе с зафиксированными зависимостями
  (`ai-teacher-backend:step42b`, Python 3.12.16). Известный риск окружения
  `KI-017`, новых проблем не заводил.
- **Итог тестов вырос на 9** (8 в `test_tasks.py`, 1 в
  `test_export_retention.py`): проверка набора таблиц retention фиксирует
  список таблиц, и новая таблица попала в него — тест обновлён.
- **Формат счёта в истории отличается от карточки результата**: в истории
  «3 из 3», в карточке — «Пройдено тестов: 3 из 3». Без этого e2e-локатор
  находил два элемента с одинаковым текстом (strict mode violation).

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Отдельная таблица vs JSON в `user_task_progress` | **Отдельная таблица** | История растёт линейно по числу попыток; JSONB в строке прогресса раздувал бы её и мешал бы считать. Отдельная таблица даёт индексы, retention и `ON DELETE CASCADE` при удалении задачи. |
| Хранить ли разбор по кейсам | **Да (`results` JSONB)** | Ученику нужен разбор той попытки, а не только «3 из 5»: без него история не объясняет, что именно сломалось. Структура совпадает с `TestCaseResult`, конвертируется без преобразований. |
| Срок хранения истории | **90 дней (`RETENTION_TASK_ATTEMPTS_DAYS`)** | Как у истории запусков кода (`code_executions`): попытка полезна для разбора ошибок, но не для хранения навсегда. |
| Чужая попытка: 403 или 404 | **404** | Ответ 403 подтверждал бы существование чужой записи. 404 не выдаёт ничего: попытка просто «не найдена». |
| Кто видит историю | **Только автор** | Разбор работ ученика учителем — отдельная задача S46-001 (с доступом по классу); смешивать её с личной историей здесь нельзя. |
| Пробная проверка в истории | **Не попадает** | Проба не засчитана — значит, её нет и в истории. Иначе ученик увидит «3 попытки», хотя отправлял один раз. |

---

## 6. Что дальше

Следующий шаг спринта 42 — **S42-003 «Автосохранение черновика»**:
колонка `draft_code` в `user_task_progress`, `PATCH /tasks/{id}/draft`,
восстановление черновика при открытии задачи и автосохранение из UI с
задержкой. Он использует уже готовый общий раннер проверки и ту же схему
«попытки не трогаем», что и S42-001/S42-002.

Затем **S42-004 «Поиск и фильтры в UI каталога»** — поиск по `q`, фильтры
категории и тега, состояние в URL.
