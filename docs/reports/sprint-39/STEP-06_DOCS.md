# S39-006 — документация и закрытие

**Дата:** 2026-11-12
**Спринт:** 39
**Статус:** завершено

## Обновлено

- `docs/PERFORMANCE.md` (новый): сценарии health 20 / tasks 10 / submit 5,
  бюджеты, baseline (`pending_runner` + локальный smoke), N+1, кэш, лимиты,
  nightly.
- `docs/CAPACITY.md` (новый): формулы, оценки, масштабирование, деградация.
- `docs/reports/perf/baseline.json` — заготовка baseline и правило регресса.
- `docs/ARCHITECTURE.md` — `cache:admin:quality`, §6.2.1 лимиты.
- `docs/RULES.md` §11.52 — лимиты 10 МБ, 413/415, таймауты, perf-регресс.
- `docs/CHANGELOG.md`, `docs/RELEASES.md`, `TODO_V0.4.md`, README.
- `.github/workflows/perf-nightly.yml` — preflight, 3 сценария,
  `compare_perf.py`, artifact.
- `scripts/ci/perf.ps1` — `-Scenario`, `-JsonOut`; `scripts/ci/compare_perf.py`.
- `backend/scripts/load_test.py` — RPS 20/10/5.

## Итог

Все инженерные задачи S39 закрыты. Реальный baseline и submit-замер — после
первого прогона на self-hosted runner; до этого nightly проверяет бюджеты и
пишет артефакт. Следующий шаг — S40 DX & Docs.
