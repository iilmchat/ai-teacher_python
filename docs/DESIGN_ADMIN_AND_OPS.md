# DESIGN_ADMIN_AND_OPS — админка, LLMOps, FinOps, guardrails

Документ для эксплуатации: что уже есть в админке, как следить за LLM и
стоимостью, какие ограничения действуют.

---

## 1. Админка (реализовано)

Доступ: роль `admin`. UI — `/admin`, API — `/api/v1/admin/*`.

### Эндпоинты

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/admin/users` | список пользователей: `role`, `search`, `skip`, `limit` |
| PATCH | `/admin/users/{id}` | смена `role` / `level` |
| DELETE | `/admin/users/{id}` | удаление пользователя со всеми данными |
| GET | `/admin/tasks` | все задачи, включая неактивные |
| GET | `/admin/tasks/review` | очередь модерации (S47-003): `source`, `difficulty`, `threshold`, `skip`, `limit` |
| POST | `/admin/tasks/{id}/moderate` | публикация, снятие, возврат в доработку (S47-003) |
| GET | `/admin/audit` | журнал аудита: `action`, `entity_type`, `actor_id`, пагинация (S47-001) |
| GET | `/admin/analytics` | сводка для дашборда |
| GET | `/admin/analytics/export` | выгрузка `users|tasks|attempts|activity` в CSV/JSON (S47-002) |
| GET | `/admin/quality` | сводка качества LLM: `by_level`, `top_problem_topics` (S47-004) |
| GET | `/admin/quality/export` | негативные оценки в CSV/JSON (S47-004) |

### Правила безопасности

- Все маршруты требуют `require_role(ADMIN)`.
- Нельзя понизить собственную роль (иначе можно потерять доступ) — 400.
- Нельзя удалить собственную учётную запись — 400.
- Повышение роли — только здесь; регистрация всегда создаёт `student` (KI-011).

### Что показывает дашборд

- пользователи: всего, по ролям, активные за 24 ч и 7 дней;
- задачи: всего/активные, по сложности;
- обучение: попытки, завершённые, среднее число попыток на задачу;
- активность: сессии чата, сообщения, запуски кода, неуспешные запуски;
- **LLM за 24 ч:** запросы, ошибки, средняя латентность, первый токен, токены,
  срабатывания fallback (S12-003);
- время формирования сводки.

Управление задачами (создание/правка) доступно роли `teacher` через
`/api/v1/tasks` (UI — `/teacher/tasks`).

### Экраны v0.5.0

| Экран | Что делает | Аудит |
|-------|------------|-------|
| `/admin/audit` | таблица «время, действие, актор, сущность, IP», фильтры по действию/типу сущности, пагинация, ссылки на задачу/класс | читает `audit_log` |
| `/admin` → «Выгрузка аналитики» | выбор набора (`users/tasks/attempts/activity`) и формата (CSV/JSON), скачивание через `api.download` | `analytics.exported` |
| `/admin/moderation` | очередь задач из LLM-генерации и импорта, метрики застревания, публикация/снятие/возврат в доработку | `task.moderated` |
| `/admin` → «Качество ответов» | негативные оценки, срезы по провайдеру/модели/уровню, проблемные темы, выгрузка | `quality.exported` |
| `/admin` → «Пользователи» | поиск, смена роли/уровня, удаление; защита от понижения/удаления себя | `user.updated`, `user.deleted` |

---

## 2. LLMOps

### Провайдеры

| Провайдер | Когда использовать | Ограничения |
|-----------|--------------------|-------------|
| DeepSeek (облако) | основной вариант | нужен ключ, платно, данные уходят наружу |
| LM Studio (локально) | приватность, офлайн-классы, fallback | нужна локальная модель (`LM_STUDIO_MODEL`), медленнее |

Переключение: `LLM_PROVIDER` в `.env` + перезапуск backend.
Резерв: `LLM_FALLBACK_PROVIDER=lm_studio` (S12-002); проверено на
`qwen/qwen3-4b-2507` (LM Studio, `127.0.0.1:8034`).

### Что логируется

- `app_starting` / `app_stopped` (structlog);
- `llm_stream_failed` — ошибка провайдера при стриминге;
- `llm_fallback_used` / `llm_all_providers_failed` — срабатывание резерва;
- `llm_unavailable` — 503 при недоступности провайдера;
- `level_policy_warning` — ответ `basic` с готовым кодом (коды, без текста);
- `ws_client_disconnected` — обрыв WebSocket;
- `domain_error` — доменные ошибки с путём и кодом.

Промпты и ответы **не** пишутся в логи: в них может быть код ученика.
Метрики вызовов (провайдер, модель, латентность, токены, статус) хранятся в
памяти процесса и доступны в `/admin/analytics` → `llm`.

### Наблюдаемость ассистента (S12-001…S12-003)

| Что | Где смотреть | Как трактовать |
|-----|--------------|----------------|
| Статус провайдера | `/api/v1/health` → `llm` | `not_configured` — нет ключа; `degraded` — ключ есть, API не отвечает |
| Fallback | `llm.fallback`, `llm.fallback_used` | рост = основной провайдер нестабилен |
| Латентность | `llm.last_hour/avg_latency_ms`, `p95` | p95 выше 5 с — деградация |
| Первый токен | `avg_first_token_ms` | > 2 с — чат кажется «зависшим» |
| Токены | `prompt/completion_tokens` | расход и стоимость (FinOps §3) |
| Нарушения политики | `metadata.warnings` в истории | рост `basic_*` — модель игнорирует промпт |

Healthcheck кэшируется на 60 с и не раскрывает ключ. Метрики обнуляются при
рестарте backend — постоянного хранилища метрик на этапе v0.2.0 нет.

### Чего пока нет (план)

- экспорт метрик в Prometheus/OpenTelemetry (сейчас — память процесса);
- алерты по доле ошибок и p95;
- версионирование промптов с UI выбора версии (сейчас — файл + метаданные ответа).

---

## 3. FinOps (стоимость)

### Текущие ограничители

| Параметр | Значение | Где |
|----------|----------|-----|
| `LLM_MAX_TOKENS` | 2000 на ответ | `app/config.py` |
| История в контексте | 20 сообщений | `prompt_builder.MAX_CONTEXT_MESSAGES` |
| Длина сообщения | 4000 символов | `MAX_MESSAGE_CHARS` |
| Размер кода в песочнице | 20 000 символов | `schemas/code.py` |
| Тест-кейсов за прогон | 20 | `test_runner.MAX_CASES_PER_RUN` |
| Таймаут песочницы | 5 c | `EXECUTOR_TIMEOUT` |
| Память песочницы | 128 МБ | `EXECUTOR_MEMORY_LIMIT` |
| Вывод песочницы | 100 000 символов | `EXECUTOR_MAX_OUTPUT` |
| Параллельных запусков | 4 | `EXECUTOR_MAX_CONCURRENCY` |

### Как считать расход

1. Оценка: `(длина промпта + длина ответа) / 1000 × цена_за_1K_токенов`.
2. Считать по фактическим `usage` из ответа провайдера (в логах пока не пишется).
3. Для класса из 30 учеников при ~10 вопросах в день — считать по недельной
   выборке, а не по пиковому дню.

### Практики экономии

- Базовый уровень — самый дешёвый по смыслу: короткие ответы.
- `LM_STUDIO` для занятий в классе снижает стоимость до нуля.
- Ограничение `max_tokens` не даёт «растекаться» ответу.
- Кэширование ответов на типовые вопросы — не реализовано; кандидат на улучшение.

---

## 4. Guardrails

### Защита исполнения кода

| Слой | Что делает |
|------|------------|
| AST-анализ | блокирует запрещённые импорты, `open/eval/exec`, dunder-атрибуты |
| RestrictedPython | ограниченный синтаксис, безопасные builtins |
| Белый список модулей | `math, random, datetime, collections, itertools, functools, string, re, statistics, decimal, fractions, json` |
| Изоляция процесса | отдельный интерпретатор, убивается по таймауту |
| Лимит памяти | `RLIMIT_AS` на POSIX, Job Object на Windows (S13-001/002) |
| Лимит параллелизма | не больше `EXECUTOR_MAX_CONCURRENCY`, при перегрузке 503 |
| Лимит вывода | `EXECUTOR_MAX_OUTPUT`, флаг `output_truncated` |
| Лимит размера | 20 000 символов кода |

Таблица лимитов: см. [ARCHITECTURE.md](ARCHITECTURE.md) §5. Признак
`memory_limit_enforced=false` означает, что ОС не дала поставить лимит
(например, процесс уже в чужом Job Object) — тогда действует таймаут;
это видно в ответе API и должно попадать в лог при разборе инцидентов.

### Защита данных

- Пароли — bcrypt, не логируются.
- JWT: access 30 мин, refresh 7 дней; при 401 клиент обновляет токен один раз.
- Чужой ресурс → 403 (чат, история запусков, задачи).
- В LLM не уходят email, username и id — только текст вопроса и история диалога.
- Frontend отдаётся nginx с security-заголовками (CSP, `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS) — S20-002.
  CSP разрешает только свой origin; единственное ослабление — `style-src
  'unsafe-inline'` (React/Tailwind/Monaco используют style-атрибуты).
  Заголовки не применяются к API-ответам только в том смысле, что им они не
  нужны; прокси `/api/` отдаёт их с того же server-блока.
