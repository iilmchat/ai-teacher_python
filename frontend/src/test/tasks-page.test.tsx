import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { TasksPage } from '@/pages/TasksPage';
import { useTasksStore } from '@/store/tasks';
import { renderWithRouter } from '@/test/utils';
import type { ProgressSummary, TaskListItem } from '@/types/api';

const TASK: TaskListItem = {
  id: '77777777-7777-7777-7777-777777777777',
  title: 'Сумма двух чисел',
  difficulty: 'easy',
  category: 'input_output',
  hints_count: 2,
  status: 'not_started',
};

const PROGRESS: ProgressSummary = {
  total_tasks: 1,
  completed: 0,
  in_progress: 0,
  not_started: 1,
  completion_rate: 0,
  by_difficulty: { easy: { total: 1, completed: 0 } },
  items: [],
};

function resetStore(): void {
  useTasksStore.setState({
    tasks: [],
    detail: null,
    progress: null,
    submission: null,
    checkResult: null,
    attempts: null,
    attemptDetail: null,
    draftSavedAt: null,
    draftSaving: false,
    filters: {
      difficulty: null,
      category: null,
      tag: null,
      status: null,
      search: '',
    },
    found: 0,
    loading: false,
    submitting: false,
    checking: false,
    error: null,
  });
}

function mockApi(tasks: TaskListItem[] = [TASK]) {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path === '/tasks/categories') {
      return { categories: ['input_output', 'loops'] };
    }
    if (path === '/tasks/progress') {
      return PROGRESS;
    }
    return tasks;
  });
}

describe('TasksPage — фильтры каталога (S42-004)', () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  it('показывает счётчик найденного', async () => {
    mockApi();
    renderWithRouter(<TasksPage />, { route: '/tasks' });

    expect(await screen.findByText('Найдено задач: 1')).toBeTruthy();
    // Без активных фильтров сброс не нужен
    expect(screen.queryByRole('button', { name: 'Сбросить фильтры' })).toBeNull();
  });

  it('фильтрует по статусу и сбрасывает фильтры', async () => {
    const user = userEvent.setup();
    mockApi();
    renderWithRouter(<TasksPage />, { route: '/tasks' });

    await screen.findByText('Найдено задач: 1');

    await user.click(screen.getByRole('button', { name: 'не начата' }));

    await waitFor(() => {
      expect(useTasksStore.getState().filters.status).toBe('not_started');
    });

    await user.click(screen.getByRole('button', { name: 'Сбросить фильтры' }));

    await waitFor(() => {
      expect(useTasksStore.getState().filters.status).toBeNull();
    });
  });

  it('ищет по названию с задержкой ввода', async () => {
    const user = userEvent.setup();
    mockApi();
    renderWithRouter(<TasksPage />, { route: '/tasks' });

    const input = await screen.findByLabelText('Поиск по задачам');
    await user.type(input, 'сумма');

    await waitFor(
      () => {
        expect(useTasksStore.getState().filters.search).toBe('сумма');
      },
      { timeout: 2000 },
    );
  });

  it('подставляет фильтры из URL', async () => {
    mockApi();
    renderWithRouter(<TasksPage />, {
      route: '/tasks?difficulty=hard&status=in_progress&q=%D1%81%D1%83%D0%BC%D0%BC%D0%B0',
    });

    await waitFor(() => {
      const filters = useTasksStore.getState().filters;
      expect(filters.difficulty).toBe('hard');
      expect(filters.status).toBe('in_progress');
      expect(filters.search).toBe('сумма');
    });
  });

  it('показывает общее пустое состояние без фильтров', async () => {
    mockApi([]);
    renderWithRouter(<TasksPage />, { route: '/tasks' });

    await screen.findByText(
      'Задач пока нет — попросите преподавателя добавить их',
    );
  });

  it('показывает подсказку, когда фильтры ничего не нашли', async () => {
    const user = userEvent.setup();
    mockApi([]);
    renderWithRouter(<TasksPage />, { route: '/tasks' });

    await user.click(await screen.findByRole('button', { name: 'не начата' }));

    await screen.findByText(
      'По вашему фильтру ничего не найдено. Попробуйте изменить условия или сбросить фильтры.',
    );
  });
});
