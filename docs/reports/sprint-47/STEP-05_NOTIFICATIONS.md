# Шаг 05 / спринт 47: центр уведомлений

**Дата:** 2026-11-10
**Спринт:** 47 (v0.5.0 «Learning Experience & Teaching Workflow»)
**Задача:** S47-005 — центр уведомлений, read-all, безопасные ссылки и бейдж
**Статус:** реализовано

---

## 1. Что сделано

1. **`POST /me/notifications/read-all`.** Сервис `mark_all_read` одним
   `UPDATE` ставит `read_at = now()` всем непрочитанным текущего
   пользователя и возвращает `{updated}`. Повторный вызов — `{updated: 0}`;
   чужие уведомления не затрагиваются.
2. **Фильтр `type`.** `GET /me/notifications` принимает `type` (строка);
   фильтр применяется к выборке, но `unread` всегда считается по всем
   уведомлениям — это счётчик бейджа, а не счётчик отфильтрованной страницы.
3. **Ссылки в payload (D-007).** Создатели уведомлений добавляют
   относительный `link` и `task_id`:
   - assignment/deadline → `/assignments` + `task_id`;
   - attempt_feedback → `/tasks/{task_id}`;
   - announcement → `/classrooms/{classroom_id}`.
   `NotificationItem` не менялся: поля живут в `payload`.
4. **Страница `/notifications`.** Список с фильтром по типу, «Прочитать»,
   «Прочитать все», переход по ссылке, пустое состояние и ошибки. Для старых
   уведомлений без `link` — fallback по типу и `task_id`/`classroom_id`.
