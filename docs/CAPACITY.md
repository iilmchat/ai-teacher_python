# CAPACITY.md — ёмкость одного узла (S39-004)

> Пилот — один VPS, 2 воркера uvicorn. Реальные замеры появятся после
> первого nightly-прогона (`docs/reports/perf/load-test-night.json`); ниже —
> методика, известные ограничения и предварительные оценки, помеченные как
> **оценка**, а не измерение.

## 1. Что измеряем

- RPS и p50/p95/p99 по `health`, `tasks`, `submit` (`load_test.py`);
- error rate (≤ 1%);
- `db_pool_connections`, `db_pool_size`, CPU/RAM (`docker stats`, Grafana);
- рост диска: PostgreSQL + логи + бэкапы (retention 14 дней).

## 2. Оценка до baseline

| Ресурс | Оценка | Комментарий |
|--------|--------|-------------|
| API health | ≥ 100 RPS | лёгкий эндпоинт, 2 воркера; бюджет 20 RPS с запасом |
| Каталог задач | ≥ 30 RPS | чтение + кэш 60 с; бюджет 10 RPS |
| Submit (песочница) | 3–5 RPS | доминирует запуск процессов; пул `EXECUTOR_POOL_SIZE=2`, `EXECUTOR_MAX_CONCURRENCY=4` |
| DB pool | 10 соединений/воркер | SQLAlchemy default; при 2 воркерах ~20; следить за `checked_out/size` |
| RAM | backend ≤ 2 ГБ, postgres ≤ 1 ГБ | лимиты S35; песочница 128 МБ на процесс |
| Диск | ~1–2 ГБ на 10k попыток + логи | зависит от кода/вывода; retention 90 дней |

Это **план**, не гарантия: после baseline заменить на измеренные значения и
указать дату/окружение.

## 3. Формулы и правила

- **Little's law:** `concurrency ≈ RPS × latency`. При submit 5 RPS и p95
  2 с нужно ~10 одновременных запросов; лимит `EXECUTOR_MAX_CONCURRENCY=4`
  и пул 2 — узкое место, поэтому submit ограничен 5 RPS.
- **Пул БД:** `db_pool_size` должен быть ≥ ожидаемой конкурентности
  запросов; при насыщении (>90%) — алерт `DatabasePoolSaturated`.
- **Песочница:** каждый submit/check запускает тест-кейсы; при росте p95
  сначала увеличивать пул/таймаут, но не выше лимитов RAM.
- **Диск:** `retention_*` + ротация Docker-логов 10 МБ × 3; бэкапы
  gzip/age, retention 14 дней.

## 4. Масштабирование (вне v0.6.0)

Multi-node вынесен за границы этапа. При переходе:
- 2+ backend за балансировщиком, sticky WS;
- общий Redis/Postgres, вынести песочницу на отдельный пул;
- Prometheus/Grafana — off-node или managed;
- пересмотреть SLO (≥ 99.5%) и лимиты.

## 5. Что делать при деградации

1. Смотреть `docs/MONITORING.md` §6: `ApiLatencyHigh`, `DatabasePoolSaturated`,
   `SandboxTimeoutsSpike`.
2. Проверить `docker stats`, `db_pool_connections`, логи slow-запросов.
3. Временно снизить `EXECUTOR_MAX_CONCURRENCY`/лимиты, перезапустить backend.
4. После инцидента — baseline/perf-прогон и запись в `docs/reports/perf/`.