- Секреты сканируются gitleaks (`.gitleaks.toml`, CI job `Security`).

### Ограничения, которые нужно знать

- Rate limiting работает через Redis и fail-open: при недоступном Redis
  запросы проходят с предупреждением (S11-003).
- Нет подтверждения email и восстановления пароля.
- Удаление пользователя необратимо (каскад по чатам, прогрессу, запускам).

---

## 5. Мониторинг и инциденты

### Что смотреть

1. `/api/v1/health` — статус приложения и LLM-провайдера (`llm.status`).
2. `docker compose ps` — health контейнеров Postgres/Redis/backend.
3. Логи backend: `llm_stream_failed`, `llm_fallback_used`, `domain_error`,
   частота 5xx.
4. Админка → LLM за 24 ч: латентность, токены, ошибки, fallback.
5. Админка → активность: падение числа сообщений/запусков может означать сбой.

### Типовые инциденты

| Симптом | Диагностика | Действие |
|---------|-------------|----------|
| Чат отвечает 503 | нет ключа или провайдер недоступен | проверить `DEEPSEEK_API_KEY`, при необходимости `LLM_PROVIDER=lm_studio` |
| Все запросы к API падают | БД недоступна | `docker compose ps`, логи postgres, порты (KI-001) |
| Порт занят, контейнер не поднялся | чужой сервис на 5432/6379 | сменить `POSTGRES_PORT`/`REDIS_PORT` |
| Медленные ответы | слишком длинная история | уменьшить `MAX_CONTEXT_MESSAGES`, проверить провайдера |
| Код «съел» CPU | бесконечный цикл | таймаут убивает процесс, проверить логи |

