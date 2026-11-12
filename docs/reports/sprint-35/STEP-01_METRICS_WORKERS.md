# S35-001 — метрики и 2 воркера

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Изменения

- `docker-compose.prod.yml`: backend запускается
  `uvicorn --workers ${UVICORN_WORKERS:-2}`; добавлены
  `PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus-multiproc` (tmpfs `1777`),
  `METRICS_ENABLED=true`.
- `backend/app/main.py`: каждая реплика публикует `app_worker_info{pid}`.
- `backend/app/core/metrics.py`: новый gauge `WORKER_INFO` (`multiprocess_mode=all`).
- `scripts/monitoring/check_metrics.py`: smoke-проверка `/metrics` —
  обязательное семейство, сумма HTTP, число воркеров по `app_worker_info`.
- `backend/tests/test_metrics_export.py`: агрегация двух процессов (counter +
  histogram), `app_worker_info`, отключение `/metrics` при
  `METRICS_ENABLED=false`.

## Почему `app_worker_info`

`process_start_time_seconds` не экспортируется в multiprocess-режиме (это
per-process метрика), поэтому число воркеров нельзя проверить по нему.
Каждый воркер в `lifespan` пишет `app_worker_info{pid=os.getpid()}` — gauge с
`multiprocess_mode=all` отдаёт все pid.

## Проверки

```
cd backend && pytest tests/test_metrics_export.py -q        # 15 passed
promtool (см. S35-003)                                      # SUCCESS
```

Реальный smoke с двумя воркерами (`uvicorn --workers 2`, порт 8012):

```
URL: http://127.0.0.1:8012/metrics
http_requests_total: 4
worker pids: 13892, 21068, 3352
OK: метрики присутствуют и агрегируются
```

Счётчики HTTP сложились с обоих воркеров; `app_worker_info` подтвердил
несколько процессов.

## Ограничение

В свежем процессе семейства с метками (`llm_requests_total`,
`sandbox_runs_total`) появляются только после первого события — это нормально
для Prometheus. Для проверки после нагрузки:
`--require llm_requests_total sandbox_runs_total`.
