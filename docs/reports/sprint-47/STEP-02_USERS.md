# Шаг 02 / спринт 47: выгрузка аналитики и карточка пользователя

**Дата:** 2026-11-08
**Спринт:** 47 (v0.5.0 «Admin Console v2»)
**Задача:** S47-002 — выгрузка, карточка пользователя, мягкая деактивация, bulk
**Статус:** реализовано

---

## 1. Что сделано

1. **`GET /api/v1/admin/users/{id}`.** Карточка: профиль (`AdminUserItem`,
   добавлен `is_active`), прогресс `{solved, attempts}`, последние 10 записей
   `audit_log` по пользователю (как актор и как сущность) и действующие сессии
   из `sessions.list_sessions`. В сессиях отдаются `id, created_at,
   last_used_at, user_agent, ip` — без служебного `jti`. Неизвестный id — 404.
2. **`PATCH /api/v1/admin/users/{id}`.** Принимает `is_active` (D-004).
   `false`: `revoke_all_sessions` отзывает все устройства, `token_version`
   увеличивается на 1, пишется `user.deactivated` со сводкой
   (`sessions_revoked`). `true`: `user.activated`, старые сессии не оживают.
   Деактивировать/понизить себя нельзя — 400. `DELETE` не менялся.
3. **`PATCH /api/v1/admin/users/bulk`.** Тело `{user_ids ≤ 100, changes:
   {role?, is_active?}}` (D-005). Сначала валидируется весь набор, затем
   изменения и отзыв сессий применяются одной транзакцией. Отчёт
   `{updated, skipped}` с машинными причинами `not_found`, `self`,
   `admin_role`, `no_changes`; пустой `updated` — 200. Одно событие
   `user.bulk_updated` с количествами, без списков логинов.
4. **UI выгрузки.** На `/admin` — карточка «Выгрузка данных»: набор
   (`users|tasks|attempts|activity`), формат (`csv|json`), пояснение про
   `EXPORT_MAX_ROWS`, скачивание через `api.download` и `saveBlob`.
5. **UI карточки.** Страница `/admin/users/{id}`: профиль, статус, прогресс,
   активные сессии, последние действия; деактивация/активация и удаление с
   подтверждением и явной подписью «Удалить безвозвратно».
6. **UI bulk.** В таблице пользователей — чекбоксы (включая «выбрать всех на
   странице»), панель «роль / активность», подтверждение в модальном окне и
   отчёт `updated/skipped` с расшифровкой причин.
7. **Тесты.** Backend — 11 (карточка, 404/403, деактивация и отзыв сессий,
   рост `token_version`, активация, запрет себя, bulk с частичными пропусками,
   пустой `updated`, валидация, лимит 100, права). Frontend — 6 новых
   (выгрузка, bulk с подтверждением и отчётом, ссылка в карточку, карточка,
   деактивация, удаление с подтверждением).
8. **Стабилизация flaky-теста S43.** Полный прогон выявил гонку
   `test_stop_interrupts_stream_and_saves_partial`: под нагрузкой поток успевал
   отдать все дельты до обработки `stop`. Задержка тестового провайдера
   увеличена с 50 до 200 мс — тест снова детерминирован.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend: новые тесты | `pytest tests/test_admin_users.py -q` | **11 passed** |
| Backend: контракт | `pytest tests/test_contract_openapi.py tests/test_api_contract_shapes.py` | **13 passed** |
| Backend: полный набор | `pytest -q` | **723 passed, 1 skipped** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 99 файлов |
| Ruff (изменённые файлы) | `ruff check app/api/v1/admin.py app/schemas/admin.py tests/test_admin_users.py` | **0** |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend unit | `pnpm test` | **271 passed** (47 файлов) |
| Frontend build | `pnpm build` | **успешно**, entry 69.91 kB gzip |
| i18n | `node scripts/check-i18n.mjs` | **OK**, 717 ключей |

---

## 3. Файлы

**Backend:**

- `backend/app/schemas/admin.py` — `is_active` в `AdminUserItem/Update`,
  `AdminUserDetail`, `AdminUserProgress`, `AdminUserSessionItem`,
  bulk-схемы и причины пропуска.