---

## 6. Бэкапы и восстановление (S20-004)

Скрипты: `scripts/backup.sh`, `scripts/restore.sh` (bash, Git Bash на Windows).

### Что делает backup.sh

1. Проверяет, что контейнер `ai_teacher_postgres` запущен (иначе дамп уйдёт в
   чужую БД — KI-001).
2. `docker exec <container> pg_dump -U ai_teacher -d ai_teacher -Fc
   --no-owner --no-privileges | gzip` → `backups/<db>_<UTC>.dump.gz`.
3. Проверяет архив через `pg_restore -l`, пишет `.sha256`.
4. Retention: удаляет дампы этой БД старше `-r N` дней (по умолчанию 14).

Параметры: `-c CONTAINER`, `-d DB`, `-u USER`, `-o DIR`, `-r DAYS`; ENV:
`POSTGRES_CONTAINER`, `POSTGRES_DB`, `POSTGRES_USER`, `BACKUP_DIR`,
`BACKUP_RETENTION_DAYS`.

### Что делает restore.sh

- `-f FILE` — дамп, `-t DB` — целевая БД (по умолчанию
  `ai_teacher_restore_check`), `--create` — создать её, `--clean` — очистить
  объекты, `--verify` — напечатать число таблиц и строк.
- Защита: восстановление поверх рабочей БД (`POSTGRES_DB`) — только с
  `--force`; служебные `postgres`/`template0`/`template1` запрещены;
  подтверждение вводом `yes`, если не указан `-y`.
- `gzip -dc FILE | docker exec -i pg_restore ... --single-transaction`.

### Smoke-проверка

```bash
bash scripts/backup.sh -o backups
bash scripts/restore.sh -f backups/ai_teacher_<stamp>.dump.gz \
     -t ai_teacher_restore_check --create -y --verify
docker exec ai_teacher_postgres dropdb -U ai_teacher ai_teacher_restore_check
```

