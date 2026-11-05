import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { RecommendedTasks } from '@/components/tasks/RecommendedTasks';
import { api } from '@/lib/api';
import { useTasksStore } from '@/store/tasks';
import { renderWithRouter } from '@/test/utils';
import type { RecommendedTaskList } from '@/types/api';

const RECOMMENDED: RecommendedTaskList = {
  items: [
    {
      id: '77777777-7777-7777-7777-777777777777',
      title: 'Сумма двух чисел',
      difficulty: 'easy',
      category: 'input_output',
      tags: ['python'],
      reason: 'starter',
      reason_text: 'С чего начать: простая задача по теме',
    },
  ],
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
    recommended: null,
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

describe('RecommendedTasks (S42-005)', () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  it('загружает и показывает рекомендации с пояснением', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue(RECOMMENDED);

    renderWithRouter(<RecommendedTasks />);

    expect(await screen.findByText('Рекомендуем дальше')).toBeTruthy();
    expect(get).toHaveBeenCalledWith('/tasks/recommended');
    expect(screen.getByText('Сумма двух чисел')).toBeTruthy();
    expect(
      screen.getByText('С чего начать: простая задача по теме'),
    ).toBeTruthy();
  });

  it('показывает подсказку, когда рекомендаций нет', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ items: [] });

    renderWithRouter(<RecommendedTasks />);

    expect(
      await screen.findByText(
        'Пока нечего рекомендовать — решите вводную задачу, и мы подберём следующую по теме и сложности.',
      ),
    ).toBeTruthy();
  });

  it('не показывает ошибку, если рекомендации не загрузились', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new Error('500'));

    renderWithRouter(<RecommendedTasks />);

    await waitFor(() => {
      expect(useTasksStore.getState().recommended).toBeNull();
    });
    expect(screen.getByText('Рекомендуем дальше')).toBeTruthy();
  });
});
