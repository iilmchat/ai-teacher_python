# Спринт 39 — Performance & Capacity

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening»
**Задачи:** S39-001…S39-006
**Статус:** завершён (реальный baseline — после первого runner-прогона)

---

## 1. Итоги

| Задача | Результат |
|--------|-----------|
| S39-001 | health 20 / tasks 10 / submit 5 RPS; nightly + `compare_perf.py`; baseline-заготовка |
| S39-002 | N+1 аудит 4 эндпоинтов; `test_query_counts.py` (рост SELECT = провал) |
| S39-003 | Кэш `/admin/quality` (TTL 60 c, инвалидация по feedback) |
| S39-004 | Caddy/nginx лимит 10 МБ, таймауты upstream, `MAX_UPLOAD_BYTES` (413/415) |
| S39-005 | `DOCS_ENABLED=false` проверен; docs не нагружают рантайм |
| S39-006 | `PERFORMANCE.md`, `CAPACITY.md`, RULES/ARCHITECTURE, отчёты |

---

## 2. Файлы

**Код/тесты:**
- `backend/scripts/load_test.py` — RPS 20/10/5;
- `backend/app/services/cache.py` — `quality_cache_key`, invalidation;
- `backend/app/api/v1/admin.py` — кэш `/admin/quality`;
- `backend/app/services/feedback_service.py` — инвалидация;
- `backend/app/api/v1/tasks.py` — лимит UploadFile (413/415);
- `backend/app/config.py` — `max_upload_bytes`;
- `backend/tests/test_query_counts.py`, `test_perf_config.py`,
  `test_cache.py`, `test_teacher.py`.

**Инфраструктура:**
- `.github/workflows/perf-nightly.yml`;
- `scripts/ci/perf.ps1`, `scripts/ci/compare_perf.py`;
- `deploy/caddy/Caddyfile`, `frontend/nginx.conf`;
- `docs/reports/perf/baseline.json`.

**Документация:**
- `docs/PERFORMANCE.md` (новый), `docs/CAPACITY.md` (новый),
  `docs/ARCHITECTURE.md`, `docs/RULES.md` §11.52,
  `docs/CHANGELOG.md`, `docs/RELEASES.md`, `TODO_V0.4.md`, README;
- `docs/reports/sprint-39/`.

---

## 3. Проверки

```
cd backend && pytest -q --cov=app --cov-fail-under=70
# 830 passed, 1 skipped; coverage 79.17%

pytest tests/test_query_counts.py tests/test_cache.py \
  tests/test_teacher.py tests/test_perf_config.py -q   # passed
docker run ... caddy validate                            # Valid configuration
docker compose ... config --quiet                        # OK
ruff / mypy                                              # чисто
```

Локальный smoke (dev, 1 воркер):

```
health 20 RPS: p50 5.6 мс, p95 8.6 мс, 0% ошибок
tasks  10 RPS: p50 16.2 мс, p95 88.5 мс, 0% ошибок
```

Submit не запускался локально (тяжёлый, ночной runner).

---

## 4. Ограничения

- **Baseline:** `docs/reports/perf/baseline.json` имеет `measured: null`;
  реальные p50/p95 на 1 реплике/2 воркерах появятся после nightly. До этого
  `compare_perf.py` проверяет только бюджеты.
- Submit 5 RPS на self-hosted runner может быть тяжёлым; при нестабильности
  снизить до 2 RPS (бюджет p95 тот же) и отразить в baseline.
- `GET /tasks/recommended` не кэширован осознанно (свежесть после submit).
- `pg_stat_statements`/`EXPLAIN` не включали — query-count тесты и индексы
  покрывают текущие риски; на пилоте можно снять топ-запросы.

---

## 5. Следующий шаг

**S40 — DX & Docs**: ADR, онбординг с нуля, CONTRIBUTING/CODEOWNERS,
шаблоны; затем S41 — release v0.6.0.