Проверено 2026-10-30 на dev-БД (14 таблиц): счётчики восстановленной БД
совпали с источником (users=5, tasks=6, chat_sessions=2, chat_messages=2,
code_executions=2), retention удалил тестовый бэкап старше 14 дней.
Детали и evidence — `docs/reports/sprint-20/SECURITY_AUDIT.md`.

### Ограничения

- Бэкапится только БД. Файлы вне БД (если появятся загрузки) и `.env` нужно
  хранить отдельно (секреты — в Vault/секретах CI).
- Расписания в репозитории нет: запуск вручную/через внешний cron или
  планировщик; для production — добавить регулярный job и off-site копию.
- Дампы содержат персональные данные (email) — хранить с ограниченным
  доступом, не коммитить (`backups/` в `.gitignore`).

---

## 7. Дорожная карта Ops

1. ~~Подключить rate limiting (KI-007)~~ — сделано в S11-003.
2. ~~Добавить e2e-тесты и прогон в CI (KI-012)~~ — сделано в S11-001/002.
3. Локальный bundle Monaco для офлайна (KI-013).
4. ~~Метрики: токены, латентность, ошибки провайдера — в админку и логи~~ —
   сделано в S12-001…003 (память процесса).
5. Автоматическое наполнение задачами при первом запуске (KI-010).
6. ~~Скрипты бэкапа/восстановления (S20-004)~~ — сделано в S20-004.
7. Автоматические бэкапы по расписанию + off-site копия — после v0.2.0.
8. Экспорт метрик в Prometheus/OTel и алерты — после v0.2.0.

---

## 10. Мониторинг и аудит (S25)

**Метрики.** `GET /metrics` (Prometheus text format) на том же процессе, без
авторизации — предназначен для внутренней сети: nginx отдаёт 404 на `/metrics`
и `/health/*`, поэтому наружу они не попадают. Собираются:

| Группа | Метрики |
|--------|---------|
| HTTP | `http_requests_total{method,path,status}`, `http_request_duration_seconds` (гистограмма) |
| Песочница | `sandbox_runs_total{mode,result}`, `sandbox_duration_seconds`, `sandbox_timeouts_total` |
| LLM | `llm_requests_total{provider,model,status}`, `llm_latency_seconds`, `llm_first_token_seconds`, `llm_tokens_total{provider,kind}`, `llm_fallbacks_total{primary}` |
| Кэш | `cache_hits_total`, `cache_misses_total`, `cache_sets_total`, `cache_invalidations_total`, `cache_errors_total` |
| Retention | `retention_runs_total{table,result}`, `retention_rows_deleted_total{table}` |
| БД | `db_pool_connections{state}`, `db_pool_size`, `db_up`, `redis_up` |
| Лимиты | `rate_limit_blocked_total{scope}` |
| Фоновые задачи | `scheduler_last_success_timestamp{job}` |
| Сборка | `app_build_info{version}`, `app_worker_info{pid}` |

LLM/кэш/retention — **события** (счётчики и гистограммы), поэтому корректно
складываются между воркерами. Prod запускается с `UVICORN_WORKERS=2` и общим
экспортёром:

```env
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus-multiproc
```

Каталог — tmpfs, чистит `docker-entrypoint.sh` перед стартом воркеров; в этом
режиме любая реплика отдаёт общий агрегат — `sum by (instance)` в Prometheus не
нужен. Пул БД — состояние процесса: `db_pool_connections` суммируется
(`livesum`), `db_pool_size` берётся максимумом; `db_up`/`redis_up` — минимумом
(деградация любого воркера видна алерту).

**Стек мониторинга (S35).** `docker-compose.monitoring.yml` (профиль
`monitoring`) поднимает Prometheus, Grafana, Loki и Promtail; порты слушают
`127.0.0.1`. Правила алертов и recording rules — `deploy/monitoring/`,
дашборды — `deploy/monitoring/grafana/dashboards/`. Валидация — `promtool`
(CI job **Monitoring config**). Детали и runbook — `docs/MONITORING.md`, SLO —
`docs/SLO.md`.

**Алерты:** 5xx rate > 5%, p95 HTTP > 2 с, backend/db/redis down, пул БД > 90%,
LLM error > 10%, LLM p95 > 30 с, fallback spike, таймауты/ошибки песочницы,
`RateLimitSpike`, `RetentionStale`, `BackupStale` (с S36).

