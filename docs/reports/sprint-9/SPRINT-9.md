# Sprint 9: Frontend Features — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён

---

## 1. Файлы (+/-)

### Созданные
```
+ frontend/src/lib/chatSocket.ts          — WS-клиент чата (start/token/done/error)
+ frontend/src/lib/markdown.ts            — разбор ``` блоков
+ frontend/src/hooks/useChatSession.ts     — связка WS ↔ стор, REST-фолбэк
+ frontend/src/store/chat.ts               — сессии, сообщения, стриминг
+ frontend/src/store/tasks.ts              — каталог, детали, submit, прогресс
+ frontend/src/components/chat/MessageList.tsx
+ frontend/src/components/chat/MessageInput.tsx
+ frontend/src/components/chat/CodeBlock.tsx
+ frontend/src/components/chat/RichText.tsx
+ frontend/src/components/chat/LevelSelector.tsx
+ frontend/src/components/code-editor/CodeEditor.tsx
+ frontend/src/components/code-editor/OutputPanel.tsx
+ frontend/src/pages/ChatPage.tsx
+ frontend/src/pages/CodePage.tsx
+ frontend/src/pages/TasksPage.tsx
+ frontend/src/pages/TaskDetailPage.tsx
+ frontend/src/test/chat-store.test.ts     — 11 тестов
+ frontend/src/test/tasks-store.test.ts    — 8 тестов
+ frontend/src/test/chat-components.test.tsx — 13 тестов
+ frontend/src/test/code-editor.test.tsx   — 8 тестов
```

### Изменённые
```
~ frontend/src/App.tsx                 — реальные страницы, /404, редирект на него
~ frontend/src/i18n/locales/{ru,en}.json — ключи chat/code/tasks/progress
~ frontend/src/vite-env.d.ts           — VITE_WS_BASE
~ frontend/.env.example                — VITE_WS_BASE
~ frontend/src/test/setup.ts           — мок Monaco
~ frontend/package.json                — @monaco-editor/react
~ frontend/src/components/chat/RichText.tsx — утилита вынесена в lib
```

Удалён: `pages/ComingSoonPage.tsx` (заменён реальными страницами).

---

## 2. Покрытие

| Файл | Тестов | Что проверяет |
|------|--------|----------------|
| `chat-store.test.ts` | 11 | сессии, создание с уровнем, стриминг, пустой ответ, REST-фолбэк, удаление |
| `tasks-store.test.ts` | 8 | загрузка, фильтры в query, submit и обновление статуса, ошибки, прогресс |
| `chat-components.test.tsx` | 13 | разбор кода, MessageList, Enter/Shift+Enter, блокировка, LevelSelector |
| `code-editor.test.tsx` | 8 | рендер редактора, вывод, ошибки, нарушения, линт |
| **Итого новых** | **40** | всего в проекте — **60** |

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Типы | `pnpm typecheck` | 0 ошибок |
| Линтер | `pnpm lint` | 0 ошибок, 0 предупреждений |
| Тесты | `pnpm test` | `60 passed` |
| Сборка | `pnpm build` | `117.31 kB gzip` (лимит 200 kB) |
| Preview | `vite preview` | `/`, `/chat`, `/code`, `/tasks`, `/tasks/:id`, `/nope` → 200 |

---

## 4. Smoke

```
GET /chat       → 200 (страница с сессиями и окном диалога)
GET /code       → 200 (Monaco + панель вывода)
GET /tasks      → 200 (каталог, фильтры, прогресс)
GET /tasks/:id  → 200 (карточка задачи)
GET /nope       → 200 → клиентский редирект на /404
```

Сквозной сценарий с живым backend не выполнялся (KI-012).

---

## 5. Что не так

1. **KI-013:** Monaco загружается с CDN — офлайн-режим редактора не работает.
2. Авто-reconnect WebSocket не реализован: при обрыве следующий запрос идёт в REST
   (пользователь видит индикатор `○ rest`).
3. Отдельной страницы статистики нет — прогресс показан блоком на `/tasks`.
4. `scrollIntoView` в jsdom отсутствует — вызов сделан опциональным.

---

## 6. Новые KI

| ID | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-013 | Open | Low | Monaco грузится с CDN, нужен локальный bundle |

---

## 7. Обоснование

- **Стриминг + фолбэк.** WS даёт токены в реальном времени; если сокет не
  поднялся (прокси, сеть), сообщение уходит обычным POST — чат остаётся рабочим.
- **Оптимистичные сообщения.** Вопрос ученика появляется сразу, ответ
  собирается из токенов; это скрывает задержку первого токена.
- **RichText вместо markdown-библиотеки.** Нужны только блоки кода; свой разбор
  в `lib/markdown.ts` — 30 строк вместо зависимости на 30 kB.
- **Enter отправляет, Shift+Enter переносит.** Ученики часто вставляют код —
  перенос строки должен оставаться доступным.
- **Уровень выбирается при создании сессии.** Так один ученик может держать
  «базовый» и «продвинутый» диалоги параллельно (согласовано с backend S5).
- **Подсказки по одной.** Педагогически важно не выдавать все подсказки сразу —
  кнопка «Показать подсказку» раскрывает следующую.
- **Результаты по кейсам с ожидаемым/фактическим выводом.** Ученик видит, на
  каком вводе расходится вывод, и учится отлаживать.

---

**Дата:** 2026-10-29
