# MONITORING.md — мониторинг, алерты и Sentry (S35)

> Эксплуатационный гид по наблюдаемости v0.6.0: как поднять Prometheus,
> Grafana и Loki, где лежат дашборды и правила, как настроен Sentry и что
> делать при срабатывании алертов. SLO и error budget — `docs/SLO.md`.

---

## 1. Архитектура

```
[backend :8000 /metrics]  <-- scrape 15s --  [Prometheus :9090]
        |                                          |
        |-- JSON-логи --> [promtail] --> [Loki :3100]
        |
        +-- ошибки/трейсы (SENTRY_DSN) --> Sentry SaaS

[Grafana :3001] --provisioning--> Prometheus + Loki
```

- Prometheus, Grafana и Loki **не публикуются наружу**: порты слушают
  `127.0.0.1` (доступ через SSH-туннель).
- `/metrics` и `/health/*` по-прежнему закрыты nginx (404) — наружу не видны.
- Профиль `monitoring` **опционален**: prod работает без него.

---

## 2. Быстрый старт

```bash
# 1. Секреты (Grafana)
cp .env.example .env
# GRAFANA_ADMIN_PASSWORD=...

# 2. Prod + мониторинг
docker compose -f docker-compose.prod.yml \
  -f docker-compose.monitoring.yml --profile monitoring up -d

# 3. Проверки
curl -fsS http://127.0.0.1:9090/-/ready
curl -fsS http://127.0.0.1:3001/api/health
python scripts/monitoring/check_metrics.py \
  --url http://127.0.0.1:8000/metrics --expect-workers 2

# 4. Доступ к UI через SSH-туннель (пример)
ssh -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 user@vps
# Grafana: http://127.0.0.1:3001 (admin / GRAFANA_ADMIN_PASSWORD)
# Prometheus: http://127.0.0.1:9090
```

Без профиля мониторинга:

```bash
docker compose -f docker-compose.prod.yml up -d
```

---

## 3. Метрики

`GET :8000/metrics` (Prometheus text format, без авторизации, только
внутренняя сеть).

| Группа | Метрики |
|--------|---------|
| HTTP | `http_requests_total{method,path,status}`, `http_request_duration_seconds` |
| LLM | `llm_requests_total{provider,model,status}`, `llm_latency_seconds`, `llm_first_token_seconds`, `llm_tokens_total{provider,kind}`, `llm_fallbacks_total{primary}` |
| Песочница | `sandbox_runs_total{mode,result}`, `sandbox_duration_seconds`, `sandbox_timeouts_total{mode}` |
| БД/Redis | `db_pool_connections{state}`, `db_pool_size`, `db_up`, `redis_up` |
| Лимиты | `rate_limit_blocked_total{scope}` |
| Фоновые задачи | `retention_runs_total`, `retention_rows_deleted_total`, `scheduler_last_success_timestamp{job}` |
| Сборка/воркеры | `app_build_info{version}`, `app_worker_info{pid}` |

**Несколько воркеров.** Prod запускает uvicorn с `UVICORN_WORKERS=2`;
`PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus-multiproc` включает общий экспортёр:
любая реплика отдаёт агрегат, `sum by (instance)` не нужен. Каталог чистит
`docker-entrypoint.sh` до старта воркеров. В `/tmp` смонтирован tmpfs `1777`.

> Проверка: `python scripts/monitoring/check_metrics.py --expect-workers 2`
> читает `app_worker_info{pid=...}` и подтверждает, что видны оба процесса,
> а счётчики не потеряны.

---

## 4. Prometheus: правила и дашборды

```
deploy/monitoring/
├── prometheus/
│   ├── prometheus.yml          # scrape backend:8000 каждые 15 с
│   └── rules/
│       ├── alerts.yml          # алерты (см. §6)
│       └── recording.yml       # job:http_... для дашбордов/SLO
├── grafana/
│   ├── provisioning/           # datasource + dashboard provider
│   └── dashboards/
│       └── ai-teacher-overview.json
├── loki/loki-config.yml
└── promtail/promtail-config.yml
```

### Валидация

```bash
# Linux/macOS: promtool из PATH или Docker-образ
sh scripts/monitoring/validate_prometheus.sh

# Windows
pwsh scripts/monitoring/validate_prometheus.ps1

# только JSON дашбордов
python scripts/monitoring/validate_dashboards.py
```

CI: job **Monitoring config** (`ci-selfhosted.yml`, `ci.yml`) запускает
`promtool check config`, `promtool check rules` и проверку JSON. Дополнительно
`backend/tests/test_monitoring_config.py` проверяет обязательные алерты,
`runbook_url` и панели дашборда без Prometheus.