**Логи.** JSON (`LOG_FORMAT=json`), каждая запись содержит `request_id`
(из `X-Request-ID`), `http_request` пишется на каждый запрос с длительностью.
`LOG_FORMAT=console` — для локальной разработки.

**Health.** Docker healthcheck и compose используют `/health/ready`
(БД + Redis), liveness — `/health/live`. `/api/v1/health` остаётся для
совместимости и показывает состояние LLM.

**Аудит.** `audit_log` (кто/что/над чем/IP/время) + `GET /api/v1/admin/audit`
с фильтрами и экран `/admin/audit` (S47-001, см. §14). Retention —
`RETENTION_AUDIT_LOG_DAYS` (365).

---

## 11. Экспорт данных и retention (S26)

**Экспорт аналитики.** `GET /api/v1/admin/analytics/export` — только admin.
Ответ потоковый (серверный курсор SQLAlchemy), поэтому большие выгрузки не
занимают память процесса. Лимит `EXPORT_MAX_ROWS` (100 000) защищает БД от
«выгрузить всё»; при обрезке в `audit_log` пишется `analytics.exported` с
параметрами. Даты — ISO 8601, CSV в UTF-8.

**Отчёт класса.** `GET /api/v1/classrooms/{id}/report` отдаёт CSV-матрицу
«ученик × задача» с overdue-флагом и итоговой строкой; доступ — владелец
класса/админ, действие аудируется.

**Retention.** Встроенный планировщик (KI-025) — `RETENTION_SCHEDULER_ENABLED`:
приложение раз в сутки в `RETENTION_SCHEDULER_AT` (UTC, по умолчанию 03:30)
само применяет `RETENTION_*_DAYS`. На время прогона берётся advisory-lock
PostgreSQL, поэтому при нескольких инстансах retention не выполнится дважды;
остановка приложения даёт доиграть текущий прогон. В production флаг включён в
`docker-compose.prod.yml`. Ручной запуск и `--dry-run` — через скрипт
`backend/scripts/apply_retention.py` (в контейнере:
`docker compose exec backend python scripts/apply_retention.py --dry-run`):

| Таблица | Настройка | По умолчанию |
|---------|-----------|--------------|
| `chat_messages` | `RETENTION_CHAT_MESSAGES_DAYS` | 90 |
| `code_executions` | `RETENTION_CODE_EXECUTIONS_DAYS` | 90 |
| `notifications` | `RETENTION_NOTIFICATIONS_DAYS` | 180 |
| `audit_log` | `RETENTION_AUDIT_LOG_DAYS` | 365 |

Cron на хосте — альтернатива планировщику (если приложение запускать без флага;
пример, раз в сутки в 03:30):

```cron
30 3 * * * cd /opt/ai-teacher && docker compose exec -T backend \
  python scripts/apply_retention.py >> /var/log/ai-teacher/retention.log 2>&1
```

Каждый запуск пишет `retention_applied` с числом удалённых строк и увеличивает
Prometheus-счётчики `retention_rows_deleted_total` / `retention_runs_total`;
`--dry-run` ничего не удаляет и показывает объём.

**Удаление аккаунта.** Пользователь удаляет себя через `DELETE /auth/me`
(пароль обязателен): анонимизация + блокировка входа. Администратор по-прежнему
может удалить пользователя полностью (`DELETE /admin/users/{id}`). Политика
данных — `docs/PRIVACY.md`.

---

## 12. Модерация задач (S47-003)

**Область.** В очередь попадают только задачи с `tasks.source ∈ {generated,
imported}`: созданные через `POST /tasks/generate` и импортированные через
`POST /tasks/import` / `/tasks/import/file`. Задачи, созданные учителем вручную
(`POST /tasks`), получают `source='manual'` и публикуются сразу; модератор
может снять такую задачу с публикации, но не «вернуть в доработку».

**Метрики очереди** (`GET /admin/tasks/review`, порог `threshold=3`):

| Поле | Формула |
|------|---------|
| `attempts` | число засчитанных попыток из `task_attempts` |
| `passed_attempts` | из них успешных |
| `success_rate` | `passed_attempts / attempts` (0, если попыток нет) |
| `avg_attempts` | среднее число попыток на ученика с прогрессом |
| `students` | ученики с `attempts > 0` |
| `stuck_students` | ученики с `attempts > threshold` и `status != completed` |

