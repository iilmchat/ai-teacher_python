import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useTasksStore } from '@/store/tasks';
import type { TaskDifficulty } from '@/types/api';

const DIFFICULTIES: Array<TaskDifficulty | null> = [null, 'easy', 'medium', 'hard'];

export function TasksPage() {
  const { t } = useTranslation();
  const tasks = useTasksStore((state) => state.tasks);
  const progress = useTasksStore((state) => state.progress);
  const filters = useTasksStore((state) => state.filters);
  const loading = useTasksStore((state) => state.loading);
  const error = useTasksStore((state) => state.error);
  const loadTasks = useTasksStore((state) => state.loadTasks);
  const loadProgress = useTasksStore((state) => state.loadProgress);
  const setFilter = useTasksStore((state) => state.setFilter);

  useEffect(() => {
    void loadTasks();
    void loadProgress();
  }, [loadTasks, loadProgress, filters.difficulty]);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">{t('tasks.title')}</h1>
        <div className="flex gap-2" role="group" aria-label={t('tasks.filterDifficulty')}>
          {DIFFICULTIES.map((difficulty) => (
            <button
              key={difficulty ?? 'all'}
              type="button"
              aria-pressed={filters.difficulty === difficulty}
              onClick={() => setFilter({ difficulty })}
              className={`rounded-lg border px-3 py-1.5 text-xs ${
                filters.difficulty === difficulty
                  ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                  : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {difficulty ? t(`tasks.difficulty.${difficulty}`) : t('tasks.all')}
            </button>
          ))}
        </div>
      </header>

      {progress && (
        <Card>
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-slate-700">{t('progress.title')}</span>
            <span className="text-slate-600">
              {t('progress.summary', {
                completed: progress.completed,
                total: progress.total_tasks,
              })}
            </span>
          </div>
          <div
            className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-200"
            role="progressbar"
            aria-valuenow={progress.completion_rate}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={t('progress.title')}
          >
            <div
              className="h-full rounded-full bg-indigo-600 transition-all"
              style={{ width: `${progress.completion_rate}%` }}
            />
          </div>
          <dl className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
            {(['easy', 'medium', 'hard'] as TaskDifficulty[]).map((difficulty) => {
              const bucket = progress.by_difficulty[difficulty];
              return (
                <div key={difficulty} className="rounded-lg bg-slate-50 p-2">
                  <dt className="text-slate-500">{t(`tasks.difficulty.${difficulty}`)}</dt>
                  <dd className="font-semibold text-slate-800">
                    {bucket ? `${bucket.completed}/${bucket.total}` : '0/0'}
                  </dd>
                </div>
              );
            })}
          </dl>
        </Card>
      )}

      {error && <Alert tone="error">{error}</Alert>}
      {loading && <Spinner />}

      {!loading && tasks.length === 0 && (
        <Alert tone="info">{t('tasks.empty')}</Alert>
      )}

      <ul className="grid gap-3 sm:grid-cols-2">
        {tasks.map((task) => (
          <li key={task.id}>
            <Card className="h-full">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold text-slate-900">{task.title}</h2>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {t(`tasks.difficulty.${task.difficulty}`)}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {t('tasks.hintsCount', { count: task.hints_count })} ·{' '}
                {t(`tasks.status.${task.status}`)}
              </p>
              <Link to={`/tasks/${task.id}`} className="mt-3 inline-block">
                <Button variant="secondary">{t('tasks.open')}</Button>
              </Link>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
