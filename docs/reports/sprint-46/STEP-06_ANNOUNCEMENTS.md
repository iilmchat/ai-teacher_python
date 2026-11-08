# Шаг 06 / спринт 46: объявления класса

**Дата:** 2026-11-08
**Спринт:** 46 (v0.5.0 «Learning Experience & Teaching Workflow»)
**Задача:** S46-006 — объявления класса и уведомления ученикам
**Статус:** реализовано

---

## 1. Что сделано

1. **Модель `ClassroomAnnouncement`** (`backend/app/models/classroom.py`):
   `classroom_id`, `author_id`, `title` (до 200), `body` (до 5000),
   `created_at`. Удаляется каскадом вместе с классом или автором.
2. **Миграция `021`** (`20261108_0021_classroom_announcements.py`):
   аддитивная таблица с индексом `(classroom_id, created_at)`.
3. **API:**
   - `GET /classrooms/{id}/announcements` — объявления класса, новые сверху;
     видят все участники (владелец и ученики), чужой учитель — 403.
   - `POST /classrooms/{id}/announcements` — публикация, только владелец;
     аудит `announcement.created`.
   - `DELETE /classrooms/{id}/announcements/{id}` — автор или владелец;
     аудит `announcement.deleted`; неизвестное объявление — 404.
   - `GET /me/announcements` — лента объявлений всех классов пользователя
     (для страницы «Мои задания»), один запрос без N+1.
4. **Уведомления.** `create_announcement_notifications` создаёт
   `Notification(type="announcement")` каждому ученику класса с payload
   `{classroom_id, classroom_name, announcement_id, title}`. Владелец
   (роль `owner`) уведомление не получает.
5. **UI:**
   - страница класса: блок «Объявления» — список с автором и датой, для
     владельца форма (тема + текст) и кнопка удаления у своих записей;
   - «Мои задания»: блок «Объявления» с названием класса, автором и датой;
   - дашборд: текст уведомления «Объявление класса «…»».
6. **Тесты.** Backend — 8 (видимость ученику и в ленте, уведомления всем
   ученикам, права, удаление, 404, чужие права, валидация, аудит,
   сортировка). Frontend — 4 (публикация, показ ученику без формы,
   удаление, лента в «Моих заданиях»).

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Backend тесты | `pytest tests/test_announcements.py` | **8 passed** |
| Backend тесты спринта | `pytest` (5 файлов S46) | **36 passed** |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | **0**, 99 файлов |
| Миграции | `alembic upgrade head` | **013 → 021**, OK |
| Frontend unit | `pnpm vitest run src/test/classroom-announcements.test.tsx` | **4 passed** |
| Frontend typecheck / lint | `pnpm typecheck`, `pnpm lint` | **0 / 0** |
| i18n | `node scripts/check-i18n.mjs` | **626 ключей, OK** |

---

## 3. Файлы

**Backend:**

- `backend/app/models/classroom.py` — `ClassroomAnnouncement`.
- `backend/app/models/__init__.py` — экспорт модели.
- `backend/alembic/versions/20261108_0021_classroom_announcements.py` —
  миграция 021.
- `backend/app/schemas/classroom.py` — `AnnouncementCreate`,
  `AnnouncementItem`, `AnnouncementList`.
- `backend/app/services/classroom_service.py` — `list_announcements`,
  `create_announcement`, `delete_announcement`, `announcements_for_user`.
- `backend/app/services/engagement_service.py` —
  `create_announcement_notifications`.
- `backend/app/api/v1/classrooms.py` — 4 эндпоинта объявлений.
- `backend/tests/test_announcements.py` — 8 тестов (новый файл).

**Frontend:**

- `frontend/src/pages/ClassroomDetailPage.tsx` — блок объявлений и форма.
- `frontend/src/pages/AssignmentsPage.tsx` — лента объявлений ученику.
- `frontend/src/types/api.ts` — `AnnouncementItem`, `AnnouncementList`.
- `frontend/src/test/classroom-announcements.test.tsx` — 4 теста (новый файл).
- `frontend/src/i18n/locales/ru.json`, `en.json` — `classrooms.announcement*`.

---

## 4. Проблемы и отклонения

- **`GET /me/announcements` сверх буквы задачи.** Без него лента на
  «Моих заданиях» требовала бы запрос на каждый класс ученика. Эндпоинт
  читает объявления только классов, где пользователь состоит.
- **Публикует только владелец.** В `ClassroomRole` пока нет роли
  со-учителя; поле `author_id` уже готово к её появлению, а удаление
  разрешено и автору, и владельцу.
- **Уведомления при удалении не отзываются.** Объявление могло быть
  прочитано; удаление ссылки из уведомления не требуется. Запись об
  удалении остаётся в аудите.
- **Лимит 200/5000 символов.** Тема и текст ограничены на уровне схемы,
  поэтому «полотно» не попадёт в БД и в уведомления.

---

## 5. Обоснование решений

| Вариант | Выбран | Почему |
|---------|--------|--------|
| Отдельная таблица объявлений | **Да** | Объявлений много, они живут дольше назначений и имеют автора. |
| Список новых сверху | **Да** | Важные объявления обычно свежие; пагинация не нужна при лимите 50. |
| Уведомление только ученикам | **Да** | Учитель сам опубликовал объявление — уведомлять его незачем. |
| Лента `/me/announcements` | **Да** | Один запрос на страницу вместо N по классам. |
| Удаление автором или владельцем | **Да** | Требование задачи; готово к со-учителям. |

---

## 6. Что дальше

Спринт 46 закрыт по коду. Далее: e2e «учитель → комментарий → ученик»,
документация (`SPEC`, `RULES`, `CHANGELOG`, `RELEASES`, `KNOWN_ISSUES`,
`TODO_V0.5`, README), итоговый отчёт `SPRINT-46.md`, PR и merge в `main`.
