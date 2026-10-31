# SPRINT-25.md — Observability & Audit Log (v0.3.0)

**Период:** 2026-10-31  
**Задачи:** S25-001…S25-005  
**Статус:** ✅ request-id, `/metrics`, liveness/readiness, аудит (миграция 011) и
админ-журнал реализованы и покрыты тестами

---

## 1. Файлы (+/-)

```
+ backend/app/core/logging.py            — structlog (JSON/console, contextvars)
+ backend/app/core/request_context.py    — X-Request-ID, контекст, лог запроса
+ backend/app/core/metrics.py            — Prometheus: HTTP/sandbox/LLM/кэш/пул БД
+ backend/app/api/health.py              — /health/live, /health/ready
+ backend/app/models/audit.py            — таблица audit_log
+ backend/alembic/versions/20261031_0011_audit_log.py
+ backend/app/schemas/audit.py           — AuditLogItem/ListResponse
+ backend/app/services/audit_service.py  — record_audit/list_audit
+ backend/tests/test_observability.py    — 13 тестов
~ backend/app/main.py                   — middlewares, /metrics, health router
~ backend/app/api/v1/admin.py           — аудит ролей/удаления, GET /admin/audit
~ backend/app/api/v1/tasks.py           — аудит create/update/delete
~ backend/app/api/v1/classrooms.py      — аудит класса/назначения
~ backend/app/core/executor.py          — метрики песочницы (S25-002)
~ backend/app/config.py                 — LOG_*, METRICS_*
~ backend/requirements.txt              — prometheus-client==0.26.0
~ backend/app/models/__init__.py        — AuditLog
~ frontend/nginx.conf                   — 404 на /metrics и /health/*
~ docker-compose.prod.yml               — healthcheck → /health/ready
~ docs: SPEC §15, DESIGN_ADMIN_AND_OPS §10, RULES §11.22, MANUAL_TESTING_GUIDE,
  CHANGELOG, RELEASES, TODO
```

---

## 2. Покрытие

13 тестов (`tests/test_observability.py`):

- **S25-001:** `X-Request-ID` возвращается как передан; генерируется `uuid4`;
  доступен сервисам через `current_request_id()`.
- **S25-002:** `/metrics` отдаёт `http_requests_total` с шаблоном пути и
  sandbox-метрики; вызов песочницы добавляет `sandbox_runs_total{mode="native"}`.
- **S25-003:** `/health/live` = 200; `/health/ready` отдаёт `checks` (database
  true, redis, llm_configured); `/api/v1/health` не сломан.
- **S25-004:** жизненный цикл задачи (`task.created/updated/deleted`) в журнале
  с actor_role/ip; смена роли (`user.updated`) и фильтры; 403 ученику;
  пагинация.

Непокрытое: реальные nginx-правила 404 для `/metrics` (проверяется в docker
smoke), алерты Prometheus (вне кода).

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | 0 |
| `mypy app` (strict) | 0 |
| Наблюдаемость/аудит | **13 passed** |
| Полный backend | **473 passed + 1 skipped** (см. RELEASES) |
| `alembic upgrade head` / `check` / `downgrade -1` + `upgrade` | OK (011) |

---

## 4. Smoke

1. `curl -i /health/live -H "X-Request-ID: trace-1"` → 200 + тот же заголовок.
2. `curl /metrics | grep http_requests_total` → счётчики по маршрутам.
3. `curl /health/ready` → 200 с `checks.database=true`.
4. `pytest -q tests/test_observability.py` → 13 passed.
5. Создать/изменить/удалить задачу учителем → `GET /admin/audit` под админом
   показывает три записи с IP и `actor_role=teacher`.

---

## 5. Что не так

1. **Метрики LLM/кэша/пула — gauge из счётчиков процесса.** На нескольких
   воркерах значения не суммируются; до общего экспортёра (v0.3.x) годятся для
   одного процесса (текущий compose поднимает один uvicorn).
2. **`audit_log` без retention.** Таблица будет расти; чистка — спринт 26
   (`RETENTION_AUDIT_DAYS`).
3. **Аудит — best-effort отдельным коммитом.** Падение процесса между действием
   и записью аудита может потерять запись; это осознанный компромисс, чтобы
   аудит никогда не блокировал действие.
4. **`/metrics` без авторизации** — по плану, для внутренней сети; nginx
   отдаёт 404, но при прямом доступе к порту 8000 метрики видны. В prod backend
   не публикуется наружу (compose: только внутри сети).

---

## 6. Новые KI

Нет. Ограничения (gauge-метрики, retention) запланированы в следующих спринтах.

---

## 7. Обоснование

1. **Отдельный реестр Prometheus.** Дефолтный registry тянет process/platform
   коллекторы и конфликтует при повторной регистрации — в тестах это ломает
   изоляцию. Свой `CollectorRegistry` + `reset_metrics()` в тестах.
2. **Мост, а не переписывание сервисов.** LLM/кэш уже считают метрики для
   `/admin/analytics`; дублировать счётчики в горячем пути ради Prometheus —
   лишняя связанность. Gauge при scrape — минимальное вмешательство.
3. **Readiness отдельно от liveness.** Падение Redis не должно перезапускать
   живой процесс; liveness не трогает зависимости.
4. **Аудит в той же сессии, но отдельным коммитом.** Репозитории коммитят
   действие сами; аудит после — единственный способ не менять их контракт.
   Ошибка аудита делает rollback только своей записи.
5. **`X-Request-ID` возвращается клиенту.** Это единственный способ связать
   жалобу пользователя с логами без доступа к серверу.