### Дашборд `AI Teacher — Overview`

Панели: HTTP по статусам, 5xx ratio, p95 latency (health/API), LLM latency
p50/p95, токены/мин, fallback/мин, пул БД, запуски и таймауты песочницы,
заблокированные лимиты. Переменные `route` и `provider`.

---

## 5. Логи и ротация

- Формат: JSON (`LOG_FORMAT=json`), поля `request_id`, `event`, `level`,
  `timestamp`; PII маскируется приложением (`mask_email`, см. RULES §11.49).
- Docker: `json-file`, `max-size: 10m`, `max-file: "3"` для всех сервисов
  (`docker-compose.prod.yml`, `docker-compose.monitoring.yml`).
- Loki: retention 7 дней (`limits_config.retention_period: 168h`).
- Promtail читает Docker-логи через `docker_sd_configs`; метки `container`,
  `service`, `level`, `event`.
- Не логировать: пароли, токены, email в открытом виде, тексты кода/промптов
  сверх необходимого.

**Ресурсы (жёсткие лимиты):**

| Сервис | RAM | CPU |
|--------|-----|-----|
| backend | 2 GB | 2.0 |
| postgres | 1 GB | 1.0 |
| redis | 128 MB | 0.5 |
| frontend | 256 MB | 0.5 |
| prometheus | 512 MB | 0.5 |
| grafana | 256 MB | 0.5 |
| loki | 256 MB | 0.5 |
| promtail | 128 MB | 0.25 |

---

## 6. Алерты и действия

Полный список — `deploy/monitoring/prometheus/rules/alerts.yml`. У каждого
алерта есть `severity`, `summary` и `runbook_url` на этот раздел.

| Алерт | Severity | Что делать |
|-------|----------|------------|
| `High5xxRate` | critical | §6.1 |
| `ApiLatencyHigh` | warning | §6.2 |
| `BackendDown` | critical | §6.3 |
| `RateLimitSpike` | warning | §6.4 |
| `DatabaseDown` | critical | §6.5 |
| `RedisDown` | warning | §6.6 |
| `DatabasePoolSaturated` | warning | §6.7 |
| `LLMErrorRateHigh` | warning | §6.8 |
| `LLMSlowResponses` | warning | §6.9 |
| `LLMFallbackSpike` | warning | §6.10 |
| `SandboxTimeoutsSpike` | warning | §6.11 |
| `SandboxErrorRateHigh` | warning | §6.12 |
| `RetentionStale` | warning | §6.13 |
| `BackupStale` | critical | §6.14 |

### 6.1 High5xxRate
1. Открыть Grafana → HTTP by status; найти путь с ошибками.
2. `docker compose logs --tail=200 backend` → `domain_error`/traceback.
3. `curl /health/ready`; проверить БД/Redis.
4. Если ошибки после деплоя — откат (S36) или повторный деплой.

### 6.2 ApiLatencyHigh
1. Сравнить p95 по путям; отделить LLM/песочницу (они медленные по природе).
2. Проверить `db_pool_connections`, медленные запросы, `sandbox_duration`.
3. При росте LLM-латентности — §6.9.

### 6.3 BackendDown
1. `docker compose ps`; `docker compose logs backend`.
2. Проверить `SECRET_KEY`/`DEBUG` (fail-fast S34-005) и миграции.
3. Рестарт: `docker compose restart backend`; если не поднимается — откат.

### 6.4 RateLimitSpike
1. `rate_limit_blocked_total` по scope: login → возможен брутфорс.
2. Проверить IP в логах (уже без PII), при абузе — блокировка на edge.
3. Убедиться, что `TRUSTED_PROXIES` настроен (иначе все клиенты — один IP).

### 6.5 DatabaseDown
1. `docker compose ps postgres`; `pg_isready`.
2. Диск/память (`docker stats`), логи postgres.
3. Рестарт; при повреждении — restore из бэкапа (S36).

### 6.6 RedisDown
1. `docker compose ps redis`; `redis-cli ping`.
2. Redis не критичен: лимиты и кэш работают fail-open, но кэш отключён.
3. Рестарт; проверить `maxmemory`/AOF.

### 6.7 DatabasePoolSaturated
1. Проверить долгие запросы (`pg_stat_activity`), утечки соединений.
2. Увеличить пул осознанно или устранить N+1.
3. Перезапуск backend сбрасывает пул.

