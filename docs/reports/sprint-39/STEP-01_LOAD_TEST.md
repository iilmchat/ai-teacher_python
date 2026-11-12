# S39-001 — нагрузочные сценарии и nightly

**Дата:** 2026-11-12
**Спринт:** 39
**Статус:** завершено (реальный baseline — после runner-прогона)

## Сценарии

`backend/scripts/load_test.py` (asyncio+httpx, открытый цикл):

| Сценарий | RPS | Бюджет p95 |
|----------|-----|------------|
| health | 20 | ≤ 300 мс |
| tasks | 10 | ≤ 300 мс |
| submit | 5 | ≤ 2000 мс |

Error rate ≤ 1%; `--scenario all` запускает последовательно.

## Nightly

`.github/workflows/perf-nightly.yml` (self-hosted, 02:00 UTC):

1. preflight раннера;
2. `scripts/ci/perf.ps1 -Scenario all -Duration 30 -JsonOut ...`;
3. `scripts/ci/compare_perf.py` — бюджеты + регресс > 20% к baseline;
4. артефакт `docs/reports/perf/load-test-night.json` (14 дней).

`docs/reports/perf/baseline.json` — статус `pending_runner`: зафиксированы
сценарии/бюджеты/правило регресса, измерения `null` до первого прогона (не
выдумываем цифры).

## Локальный smoke (dev, 1 воркер)

| Сценарий | RPS | p50 | p95 | Ошибки |
|----------|-----|-----|-----|--------|
| health | 20 | 5.6 мс | 8.6 мс | 0% |
| tasks | 10 | 16.2 мс | 88.5 мс | 0% |

Submit локально не запускался (тяжёлый; ночной runner). Это **не baseline** —
другое окружение; цифры зафиксированы в `docs/PERFORMANCE.md`.
