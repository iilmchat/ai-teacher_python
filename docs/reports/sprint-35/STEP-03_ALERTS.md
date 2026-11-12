# S35-003 — алерты как код

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Конфигурация

```
deploy/monitoring/prometheus/
├── prometheus.yml           # scrape backend:8000 каждые 15 с, rule_files
└── rules/
    ├── alerts.yml           # 14 алертов
    └── recording.yml        # 7 recording rules
```

### Алерты (`alerts.yml`)

| Группа | Алерты |
|--------|--------|
| HTTP | `High5xxRate` (>5%), `ApiLatencyHigh` (p95 > 2 с), `BackendDown`, `RateLimitSpike` |
| Зависимости | `DatabaseDown` (`db_up==0`), `RedisDown`, `DatabasePoolSaturated` (>90%) |
| LLM | `LLMErrorRateHigh` (>10%), `LLMSlowResponses` (p95 > 30 с), `LLMFallbackSpike` |
| Sandbox | `SandboxTimeoutsSpike`, `SandboxErrorRateHigh` (>20%) |
| Ops | `RetentionStale` (48 ч), `BackupStale` (метрика — S36-006) |

У каждого — `severity`, `summary`, `description`, `runbook_url` на
`docs/MONITORING.md#<anchor>`.

### Новые метрики

- `db_up`, `redis_up` — обновляются в `/health/ready` (`multiprocess_mode=min`);
- `rate_limit_blocked_total{scope}` — middleware и `is_user_limited`;
- `scheduler_last_success_timestamp{job="retention"}` — после успешного прогона;
- `app_worker_info{pid}` — S35-001.

## Валидация

```bash
# Linux/macOS
sh scripts/monitoring/validate_prometheus.sh
# Windows
pwsh -NoProfile -File ./scripts/monitoring/validate_prometheus.ps1
```

Скрипт использует локальный `promtool` или Docker
`prom/prometheus:v3.5.0`, затем проверяет Grafana JSON.

**Результат:**

```
SUCCESS: /etc/prometheus/prometheus.yml is valid prometheus config file syntax
SUCCESS: 14 rules found (alerts.yml)
SUCCESS: 7 rules found (recording.yml)
OK: 1 dashboard(s) валидны
```

CI: job **Monitoring config** добавлен в `ci.yml` и `ci-selfhosted.yml`
(запускается на PR/push; `release.yml` переиспользует self-hosted гейты).

## Тесты

`backend/tests/test_monitoring_config.py` (5 тестов): scrape backend,
обязательные алерты и `runbook_url`, выражения 5xx/DB/sandbox/LLM, recording
names, валидность Grafana JSON.
