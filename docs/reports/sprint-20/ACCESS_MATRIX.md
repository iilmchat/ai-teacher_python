# ACCESS_MATRIX — спринт 20, S20-003 (endpoint × role + IDOR)

**Дата:** 2026-10-30 · **Статус:** ✅ выполнено (1 находка — исправлена Lead в этом же спринте)
**Задача:** S20-003 · **Исполнитель:** `qa-access`
**Код:** `backend/tests/test_access_matrix.py` (35 тестов) · **Приложение не менялось** этим аудитом (кроме фикса, который сделал Lead).

---

## 1. Итоги (TL;DR)

- Проверена матрица доступа для **всех** REST-роутеров v1 (auth, users, chat, code,
  tasks, admin, teacher, classrooms, engagement) + health/root + WebSocket.
- **RBAC работает:** аноним не проходит на защищённые маршруты; student → 403 на
  teacher/admin; teacher → 403 на admin; admin проходит и teacher-, и admin-маршруты.
- **IDOR не найден** ни по одному приватному ресурсу: чужие чат-сессии/сообщения,
  история запусков кода, уведомления, классы, назначения, прогресс класса,
  версии задач и профиль недоступны; списки показывают только свои объекты.
- **Найдена 1 уязвимость (low):** `GET /api/v1/tasks/{id}/hints/{index}` не требовал
  аутентификации и отдавал подсказки анонимно (200). Подтверждено на живом
  backend, передано Lead, **исправлено в рабочем дереве** (`_: CurrentUser`).
  Регрессионный тест `test_task_hints_require_auth` закрепляет поведение.
- Системное расхождение с формулировкой «аноним → 401»: FastAPI `HTTPBearer`
  при **отсутствии** заголовка отдаёт **403** (Not authenticated), а **401**
  только для невалидного/просроченного токена. Так ведут себя все защищённые
  маршруты; это конвенция фреймворка, а не дыра (см. §4). Матрица фиксирует
  фактический код и помечает ожидание 401/403.
- Тесты: `pytest tests/test_access_matrix.py -q` → **35 passed** (43.3 с).
  Полный прогон — см. §7.

---

## 2. Легенда и методика

| Код | Значение |
|---|---|
| `200/201/204` | маршрут разрешён роли (ожидание = факт) |
| `403` | роль/участие не позволяют (зависимость `require_role` или доменный `AccessDeniedError`) |
| `403*` | нет заголовка `Authorization` — `HTTPBearer` отдаёт 403 «Not authenticated» |
| `401` | невалидный/просроченный/неверного типа токен |
| `404` | объект не найден **или** намеренно скрыт от чужого пользователя |
| `422` | валидация тела/параметров |
| `close 4401/4404` | WebSocket: нет/битый токен → 4401, чужая сессия → 4404 |
| `CR` | code review: маршрут использует ту же зависимость (`CurrentUser`/`TeacherUser`/`AdminUser`) или owner-проверку сервиса, что и покрытая тестом строка; отдельный тест не дублировался |

Методика: интеграционные тесты `httpx.AsyncClient` + `ASGITransport` на реальной
PostgreSQL (conftest, транзакция с откатом), уникальные пользователи на тест;
роли `teacher`/`admin` поднимаются напрямую в БД (как в `test_admin.py`), токены
используются после смены роли. Плюс контрольные пробы `curl`/`Invoke-WebRequest`
на живом uvicorn (127.0.0.1:8000) для проверки кодов анонимных запросов и фикса.

Ссылки на тесты (`M…`) — из `backend/tests/test_access_matrix.py`; `E:` — уже
существующие наборы, которые покрывают строку (не дублировались).

---

## 3. Матрица endpoint × роль

### 3.1 Публичные (без токена, осознанно)

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `GET /api/v1/health` | 200 | 200 | 200 | 200 | M1 |
| `GET /` (root) | 200 | 200 | 200 | 200 | M1 (health) / code review |
| `POST /api/v1/auth/register` | 201 | 201 | 201 | 201 | E: test_auth.py |
| `POST /api/v1/auth/login` | 200 | 200 | 200 | 200 | E: test_auth.py |
| `GET /api/v1/chat/levels` | 200 | 200 | 200 | 200 | M1 |
| `GET /api/v1/users/levels` | 200 | 200 | 200 | 200 | M1 |
| `POST /api/v1/code/lint` | 200 | 200 | 200 | 200 | M1 |
| `GET /api/v1/code/limits` | 200 | 200 | 200 | 200 | M1 |

