import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { TaskDetailPage } from '@/pages/TaskDetailPage';
import { useTasksStore } from '@/store/tasks';
import { renderWithRouter } from '@/test/utils';
import type { SubmitResponse, TaskDetail } from '@/types/api';

const TASK_ID = '77777777-7777-7777-7777-777777777777';

const DETAIL: TaskDetail = {
  id: TASK_ID,
  title: 'Сумма двух чисел',
  description: 'Считайте два числа и выведите их сумму.',
  difficulty: 'easy',
  category: 'input_output',
  hints: [],
  solution_template: 'a = int(input())\nb = int(input())\nprint(a + b)\n',
  test_cases_count: 2,
  status: 'not_started',
  attempts: 0,
};

const CHECK: SubmitResponse = {
  passed: false,
  passed_count: 0,
  total_count: 2,
  attempts: 0,
  status: 'not_started',
  results: [
    {
      index: 1,
      passed: false,
      description: 'Положительные',
      input: '2\n3\n',
      expected_output: '5',
      actual_output: '0',
      error: null,
    },
  ],
  message: 'Пройдено 0 из 2 тестов. Пробная проверка — попытка не засчитывается.',
  practice: true,
};

function resetStore(): void {
  useTasksStore.setState({
    tasks: [],
    detail: null,
    progress: null,
    submission: null,
    checkResult: null,
    filters: { difficulty: null, category: null },
    loading: false,
    submitting: false,
    checking: false,
    error: null,
  });
}

describe('TaskDetailPage', () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  it('показывает кнопку пробной проверки и подсказку', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(DETAIL);

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    expect(await screen.findByRole('button', { name: /Пробная проверка/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Отправить решение/ })).toBeTruthy();
    expect(screen.getByText(/не засчитывается в попытки/)).toBeTruthy();
  });

  it('пробная проверка показывает разбор, не меняя попытки', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'get').mockResolvedValue(DETAIL);
    const post = vi.spyOn(api, 'post').mockResolvedValue(CHECK);

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    await user.click(await screen.findByRole('button', { name: /Пробная проверка/ }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith(`/tasks/${TASK_ID}/check`, {
        code: DETAIL.solution_template,
      });
    });

    // Разбор по тест-кейсу показан
    expect(await screen.findByText(/Результат пробной проверки/)).toBeTruthy();
    expect(screen.getByText(/Положительные/)).toBeTruthy();
    // Счётчик попыток на карточке задачи не изменился
    expect(screen.getByText(/Попыток: 0/)).toBeTruthy();
  });
});
