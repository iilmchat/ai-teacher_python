## Что и зачем

<!-- Одна логическая задача. Ссылки: S<N>-NNN / KI-NNN / ADR. -->

## Изменения

- [ ] Backend
- [ ] Frontend
- [ ] Инфраструктура/CI
- [ ] Документация/отчёт

## Проверки

<!-- Отметьте выполненные; для каждого пункта — команда или ссылка. -->

- [ ] `bash scripts/ci/gates.sh --fast` (или `pwsh scripts/ci/gates.ps1 -Fast`)
- [ ] `bash scripts/ci/gates.sh --full --ci` — перед мержем в `main`
- [ ] Backend: `pytest -q --cov=app --cov-fail-under=70`
- [ ] Frontend: `pnpm typecheck && pnpm lint && pnpm test:coverage`
- [ ] Миграции: `alembic upgrade head && alembic check`
- [ ] Вручную проверен сценарий из задачи
- [ ] Отчёт шага: `docs/reports/sprint-N/STEP-MM_*.md`

## Риски и откат

<!-- Ломающие изменения, миграции, откат, влияние на пилот. -->

## Чек-лист

- [ ] Нет секретов/PII в диффе
- [ ] Обновлены `CHANGELOG`/`RELEASES` при изменении поведения
- [ ] Новые ENV добавлены в `.env.example` (env-drift)
- [ ] CI зелёный
