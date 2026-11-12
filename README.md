# AI Teacher for Python

Интерактивный ассистент-учитель по Python для школьников 10–17 лет.
Помогает **думать**, а не списывать: три уровня помощи, безопасная песочница кода
и задачи с автопроверкой.

**Версия:** v0.5.0 · **© 2026 RuChating (iilmchat)**

[![CI](https://github.com/iilmchat/ai-teacher_python/actions/workflows/ci-selfhosted.yml/badge.svg?branch=main)](https://github.com/iilmchat/ai-teacher_python/actions/workflows/ci-selfhosted.yml)
— 7 job'ов: lint, test, frontend, security, e2e, docker, perf (self-hosted runner;
подробности — [docs/CI.md](docs/CI.md))

**Стек:** Python 3.12 + FastAPI · React 19 · PostgreSQL 17 + pgvector · Redis · DeepSeek / LM Studio · Docker Compose

---

## Возможности

- **Три уровня помощи** — базовый (наводящие вопросы, без готового кода),
  средний (объяснение + пример синтаксиса), продвинутый (полное решение с разбором).
- **Чат** со стримингом ответов (WebSocket) и REST-фолбэком; заголовки и
  закрепление сессий, остановка и повтор ответа, оценка 👍/👎, экспорт,
  шаблоны промптов, передача кода в песочницу.
- **Песочница кода** — RestrictedPython + изоляция процесса, белый список модулей,
  лимиты времени, памяти и вывода, ограничение параллельных запусков;
  линтер с ошибками безопасности и подсказками по стилю; `stdin`, история
  запусков, разбор кода, файлы `.py`, сниппеты и сохранение редактора.
- **Задачи** — 6 готовых, проверка по тест-кейсам с `input()`, подсказки по одной,
  подробный отчёт; проверка без траты попытки, история попыток, автосохранение
  черновика, поиск/фильтры и рекомендации; импорт/экспорт JSON/YAML, генерация
  через LLM, теги и версии.
- **Прогресс** — статусы, попытки, процент решения, разбивка по сложности;
  дашборд с серией дней, достижениями и уведомлениями.
- **Классы** — создание класса, вступление по коду, назначения задач с
  дедлайнами, матрица прогресса класса, «мои задания», объявления класса,
  массовое добавление/снятие учеников списком логинов.
- **Кабинет учителя** — CRUD задач с конструктором тест-кейсов, импорт файла,
  прогресс учеников, просмотр их работ и кода, комментарии к попыткам,
  drill-down «кто как справился» по назначению, перенос и снятие назначений.
- **Админка** — пользователи и роли, задачи, аналитика (DAU, попытки, сообщения,
  запуски), журнал аудита, выгрузка данных, модерация задач, сводка качества LLM
  и центр уведомлений с бейджем.
- **Аккаунт** — смена пароля с отзывом сессий, правка профиля, удаление
  аккаунта, выгрузка своих данных, настройки уведомлений и языка.
- **Надёжность LLM** — healthcheck провайдера, fallback «облако → локально»,
  метрики латентности и токенов, детектор готовых решений на базовом уровне.
- **Кэш и поиск** — справочники (`/chat/levels`, `/tasks/categories`, каталог)
  кэшируются в Redis на 60 с с инвалидацией при правке задач; поиск по своей
  истории чата — ILIKE всегда, семантический (pgvector) за флагом
  `RAG_ENABLED`.
- **Безопасность и эксплуатация** — CSP и security-заголовки nginx, gitleaks в
  CI, Dependabot, аудит зависимостей, бэкап/восстановление БД скриптами,
  встроенный retention-планировщик (KI-025) и метрики удалённых строк.
- **i18n** — русский и английский.

---

## Быстрый старт

```bash
git clone https://github.com/iilmchat/ai-teacher_python.git
cd ai-teacher_python
cp .env.example .env            # заполните SECRET_KEY, POSTGRES_PASSWORD, DEEPSEEK_API_KEY

docker compose up -d postgres redis

# Backend
cd backend
python -m venv venv && .\venv\Scripts\Activate.ps1   # Linux: source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_tasks.py
uvicorn app.main:app --reload --port 8000

# Frontend (в новом терминале)
cd frontend
pnpm install --allow-build=esbuild
pnpm dev
```

- Frontend: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8000/api/v1/health> · Swagger: <http://127.0.0.1:8000/api/docs>

Подробно, с типичными ошибками — [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

> **Эксплуатация v0.2.0.** Бэкап БД: `bash scripts/backup.sh` (pg_dump через
> `docker exec`, gzip + sha256, retention 14 дней), восстановление —
> `bash scripts/restore.sh ... --create --verify` (подробно — GETTING_STARTED
> §8). Аудит зависимостей и security-заголовки — [SECURITY_AUDIT](docs/reports/sprint-20/SECURITY_AUDIT.md).

---

## Статус

| Показатель | Значение |
|------------|----------|
| Версия | **v0.5.0** (2026-11-10), single-node (D-001) |
| Спринты | 1–48 завершены; v0.6.0 «Production Hardening» — спринты 34–36 закрыты, 37 — инженерия закрыта (GitFlic-гейт ждёт владельца), далее 38–41; v0.7.0 (49–52) — следующий |
| Тесты backend | **708 passed + 22 skip** в образе Python 3.12 (контейнерная изоляция без Docker-in-Docker); локально — **729 passed + 1 skip** |
| Миграции | Alembic head **022** (22 миграции) |
| Тесты frontend | **274** unit + **37** e2e (Playwright; 1 skip) |
| Покрытие | backend порог 70%, frontend 70/60/70% |
| Ruff / MyPy strict | 0 / 0 (101 файл) |
| TypeScript | strict, 0 ошибок |
| Размер фронтенда | entry **70.56 kB** gzip (лимит 80) |
| Зависимости | frontend 0 high/critical (1 moderate); Python 0 блокирующих |

---

## Документация

Навигация: [docs/README.md](docs/README.md)

- [docs/SPEC.md](docs/SPEC.md) — контракты API, схема БД, критерии приёмки
- [Design.md](Design.md) — исходный дизайн и решения
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — как устроено сейчас
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — инструкция ученику
- [docs/ASSISTANT_LEVELS.md](docs/ASSISTANT_LEVELS.md) — уровни помощи
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — развёртывание
- [docs/MANUAL_TESTING_GUIDE.md](docs/MANUAL_TESTING_GUIDE.md) — приёмка
- [docs/LLM_EVAL.md](docs/LLM_EVAL.md) — оценка качества ответов LLM
- [docs/DESIGN_ADMIN_AND_OPS.md](docs/DESIGN_ADMIN_AND_OPS.md) — админка, LLMOps, FinOps
- [docs/PROMPT_CURRENT.md](docs/PROMPT_CURRENT.md) — актуальные инструкции ассистента
- [docs/RULES.md](docs/RULES.md) — правила разработки
- [docs/RELEASES.md](docs/RELEASES.md) · [docs/CHANGELOG.md](docs/CHANGELOG.md) · [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)
- [docs/MONITORING.md](docs/MONITORING.md) — Prometheus/Grafana/Loki, алерты, Sentry и runbook
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — деплой/откат, инциденты, бэкап и восстановление
- [docs/SLO.md](docs/SLO.md) — SLI/SLO, error budget и burn-rate
- [docs/releases/v0.5.0.md](docs/releases/v0.5.0.md) — релиз-ноты v0.5.0 (single-node, D-001)
- [docs/reports/sprint-19/SPRINT-19.md](docs/reports/sprint-19/SPRINT-19.md) · [docs/reports/sprint-20/SPRINT-20.md](docs/reports/sprint-20/SPRINT-20.md)
- [UPGRADE.md](docs/UPGRADE.md) — обновление до v0.6.0 (auth & edge hardening,
  breaking refresh; архив v0.3.3 → v0.5.0);
- [TODO_V0.4.md](TODO_V0.4.md) — **текущий этап v0.6.0** «Production
  Hardening»: спринт 34 закрыт, спринты 35–41 по плану; multi-node вынесен
  за границы этапа;
- [TODO_V0.5.md](TODO_V0.5.md) — **завершённый этап v0.5.0** (спринты 42–48):
  аудит продукта и план задач `S42-001`…`S48-003`;
- [TODO_V0.7.md](TODO_V0.7.md) — этап v0.7.0 (спринты 49–52): траектории,
  доступность и PWA, httpOnly-cookie (`KI-027`), релиз;
  завершённые [TODO_V0.3.md](TODO_V0.3.md) — v0.3.0, [TODO_V0.2.md](TODO_V0.2.md) — v0.2.0
  и [TODO.md](TODO.md) — v0.1.0
- [SECURITY.md](SECURITY.md) — политика безопасности и контакт для уязвимостей;
  [LICENSE](LICENSE) — MIT

---

## Лицензия

MIT License · © 2026 RuChating (iilmchat) — [LICENSE](LICENSE)