5. **Безопасность ссылок.** Клиент принимает только путь, начинающийся с
   одного `/`, без `//`, `\` и схемы (`javascript:`, `http:`, `data:`).
   Если `link` есть, но не прошёл проверку, он игнорируется целиком —
   fallback не подменяет вредоносный payload. Fallback строится только когда
   `link` отсутствует; id проверяются по `[a-zA-Z0-9-]+`.
6. **Общий Zustand-стор.** `store/notifications.ts` хранит `items`, `unread`
   и `filterType`; `read` и `read-all` обновляют счётчик, `AppLayout`
   показывает бейдж, дашборд и страница используют тот же стор. Бейдж
   обновляется без перезагрузки страницы.
7. **Экран аудита и выгрузка для e2e.** Для сквозного сценария добавлены
   `/admin/audit` (фильтры, пагинация, ссылки на задачу/класс) и блок выгрузки
   аналитики на `/admin` (набор `users|tasks|attempts|activity`, CSV/JSON).
   Это UI-часть S47-001/S47-002, необходимая для проверяемого пути
   «аудит → выгрузка → модерация».
8. **E2E.** `frontend/e2e/sprint47-admin.spec.ts`: админ создаёт задачу
   (аудит `task.created`), импортирует задачу (source=imported), видит запись
   в журнале, скачивает CSV аналитики и снимает импортированную задачу с
   публикации в `/admin/moderation`. Сценарий зелёный.
9. **Тесты.** Backend: `tests/test_notifications.py` — read-all (свои/чужие,
   повтор), фильтр, payload ссылок; дополнены проверки assignment/deadline.
   Frontend: `notifications.test.tsx` — страница, фильтр, read-all, бейдж,
   безопасность ссылок; обновлён `dashboard.test.tsx` под общий стор.
10. **Документация.** `docs/SPEC.md`, `docs/CHANGELOG.md`, `TODO_V0.5.md`,
    этот отчёт, OpenAPI-снапшот.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `ruff check app tests scripts/seed_e2e.py` | **0** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 101 файл |
| Backend, уведомления + контракт | `pytest tests/test_contract_openapi.py tests/test_notifications.py tests/test_engagement.py` | **22 passed** |
| Backend, полный прогон | `pytest -q` | **728 passed, 1 skipped** (600.50 с) |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend tests | `pnpm test` | **274 passed** (46 файлов) |
| Frontend build | `pnpm build` | **успешно**, entry 70.57 kB gzip |
| i18n | `node scripts/check-i18n.mjs` | **747 ключей, ru/en паритет** |
| E2E | `playwright test e2e/sprint47-admin.spec.ts` | **1 passed** |

---

## 3. Файлы

**Backend:**

- `backend/app/services/engagement_service.py` — `mark_all_read`, фильтр
  `type`, `link`/`task_id` в создателях уведомлений.
- `backend/app/services/classroom_service.py` — передача `task_id` в
  assignment-уведомления.
- `backend/app/api/v1/engagement.py` — `read-all`, параметр `type`.
- `backend/app/schemas/engagement.py` — `NotificationsReadAllResponse`.
- `backend/scripts/seed_e2e.py` — админ `e2e_admin` для e2e.
- `backend/tests/test_notifications.py` — 3 теста; `test_engagement.py` —
  проверки payload.
- `backend/tests/contracts/openapi.json` — снапшот.

**Frontend:**

- `frontend/src/pages/NotificationsPage.tsx` — центр уведомлений.
- `frontend/src/store/notifications.ts` — общий стейт и счётчик.
- `frontend/src/lib/notifications.ts` — безопасные ссылки, fallback, текст.
- `frontend/src/components/layout/AppLayout.tsx` — бейдж и ссылка.
- `frontend/src/pages/DashboardPage.tsx` — переход на общий стор.
- `frontend/src/pages/AdminAuditPage.tsx`, `AdminPage.tsx` — аудит и выгрузка
  для e2e.
- `frontend/src/App.tsx`, `types/api.ts`, `i18n/locales/*.json`.
- `frontend/src/test/notifications.test.tsx`, `dashboard.test.tsx`.
- `frontend/e2e/sprint47-admin.spec.ts`.

**Документация:**

- `docs/SPEC.md`, `docs/CHANGELOG.md`, `TODO_V0.5.md`,
  `docs/reports/sprint-47/STEP-05_NOTIFICATIONS.md`.

---

## 4. Проблемы и отклонения

- **Небезопасная ссылка не заменяется fallback.** Если `payload.link`
  присутствует, но не прошёл проверку, уведомление остаётся без перехода;
  fallback применяется только к старым уведомлениям без `link`. Это строже
  требования «игнорировать» и не даёт подменить безопасный маршрут.
- **`unread` не фильтруется.** Счётчик бейджа должен показывать все
  непрочитанные; фильтр `type` влияет только на `items`.
- **Бейдж обновляется по событиям, а не polling'ом.** После read/read-all
  счётчик синхронизирован; новые уведомления появятся при следующем
  открытии/загрузке страницы — отдельного WebSocket-пуша уведомлений нет.
- **UI аудита/выгрузки — минимальный срез для e2e.** Он закрывает путь
  «аудит → выгрузка → модерация»; расширенная карточка пользователя и
  массовые действия остаются в объёме S47-002.
- **Миграции нет.** S47-005 не меняет схему БД.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| `read-all` одним UPDATE | **Да** | Не N запросов и не загрузка строк в память; `RETURNING id` даёт точный счётчик. |
| `unread` по всем уведомлениям | **Да** | Бейдж должен показывать общее число, независимо от открытого фильтра. |
| Общий Zustand-стор | **Да** | Бейдж, дашборд и страница не расходятся после read/read-all. |
| Валидация ссылки + fallback только без `link` | **Да** | Вредоносный payload не может подменить маршрут; старые уведомления остаются кликабельными. |
| Отдельная страница `/notifications` | **Да** | Список с фильтром и массовым действием не помещается в карточку дашборда. |
| UI аудита/выгрузки в этом шаге | **Да** | Без них e2e-сценарий админки не был бы проверяемым через интерфейс. |

---

## 6. Что дальше

Спринт 47 закрыт: S47-001…S47-005 и e2e «админ: аудит → выгрузка →
модерация» готовы. Следующий спринт — 48, релиз v0.5.0.
