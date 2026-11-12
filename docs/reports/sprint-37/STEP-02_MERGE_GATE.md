# S37-002 — GitFlic merge-gate (KI-023)

**Дата:** 2026-11-12
**Спринт:** 37
**Статус:** инженерия завершена; активация — владелец

## Что сделано

- `scripts/ci/gitflic-gate.ps1`:
  - проверяет, что `gitflic-ci.yaml` содержит обязательные job'ы
    (`lint`, `test`, `frontend`, `security-backend`, `security-frontend`,
    `gitleaks`);
  - печатает пошаговую инструкцию настройки UI;
  - `-Json` для отчёта.
- `docs/CI.md`:
  - §10.3 обновлён — статус, скрипт, ссылка на §14.2;
  - §14.2 — полный merge-gate runbook (MR-пайплайн, защита `main`, required
    pipeline status, проверка красным MR).
- `docs/KNOWN_ISSUES.md` — `KI-023` переведён в **In Progress** с перечнем
  готового; закрытие — после фактического красного MR в GitFlic.

## Почему не Resolved

В окружении нет access token GitFlic и доступа владельца к настройкам
проекта, поэтому включить защиту ветки и подтвердить блокировку merge
технически невозможно. Имитировать гейт (поставить `Resolved` без проверки)
не стали — это противоречит аудиту.

## Как включить (владелец)

1. GitFlic → Settings → CI/CD: Enable Merge Request Pipeline (+ merge-result).
2. Branches → `main`: запрет force-push/прямых push, только MR.
3. Включить «Проверять статус последнего конвейера при слиянии».
4. Required: `lint`, `test`, `frontend`, `security-backend`,
   `security-frontend`, `gitleaks`.
5. Красный MR → Merge недоступен; зелёный → доступен. Зафиксировать дату в
   `KI-023` и закрыть.

## Проверки

```
pwsh -NoProfile -File scripts/ci/gitflic-gate.ps1
# Jobs: docker, e2e, frontend, gitleaks, lint, release,
#       security-backend, security-frontend, test
# чек-лист напечатан, exit 0
```
