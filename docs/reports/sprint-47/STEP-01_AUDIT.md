# Шаг 01 / спринт 47: экран журнала аудита

**Дата:** 2026-11-08
**Спринт:** 47 (v0.5.0 «Admin Console v2»)
**Задача:** S47-001 — журнал аудита: поиск, имя актора, CSV, UI
**Статус:** реализовано

---

## 1. Что сделано

1. **`GET /api/v1/admin/audit`.** Добавлен параметр `search` — ILIKE по
   `AuditLog.action` (регистронезависимо, не по `payload`). В ответе появилось
   поле `actor_username`: `users` присоединяется по `actor_id`; для удалённого
   аккаунта (`actor_id IS NULL`) — `null`, запрос не падает.
2. **`GET /api/v1/admin/audit/export`.** Отдельный потоковый CSV-эндпоинт
   (D-006) с теми же фильтрами (`action`, `entity_type`, `actor_id`, `search`).
   Отдаёт `utf-8-sig` (Excel не ломает кириллицу), лимит `EXPORT_MAX_ROWS`,
   заголовок `X-Export-Limit`, пишет `audit.exported` со сводкой фильтров
   (без текстов и списков логинов).
3. **Стриминг через серверный курсор.** `stream_audit_csv` использует
   `AsyncSession.stream`, поэтому выгрузка не загружает журнал в память.
4. **UI `/admin/audit`.** Таблица (время, действие, актор, сущность, IP) на
   `Table/Tr/Td/Th` (на мобильных — карточки), фильтры по действию, типу
   сущности и id актора, поиск, пагинация, кнопка «Скачать CSV».
5. **Ссылки на сущности.** `task → /tasks/{id}`, `user → /admin/users/{id}`,
   `classroom → /classrooms/{id}`; неизвестный тип выводится текстом без
   ссылки.
6. **Тесты.** Backend — 7 (фильтры, поиск, имя актора, пагинация, CSV,
   аудит выгрузки, права). Frontend — 4 (таблица и ссылки, поиск, пагинация,
   скачивание CSV).

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend: новые тесты | `pytest tests/test_admin_audit.py -q` | **7 passed** |
| Backend: полный набор | `pytest -q` | **712 passed, 1 skipped** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 99 файлов |
| Ruff (изменённые файлы) | `ruff check app/api/v1/admin.py app/services/audit_service.py app/schemas/audit.py tests/test_admin_audit.py` | **0** |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend unit | `pnpm test` | **265 passed** (45 файлов) |
| Frontend build | `pnpm build` | **успешно**, entry 69.83 kB gzip |
| i18n | `node scripts/check-i18n.mjs` | **OK**, 651 ключ, кириллицы вне локалей нет |

---

## 3. Файлы

**Backend:**

- `backend/app/services/audit_service.py` — `search`, join `users`,
  `stream_audit_csv`.
- `backend/app/schemas/audit.py` — `AuditLogItem.actor_username`.
- `backend/app/api/v1/admin.py` — `search` в списке, `GET /admin/audit/export`,
  `audit.exported`.
- `backend/tests/test_admin_audit.py` — 7 тестов (новый файл).

**Frontend:**

- `frontend/src/pages/AdminAuditPage.tsx` — страница журнала (новый файл).
- `frontend/src/pages/AdminPage.tsx` — ссылка на журнал.
- `frontend/src/App.tsx` — маршрут `/admin/audit` (lazy).
- `frontend/src/types/api.ts` — `AuditLogItem`, `AuditLogListResponse`.
- `frontend/src/test/admin-audit.test.tsx` — 4 теста (новый файл).
- `frontend/src/i18n/locales/ru.json`, `en.json` — блок `adminAudit`, ключ
  `admin.auditLink`.

**Документация:**

- `docs/SPEC.md` §15 — контракт списка и CSV.
- `TODO_V0.5.md` — S47-001 отмечен `[x]`.
- `docs/CHANGELOG.md` — запись в `[Unreleased]`.
- `docs/reports/sprint-47/STEP-01_AUDIT.md` — этот отчёт.

---

## 4. Проблемы и отклонения

- **Локальный ruff 0.8.1 не читает конфиг проекта.** В `pyproject.toml`
  используется селектор `UP046`, который понимает только закреплённый в
  `requirements.txt` ruff 0.17.3; поставить его локально нельзя (PyPI
  недоступен, KI-017). Проверка изменённых файлов выполнена ruff 0.8.1 с
  временным конфигом, идентичным проектному, но без `UP046`. Найденные вне
  изменённых файлов замечания (`UP038`, `C416`, `I001`) существовали до шага
  и не связаны с S47-001. В CI используется ruff 0.17.3.
- **`audit.exported` пишется до потоковой отдачи.** Если фильтр явно выбирает
  `action=audit.exported`, запись о текущей выгрузке попадёт и в CSV, и в
  список. Это ожидаемое следствие одного журнала; отдельного исключения не
  вводили.
- **Новых KI нет.**

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Хранить `actor_username` в `audit_log` | **Join `users`** | Не дублируем ПДн в журнале; имя всегда актуально, а удалённый аккаунт честно даёт `null`. |
| CSV через `export_service` | **Отдельный эндпоинт** | У журнала свой набор колонок и фильтров (D-006); `export_service` обслуживает аналитические наборы. |
| Поиск по `payload` | **Только ILIKE по `action`** | Требование шага; `payload` — сводка и не предназначен для полнотекстового поиска. |
| Ссылки на сущности на клиенте | **Whitelist по `entity_type`** | Неизвестный тип не превращается в битую ссылку; маршруты не собираются из произвольных строк. |
| Фильтры в CSV | **Те же, что у списка** | Приёмка: UI и файл дают одинаковый набор строк. |

---

## 6. Что дальше

Шаг 02: карточка пользователя (`GET /admin/users/{id}`), мягкая деактивация
с отзывом сессий, атомарный `PATCH /admin/users/bulk`, UI выгрузки аналитики и
массовых действий.
