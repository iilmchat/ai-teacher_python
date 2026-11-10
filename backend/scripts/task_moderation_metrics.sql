-- Метрики очереди модерации задач (S47-003, спайк).
--
-- Запуск (после alembic upgrade head):
--   psql "$DATABASE_URL" -v threshold=3 -v limit=50 \
--        -f backend/scripts/task_moderation_metrics.sql
--
-- Что считается:
--   attempts       — засчитанные попытки из task_attempts;
--   success_rate   — доля успешных попыток (passed / attempts), 0 если попыток нет;
--   avg_attempts   — среднее число попыток на ученика, у которого есть прогресс;
--   students       — число учеников с attempts > 0;
--   stuck_students — ученики с attempts > threshold и незавершённой задачей.
--
-- Очередь — только generated/imported (решение D-002/D-003): ручные задачи
-- учителя публикуются сразу. Порядок — «сначала проблемные»: больше
-- застрявших, затем ниже доля успеха, затем больше попыток.

WITH queue AS (
    SELECT id, title, description, difficulty, category, source, is_active,
           moderation_comment, created_at
    FROM tasks
    WHERE source IN ('generated', 'imported')
),
attempt_stats AS (
    SELECT ta.task_id,
           count(*)::int AS attempts,
           count(*) FILTER (WHERE ta.passed)::int AS passed_attempts
    FROM task_attempts ta
    JOIN queue q ON q.id = ta.task_id
    GROUP BY ta.task_id
),
progress_stats AS (
    SELECT p.task_id,
           count(*) FILTER (WHERE p.attempts > 0)::int AS students,
           count(*) FILTER (
               WHERE p.attempts > :threshold AND p.status <> 'completed'
           )::int AS stuck_students,
           avg(p.attempts) FILTER (WHERE p.attempts > 0)::float AS avg_attempts
    FROM user_task_progress p
    JOIN queue q ON q.id = p.task_id
    GROUP BY p.task_id
)
SELECT q.id,
       q.title,
       q.difficulty,
       q.source,
       q.is_active,
       q.moderation_comment,
       COALESCE(a.attempts, 0) AS attempts,
       CASE WHEN COALESCE(a.attempts, 0) = 0 THEN 0
            ELSE round(a.passed_attempts::numeric / a.attempts, 4)
       END AS success_rate,
       COALESCE(round(p.avg_attempts::numeric, 2), 0) AS avg_attempts,
       COALESCE(p.students, 0) AS students,
       COALESCE(p.stuck_students, 0) AS stuck_students
FROM queue q
LEFT JOIN attempt_stats a ON a.task_id = q.id
LEFT JOIN progress_stats p ON p.task_id = q.id
ORDER BY COALESCE(p.stuck_students, 0) DESC,
         CASE WHEN COALESCE(a.attempts, 0) = 0 THEN 1
              ELSE a.passed_attempts::numeric / a.attempts END ASC,
         COALESCE(a.attempts, 0) DESC,
         q.created_at DESC
LIMIT :limit;
