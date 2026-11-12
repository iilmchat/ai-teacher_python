# S35-004 — Grafana как код

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Файлы

```
deploy/monitoring/grafana/
├── provisioning/datasources/prometheus.yml   # datasource uid=prometheus
├── provisioning/dashboards/dashboards.yml    # folder AI Teacher
└── dashboards/ai-teacher-overview.json       # дашборд
```

## Дашборд `AI Teacher — Overview`

Панели (uid `ai-teacher-overview`):

1. HTTP requests by status (`http_requests_total`).
2. 5xx ratio (`job:http_errors_5xx:ratio5m`).
3. Latency p95: health и API.
4. LLM latency p50/p95 по провайдеру.
5. LLM tokens per minute (prompt/completion).
6. LLM fallbacks per minute.
7. DB pool: `checked_out` vs `pool size`.
8. Sandbox runs per minute по mode/result.
9. Sandbox timeouts.
10. Rate limit blocked по scope.

Переменные: `route` (path), `provider`. Refresh 30 с, окно по умолчанию 6 ч.

## Проверка запуска

Стек поднят через
`docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml --profile monitoring`:

```
Grafana 11.6.0: /api/health → {"database":"ok","version":"11.6.0"}
API /api/search → папка "AI Teacher", дашборд "AI Teacher — Overview"
provisioning: datasource insert + "finished to provision dashboards" (без ошибок)
```

Loki 3.4.2 `/ready` → `ready`; Prometheus `/-/ready` → 200.
После проверки контейнеры и временные volumes мониторинга удалены.

## Валидация без Grafana

`scripts/monitoring/validate_dashboards.py` (JSON, title/uid/panels/targets) и
`tests/test_monitoring_config.py::test_grafana_dashboard_is_valid_and_has_panels`.

## Ограничение

Дашборд один (overview); отдельные FinOps/DB/ops-дашборды из TODO не заводились
— данные по ним есть на overview. Расширение — по мере эксплуатации, без
изменения инфраструктуры (provisioning читает каталог).
