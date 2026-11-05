# Промпт для новой сессии ассистента-агента

Ниже — готовый текст, который нужно передать новому чату. Он самодостаточен: агент сможет продолжить работу без дополнительного контекста.

---

## Текст промпта (копировать целиком)

Продолжи разработку проекта **AI Teacher for Python** (репозиторий `C:\Projects\AI\ai-teacher_python`). Ты — ассистент-агент по правилам этого репозитория: см. `docs/RULES.md` (обязателен к прочтению перед правками) и `TODO_V0.5.md` (план текущего этапа).

### Текущее состояние

- Ветка: `sprint/42-learning-loop` (запушена в `origin/sprint/42-learning-loop`). Рабочее дерево чистое.
- Последний коммит: `83f29ae feat(tasks): recommend the next task with an explanation (S42-005)`.
- Идёт **спринт 42 «Student Learning Loop»** этапа v0.5.0 «Learning Experience & Teaching Workflow».
- Готово: **S42-001 … S42-005** (по шагам 01–05, отчёты в `docs/reports/sprint-42/STEP-0{1..5}_*.md`).
- Осталось в спринте: **S42-006** (последняя задача спринта) → затем отчёт спринта `docs/reports/sprint-42/SPRINT-42.md` (7 разделов по `docs/RULES.md` §2.4) и запись в `docs/RELEASES.md`.
- Активные KI: `KI-023` (merge-gate, High, вне нашего контроля), `KI-028` (смена пароля — закрывается в спринте 45), `KI-029` (`best_solution` не читается — закрывается в 46), `KI-030` (часть API без UI — закрывается в 42–47).

### Твоя задача: S42-006 «Связка задачи и ассистента»

Текст задачи (из `TODO_V0.5.md`):

> - [ ] Deep-link `/chat?task=<task_id>`: ассистент получает контекст задачи (системная подсказка с заголовком, описанием и условиями — без эталонного решения).
> - [ ] Кнопка «Спросить ассистента» на странице задачи и на странице результатов; в чате — плашка контекста с названием задачи и снятием.
> - [ ] Контекст задачи попадает в `message_metadata` запроса, не в `content` (не утекает в историю ученика) и не логируется в PII-виде.
> - [ ] Тесты: контекст в запросе, отсутствие утечки в текст сообщения, корректная очистка контекста.

Оценка — 6 ч. Зависимость: S42-001 (выполнена).

### На что обратить внимание (это выяснено чтением кода)

- **Контекст задачи не должен попадать в `content`.** `ChatService.send_message(session, content)` и `stream_reply(session, content)` принимают только текст и кладут его в `ChatMessage.content`. Метаданные сообщения — `ChatMessage.message_metadata` (JSONB), в репозитории `create_message(..., metadata=...)`. Значит контекст надо передавать отдельным аргументом до/рядом с `content` и класть в метаданные, а в LLM-промпт добавлять отдельным системным сообщением (см. `app/services/llm/prompt_builder.py::build_messages` — он собирает `[system] + хвост истории + user`; контекст задачи логично добавить вторым системным сообщением, а не в текст пользователя).
- **Эталонного решения в контексте быть не должно.** У задачи есть `solution_template` (в `app/models/task.py::Task`) и `test_cases` с `expected_output` — их в контекст класть нельзя, иначе ассистент выдаст готовое решение. Брать только `title`, `description` и, возможно, список тест-кейсов без ожидаемых выводов.
- **Есть два пути отправки сообщения:** REST (`POST /api/v1/chat/sessions/{id}/messages`, схема `ChatMessageRequest{content}` в `backend/app/schemas/chat.py`) и WebSocket (`/api/v1/chat/ws/{session_id}`, протокол `{"type":"chat","content":"..."}` в `backend/app/api/websocket.py` + `frontend/src/lib/chatSocket.ts`). Deep-link работает через WebSocket-путь (стриминг), поэтому контекст задачи нужно провести **через оба** пути.
- **Фронтенд:** страница чата — `frontend/src/pages/ChatPage.tsx`, стор — `frontend/src/store/chat.ts`, WS-клиент — `frontend/src/lib/chatSocket.ts`. Deep-link читается через `useSearchParams` (react-router-dom) — так уже сделано в `frontend/src/pages/TasksPage.tsx` (S42-004), следуй тому же стилю.
- **Кнопка «Спросить ассистента»** — на странице задачи (`frontend/src/pages/TaskDetailPage.tsx`) и на странице результатов (блок результатов там же, компонент `ResultsCard`).
- **Уровень ассистента и политика промптов** (`basic` / `intermediate` / `advanced`) не меняем; контекст задачи не должен ломать проверку политики (`app/services/llm/policy.py`).

### Обязательные правила работы

