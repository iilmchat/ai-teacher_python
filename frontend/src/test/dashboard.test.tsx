import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { DashboardPage } from '@/pages/DashboardPage';
import { useAuthStore } from '@/store/auth';
import { renderWithRouter } from '@/test/utils';
import type { User } from '@/types/api';

const USER: User = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'student@example.com',
  username: 'student',
  role: 'student',
  level: 'basic',
  created_at: '2026-10-29T10:00:00',
  last_active: '2026-10-29T10:00:00',
  settings: {},
};

function mockDashboard() {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path === '/me/stats') {
      return {
        solved: 3,
        attempts: 6,
        avg_attempts: 2,
        streak_days: 3,
        achievements_count: 1,
        chat_sessions: 2,
        chat_messages: 10,
      };
    }
    if (path === '/me/achievements') {
      return {
        items: [
          {
            code: 'first_task',
            title: 'Первая задача',
            description: 'Решена первая задача',
            icon: '🚀',
            earned_at: '2026-10-29T10:00:00',
          },
        ],
      };
    }
    if (path === '/me/notifications') {
      return {
        unread: 1,
        items: [
          {
            id: 'n1',
            type: 'assignment',
            payload: { title: 'Циклы' },
            read_at: null,
            created_at: '2026-10-29T10:00:00',
          },
        ],
      };
    }
    return {
      total_tasks: 3,
      completed: 3,
      in_progress: 0,
      not_started: 0,
      completion_rate: 100,
      by_difficulty: {},
      items: [
        {
          task_id: 't1',
          title: 'Сумма',
          difficulty: 'easy',
          status: 'completed',
          attempts: 2,
          completed_at: '2026-10-29T10:00:00',
        },
      ],
    };
  });
}

describe('DashboardPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER });
    vi.restoreAllMocks();
  });

  it('показывает серию, достижения и уведомления', async () => {
    mockDashboard();

    renderWithRouter(<DashboardPage />);

    await waitFor(() =>
      expect(screen.getByText('Первая задача')).toBeInTheDocument(),
    );
    expect(screen.getByText('3 🔥')).toBeInTheDocument();
    expect(screen.getByText(/Новое задание: Циклы/)).toBeInTheDocument();
    expect(screen.getByText(/Непрочитанных: 1/)).toBeInTheDocument();
  });

  it('показывает последние задачи', async () => {
    mockDashboard();

    renderWithRouter(<DashboardPage />);

    await waitFor(() => expect(screen.getByText('Сумма')).toBeInTheDocument());
  });
});
