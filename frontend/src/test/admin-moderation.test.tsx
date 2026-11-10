import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { AdminModerationPage } from '@/pages/AdminModerationPage';
import { renderWithRouter } from '@/test/utils';
import type {
  AdminTaskReviewResponse,
  TaskModerateResponse,
} from '@/types/api';

const QUEUE: AdminTaskReviewResponse = {
  total: 1,
  threshold: 3,
  items: [
    {
      id: 'task-1',
      title: 'Задача из LLM',
      description: 'Посчитайте сумму чисел.',
      difficulty: 'easy',
      category: 'loops',
      source: 'generated',
      is_active: false,
      moderation_comment: 'Проверьте тесты',
      test_cases_count: 2,
      hints_count: 1,
      created_at: '2026-11-10T10:00:00',
      metrics: {
        attempts: 4,
        passed_attempts: 1,
        success_rate: 0.25,
        avg_attempts: 2.5,
        students: 2,
        stuck_students: 1,
      },
      recent_attempts: [
        {
          id: 'attempt-1',
          user_id: 'user-1',
          username: 'pupil',
          passed: false,
          passed_count: 0,
          total_count: 2,
          created_at: '2026-11-10T10:05:00',
        },
      ],
    },
  ],
};

const MODERATED: TaskModerateResponse = {
  id: 'task-1',
  title: 'Задача из LLM',
  action: 'publish',
  source: 'generated',
  is_active: true,
  moderation_comment: null,
};

describe('AdminModerationPage (S47-003)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue(QUEUE);
  });

  it('показывает очередь, метрики и последние попытки', async () => {
    renderWithRouter(<AdminModerationPage />, { route: '/admin/moderation' });

    expect(await screen.findAllByText('Задача из LLM')).not.toHaveLength(0);
    expect(screen.getAllByText('25%').length).toBeGreaterThan(0);
    expect(screen.getByText('Проверьте тесты')).toBeInTheDocument();
    expect(screen.getByText('pupil')).toBeInTheDocument();
    expect(screen.getByText('Не пройдена')).toBeInTheDocument();
  });

  it('публикует задачу и обновляет очередь', async () => {
    const post = vi
      .spyOn(api, 'post')
      .mockResolvedValue(MODERATED);

    renderWithRouter(<AdminModerationPage />, { route: '/admin/moderation' });
    await screen.findAllByText('Задача из LLM');

    await userEvent.click(screen.getByRole('button', { name: 'Опубликовать' }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/admin/tasks/task-1/moderate', {
        action: 'publish',
      });
    });
    expect(await screen.findByText('Задача опубликована')).toBeInTheDocument();
  });

  it('возвращает в доработку только с комментарием', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      ...MODERATED,
      action: 'return_to_revision',
      is_active: false,
      moderation_comment: 'Уточните тесты',
    });

    renderWithRouter(<AdminModerationPage />, { route: '/admin/moderation' });
    await screen.findAllByText('Задача из LLM');

    await userEvent.click(
      screen.getByRole('button', { name: 'Вернуть в доработку' }),
    );
    const dialog = screen.getByRole('dialog');
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Вернуть в доработку' }),
    );

    expect(await screen.findByText('Комментарий обязателен')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await userEvent.type(
      within(dialog).getByLabelText('Комментарий'),
      'Уточните тесты',
    );
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Вернуть в доработку' }),
    );

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/admin/tasks/task-1/moderate', {
        action: 'return_to_revision',
        comment: 'Уточните тесты',
      });
    });
  });

  it('передаёт фильтр источника в запрос очереди', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue(QUEUE);

    renderWithRouter(<AdminModerationPage />, { route: '/admin/moderation' });
    await screen.findAllByText('Задача из LLM');

    await userEvent.selectOptions(screen.getByLabelText('Источник'), 'generated');

    await waitFor(() => {
      expect(get).toHaveBeenLastCalledWith(
        expect.stringContaining('source=generated'),
      );
    });
  });
});