1. **Один шаг = один коммит** с Conventional Commits и ссылкой на задачу в теле: `feat(tasks): ... (S42-006)`. Ветку не меняй (остаёмся на `sprint/42-learning-loop`), пока не попросят иначе.
2. **Перед коммитом обязательно** (RULES §10):
   - `cd backend && .\venv\Scripts\ruff.exe check app tests scripts` → 0
   - `cd backend && .\venv\Scripts\mypy.exe app --config-file ../pyproject.toml` → 0
   - `cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build` → зелёные
   - `node scripts/check-i18n.mjs` → OK (все новые строки — в `frontend/src/i18n/locales/ru.json` **и** `en.json`, ключи ru/en обязаны совпадать)
3. **Отчёт по шагу** — `docs/reports/sprint-42/STEP-06_<ТЕМА>.md`, 7 разделов по `docs/RULES.md` §12: шапка; что сделано; проверки; файлы; проблемы и отклонения; обоснование решений; что дальше. Пиши по-русски, как в предыдущих пяти отчётах.
4. **Обнови документацию в том же коммите**: `docs/SPEC.md` (контракт эндпоинта/схемы), `docs/USER_GUIDE.md` (сценарий для ученика), при необходимости `docs/RULES.md` (новое правило) и `docs/PRIVACY.md` (если появляются новые ПДн), `docs/CHANGELOG.md` (`[Unreleased]`), `docs/RELEASES.md` (отчёт по шагу), `TODO_V0.5.md` (задача → `[x]`, журнал плана §12). Правило «один факт — один источник правды»: не дублируй детали API между файлами.
5. **Планировщик следующих шагов:** после S42-006 — отчёт спринта `docs/reports/sprint-42/SPRINT-42.md` (7 разделов по `docs/RULES.md` §2.4) и запись в `docs/RELEASES.md`. Спринт 42 закрывает 6 задач; дальше по плану — спринт 43 «Chat Productivity» (S43-001 … S43-005) и релиз v0.5.0 в спринте 48.

### Проверки: где и как запускать

**Локальный venv устарел** (`backend/venv` — fastapi 0.115.5 вместо 0.162.0 из `requirements.txt`). Из-за этого на нём падают **контрактные тесты OpenAPI** (`tests/test_contract_openapi.py`) и **тест матрицы доступа** (`tests/test_access_matrix.py`) — это происходит и без твоих правок (проверено через `git stash`), это `KI-017`, а не твоя регрессия.

Поэтому полный backend-прогон делай **в образе** с зафиксированными зависимостями:

```powershell
docker build -t ai-teacher-backend:step42g ./backend
docker run --rm --network host `
  -e POSTGRES_HOST=127.0.0.1 -e POSTGRES_PORT=5434 `
  -e REDIS_HOST=127.0.0.1 -e REDIS_PORT=6381 `
  -e POSTGRES_USER=ai_teacher -e POSTGRES_PASSWORD=change_me_password `
  -e POSTGRES_DB=ai_teacher -e SECRET_KEY=change_me_secret_key_for_jwt_encoding `
  -v "${PWD}:/src:ro" --entrypoint python ai-teacher-backend:step42g `
  -m pytest -q -p no:cacheprovider /src/backend/tests
```

Ожидаемая база на момент старта: **557 passed, 22 skipped**.

Postgres и Redis уже подняты: `ai_teacher_postgres` (127.0.0.1:5434), `ai_teacher_redis` (127.0.0.1:6381).

E2E (Playwright) — из `frontend/`:

```powershell
$env:CI=''; $env:E2E_PYTHON="$PWD\backend\venv\Scripts\python.exe"
$env:E2E_POSTGRES_PORT='5434'; $env:E2E_REDIS_PORT='6381'
cd frontend; pnpm exec playwright test
```

Ожидаемая база: **22 passed, 1 skipped**. Frontend unit: **125 passed** (19 файлов).

### Ловушки, на которые уже наступали

- **Окончания строк.** В репозитории файлы лежат с LF; `git config core.autocrlf=true`, и python-скрипты, пишущие через `newline=''`, легко превращают файл в CRLF — diff начинает выглядеть как переписывание всего файла. После правок проверь `git diff --stat`: если изменено «всё», а менялась пара строк, — это CRLF. Нормализуй: `python -c "import io;p='<file>';d=io.open(p,'rb').read();io.open(p,'wb').write(d.replace(b'\r\n',b'\n'))"`.
- **Порядок маршрутов в FastAPI.** Статические пути (`/tasks/progress`, `/tasks/recommended`) объявляются **до** `/{task_id}`, иначе UUID-маршрут пытается разобрать слово как UUID (уже попадалось на `/tasks/recommended`).
- **Кэш списка задач** (`app/services/cache.py::tasks_list_cache_key`) включает пользователя и все фильтры — при добавлении нового фильтра ключ надо расширить, иначе выдача смешается между учениками.
- **Локальный venv** отстаёт (см. выше) — не ориентируйся на его падения.
- **Тестовые фикстуры.** В `backend/tests/test_tasks.py` локальный `TASK_PAYLOAD` **не содержит** `tags` (в отличие от `tests/task_helpers.py`), поэтому для проверки фильтра по тегу используется отдельный хелпер `_create_task_with_tags`.
- **Monaco в jsdom не рендерится** — в unit-тестах страниц редактор кода подменяется `vi.mock('@/components/code-editor/CodeEditor')` простым `textarea` c `data-testid="code-input"`.
- **fake-таймеры в vitest:** `vi.useFakeTimers({ shouldAdvanceTime: true })` — иначе `findBy*` зависает; для автосохранения черновика используется debounce 800 мс.

