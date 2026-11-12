# Спринт 37 — CI Gates & GitFlic

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening»
**Задачи:** S37-001…S37-006
**Статус:** инженерия завершена; активация GitFlic-гейта — владелец (KI-023)

---

## 1. Итоги

| Задача | Результат |
|--------|-----------|
| S37-001 | GitFlic-агент/required checks: доступ владельца нужен — подготовлены `gitflic-gate.ps1` и runbook, `KI-023` In Progress |
| S37-002 | Паритет GitHub ↔ GitFlic: `check_ci_parity.py`, одинаковые базовые job'ы/команды |
| S37-003 | Coverage gate: backend 70% в GitHub/GitFlic, frontend `test:coverage` |
| S37-004 | Preflight раннера в каждом self-hosted job и release; fail-fast по Docker/диску/workspace |
| S37-005 | `gates.sh`/`gates.ps1` + `make release-check` (fast/full/json) |
| S37-006 | `docs/CI.md` §10.3/§14/§15, `KNOWN_ISSUES`, отчёты |

---

## 2. Файлы

**CI/скрипты:**
- `scripts/ci/preflight.ps1`, `preflight.sh`
- `scripts/ci/check_ci_parity.py`
- `scripts/ci/gitflic-gate.ps1`
- `scripts/ci/gates.sh`, `gates.ps1`, `Makefile`
- `.github/workflows/ci-selfhosted.yml` (preflight ×9, parity, coverage)
- `.github/workflows/ci.yml` (coverage, frontend coverage, parity)
- `.github/workflows/release.yml` (preflight)
- `gitflic-ci.yaml` (preflight, parity, pins, i18n, coverage)
- `scripts/ci/backend-test.sh`, `scripts/ci/frontend.sh`

**Тесты/документация:**
- `backend/tests/test_ci_config.py`
- `docs/CI.md`, `docs/KNOWN_ISSUES.md`, `docs/CHANGELOG.md`,
  `docs/RELEASES.md`, `TODO_V0.4.md`
- `docs/reports/sprint-37/`

---

## 3. Проверки

```
python scripts/ci/check_ci_parity.py
# CI parity OK

pwsh -File scripts/ci/gitflic-gate.ps1
# обязательные job'ы найдены, чек-лист владельцу

bash scripts/ci/gates.sh --fast --json
# image-pins/ci-parity/backend-lint/mypy/frontend-typecheck/lint/unit — ok
# gates-report.json: ok=true

cd backend && pytest tests/test_ci_config.py -q   # 8 passed
cd backend && pytest -q --cov=app --cov-fail-under=70
# 788 passed, 1 skipped; coverage 79.03% (порог 70%)
frontend: pnpm test:coverage                      # 279 passed, lines 82.23%
```

YAML `ci.yml`, `ci-selfhosted.yml`, `release.yml`, `docker-publish.yml`,
`gitflic-ci.yaml` — валиден.

---

## 4. Ограничение (KI-023)

GitHub Free/private не даёт branch protection (403). GitFlic-гейт
подготовлен, но его включение требует токена/агента и доступа владельца к
настройкам проекта. Поэтому `KI-023` переведён в **In Progress**, не в
`Resolved`: без красного тестового MR нельзя утверждать, что merge
блокируется. После активации — закрыть с датой и платформой.

---

## 5. Следующий шаг

**S38 — Security & Privacy**: ASVS L1, DPIA, секреты, e-mail/LLM-safety
решения; затем S39 (performance), S40 (DX/docs), S41 (release v0.6.0).
