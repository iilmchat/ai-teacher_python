# S37-001 — preflight раннера

**Дата:** 2026-11-12
**Спринт:** 37
**Статус:** завершено

## Проблема

Self-hosted runner может быть offline → job остаётся `queued`; а если онлайн,
но Docker/диск/checkout сломаны — job висит/падает поздно.

## Решение

- `scripts/ci/preflight.ps1` — первый шаг **всех 9 self-hosted job'ов** и
  `release.yml`:
  - Docker CLI + daemon (таймаут 25 с);
  - свободное место ≥ 2 ГБ (`CI_MIN_FREE_GB`);
  - workspace записываемый;
  - ключевые скрипты/файлы на месте.
- `scripts/ci/preflight.sh` — аналогичная проверка для GitFlic job'ов
  (workspace, файлы, диск); Docker daemon на Windows-агенте проверяет
  `preflight.ps1`.
- В `gitflic-ci.yaml` preflight добавлен в `before_script` или начало script
  всех job'ов (lint/test/frontend/security/gitleaks/release/e2e/docker).

## Ограничение

Если раннер **полностью offline**, GitHub не запускает job — preflight внутри
job'а не поможет; PR останется `queued` до возвращения раннера. Это
платформенное ограничение GitHub Free (нет hosted-job и branch protection,
`KI-023`). Документировано в `docs/CI.md` §14.1; после поднятия раннера job
стартует и preflight даёт красный/зелёный статус за десятки секунд.

## Проверки

- YAML всех workflow валиден (`test_ci_config.py`).
- `preflight.ps1` присутствует во всех 9 job'ах self-hosted и release.
- `preflight.sh` — во всех GitFlic job'ах (parity-скрипт).
