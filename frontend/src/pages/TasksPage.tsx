import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { api } from '@/lib/api';
import { useTasksStore, type TaskFilters } from '@/store/tasks';
import type { TaskDifficulty, TaskStatus } from '@/types/api';

const DIFFICULTIES: Array<TaskDifficulty | null> = [null, 'easy', 'medium', 'hard'];

const STATUSES: Array<TaskStatus | null> = [null, 'not_started', 'in_progress', 'completed'];

/** Пауза перед отправкой поискового запроса (S42-004). */
const SEARCH_DEBOUNCE_MS = 300;

/** Разбор фильтров из query-параметров URL (S42-004). */
function filtersFromParams(params: URLSearchParams): Partial<TaskFilters> {
  const difficulty = params.get('difficulty');
  const status = params.get('status');
  return {
    difficulty:
      difficulty === 'easy' || difficulty === 'medium' || difficulty === 'hard'
        ? difficulty
        : null,
    category: params.get('category'),
    tag: params.get('tag'),
    status:
      status === 'not_started' || status === 'in_progress' || status === 'completed'
        ? status
        : null,
    search: params.get('q') ?? '',
  };
}

/** Фильтры → query-параметры URL: ссылкой можно поделиться (S42-004). */
function paramsFromFilters(filters: TaskFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.difficulty) {
    params.set('difficulty', filters.difficulty);
  }
  if (filters.category) {
    params.set('category', filters.category);
  }
  if (filters.tag) {
    params.set('tag', filters.tag);
  }
  if (filters.status) {
    params.set('status', filters.status);
  }
  const search = filters.search.trim();
  if (search) {
    params.set('q', search);
  }
  return params;
}

export function TasksPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const tasks = useTasksStore((state) => state.tasks);
  const progress = useTasksStore((state) => state.progress);
  const filters = useTasksStore((state) => state.filters);
  const found = useTasksStore((state) => state.found);
  const loading = useTasksStore((state) => state.loading);
  const error = useTasksStore((state) => state.error);
  const loadTasks = useTasksStore((state) => state.loadTasks);
  const loadProgress = useTasksStore((state) => state.loadProgress);
  const setFilter = useTasksStore((state) => state.setFilter);
  const resetFilters = useTasksStore((state) => state.resetFilters);

  const [categories, setCategories] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState(filters.search);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filtersReady = useRef(false);

  // Фильтры из URL при первом открытии страницы
  useEffect(() => {
    if (filtersReady.current) {
      return;
    }
    filtersReady.current = true;
    setFilter(filtersFromParams(searchParams));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void api
      .get<{ categories: string[] }>('/tasks/categories')
      .then((data) => setCategories(data.categories ?? []))
      .catch(() => setCategories([]));
  }, []);

  // Каталог перечитывается при смене любого фильтра
  const filterKey = useMemo(
    () =>
      [
        filters.difficulty ?? '',
        filters.category ?? '',
        filters.tag ?? '',
        filters.status ?? '',
        filters.search,
      ].join('|'),
    [filters],
  );

  useEffect(() => {
    void loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  useEffect(() => {
    void loadProgress();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Фильтры отражаются в URL: ссылкой можно поделиться
  useEffect(() => {
    if (!filtersReady.current) {
      return;
    }
    const next = paramsFromFilters(filters);
    const current = searchParams.toString();
    if (next.toString() !== current) {
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  const applyFilter = useCallback(
    (patch: Partial<TaskFilters>) => {
      setFilter(patch);
    },
    [setFilter],
  );

  // Поиск с задержкой ввода (S42-004)
  function handleSearchChange(value: string) {
    setSearchInput(value);
    if (searchTimer.current) {
      clearTimeout(searchTimer.current);
    }
    searchTimer.current = setTimeout(() => {
      applyFilter({ search: value });
    }, SEARCH_DEBOUNCE_MS);
  }

  function handleReset() {
    if (searchTimer.current) {
      clearTimeout(searchTimer.current);
    }
    setSearchInput('');
    resetFilters();
  }

  const hasFilters =
    filters.difficulty !== null ||
    filters.category !== null ||
    filters.tag !== null ||
    filters.status !== null ||
    filters.search.trim() !== '';

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-slate-900">{t('tasks.title')}</h1>
        <div
          className="flex gap-2"
          role="group"
          aria-label={t('tasks.filterDifficulty')}
        >
          {DIFFICULTIES.map((difficulty) => (
            <button
              key={difficulty ?? 'all'}
              type="button"
              aria-pressed={filters.difficulty === difficulty}
              onClick={() => applyFilter({ difficulty })}
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

      <Card title={t('tasks.filtersTitle')}>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">{t('tasks.searchLabel')}</span>
            <input
              type="search"
              value={searchInput}
              onChange={(event) => handleSearchChange(event.target.value)}
              placeholder={t('tasks.searchPlaceholder')}
              aria-label={t('tasks.searchLabel')}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </label>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-700">
                {t('tasks.categoryLabel')}
              </span>
              <select
                value={filters.category ?? ''}
                onChange={(event) =>
                  applyFilter({ category: event.target.value || null })
                }
                aria-label={t('tasks.categoryLabel')}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              >
                <option value="">{t('tasks.all')}</option>
                {categories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-700">{t('tasks.tagLabel')}</span>
              <input
                type="text"
                value={filters.tag ?? ''}
                onChange={(event) => applyFilter({ tag: event.target.value || null })}
                placeholder={t('tasks.tagPlaceholder')}
                aria-label={t('tasks.tagLabel')}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </label>
          </div>

          <div
            className="flex flex-wrap items-center gap-2"
            role="group"
            aria-label={t('tasks.statusLabel')}
          >
            <span className="text-sm font-medium text-slate-700">
              {t('tasks.statusLabel')}
            </span>
            {STATUSES.map((status) => (
              <button
                key={status ?? 'all'}
                type="button"
                aria-pressed={filters.status === status}
                onClick={() => applyFilter({ status })}
                className={`rounded-lg border px-3 py-1.5 text-xs ${
                  filters.status === status
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {status ? t(`tasks.status.${status}`) : t('tasks.all')}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-slate-500" role="status">
              {t('tasks.found', { count: found })}
            </p>
            {hasFilters && (
              <Button variant="ghost" onClick={handleReset}>
                {t('tasks.resetFilters')}
              </Button>
            )}
          </div>
        </div>
      </Card>

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
        <Alert tone="info">
          {hasFilters ? t('tasks.emptyFiltered') : t('tasks.empty')}
        </Alert>
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