Обоснование: справочники уровней и лимитов песочницы не содержат приватных
данных; `lint` — чистая функция без БД/сети. Замечание: `code/lint` — публичный
CPU-потребитель; при злоупотреблении стоит добавить rate limit (не в скоупе S20-003).

### 3.2 Аутентификация и пользователи

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `POST /auth/refresh` | 200/401 по токену | 200 | 200 | 200 | E: test_auth.py |
| `POST /auth/logout` | 403* | 200 | 200 | 200 | CR (`get_current_user`) |
| `GET /auth/me` | 403* / 401 | 200 (свой) | 200 (свой) | 200 (свой) | M2, M3, M16 |
| `PATCH /auth/me` | 403* | 200 (свой) | 200 | 200 | CR (`get_current_active_user`) |
| `GET /users/me` | 403* | 200 | 200 | 200 | M2 |
| `PATCH /users/me/level` | 403* | 200 | 200 | 200 | CR (`CurrentUser`) |
| `GET /users/me/level` | 403* | 200 | 200 | 200 | CR (`CurrentUser`) |
| `POST /users/me/activity` | 403* | 200 | 200 | 200 | CR (`CurrentUser`) |
| `GET /users/{id}` | 403* | 403 | 403 | 200 | M4, M5, M16 |
| `PATCH /users/{id}/role` | 403* | 403 | 403 | 200 | M4, M5 |

Самостоятельная смена роли через `/auth/me` невозможна: `UserUpdate` не содержит
`role`; регистрация игнорирует присланную роль и всегда создаёт `student`
(SPEC §2, E: `test_tasks.py::test_register_ignores_requested_role`).

### 3.3 Чат (REST) и поиск

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `POST /chat/sessions` | 403* | 201 | 201 | 201 | M2, E: test_chat.py |
| `GET /chat/sessions` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | M2, M8, CR |
| `GET /chat/sessions/{id}` | 403* | своя 200 / чужая 403 / нет 404 | своя 200 / чужая 403 | своя 200 / чужая 403 | M8, E: test_chat.py, CR |
| `DELETE /chat/sessions/{id}` | 403* | своя 204 / чужая 403 | своя 204 / чужая 403 | своя 204 / чужая 403 | M8, E: test_chat.py, CR |
| `POST /chat/sessions/{id}/messages` | 403* | своя 201 / чужая 403 | своя 201 / чужая 403 | своя 201 / чужая 403 | M8, E: test_chat.py, CR |
| `GET /chat/search?q=` | 403* | 200 (только свои) | 200 (свои) | 200 (свои) | M2, M9 |
| `WS /chat/ws/{id}?token=` | close 4401 | своя — стрим / чужая — close 4404 | то же | то же | E: test_websocket.py; code review `websocket.py` |

ADMIN **не** обходит owner-проверку чата: `ChatService.get_session` сравнивает
`session.user_id` с текущим пользователем (admin не читает чужую переписку).
`/chat/search` фильтрует по `chat_sessions.user_id` в SQL — админ тоже видит
только свои сообщения.

### 3.4 Код (песочница)

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `POST /code/execute` | 403* | 200 | 200 | 200 | M2, E: test_code_api.py |
| `POST /code/analyze` | 403* | 200 | 200 | 200 | E: test_code_api.py |
| `GET /code/history` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | M2, M10 |
| `GET /code/history/{id}` | 403* | своя 200 / чужая 403 / нет 404 | своя 200 / чужая 403 | своя 200 / чужая 403 | M10, E: test_code_api.py |
| `POST /code/lint`, `GET /code/limits` | 200 | 200 | 200 | 200 | M1 |

