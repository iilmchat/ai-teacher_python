# Спринт 38 — Security & Privacy (ASVS L1, секреты, детская безопасность)

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening»
**Задачи:** S38-001…S38-007
**Статус:** завершён

---

## 1. Итоги

| Задача | Результат |
|--------|-----------|
| S38-001 | `ASVS_L1.md`, `SECURITY_AUDIT.md`, `DPIA.md` — доказательства, риски, вывод для пилота |
| S38-002 | `*_FILE`-секреты в config, Docker secrets override, deploy-валидация |
| S38-003 | Caddy: CSP (Monaco/Vite/Sentry), XFO, nosniff, Referrer/Permissions, COOP/CORP; HSTS только TLS; docs off |
| S38-004 | Защитные инструкции во всех промптах, фильтр injection/токсичности/self-harm, `KI-036` |
| S38-005 | PRIVACY §8 (LLM/Sentry/дети), статус `KI-035` (отложено) |
| S38-006 | SECURITY/RULES/LLM_EVAL/PROMPT_CURRENT, отчёты |
| S38-007 | CHANGELOG/RELEASES/TODO/README, commit/push |

---

## 2. Файлы

**Backend:**
- `app/config.py` — `*_FILE`, `LLM_GUARDRAILS_ENABLED`, model-validator;
- `app/services/llm/guardrails.py` — детектор и security-инструкции;
- `app/services/llm/prompt_builder.py` — security-блок во всех промптах;
- `app/services/chat_service.py` — фильтр в REST/WS/regenerate;
- `app/services/llm/prompts/versions.json` — basic 2, intermediate 3,
  advanced 2;
- тесты: `test_guardrails.py`, `test_secret_files.py`, `test_chat.py`
  (dynamic prompt_version), `test_deploy_config.py` (headers/secrets).

**Edge/конфиг:**
- `deploy/caddy/Caddyfile` — security headers/CSP/COOP/CORP;
- `frontend/nginx.conf` — HSTS убран (edge — Caddy);
- `docker-compose.prod.yml` — `*_FILE` passthrough, guardrails flag;
- `deploy/docker-compose.secrets.example.yml` — Docker secrets;
- `scripts/deploy.sh` — ENV или `*_FILE`;
- `.env.example`, `.env.prod.example`, `.gitignore`.

**Документация:**
- `docs/ASVS_L1.md`, `docs/SECURITY_AUDIT.md`, `docs/DPIA.md` (новые);
- `SECURITY.md`, `docs/PRIVACY.md` §8, `docs/RULES.md` §11.51,
  `docs/LLM_EVAL.md` §8, `docs/PROMPT_CURRENT.md`,
  `docs/KNOWN_ISSUES.md` (`KI-036`), `CHANGELOG`, `RELEASES`, `TODO_V0.4`,
  README; `docs/reports/sprint-38/`.

---

## 3. Проверки

```
cd backend && pytest -q --cov=app --cov-fail-under=70
# 817 passed, 1 skipped; coverage 79.18%

pytest tests/test_guardrails.py tests/test_secret_files.py \
  tests/test_prompts.py tests/test_deploy_config.py tests/test_chat.py
# 93 passed

cd frontend && pnpm test      # 279 passed
cd frontend && pnpm typecheck # OK
cd frontend && pnpm build && pnpm test:offline  # OK, no CDN
docker run ... caddy validate # Valid configuration
docker compose ... config --quiet (prod + secrets)  # OK
ruff / mypy                   # чисто
```

---

## 4. Безопасность и ограничения

- **ASVS L1:** открытых High в приложении нет; `KI-023` (merge-gate) —
  процессный High. `KI-027` (Low), `KI-035`/`KI-036` (Med) остаются.
- **Guardrails:** фильтр входа + защитные инструкции; ответы модели не
  модерируются полностью (`KI-036`), живой adversarial-прогон DeepSeek не
  выполнялся (нет ключа).
- **CSP/TLS:** конфигурация Caddy валидирована; реальный ACME/браузерный e2e —
  на пилоте (нет домена). Monaco/Vite проверены сборкой (`blob:` worker,
  inline styles разрешены).
- **Секреты:** `_FILE`/Docker secrets поддержаны; `age` для бэкапов
  рекомендуется, но не форсируется.

---

## 5. Следующий шаг

**S39 — Performance & Capacity**: nightly load, N+1/индексы, кэш, ёмкость;
затем S40 (DX/docs) и S41 (release v0.6.0).
