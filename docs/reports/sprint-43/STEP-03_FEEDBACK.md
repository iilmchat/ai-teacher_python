# Шаг 03 / спринт 43: оценка ответов

**Дата:** 2026-11-06  
**Спринт:** 43 (v0.5.0 «Learning Experience & Teaching Workflow»)  
**Задача:** S43-003 — оценка ответов  
**Статус:** реализовано

---

## 1. Что сделано

1. **Таблица оценок.** `message_feedback` (миграция `017`): `message_id`,
   `user_id`, `value` (+1 / −1), `comment` (nullable, до 500 символов),
   `created_at`. Уникальное ограничение `uq_message_feedback_message_user` на
   пару «сообщение × ученик» и CHECK-constraint `value IN (-1, 1)`.
2. **API оценок.** `POST /chat/messages/{id}/feedback` — поставить или изменить
   оценку; `DELETE /chat/messages/{id}/feedback` — снять; `GET
   /chat/sessions/{id}/feedback` — мои оценки по сессии (нужны, чтобы после
   перезагрузки страницы интерфейс помнил оценку).
3. **Изоляция.** Оценить можно только ответ ассистента в своей сессии: чужая
   сессия — 403, неизвестное сообщение — 404, вопрос ученика — 422.
4. **Сводка качества.** `GET /admin/quality` (только администратор):
   счётчики `total` / `positive` / `negative`, доля одобрения, срезы по
   провайдеру и модели (берутся из `metadata` ответа) и последние 20
   негативных оценок с текстом ответа и комментарием ученика.
5. **Настоящий id сообщения в протоколе.** События `done` и `stopped` теперь
   содержат `message_id` сохранённого ответа. Раньше клиент знал только
   локальный идентификатор — оценить такой ответ было невозможно (404).
6. **Интерфейс чата.** Кнопки «👍» и «👎» под ответом ассистента, комментарий
   по клику (до 500 символов) и снятие оценки. Оценка подсвечивается, поле
   комментария открывается сразу после негативной оценки.
7. **Админка.** Карточка «Качество ответов ассистента»: счётчики, доля
   одобрения, таблица по провайдерам и список негативных оценок с текстом
   ответа.
8. **Связь с LLM-as-judge.** В `docs/LLM_EVAL.md` §4 описано, как
   негативные оценки учеников превращаются в набор для судьи.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `ruff check app tests scripts` (в `backend/`) | **0** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 94 файла |
| Backend targeted | `pytest -q tests/test_feedback.py tests/test_chat.py tests/test_websocket_stream.py` | **51 passed** |
| Backend полный (локально) | `pytest -q` | **608 passed, 1 skipped** |
| Миграция `017` | `alembic upgrade head` → `alembic check` → `downgrade 016` → `upgrade head` | **OK** — «No new upgrade operations detected» |
| Frontend typecheck | `pnpm typecheck` | **0** |
| Frontend lint | `pnpm lint` | **0** |
| Frontend unit | `pnpm test` | **171 passed** (было 158) |
| Frontend build | `pnpm build` | **OK** |
| i18n-аудит | `node scripts/check-i18n.mjs` | **OK**, 396 ключей в ru/en |
| E2E (полный набор) | `pnpm exec playwright test` | **26 passed**, 1 skipped (было 25) |

---

## 3. Файлы

**Backend:**

- `backend/app/models/chat.py` — модель `MessageFeedback` (уникальность, CHECK).
- `backend/alembic/versions/20261106_0017_message_feedback.py` — миграция
  `017` (новый файл).
- `backend/app/db/repositories/chat.py` — `MessageFeedbackRepository`:
  `get_for_user`, `list_for_messages`, `upsert`, `delete_for_user`.
- `backend/app/services/feedback_service.py` — пользовательские операции и
  агрегаты качества (новый файл).
- `backend/app/schemas/chat.py` — `MessageFeedbackCreate`,
  `MessageFeedbackResponse`.
- `backend/app/schemas/admin.py` — `AdminQualityResponse`, `QualityBreakdown`,
  `QualityNegativeItem`.
- `backend/app/api/v1/chat.py` — три маршрута оценок.
- `backend/app/api/v1/admin.py` — `GET /admin/quality`.
- `backend/app/api/websocket.py` — `message_id` в событиях `done`/`stopped`.
- `backend/tests/test_feedback.py` — 11 тестов (новый файл).

**Frontend:**

- `frontend/src/types/api.ts` — `MessageFeedback`, `AdminQualityResponse`,
  `QualityBreakdown`, `QualityNegativeItem`.
- `frontend/src/store/chat.ts` — `feedback`, `loadFeedback`, `setFeedback`,
  `clearFeedback`, `message_id` в `finishStream`.
- `frontend/src/components/chat/MessageFeedback.tsx` — кнопки оценки и
  комментарий (новый файл).