### 3.5 Задачи

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `GET /tasks` | 403* | 200 | 200 | 200 | M2, E: test_tasks.py |
| `GET /tasks/progress` | 403* | 200 | 200 | 200 | M2 |
| `GET /tasks/stats` | 403* | 200 | 200 | 200 | E: test_tasks.py |
| `GET /tasks/categories` | 403* | 200 | 200 | 200 | E: test_tasks.py |
| `GET /tasks/{id}` | 403* | 200 | 200 | 200 | CR (`CurrentUser`); E: test_tasks.py |
| `GET /tasks/{id}/hints/{i}` | **403*** ✅ (было 200 — F1) | 200 | 200 | 200 | M17 |
| `POST /tasks/{id}/submit` | 403* | 200 | 200 | 200 | CR + E: test_tasks.py::test_submit_requires_auth |
| `POST /tasks` | 403* | 403 | 201 | 201 | M4, M6, M7 |
| `PATCH /tasks/{id}` | 403* | 403 | 200 | 200 | M4, M6 |
| `DELETE /tasks/{id}` | 403* | 403 | 204 | 204 | M4 (student), CR (teacher/admin) |
| `GET /tasks/export` | 403* | 403 | 200 | 200 | CR (`TeacherUser`) |
| `POST /tasks/import` | 403* | 403 | 200 | 200 | M4 |
| `POST /tasks/import/preview`, `/import/file` | 403* | 403 | 200 | 200 | CR (`TeacherUser`), M4 (роль) |
| `POST /tasks/generate` | 403* | 403 | 200/422 | 200/422 | CR (`TeacherUser`) |
| `GET /tasks/{id}/versions` | 403* | 403 | 200 | 200 | M4, M15 |
| `POST /tasks/{id}/versions/{v}/restore` | 403* | 403 | 200 | 200 | M4, M15 |

Каталог задач — **общий** (SPEC §2): любой teacher/admin может править/откатывать
любую задачу, `created_by` — только аудит. Это не IDOR: содержимое задач не
приватно и одинаково доступно всем авторизованным ученикам (документируется в M15).
Неактивные задачи исключены из каталога, но доступны по прямому id
(`GET /tasks/{id}`, hints) любому авторизованному — согласовано с поведением
карточки задачи; данных, скрытых от ученика, там нет.

### 3.6 Админка и кабинет учителя

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `GET /admin/users` | 403* | 403 | 403 | 200 | M4, M5, M7 |
| `PATCH /admin/users/{id}` | 403* | 403 | 403 | 200 | E: test_admin.py (200), CR (403) |
| `DELETE /admin/users/{id}` | 403* | 403 | 403 | 200 (не себя) | E: test_admin.py (200), CR (403) |
| `GET /admin/tasks` | 403* | 403 | 403 | 200 | M4, M5 |
| `GET /admin/analytics` | 403* | 403 | 403 | 200 | M4, M5, M7 |
| `GET /teacher/students` | 403* | 403 | 200 | 200 | M4, M6, M7 |
| `GET /teacher/students/{id}/progress` | 403* | 403 | 200 / не-ученик 404 | 200 / 404 | CR (`TeacherUser`); E: test_teacher.py |
| `GET /teacher/tasks` | 403* | 403 | 200 | 200 | M4, M6 |
| `GET /teacher/tasks/{id}` | 403* | 403 | 200 / нет 404 | 200 / 404 | M6 (200), CR (student 403), E: test_teacher.py |

Админ наследует teacher-права (`require_role` пропускает `ADMIN`), но **не**
получает доступ к чужим приватным объектам (`/users/{id}` — да, только это
знание админское; чаты/история/уведомления — нет).
`PATCH/DELETE /admin/users/{id}` запрещают понижение/удаление самого себя → 400
(E: `test_admin.py::test_admin_cannot_demote_self`,
`test_admin_cannot_delete_self`).

