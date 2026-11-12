# S35-006 — SLO и error budget

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Документ

`docs/SLO.md`:

- окно 30 дней, исключения (плановые работы до 30 мин);
- базовые SLO: доступность **≥ 99%**, ошибки **< 1%**, health p95 **< 100 мс**,
  API p95 ≤ 500 мс, submit p95 ≤ 2 с, успешность LLM ≥ 99%;
- PromQL для каждого SLI;
- error budget для 99% — **≈ 7 ч 12 мин/мес**, правила расходования
  (50/75/100%);
- связь алертов (`High5xxRate`, `DatabaseDown`, `LLMSlowResponses` и др.) с SLO;
- рекомендация burn-rate для перехода на SRE-режим;
- ограничения одного узла (почему 99%, а не 99.9%).

## Связь с алертами

`docs/MONITORING.md` §6 — runbook по каждому алерту;
`docs/DESIGN_ADMIN_AND_OPS.md` §10 ссылается на SLO и MONITORING без
дублирования таблиц.

## Проверки

Документ не требует автотестов; PromQL-выражения используют существующие
метрики (`http_requests_total`, `http_request_duration_seconds_bucket`,
`llm_requests_total`) и recording rules из S35-003.
