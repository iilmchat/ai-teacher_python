import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { ChatPage } from '@/pages/ChatPage';
import { useChatStore } from '@/store/chat';
import { renderWithRouter } from '@/test/utils';
import type { TaskDetail } from '@/types/api';

const TASK_ID = '77777777-7777-7777-7777-777777777777';

const DETAIL: TaskDetail = {
  id: TASK_ID,
  title: 'Сумма двух чисел',
  description: 'Считайте два числа и выведите их сумму.',
  difficulty: 'easy',
  category: 'input_output',
  hints: [],
  solution_template: null,
  test_cases_count: 2,
  status: 'not_started',
  attempts: 0,
};

function resetStore(): void {
  useChatStore.setState({
    sessions: [],
    active: null,
    draft: '',
    streaming: false,
    loading: false,
    error: null,
    taskContext: null,
  });
}

describe('ChatPage: контекст задачи из deep-link', () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  it('показывает плашку с названием задачи из /chat?task=id', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/chat/sessions') {
        return [];
      }
      return DETAIL;
    });

    renderWithRouter(<ChatPage />, { route: `/chat?task=${TASK_ID}` });

    expect(await screen.findByText('Сумма двух чисел')).toBeInTheDocument();
    expect(screen.getByText(/Контекст задачи/)).toBeInTheDocument();
    expect(useChatStore.getState().taskContext).toEqual({
      id: TASK_ID,
      title: 'Сумма двух чисел',
    });
  });

  it('снятие контекста убирает плашку и очищает состояние', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/chat/sessions') {
        return [];
      }
      return DETAIL;
    });

    renderWithRouter(<ChatPage />, { route: `/chat?task=${TASK_ID}` });
    await screen.findByText('Сумма двух чисел');

    await user.click(screen.getByRole('button', { name: 'Убрать' }));

    await waitFor(() => {
      expect(screen.queryByText('Сумма двух чисел')).not.toBeInTheDocument();
    });
    expect(useChatStore.getState().taskContext).toBeNull();
  });

  it('без параметра task в URL контекст очищается', async () => {
    useChatStore.setState({ taskContext: { id: TASK_ID, title: 'Старая задача' } });
    vi.spyOn(api, 'get').mockResolvedValue([]);

    renderWithRouter(<ChatPage />, { route: '/chat' });

    await waitFor(() => {
      expect(useChatStore.getState().taskContext).toBeNull();
    });
  });
});