Сортировка — «сначала проблемные»: больше `stuck_students`, затем ниже
`success_rate`, затем больше `attempts`, затем новые задачи. В карточке —
последние 5 попыток. Фильтры: `source`, `difficulty`, `threshold`, `skip`,
`limit`.

**Действия** (`POST /admin/tasks/{id}/moderate`):

- `publish` — `is_active=true`, `moderation_comment` очищается;
- `unpublish` — `is_active=false`, комментарий сохраняется;
- `return_to_revision` — `is_active=false`, комментарий 1…1000 символов
  сохраняется в `tasks.moderation_comment` и виден учителю в списке задач.

**Аудит.** `task.moderated` с `{action}` и (для возврата) `{comment_length}`;
текст комментария в журнал не пишется. Действия инвалидируют кэш каталога,
поэтому публикация/снятие сразу видны ученику.

**Процедура.** Раз в день (или перед публикацией класса) открыть
`/admin/moderation`, отфильтровать `generated` и `imported`, разобрать задачи
с высоким `stuck_students` и низким `success_rate`. Задача с плохим условием
или тестами возвращается в доработку с конкретным комментарием; после правки
учитель публикует её снова.

---

## 13. Сводка качества LLM (S47-004)

**Источник.** Оценки учеников `message_feedback` (`value = +1/−1`,
`comment` до 500 символов) и агрегаты `GET /admin/quality`:

- общее число оценок, доля негативных, срезы по провайдеру и модели;
- `by_level` — по уровню помощи из `chat_sessions.level` (пустой уровень —
  `unknown`);
- `top_problem_topics` — категории и теги задач, к которым относятся
  негативные оценки;
- связка с задачей — через `task_context.task_id` ближайшего предыдущего
  вопроса ученика (оценка привязана к ответу, контекст хранится в метаданных
  вопроса); без контекста или для удалённой задачи — группа «без задачи».

**Выгрузка** `GET /admin/quality/export?format=csv|json` — потоково, с
серверным курсором и `EXPORT_MAX_ROWS`; поля `message_id`, `comment`,
`provider`, `model`, `level`, `task_id`, `created_at`. Каждая выгрузка —
`quality.exported` в аудите.

**Как использовать.** Недельный разбор: сначала доля негативных по уровням,
затем топ проблемных тем. Негативные оценки с комментариями — вход для
LLM-as-judge (`docs/LLM_EVAL.md`); по результатам правятся промпты уровня или
формулировки задач. Оценки не влияют на выдачу ответов ученику автоматически и
не используются для дообучения модели. При малом числе оценок (< 30) срезы
носит сигнальный характер — не делайте выводов по одной теме.

---

## 14. Аудит и выгрузка данных в UI (S47-001/S47-002)

**Журнал аудита.** `/admin/audit` показывает `audit_log` (кто, что, над чем,
IP, время) с фильтрами `action`, `entity_type`, `actor_id` и пагинацией.
Новые записи сверху. Ссылки на задачу/класс ведут в соответствующий раздел.
Журнал доступен только admin; retention — `RETENTION_AUDIT_LOG_DAYS` (365).
Аудит пишется best-effort: ошибка записи не ломает основное действие.

**Выгрузка аналитики из UI.** На `/admin` выберите набор и формат:
`users`, `tasks`, `attempts`, `activity` × `csv|json`. Используется тот же
`GET /admin/analytics/export`, что и из API: потоковый ответ, лимит
`EXPORT_MAX_ROWS` (100 000), `X-Export-Limit`, `Content-Disposition:
attachment`, каждая выгрузка — `analytics.exported`.

**Разграничение выгрузок:**

| Кто | Что | Куда |
|-----|-----|------|
| ученик | свои профиль, прогресс, попытки, чаты, уведомления, достижения | `GET /users/me/export` (JSON) |
| учитель | отчёт/журнал своего класса | `GET /classrooms/{id}/report`, `/gradebook/csv` |
| админ | аналитика по платформе и негативные оценки LLM | `/admin/analytics/export`, `/admin/quality/export` |

Выгрузка содержит ПДн: файл не кэшируется, не публикуется через nginx как
статический ресурс и после скачивания живёт только на устройстве
пользователя. Перед передачей файла третьим лицам проверьте основание
(152-ФЗ, `docs/PRIVACY.md`).
