# S37-003/004 — паритет CI и coverage-гейты

**Дата:** 2026-11-12
**Спринт:** 37
**Статус:** завершено

## Паритет

`scripts/ci/check_ci_parity.py` (stdlib) проверяет:

- GitHub `ci.yml` и `ci-selfhosted.yml`: `lint`, `test`, `frontend`,
  `security`;
- GitFlic: `lint`, `test`, `frontend`, `security-*`, `gitleaks`;
- backend coverage `--cov-fail-under=70` во всех трёх пайплайнах;
- frontend `test:coverage` в GitHub/GitFlic и `scripts/ci/frontend.sh`;
- preflight в 9 self-hosted job'ах + release + GitFlic;
- наличие `gates.sh`/`gates.ps1`.

Скрипт входит в job **Deploy config** (GitHub) и `lint` (GitFlic).

Вывод:

```
CI parity OK
  GitHub self-hosted jobs: deploy-config, docker, e2e, frontend, lint,
    monitoring, perf, security, test
  GitFlic jobs: docker, e2e, frontend, gitleaks, lint, release,
    security-backend, security-frontend, test
  coverage: backend 70%, frontend test:coverage
```

Различия оставлены только технические: в GitFlic security разнесён на три
job'а (pip-audit/pnpm audit/gitleaks), e2e и docker идут на Windows-агенте
(нужен Docker Desktop/Playwright).

## Coverage

| Платформа | Backend | Frontend |
|-----------|---------|----------|
| `ci.yml` | `--cov-fail-under=70` | `pnpm test:coverage` |
| `ci-selfhosted` (`backend-test.sh`) | `COVERAGE_MIN=70` | `frontend.sh` → `test:coverage` |
| `gitflic-ci.yaml` | `--cov-fail-under=70` | `pnpm test:coverage` |

Frontend-пороги — в `frontend/vite.config.ts` (lines/functions 70%,
branches/statements 60%). Локальный прогон: **lines 82.23%, branches 72.2%,
functions 85.29%, statements 82.31%** — с запасом.

## Тесты

`backend/tests/test_ci_config.py` (8 тестов): YAML, preflight в каждом job,
coverage-строки, обязательные job'ы, parity-скрипт, gates-скрипты.
