# Sprint 17: Engagement — Отчёт

**Период:** 2026-10-30
**Статус:** ✅ Завершён (email-уведомления — вне scope)

---

## 1. Файлы (+/-)

### Backend
```
+ app/models/engagement.py               — Achievement, UserAchievement, Notification
+ app/schemas/engagement.py              — достижения, статистика, уведомления
+ app/services/engagement_service.py     — правила, streak, уведомления
+ app/api/v1/engagement.py               — /me/achievements, /me/stats, /me/notifications
+ app/data/achievements.py               — справочник для тестов/seed
+ alembic/versions/20261030_0008_engagement.py
+ tests/test_engagement.py               — 7 тестов
~ app/models/__init__.py                 — регистрация моделей
~ app/main.py                            — роутер engagement
~ app/services/task_service.py           — выдача достижений после submit
~ app/services/classroom_service.py      — уведомления при назначении
~ tests/conftest.py                      — seed достижений после create_all
```

### Frontend
```
+ pages/DashboardPage.tsx                — прогресс-бар, streak, достижения, уведомления
+ test/dashboard.test.tsx                — 2 теста
~ App.tsx                                — маршрут /dashboard
~ layout/AppLayout.tsx                   — ссылка «Дашборд»
~ types/api.ts                           — типы вовлечения
~ i18n locales                           — раздел dashboard
```

### Документы
```
~ SPEC, ARCHITECTURE, USER_GUIDE, MANUAL_TESTING_GUIDE, RULES §11.16
~ README, docs/README, TODO_V0.2, RELEASES, CHANGELOG
+ docs/reports/sprint-17/SPRINT-17.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Backend тесты | 264 | **271** (+7) |
| Frontend unit | 74 | **76** (+2) |
| Backend покрытие | 80% | **80%** |

Новые тесты:

- backend: max_streak, первое достижение + уведомление, stats со серией,
  `/me/achievements` + `/me/stats`, уведомление о назначении и read,
  deadline ≤72 ч, чужое уведомление 404
- frontend: дашборд с серией/достижением/уведомлением, последние задачи

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend | `pytest -q` | **271 passed, 1 skipped** |
| Ruff / MyPy | `ruff check`, `mypy app` | 0 / 0 |
| Миграции | `alembic upgrade head`, `alembic check` | 008, без расхождений |
| Frontend | `pnpm typecheck && lint && test && build` | 76 passed, 0/0 |
| Бандл | `pnpm build` | entry 77.72 kB gzip |

---

## 4. Smoke

1. Решить первую задачу → в `/me/achievements` появляется `first_task`,
   на дашборде — уведомление достижения.
2. Решения три дня подряд → `streak_days=3`, достижение `streak_3`.
3. Решить все лёгкие задачи → `all_easy`.
4. Назначить задачу классу → у ученика уведомление `assignment`; при дедлайне
   ≤72 ч — ещё и `deadline` (при следующем GET).
5. Отметить уведомление прочитанным → `read_at` заполнен, unread уменьшается.
6. Чужое уведомление → 404.

---

## 5. Что не так

- **Email-уведомления не сделаны** — нужен SMTP-конфиг и фичефлаг; in-app
  закрывает DoD.
- **«Время в чате» не считается:** нет длительности сессии; отдаём число
  сессий и сообщений.
- Напоминание о дедлайне создаётся лениво при открытии уведомлений, а не
  планировщиком; если ученик не заходит, уведомления не появятся.
- Правило «все задачи сложности» считается по всем активным задачам, а не
  только назначенным классу.
- CI не стартовал (KI-014, биллинг) — мерж по временному разрешению.

---

## 6. Новые KI

Нет. Открыт только KI-014 (CI/биллинг).

---

## 7. Обоснование

- **Достижения — данные + правила в сервисе.** Справочник в БД (миграция),
  правила — код; добавление достижения не требует менять схему.
- **Оценка достижений после submit, но вне критического пути.** Ошибка выдачи
  логируется и не ломает ответ ученику.
- **Streak по датам UTC+3.** Школьники занимаются вечером; UTC-дата сдвигала бы
  серию. Дубли одного дня схлопываются.
- **Уведомления — in-app таблица.** Не нужен SMTP для DoD; email можно добавить
  позже, не меняя API.
- **Ленивые дедлайн-напоминания.** Планировщик — отдельная инфраструктура;
  проверка при чтении уведомлений достаточна для v0.2.0.