- `backend/app/api/v1/admin.py` — карточка, мягкая деактивация, bulk.
- `backend/tests/test_admin_users.py` — 11 тестов (новый файл).
- `backend/tests/contracts/openapi.json` — снапшот OpenAPI (аддитивные
  схемы и поле `is_active`).
- `backend/tests/test_websocket_stream.py` — стабилизация flaky-теста S43.

**Frontend:**

- `frontend/src/components/admin/AdminExportCard.tsx` — выгрузка (новый).
- `frontend/src/components/admin/UserBulkPanel.tsx` — массовые действия (новый).
- `frontend/src/pages/AdminUserPage.tsx` — карточка пользователя (новый).
- `frontend/src/pages/AdminPage.tsx` — выгрузка, чекбоксы, bulk, удаление с
  подтверждением.
- `frontend/src/App.tsx` — маршрут `/admin/users/:userId`.
- `frontend/src/types/api.ts` — типы карточки, сессий и bulk.
- `frontend/src/test/admin-users.test.tsx`,
  `frontend/src/test/admin-user-detail.test.tsx` — 6 тестов (новые файлы).
- `frontend/src/i18n/locales/ru.json`, `en.json` — `admin.export.*`,
  `admin.bulk.*`, `admin.userDetail.*`.

**Документация:**

- `docs/SPEC.md` §15 — контракты карточки, деактивации и bulk.
- `TODO_V0.5.md` — S47-002 отмечен `[x]`.
- `docs/CHANGELOG.md` — запись в `[Unreleased]`.
- `docs/reports/sprint-47/STEP-02_USERS.md` — этот отчёт.

---

## 4. Проблемы и отклонения

- **Снапшот OpenAPI перегенерирован.** `AdminUserItem.is_active` — новое
  обязательное поле ответа, поэтому тест контракта требовал осознанного
  обновления. Скрипт `scripts/snapshot_openapi.py` пишет файл с сортировкой
  ключей, из-за чего дифф большой, хотя изменения аддитивные (новые пути и
  схемы, одно поле). Поведение API не удалено и не изменено.
- **Нет флага `current` у сессий.** Админ не имеет access-токена целевого
  пользователя, поэтому «текущая» сессия для него неопределима; по
  уточнению к шагу отдаются только `id, created_at, last_used_at,
  user_agent, ip`.
- **Деактивация: отзыв сессий и обновление пользователя — два коммита.**
  `revoke_all_sessions` коммитит сам (переиспользование сервиса S45-005, как
  в смене пароля). Если обновление пользователя упадёт после отзыва, сессии
  останутся отозванными — безопасный отказ (пользователь выйдет, доступ не
  станет шире). Bulk, наоборот, применяет изменения и отзыв сессий одной
  транзакцией.
- **Приоритет причин в bulk.** `self` проверяется раньше `no_changes`, поэтому
  администратор всегда видит «нельзя менять себя», даже если изменения
  совпадают. Это ожидаемое поведение.
- **Flaky-тест S43 исправлен, новых KI нет.**

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Расширять `AdminUserItem` или отдельная `AdminUserDetail` | **Nested `AdminUserDetail`** | Профиль переиспользуется в списке, а карточка не раздувает контракт списка. |
| Новый запрос сессий | **`sessions.list_sessions`** | Уже учитывает `revoked_at` и сортировку; дублировать SQL не нужно. |
| Деактивация через `DELETE` | **`is_active=false` + отзыв сессий** | D-004: обратимое действие, история и прогресс сохраняются. |
| Bulk как N вызовов `PATCH` | **Один эндпоинт, одна транзакция** | D-005: нет частично применённого состояния, отчёт объясняет пропуски. |
| Причины пропуска строками | **Машинные коды + i18n** | API стабилен, перевод — на клиенте; списки логинов в ответ/аудит не попадают. |
| Отдельная страница карточки | **`/admin/users/:id`** | Ссылки из аудита и списка ведут на неё; модалка хуже для deep-link и a11y. |

---

## 6. Что дальше

Шаг 03: спайк метрик «застревания», миграция `tasks.source` /
`moderation_comment`, очередь `GET /admin/tasks/review`, действия модерации,
аудит `task.moderated` и UI `/admin/moderation`.
