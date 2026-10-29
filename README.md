# AI Teacher for Python

**Версия:** v0.1.0  
**Стек:** Python 3.12 + FastAPI | React 19 | PostgreSQL 17 + pgvector | Redis | LM Studio / DeepSeek | Docker Compose  
**© 2026 RuChating (iilmchat)**

---

## Описание

Интерактивный AI-ассистент для обучения школьников программированию на Python с тремя уровнями помощи:

- **Базовый** — подсказки и наводящие вопросы
- **Средний** — частичные объяснения с примерами
- **Продвинутый** — полные решения с разбором

## Функции

- Чат-бот с адаптивным уровнем помощи
- Генерация и проверка заданий
- Анализ кода с объяснением ошибок
- Прогресс-обучение (от простого к сложному)
- Административная панель для учителей

## Быстрый старт

### Требования

- Python 3.12+
- Node.js 20+
- Docker Desktop
- PostgreSQL 17
- Redis

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/ruchating/ai-teacher-python.git
cd ai-teacher-python

# Скопировать .env.example в .env
cp .env.example .env

# Запустить с помощью Docker Compose
docker compose up -d

# Или запустить локально
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
pnpm install
pnpm dev
```

### Доступ

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Документация

- [Design.md](Design.md) — архитектура проекта
- [TODO.md](TODO.md) — план разработки
- [docs/RULES.md](docs/RULES.md) — правила разработки
- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) — руководство по установке

## Разработка

### Статус проекта

🚧 В разработке — Спринт 1

### CI/CD

- [![CI](https://github.com/ruchating/ai-teacher-python/workflows/CI/badge.svg)](https://github.com/ruchating/ai-teacher-python/workflows/CI/badge.svg)
- [![Tests](https://img.shields.io/badge/tests-0%20passed-9cf)](https://img.shields.io/badge/tests-0%20passed-9cf)
- [![Coverage](https://img.shields.io/badge/coverage-0%25-green)](https://img.shields.io/badge/coverage-0%25-green)

## Лицензия

MIT License

---

**© 2026 RuChating (iilmchat)**