- `frontend/src/components/chat/MessageList.tsx` — блок оценки под ответом.
- `frontend/src/pages/ChatPage.tsx` — передача оценок в список сообщений.
- `frontend/src/pages/AdminPage.tsx` — карточка «Качество ответов ассистента».
- `frontend/src/lib/chatSocket.ts` — `message_id` в событиях `done`/`stopped`.
- `frontend/src/hooks/useChatSession.ts` — передача `messageId` в стор.
- `frontend/src/i18n/locales/ru.json`, `en.json` — ключи оценок и сводки.
- `frontend/src/test/message-feedback.test.tsx` — 5 тестов компонента (новый
  файл).
- `frontend/src/test/admin-quality.test.tsx` — 3 теста админки (новый файл).
- `frontend/src/test/chat-store.test.ts` — 4 теста стора.
- `frontend/src/test/chat-socket.test.ts` — тест `message_id` в протоколе.
- `frontend/e2e/chat.spec.ts` — сценарий «оценивает ответ ассистента».

**Документация:** `docs/SPEC.md` §3.3 и схема БД, `docs/USER_GUIDE.md` §3,
`docs/RULES.md` §11.37, `docs/LLM_EVAL.md` §4, `docs/RELEASES.md`,
`docs/CHANGELOG.md`, `TODO_V0.5.md`.

---

## 4. Проблемы и отклонения

- **Клиент знал только локальный id ответа.** Ответ, пришедший по
  WebSocket, рисуется локально, и его идентификатор не существует в БД:
  оценка такого ответа давала 404. Решение — сервер передаёт `message_id`
  сохранённого сообщения в событиях `done`/`stopped`, клиент подставляет его
  в локальное сообщение. Изменение затронуло протокол чата, поэтому
  попутно обновлены тесты сокета.
- **Оценки нельзя было бы показать после перезагрузки.** Добавлен
  `GET /chat/sessions/{id}/feedback`: стор подгружает оценки при открытии
  чата, поэтому активная оценка не теряется.
- **Полная выгрузка негативных оценок отложена до S47-004.** Сейчас
  `negative_samples` — это окно в 20 последних записей. Этого хватает, чтобы
  начать прогоны LLM-as-judge, но не для полноценной регрессии; в
  `docs/LLM_EVAL.md` ограничение зафиксировано явно.
- **Агрегаты по провайдеру и модели читаются из `metadata` ответа.** Отдельной
  колонки с провайдером нет, а дублировать её в таблице оценок — значит
  рассинхронизировать данные. Срез строится в SQL по JSONB-полям.
- **Оценка не влияет на ответ и не скрывает его.** Это сигнал качества, а не
  модерация: текст ответа и его оценка хранятся раздельно.
- **`docs/PRIVACY.md` не менялся.** Оценка и комментарий — мнение ученика о
  тексте ответа ассистента, а не персональные данные о человеке.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Хранить оценку в `metadata` сообщения или в отдельной таблице | **Отдельная таблица** | Уникальность «одна оценка на ученика и сообщение» выражается констрейнтом, по сообщению считаются агрегаты, а `metadata` ответа не смешивается с оценкой. |
| Несколько оценок на одно сообщение или одна | **Одна на пару «сообщение × ученик»** | Ученик меняет мнение, а не копит дубли; агрегаты остаются осмысленными. |
| Хранить оценку в сообщении или отдельной сущности | **Отдельной сущностью** | Оценку можно снять, не трогая ответ, и собрать по ней статистику без разбора JSONB. |
| Значение 1 / −1 или «like/dislike» | **+1 / −1** | Число складывается: средняя оценка считается прямо, а не через отдельную таблицу соответствий. |
| Показывать оценки сразу или после перезагрузки | **Сразу и после перезагрузки** | Отдельный `GET` по сессии: активная оценка не теряется при обновлении страницы. |
| Сводка качества в общей аналитике или отдельным маршрутом | **Отдельным `GET /admin/quality`** | Оценки — отдельный срез с агрегатами по провайдеру и модели; общая аналитика их не содержит и не должна разрастаться. |
| Комментарий привязывать к оценке или к сообщению | **К оценке** | Комментарий без оценки бессмысленен, а при смене оценки комментарий обновляется вместе с ней. |
| Показывать ученику чужие оценки | **Нет** | Оценка — личное мнение; публичные счётчики — только у администратора. |

---

## 6. Что дальше

Спринт 43 продолжается: S43-004 (экспорт диалога в Markdown/JSON и стартовые
шаблоны промптов) и S43-005 (код из чата в песочницу и обратно). Оценки
подготовлены как вход для LLM-as-judge (S47-004): полноценная выгрузка
негативных оценок и регрессия по ним — задача следующего спринта. После
закрытия спринта — сводный отчёт `docs/reports/sprint-43/SPRINT-43.md`.