### 6.8 LLMErrorRateHigh
1. Проверить ключ/квоту провайдера и `LLM_PROVIDER`.
2. Fallback настроен? `LLM_FALLBACK_PROVIDER`.
3. Временная деградация: сообщить пользователям, включить локальный провайдер.

### 6.9 LLMSlowResponses
1. Проверить статус провайдера и сеть.
2. Снизить `LLM_MAX_TOKENS`/уровень помощи при перегрузке.
3. Fallback на LM Studio.

### 6.10 LLMFallbackSpike
1. Основной провайдер нестабилен — проверить его статус.
2. Убедиться, что fallback отвечает и не исчерпал лимиты.
3. Не отключать fallback «чтобы не шумело».

### 6.11 SandboxTimeoutsSpike
1. Проверить `EXECUTOR_*` (таймаут, конкурентность, пул).
2. Нагрузка: `sandbox_runs_total` по mode; при перегрузе — ограничить.
3. Контейнерный режим: проверить Docker и образ runner.

### 6.12 SandboxErrorRateHigh
1. Логи `executor`/`sandbox`; частые `RestrictedFeatureError` — не ошибка.
2. Проверить пул интерпретаторов и память контейнера.
3. После релиза — откат при систематических сбоях.

### 6.13 RetentionStale
1. `RETENTION_SCHEDULER_ENABLED=true`, время `RETENTION_SCHEDULER_AT`.
2. Логи `retention_scheduler_*`; advisory-lock не занят.
3. Ручной прогон: `python backend/scripts/apply_retention.py`.

### 6.14 BackupStale
1. Проверить `ai-teacher-backup.timer` (systemd) и `backup.env`.
2. Логи последнего запуска; место на диске и доступ к S3.
3. Сделать бэкап вручную и проверить restore drill (S36-007).

---

## 7. Sentry

### Backend
`.env` / prod-compose:

```env
SENTRY_DSN=https://<key>@o<org>.ingest.sentry.io/<project>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05
SENTRY_RELEASE=0.6.0+<git-sha>
```

- Без DSN — no-op (`sentry_disabled` в логах).
- `send_default_pii=False`, `max_request_body_size="never"`.
- `before_send` вычищает: тело/query/cookies, `user.email/username/ip`,
  секретные заголовки, `extra` с кодом/промптами/токенами, строки кода в
  stacktrace; email/IP в сообщениях маскируются (`<email>`, `<ip>`).
- Ошибка инициализации Sentry не роняет старт.

### Frontend
DSN передаётся **в runtime** через `/config.js` (entrypoint контейнера пишет
файл из `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `APP_RELEASE`,
`SENTRY_TRACES_SAMPLE_RATE`). Альтернатива для сборки — `VITE_SENTRY_DSN`.

- `dataCollection`: userInfo/cookies/headers/bodies/query — выключены.
- `beforeSend` повторяет серверную политику (код, промпты, email, IP).
- CSP `connect-src` разрешает только `*.sentry.io` / `*.ingest.sentry.io`.

### Какие данные уходят
Только техническая ошибка: тип, сообщение (с маскированными email/IP),
stacktrace без исходных строк кода, теги окружения/релиза. Тексты решений,
промпты, email и IP не отправляются. Основание — безопасность и качество
(законный интерес), подробнее — `docs/PRIVACY.md` §7.

### Проверка
- Backend: временно вызвать исключение на dev/staging и убедиться, что в
  Sentry нет `request.data`, `user.email`, `user.ip_address`.
- Frontend: то же в консоли браузера; проверить отсутствие ошибок CSP.

---

## 8. Ограничения и troubleshooting

| Симптом | Причина/решение |
|---------|-----------------|
| `Target backend DOWN` | backend не стартовал (fail-fast SECRET_KEY?), неверная сеть compose |
| В метриках один pid | `PROMETHEUS_MULTIPROC_DIR` не задан или каталог не общий для воркеров |
| Все клиенты — один IP | `TRUSTED_PROXIES` не содержит адрес Caddy/nginx |
| Grafana пустая | datasource `prometheus` не поднялся; проверить `/api/health` |
| Нет логов в Loki | promtail не видит docker.sock; проверить mounts и `/ready` |
| Алерт `BackupStale` всегда | метрика появится в S36-006; до этого алерт не активен |
| Grafana/ Prometheus недоступны снаружи | так и задумано: порты на 127.0.0.1, используйте SSH-туннель |

**Ограничения одного узла.** Prometheus/Grafana/Loki живут на том же VPS:
падение узла останавливает и мониторинг. Для пилота это принято; off-site
метрики/логи и HA — после v0.6.0.
