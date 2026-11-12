# Спринт 35 — Observability & Monitoring

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening» (план `TODO_V0.4.md`)
**Задачи:** S35-001…S35-007
**Статус:** завершён

---

## 1. Итоги по задачам

| Задача | Результат |
|--------|-----------|
| S35-001 | Prod: `UVICORN_WORKERS=2`, `PROMETHEUS_MULTIPROC_DIR` (tmpfs), `app_worker_info{pid}`; реальный smoke с 2 воркерами |
| S35-002 | Sentry backend + frontend, runtime `/config.js`, PII-фильтр (`before_send`/`dataCollection`) |
| S35-003 | `deploy/monitoring/prometheus/`: 14 алертов + 7 recording rules; `promtool` в CI и локальных скриптах; новые метрики `db_up`, `redis_up`, `rate_limit_blocked_total`, `scheduler_last_success_timestamp` |
| S35-004 | Grafana provisioning + дашборд `AI Teacher — Overview`; проверен запуском |
| S35-005 | `mem_limit`/`cpus` для всех сервисов; Docker logs `json-file 10m×3` |
| S35-006 | `docs/SLO.md`: 99% доступность, ошибки <1%, health p95 <100 мс, error budget |
| S35-007 | `docs/MONITORING.md`, обновления RULES/PRIVACY/DESIGN/CI/CHANGELOG/RELEASES/TODO |

---

## 2. Файлы

**Backend:**
- `app/core/metrics.py` — `db_up`, `redis_up`, `rate_limit_blocked_total`,
  `scheduler_last_success_timestamp`, `app_worker_info`, helper'ы;
- `app/core/sentry.py` — новый модуль (init + PII-фильтр);
- `app/main.py` — `init_sentry()`, `worker_info_observed()`;
- `app/api/health.py` — gauges доступности;
- `app/core/rate_limiter.py` — счётчик блокировок;
- `app/services/scheduler.py` — timestamp успешного retention;
- `app/config.py` — `SENTRY_*`;
- `requirements.txt` — `sentry-sdk[fastapi]==2.74.0`;
- тесты: `test_metrics_export.py`, `test_sentry.py`,
  `test_monitoring_config.py`.

**Frontend:**
- `src/lib/sentry.ts`, `src/main.tsx`, `src/vite-env.d.ts`;
- `public/config.js`, `docker-entrypoint.d/40-runtime-config.sh`;
- `Dockerfile`, `nginx.conf` (CSP + `/config.js`);
- `package.json` (+`@sentry/react@11.12.0`);
- `src/test/sentry.test.ts`.

**Инфраструктура:**
- `deploy/monitoring/prometheus/{prometheus.yml,rules/alerts.yml,rules/recording.yml}`;
- `deploy/monitoring/grafana/**`;
- `deploy/monitoring/{loki,promtail}/*`;
- `docker-compose.monitoring.yml`;
- `docker-compose.prod.yml` (воркеры, метрики, Sentry, лимиты, логи);
- `scripts/monitoring/{check_metrics.py,validate_dashboards.py,validate_prometheus.sh,validate_prometheus.ps1}`;
- CI: job **Monitoring config** в `ci.yml`, `ci-selfhosted.yml`.

**Документация:** `docs/MONITORING.md`, `docs/SLO.md`, `docs/PRIVACY.md` §7,
`docs/RULES.md` §11.50, `docs/DESIGN_ADMIN_AND_OPS.md` §10, `docs/CI.md`,
`docs/CHANGELOG.md`, `docs/RELEASES.md`, `README.md`, `docs/README.md`,
`TODO_V0.4.md`, `.env.example`, отчёты `docs/reports/sprint-35/`.

---

## 3. Доказательства

### Метрики с двух воркеров

```
uvicorn app.main:app --workers 2 --port 8012
GET /health/live ×3, /health/ready
python scripts/monitoring/check_metrics.py --expect-workers 2 --min-http 4

URL: http://127.0.0.1:8012/metrics
http_requests_total: 4
worker pids: 13892, 21068, 3352
OK: метрики присутствуют и агрегируются
```

Плюс тест `test_multiprocess_counters_and_histograms_are_summed`: два
независимых процесса, counter sum и histogram count/sum складываются.

### Prometheus

```
promtool check config → SUCCESS
alerts.yml → SUCCESS: 14 rules found
recording.yml → SUCCESS: 7 rules found
```

### Grafana / Loki

```
Prometheus /-/ready → 200
Grafana /api/health → {"database":"ok","version":"11.6.0"}
Grafana /api/search → дашборд "AI Teacher — Overview" (uid ai-teacher-overview)
Loki /ready → ready
provisioning dashboards → "finished to provision dashboards" (без ошибок)
```

Контейнеры и временные volumes после проверки удалены.

### Лимиты

```
ai-teacher_python-prometheus-1  19.14MiB / 512MiB
```

`docker compose config --quiet` — валидно.

---

## 4. Тесты

```
cd backend && pytest -q                                    # 772 passed, 1 skipped
cd frontend && pnpm test                                   # 279 passed (47 files)
cd frontend && pnpm run typecheck && pnpm build            # OK
```

Entry-чанк после выноса Sentry — **71.37 kB gzip** (< 80 kB, RULES §3.2);
Sentry — отдельный чанк 57.34 kB gzip.

---

## 5. Ограничения и следующий шаг

- Дашборд один (overview); отдельные FinOps/DB/ops-панели — по мере
  эксплуатации.
- `BackupStale` ссылается на метрику, которая появится в S36-006.
- Алерты видны в Prometheus UI; Alertmanager не подключён (опционален для
  пилота).
- Source maps для frontend Sentry — задача релизного workflow (S36+).
- Далее по плану: **S36 — Registry, Deploy, TLS & Backup/DR**.