### 3.7 Классы и назначения

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `POST /classrooms` | 403* | 403 | 201 | 201 | M4 (student 403), E: test_classrooms.py (201) |
| `GET /classrooms` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | M2, M13 |
| `GET /classrooms/{id}` | 403* | участник 200 / нет 403 / нет класса 404 | участник 200 / не участник 403 | участник 200 / нет 403 | CR (`CurrentUser`), M13, M14 |
| `POST /classrooms/join` | 403* | 200 / неверный код 404 | 200 / 404 | 200 / 404 | CR (`CurrentUser`), E: test_classrooms.py |
| `POST /classrooms/{id}/join` | 403* | 200 / чужой класс 422 | 200 / 422 | 200 / 422 | CR (`CurrentUser` + `join_by_code`) |
| `DELETE /classrooms/{id}/members/{uid}` | 403* | 403 | владелец 204 / другой teacher 403 | владелец 204 / иначе 403 | CR (`TeacherUser`), E: test_classrooms.py (204), M14 (403) |
| `POST /classrooms/{id}/assignments` | 403* | 403 | владелец 201 / другой teacher 403 | владелец 201 / иначе 403 | E: test_classrooms.py::test_student_cannot_assign_task, M14 |
| `GET /classrooms/{id}/assignments` | 403* | участник 200 / нет 403 | участник 200 / нет 403 | участник 200 / нет 403 | M12, M13, CR |
| `GET /classrooms/{id}/progress` | 403* | 403 | владелец 200 / другой teacher 403 | владелец 200 / иначе 403 | M4, M14 |
| `GET /me/assignments` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | M2, M12 |

Ключевое: `class_progress` и управление участниками/назначениями проверяют
**владение**, а не только роль (RULES §11.15) — админ не-владелец получает 403.
Членство в классе — тоже проверка сервиса: admin не-участник не видит детали.

### 3.8 Вовлечение (`/me`)

| Endpoint | anon | student | teacher | admin | Evidence |
|---|---|---|---|---|---|
| `GET /me/achievements` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | CR (`CurrentUser`); нет IDOR-поверхности |
| `GET /me/stats` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | CR (`CurrentUser`); нет IDOR-поверхности |
| `GET /me/notifications` | 403* | 200 (свои) | 200 (свои) | 200 (свои) | M2, M11 |
| `POST /me/notifications/{id}/read` | 403* | своё 200 / чужое 404 / нет 404 | своё 200 / чужое 404 | своё 200 / чужое 404 | M2, M11 |

`/me/*` всегда строятся от `current_user.id` — параметра «чужой id» нет,
поэтому IDOR-поверхность отсутствует by construction.

---

## 4. Расхождение «аноним → 401» (не уязвимость)

Ожидание из брифа: аноним должен получать 401. Фактически без заголовка
`Authorization: Bearer …` FastAPI `HTTPBearer` (используется в
`get_current_user`) отдаёт **403** с `detail="Not authenticated"`; 401 приходит
только на **невалидный** токен. Проверено тестом
`M3 test_missing_credentials_403_and_invalid_token_401`:

```
GET /api/v1/auth/me                 -> 403  (нет заголовка)
GET /api/v1/auth/me (Bearer garbage)-> 401  (битый токен)
```

Это единообразно для всех защищённых маршрутов (анонимные пробы §3 дают 403).
Исправление «всегда 401» — одна общая настройка `HTTPBearer(auto_error=False)`
+ зависимость, меняющая коды на всём API; вне скоупа S20-003 (менять поведение
контракта без задачи нельзя). Для матрицы это зафиксировано как `403*`.

---

## 5. IDOR-проверки (сводка)

| Вектор | Атака | Результат | Evidence |
|---|---|---|---|
| Чат-сессия | чужой `GET/DELETE/POST messages` | 403; список чужого пуст; нет id → 404 | M8 |
| Чат-поиск (S19-005) | поиск строки из чужой переписки | `total=0`, выданы только свои session_id | M9 |
| История кода | чужой `GET history/{id}` | 403; список без чужой записи; нет id → 404 | M10 |
| Уведомления | чужой `POST …/read` | **404** (не раскрываем существование id, RULES §11.16.5); список без чужих | M11 |
| `/me/assignments` | второй ученик, не участник класса | пустой список; чужие assignments класса → 403 | M12 |
| Класс (чужой) | detail/assignments/progress | 403; `GET /classrooms` не показывает чужой класс | M13 |
| Класс (другой teacher) | detail/assignments/progress/assign/remove | 403 (только владелец управляет) | M14 |
| Версии задачи | student смотрит/откатывает | 403; другой teacher — 200 (общий каталог, by design) | M15 |
| Профиль | student/teacher читает `/users/{id}` | 403; admin — 200; свой — `/auth/me` 200 | M16 |
| Подсказки задачи | анонимный запрос | после фикса 403 (до — 200, F1); auth 200 | M17 |
| WebSocket | нет/битый токен; чужая сессия | close 4401; close 4404 | E: test_websocket.py + code review |

