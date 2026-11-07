# Шаг 04 / спринт 45: настройки уведомлений и языка

**Дата:** 2026-11-07  
**Спринт:** 45 (v0.5.0 «Learning Experience & Teaching Workflow»)  
**Задача:** S45-004 — уведомления и язык  
**Статус:** реализовано

---

## 1. Что сделано

1. **Ключи `users.settings`.** `language` (`ru`/`en`), `email_notifications`,
   `deadline_notifications`, `deadline_days` (1…14). Схема
   `UserSettingsUpdate` валидирует значения (422 на чужой язык или порог вне
   границ); `PATCH /users/me/settings` по-прежнему дополняет настройки, а не
   заменяет.
2. **Хелпер `notification_prefs.py`.** Сводит настройки с дефолтами:
   `ru`, оба уведомления включены, 3 дня. Отсутствие ключа = дефолт, поэтому
   миграция существующих пользователей не нужна; битые значения (например,
   неизвестный язык) откатываются к дефолту.
3. **Рассылки уважают настройки.** `_send_assignment_emails`
   (`classroom_service.py`) пропускает учеников с выключенными письмами;
   `sync_deadline_notifications` не создаёт напоминаний при выключенном флаге
   и использует `deadline_days` как окно; `scripts/notify_deadlines.py`
   фильтрует получателей по обоим флагам.
4. **UI профиля.** Карточка «Уведомления»: два переключателя, порог дней и
   язык. Каждое изменение сохраняется сразу; ошибка показывается рядом.
5. **Переключатель языка в шапке.** Меняет язык мгновенно
   (`i18n.changeLanguage`); авторизованному сохраняет выбор в профиле через
   `savePreferences`. При входе язык профиля применяется после `GET
   /auth/me`, поэтому выбор переживает смену устройства.
6. **Тесты.** Backend — 11: дефолты, откат неизвестного языка, границы
   `deadline_days`, сохранение/чтение, 422, частичный PATCH, выключенные
   напоминания, окно дней, фильтрация e-mail-рассылки, отправка включённым.
   Frontend — 6: дефолтное состояние, выключение писем, смена порога, ошибка
   сохранения, гостевой и авторизованный переключатель языка.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest tests/test_notification_settings.py` | **11 passed** |
| Backend регрессия | `pytest -k "assignment or notif or classroom or engagement"` | **29 passed** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 97 файлов |
| Frontend typecheck / lint | `pnpm typecheck`, `pnpm lint` | **0 / 0** |
| Frontend unit | `pnpm test -- --run notification-settings` | **6 passed** |
| i18n-аудит | `node scripts/check-i18n.mjs` | **OK**, 530 ключей |

---

## 3. Файлы

**Backend:**

- `backend/app/services/notification_prefs.py` — дефолты и сведение (новый).
- `backend/app/schemas/user.py` — новые ключи `UserSettingsUpdate`.
- `backend/app/api/v1/users.py` — обработка новых ключей.
- `backend/app/services/engagement_service.py` — окно и флаг дедлайнов.
- `backend/app/services/classroom_service.py` — фильтр e-mail-рассылки.
- `backend/scripts/notify_deadlines.py` — те же правила для CLI.
- `backend/tests/test_notification_settings.py` — 11 тестов (новый файл).

**Frontend:**

- `frontend/src/components/profile/NotificationSettingsCard.tsx` (новый).
- `frontend/src/components/layout/AppLayout.tsx` — переключатель языка.
- `frontend/src/pages/ProfilePage.tsx` — карточка.
- `frontend/src/store/auth.ts` — `savePreferences`, применение языка профиля.
- `frontend/src/types/api.ts` — `UiLanguage`, `UserPreferences`.
- `frontend/src/i18n/locales/ru.json`, `en.json` — `profile.notifications.*`,
  `language.*`.
- `frontend/src/test/notification-settings.test.tsx` — 6 тестов (новый файл).

---

## 4. Проблемы и отклонения

- **Плюральные ключи не используются.** В проекте нет формы `_one/_few`,
  а i18n-аудит требует одинаковый набор ключей в ru/en. Порог выводится
  одним ключом `daysValue` («{{count}} дн.» / «{{count}} days»).
- **Уведомление о дедлайне — in-app, письмо — отдельный флаг.** Выключение
  `deadline_notifications` убирает напоминание в приложении, а письма
  дополнительно зависят от `email_notifications`; так пользователь может
  оставить письма, но отключить шум в приложении.
- **Порог применяется к in-app напоминаниям.** CLI-скрипт использует общий
  горизонт из конфигурации (`NOTIFICATIONS_DEADLINE_HOURS`), но фильтрует
  получателей по флагам; персональный `deadline_days` действует в
  приложении.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Хранить настройки отдельными колонками | **`users.settings` JSONB** | Уже существующий закрытый список; миграция не нужна. |
| Требовать полный объект настроек | **Частичный PATCH** | Клиент меняет один ключ, не перезаписывая сниппеты/шаблон. |
| Применять язык только после перезагрузки | **Сразу + сохранить** | Требование шага: переключатель в шапке меняет интерфейс мгновенно. |
| Отдельная страница настроек | **Карточка профиля** | Все настройки аккаунта уже собраны там. |

---

## 6. Что дальше

Шаг 05: активные сессии, точечный отзыв и «выйти на всех устройствах».
