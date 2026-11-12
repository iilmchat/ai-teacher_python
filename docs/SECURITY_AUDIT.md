# SECURITY_AUDIT.md — аудит безопасности v0.6.0 (S38-001)

**Дата:** 2026-11-12
**Область:** backend, frontend, edge (Caddy), конфигурация деплоя, LLM-поток,
CI.
**Метод:** OWASP ASVS L1 self-assessment по коду и тестам; ручная проверка
конфигов; `ruff`/`mypy`/`pytest`; `pip-audit`/`pnpm audit`/`gitleaks` (CI);
`promtool`/`caddy validate`; чтение существующих отчётов спринтов 20/34–37.
**Детальный чек-лист:** [ASVS_L1.md](ASVS_L1.md). **DPIA:** [DPIA.md](DPIA.md).

---

## 1. Итог

- Открытых **Critical/High уязвимостей в приложении не найдено**.
- High `KI-023` — процессный риск CI (merge-gate), не уязвимость кода.
- Закрыты в v0.6.0: `KI-032` (`is_active` в RBAC), `KI-033` (refresh в теле),
  `KI-034` (XFF/trusted proxy), `KI-015/019/020/021` (зависимости/песочница).
- Принятые/отложенные: `KI-027` (JWT в localStorage, Low), `KI-035`
  (e-mail/reset, Med), `KI-036` (модерация LLM, Med).
- Для закрытого пилота — допустимо при выполнении `RUNBOOK.md`; для
  публичного production нужны отдельный VPS, юридическая проверка и
  закрытие отложенных пунктов.

---

## 2. Что проверено и чем подтверждено

| Область | Проверка | Доказательство |
|---------|----------|----------------|
| Аутентификация | bcrypt, JWT, rate limit, inactive | `tests/test_auth.py`, `test_rate_limit.py` |
| Сессии | `tv`/`jti`, отзыв, «выйти везде» | `tests/test_sessions.py`, `test_password_change.py` |
| RBAC/ownership | роли, классы, задачи, чат | `tests/test_access_matrix.py` |
| Ввод | Pydantic-схемы, лимиты | `tests/test_*_api.py`, 422-кейсы |
| Песочница | обходы RestrictedPython, память/таймаут | `test_executor.py`, `test_sandbox_*` |
| Секреты | gitleaks, `.env.example`, `_FILE` | CI Security, S38-002 |
| Edge | TLS, CSP/HSTS/headers, WS | `caddy validate`, `test_deploy_config.py` |
| Ошибки/логи | generic auth, PII-маскирование, Sentry | `test_sentry.py`, S35 |
| Данные | retention, экспорт, удаление | `test_scheduler.py`, `test_personal_export.py` |
| CI/поставка | digest, SBOM, audit, preflight | S36/S37, CI jobs |
| LLM-контекст | минимум данных, без идентификаторов | `prompt_builder.py`, `PRIVACY.md` §8 |

---

## 3. Изменения этого спринта

1. **ASVS L1** — чек-лист с доказательствами (`ASVS_L1.md`), без «галочек» без
   тестов.
2. **Секреты `_FILE`** — `POSTGRES_PASSWORD_FILE`, `SECRET_KEY_FILE`,
   `DEEPSEEK_API_KEY_FILE`, `SENTRY_DSN_FILE`, `SMTP_PASSWORD_FILE`
   (приоритет файла над ENV, fail-fast при ошибке чтения); пример Docker
   secrets — `deploy/docker-compose.secrets.example.yml`.
3. **Caddy headers** — CSP (с Monaco/Vite/Sentry), X-Frame-Options,
   X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP/CORP;
   HSTS только в TLS-блоке; HSTS убран из nginx.
4. **LLM guardrails** — защитные инструкции во всех системных промптах,
   фильтр prompt injection/токсичности/самоповреждения до сохранения и вызова
   LLM; `KI-036` на полную модерацию.
5. **Privacy** — раздел про LLM/Sentry, DPIA, статус `KI-035`.

---

## 4. Остаточные риски

| Риск | Severity | Мера/план |
|------|----------|-----------|
| XSS-кража JWT из localStorage, access не отзывается | Low (Accepted) | CSP, короткий TTL; cookie/BFF — `KI-027`, v0.7.0 |
| Нет e-mail-подтверждения/сброса пароля | Med | `KI-035`, v0.7.0; смена пароля изнутри есть |
| Неполная модерация ответов LLM для детей | Med | фильтр S38-004; `KI-036` — полноценный модератор |
| Merge-gate не активирован | High (процесс) | `KI-023`; preflight + ручной гейт |
| Один узел | High (инфраструктура) | отдельный VPS, бэкапы/DR, RUNBOOK |
| Бэкапы не всегда шифруются | Medium | `AGE_RECIPIENT` рекомендуется; ключ вне репозитория |
| Трансграничная передача DeepSeek | Medium | раскрытие в PRIVACY; локальный LM Studio |

---

## 5. Проверки приёмки

```bash
cd backend && pytest -q --cov=app --cov-fail-under=70
# 788 passed, 1 skipped; coverage 79.03%

python scripts/ci/check_ci_parity.py          # CI parity OK
pwsh scripts/ci/gitflic-gate.ps1              # обязательные job'ы
docker run ... caddy validate                 # Valid configuration
python backend/scripts/check_image_pins.py    # все образы по digest
```

`pip-audit`/`pnpm audit`/`gitleaks` — в CI job Security; на дату аудита
критичных находок нет (см. логи CI/спринт 20).

---

## 6. Рекомендации перед публичным production

1. Закрыть `KI-027` (httpOnly-cookie/BFF), `KI-035`, `KI-036`.
2. Активировать GitFlic merge-gate (`KI-023`) и проверить красным MR.
3. Обязательное `age`-шифрование всех бэкапов, ключ в менеджере секретов.
4. Внешний пентест (ASVS L2), нагрузочное тестирование, DR-учение на копии.
5. Юридическая проверка 152-ФЗ/согласий для детей; отдельный VPS.
