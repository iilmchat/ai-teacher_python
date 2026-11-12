# S38-006 — документация и закрытие

**Дата:** 2026-11-12
**Спринт:** 38
**Статус:** завершено

## Обновлено

- `SECURITY.md` — `*_FILE`/Docker secrets, детская безопасность LLM, ASVS/
  DPIA/AUDIT ссылки.
- `RULES.md` §11.51 — приоритет `*_FILE`, Docker secrets, guardrails, запрет
  отключать фильтр в prod.
- `docs/PRIVACY.md` — LLM-поток, Sentry, e-mail, DPIA.
- `docs/LLM_EVAL.md` §8 — adversarial-сценарии, ограничения, версии промптов.
- `docs/PROMPT_CURRENT.md` — версии basic 2/intermediate 3/advanced 2,
  security-блок, guardrails.
- `docs/ASVS_L1.md`, `docs/SECURITY_AUDIT.md`, `docs/DPIA.md` — новые.
- `docs/KNOWN_ISSUES.md` — `KI-036` (Med) + `KI-023` In Progress.
- `docs/CHANGELOG.md`, `docs/RELEASES.md`, `TODO_V0.4.md`, README.
- `docs/reports/sprint-38/`.

## i18n

Фильтр возвращает русские сообщения через `ValidationError.detail`; новых
UI-строк нет. Для англоязычного интерфейса сообщения фильтра стоит
локализовать в v0.7.0 (не блокер пилота).
