# PERFORMANCE.md — нагрузка, лимиты и кэширование (S39)

> Как запускать нагрузочные тесты, какие сценарии и бюджеты действуют, что
> кэшируется и какие входные лимиты включены. Ёмкость узла — [CAPACITY.md](CAPACITY.md).
> SLO — [SLO.md](SLO.md), алерты — [MONITORING.md](MONITORING.md).

---

## 1. Нагрузочные сценарии

Раннер — `backend/scripts/load_test.py` (asyncio+httpx, открытый цикл,
фиксированный RPS). Nightly — `.github/workflows/perf-nightly.yml`
(self-hosted runner, 02:00 UTC), PR-smoke — job `Perf smoke` в CI.

| Сценарий | Эндпоинт | RPS | Бюджет p95 | Что проверяет |
|----------|----------|-----|------------|----------------|
| `health` | `GET /api/v1/health` | 20 | ≤ 300 мс | отдача API/LLM-health |
| `tasks` | `GET /api/v1/tasks` | 10 | ≤ 300 мс | чтение каталога под токеном |
| `submit` | `POST /api/v1/tasks/{id}/submit` | 5 | ≤ 2000 мс | песочница (самый тяжёлый) |

Дополнительно: error rate ≤ 1% в каждом сценарии; код выхода 1 при
нарушении. `all` запускает все три последовательно.

```bash
# локально (backend на 8000, seed включён)
python backend/scripts/load_test.py --scenario all --duration 25 \
  --json-out docs/reports/perf/load-test-local.json

# только health / только submit
python backend/scripts/load_test.py --scenario health --duration 10
python backend/scripts/load_test.py --scenario submit --rps 2 --duration 30
```

Ночной прогон пишет `docs/reports/perf/load-test-night.json`; сравнение с
baseline (`docs/reports/perf/baseline.json`) — `scripts/ci/compare_perf.py`:
рост p95 более чем на 20% от измеренного baseline или превышение бюджета —
красный job.

**Baseline:** пока `measured: null` — ждёт первого прогона на self-hosted
runner. Цифры не выдумываются; после прогона заполнить `measured` (p95, мс)
и зафиксировать окружение (CPU/RAM/workers).

Локальный smoke 2026-11-12 (dev, 1 воркер, Windows, после `alembic upgrade
head`; **не baseline**, другой runner/нагрузка):

| Сценарий | RPS | p50 | p95 | Ошибки | Вердикт |
|----------|-----|-----|-----|--------|---------|
| health | 20 | 5.6 мс | 8.6 мс | 0% | PASS |
| tasks | 10 | 16.2 мс | 88.5 мс | 0% | PASS |

Submit в локальном smoke не запускался (тяжёлый, ждёт nightly runner);
бюджет — 2000 мс p95.

---

## 2. N+1 и query-count

Аудит ключевых эндпоинтов:

| Эндпоинт | Запросы | Вывод |
|----------|---------|-------|
| `GET /admin/users` | count + список | N+1 нет (нет связей в ответе) |
| `GET /admin/audit` | count + страница | N+1 нет |
| `GET /me/notifications` | user, sync-deadline (join), список, unread | N+1 нет |
| `GET /admin/tasks/review` | очередь+агрегаты, recent-attempts (окно), count | N+1 нет (3–4 запроса независимо от строк) |

Регрессия ловится `backend/tests/test_query_counts.py`: число SELECT при
5 и 30–40 строках должно быть одинаковым. Если появится ленивая загрузка в
цикле — тест упадёт.

Индексы уже покрывают фильтры/сортировки: `idx_tasks_active_created`,
`idx_tasks_source_created`, `idx_audit_log_*`, `idx_notifications_*`,
`idx_progress_user`. Новых индексов в S39 не добавляли — не было
подтверждённой необходимости.

---

## 3. Кэширование

| Данные | Ключ | TTL | Инвалидация |
|--------|------|-----|-------------|
| Уровни чата | `cache:chat:levels` | 60 с | статический справочник |
| Категории задач | `cache:tasks:categories` | 60 с | любая мутация задач (`cache:tasks:*`) |
| Список задач | `cache:tasks:list:<user>:...` | 60 с | мутация задач/прогресса |
| Сводка качества | `cache:admin:quality` | 60 с | оценка/удаление feedback |

`GET /admin/quality` — тяжёлые агрегаты по `message_feedback`/чатам;
кэш на 60 с допустим для админского экрана, свежесть обеспечивается
инвалидацией при `set_feedback`/`remove_feedback`. `GET /tasks/recommended`
не кэшировали: результат сильно зависит от прогресса и меняется после
каждого submit; TTL 60 с дал бы ложные рекомендации, а инвалидация по
пользователю усложнила бы код без доказанной выгоды.

Fail-open: Redis недоступен → запросы работают без кэша (см. `cache.py`).
Метрики `cache_*_total` и hit-rate — в `/admin/analytics` и Grafana.

---

## 4. Входные лимиты и таймауты

| Уровень | Лимит | Где |
|---------|-------|-----|
| Тело запроса | 10 МБ | `request_body { max_size 10MB }` в Caddy; `client_max_body_size 10m` в nginx |
| Импорт задач | 10 МБ, JSON/YAML, UTF-8 | `MAX_UPLOAD_BYTES`; чтение `limit+1` байт; 413/415 |
| LLM/WS upstream | dial 5 с, response header 60 с, read 600 с | Caddy `transport http` |
| Стриминг | `flush_interval -1` | Caddy, без буферизации токенов |
| nginx API/WS | connect 5 с, send 60 с, read 3600 с | `frontend/nginx.conf` |
| Песочница | `EXECUTOR_TIMEOUT` (5 с), память 128 МБ | `config.py`, executor |

При превышении размера импорт возвращает **413**, неподдерживаемый тип —
**415**; тесты — `tests/test_teacher.py`.

---

## 5. Swagger/OpenAPI

`DOCS_ENABLED=false` в prod (S34-006): `/api/docs`, `/api/redoc`,
`/api/openapi.json` → 404, схема не строится на запрос. Caddy проксирует
`/api/*`, но маршрутов документации в backend нет; отдельного лимита на docs
не требуется. Тест — `tests/test_security_settings.py`.

---

## 6. Nightly workflow

`.github/workflows/perf-nightly.yml`:

1. preflight раннера (S37);
2. поднимает backend (`scripts/ci/perf.ps1`, echo provider, отдельный порт);
3. `load_test.py --scenario all --duration 30 --json-out ...`;
4. `compare_perf.py` — бюджеты + регресс > 20% (если baseline заполнен);
5. артефакт `load-test-night.json` (14 дней).

Реальный baseline будет добавлен после первого прогона на runner'е; до этого
ночной job проверяет только бюджеты p95/error rate.