### Контекст проекта (чтобы не изучать заново)

Стек: Python 3.12 + FastAPI (backend/, `app/api/v1/*`, `app/services/*`, `app/models/*`, `app/db/repositories/*`), React 19 + TypeScript strict + Zustand + Tailwind 4 + i18next (frontend/, `src/pages/*`, `src/store/*`, `src/components/*`), PostgreSQL 17 + pgvector, Redis, песочница кода на RestrictedPython (изолированный процесс), LLM — DeepSeek с fallback на LM Studio, три уровня помощи (`basic`/`intermediate`/`advanced`).

Данные: `users` (роли student/teacher/admin), `tasks` + `user_task_progress` + `task_versions` + `task_attempts`, `chat_sessions`/`chat_messages`, `classrooms`/`assignments`/`assignment_templates`, `code_executions`, `achievements`/`notifications`, `audit_log`.

Маршруты фронтенда: `/`, `/chat`, `/code`, `/tasks`, `/tasks/:taskId`, `/classrooms`, `/classrooms/:id`, `/classrooms/:id/gradebook`, `/assignments`, `/dashboard`, `/profile`, `/teacher/tasks`, `/teacher/students`, `/admin`, `/login`, `/register`.

Бэкенд-группы API: auth, users, chat, code, tasks, classrooms, teacher, admin, engagement + WebSocket `/api/v1/chat/ws/{session_id}`.

### Твой первый порядок действий

1. `git checkout sprint/42-learning-loop && git status` — убедись, что дерево чистое и на нужной ветке.
2. Прочитай `docs/RULES.md` (разделы 3–12) и `TODO_V0.5.md` §5 (спринт 42, задача S42-006).
3. Прочитай `docs/reports/sprint-42/STEP-05_RECOMMENDED_TASKS.md` — это формат отчёта и принятые в спринте решения (особенно разделы 4–6).
4. Изучи путь сообщения в чате: `frontend/src/lib/chatSocket.ts` → `backend/app/api/websocket.py` → `backend/app/services/chat_service.py` → `app/services/llm/prompt_builder.py`.
5. Реализуй S42-006, покрой тестами (backend + frontend + e2e), обнови документацию, напиши `STEP-06_*.md`, закоммить и запушь.

Если что-то в задаче или в плане выглядит спорным — сначала доведи задачу до конца по плану, а расхождения опиши в разделе 4 отчёта («Проблемы и отклонения») и в `TODO_V0.5.md` §12 (журнал плана). Не задавай уточняющих вопросов по мелочам: по плану и RULES ответы однозначны, спорные места — фиксируй в отчёте.

---

## Что учтено в промпте (для меня, не для агента)

- **Точное состояние репозитория** проверено командами: ветка `sprint/42-learning-loop`, HEAD `83f29ae`, дерево чистое, задачи S42-001…005 закрыты, S42-006 — последняя.
- **Реальные узкие места S42-006** найдены чтением кода, а не предположены: `send_message`/`stream_reply` принимают только `content`; метаданные сообщения — `message_metadata` (JSONB) через `create_message(..., metadata=...)`; `build_messages` собирает `[system] + хвост истории + user`; два пути отправки (REST и WebSocket) — контекст надо провести через оба; `solution_template` и `test_cases[].expected_output` не должны попадать в контекст.
- **Окружение:** локальный venv отстаёт (fastapi 0.115.5 против 0.162.0) → контрактные тесты и матрица доступа падают и без новых правок (проверено `git stash`); рабочий путь — Docker-образ; Postgres/Redis уже подняты на 5434/6381.
- **Ожидаемые счётчики тестов** зафиксированы как точка отсчёта: backend 557+22, frontend 125 unit / 22 e2e — чтобы следующий агент сразу увидел регрессию.
- **Ловушки** из этого и прошлых шагов (CRLF-diff, порядок маршрутов FastAPI, ключ кэша, `TASK_PAYLOAD` без тегов, Monaco в jsdom, fake-таймеры) — вынесены в промпт, чтобы не повторялись.
- **Правила оформления** (один шаг = один коммит, отчёт по 7 разделам, обновление документации в том же коммите) — из `docs/RULES.md`, конкретизированы под S42-006.