---

## 6. Находки

### F1 (LOW, ИСПРАВЛЕНО) — отсутствие auth на `GET /tasks/{id}/hints/{index}`

- **Было:** маршрут `get_hint` в `backend/app/api/v1/tasks.py` не имел
  auth-зависимости (в отличие от всех остальных `/tasks`-роутов). Анонимный
  запрос получал **200** и текст подсказки; 404 на несуществующую задачу
  позволял пробовать id на существование.
- **Репродукция (до фикса, живой backend):** задача
  `b0e25fb0-cfb6-4bbe-9be1-5d2504ae2c91`;
  `GET /api/v1/tasks/<id>/hints/0` без токена → `200`, с токеном → `200`;
  `GET /api/v1/tasks/<id>` без токена → `403` (несогласованность).
- **Оценка:** low — подсказки не PII и доступны любому авторизованному ученику в
  карточке задачи; мутаций нет. Но это нарушение контракта «все защищённые
  маршруты требуют auth» и лишняя поверхность для перебора task id.
- **Исправление (Lead, S20-003):** добавлен `_: CurrentUser` в `get_hint`
  (`tasks.py:250-257`), семантика `is_active` не менялась (карточка задачи тоже
  отдаёт неактивные задачи авторизованным).
- **Верификация после фикса (живой backend):**
  аноним → **403**; student с токеном → **200** (`{index, hint, total: 3}`);
  регрессия — `M17 test_task_hints_require_auth` (аноним 401/403 и никакого
  `hint` в теле, auth 200 и корректная подсказка).

### Прочее, что проверено и признано корректным

- Отсутствие заголовка → 403 (framework), невалидный токен → 401 (§4).
- Задачи — общий каталог teacher/admin; кросс-редактирование by design (§3.5).
- Неактивные задачи читаются по прямому id авторизованным — согласовано с
  `TaskDetail`; скрытых от ученика данных в них нет.
- Чужое уведомление → 404, а не 403 — осознанно против enumeration (RULES §11.16.5).
- JWT-роль читается из БД на каждый запрос: смена роли применяется сразу
  (не нужно перелогиниваться), отзыв пользователя также действует немедленно.
- Rate limiting в матрице выключен autouse-фикстурой (S11): это аудит
  авторизации, а не троттлинга; лимиты покрыты `test_rate_limit.py`.

---

## 7. Проверки

Команды — из `backend/`, Python `backend\venv\Scripts\python.exe`.

| Проверка | Команда | Результат |
|---|---|---|
| Матрица доступа | `python -m pytest tests/test_access_matrix.py -q` | **35 passed**, 43.29 с |
| Полный backend (после фикса F1) | `python -m pytest -q` | **341 passed, 1 skipped** (342 collected), 200.41 с |
| Ruff (новый файл) | `python -m ruff check tests/test_access_matrix.py` | **All checks passed** |
| Mypy | не применимо (mypy гоняется по `app`, тесты вне строгого режима) | — |

Состав тестов: 17 функций, 35 исполняемых кейсов (15 параметров
student→403, 5 teacher→403, анонимный/публичный/IDOR/positive-тесты).
Приложение не менялось; файл `test_access_matrix.py` и этот отчёт — единственные
артефакты задачи.

---

## 8. Ограничения аудита

- Проверялись REST-маршруты и WebSocket-авторизация; **не** проверялись:
  CORS-политика (в dev допускается), JWT-exp/refresh-сроки (есть в
  `test_auth.py`), rate limiting (S11), SQL-инъекции (SQLAlchemy ORM),
  конкурентные гонки (двойной submit/двойное чтение).
- Аудит через `ASGITransport` (без реального сетевого слоя) + точечные пробы
  на живом uvicorn; прокси/nginx и прод-конфиг не входили в скоуп.
- Матрица фиксирует текущую реализацию; при добавлении новых эндпоинтов
  `test_access_matrix.py` должен пополняться (правило RULES §4.1: каждый
  эндпоинт — с интеграционным тестом).
- Один и тот же аккаунт не может одновременно быть student и teacher в разных
  кейсах (используются отдельные пользователи на тест, транзакция откатывается).
