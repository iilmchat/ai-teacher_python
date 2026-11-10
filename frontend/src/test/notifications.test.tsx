import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { AppLayout } from '@/components/layout/AppLayout';
import {
  isSafeNotificationLink,
  notificationLink,
} from '@/lib/notifications';
import { api } from '@/lib/api';
import { NotificationsPage } from '@/pages/NotificationsPage';
import { useAuthStore } from '@/store/auth';
import { useNotificationsStore } from '@/store/notifications';
import { renderWithRouter } from '@/test/utils';
import type { AppNotification, NotificationsResponse } from '@/types/api';

const ASSIGNMENT: AppNotification = {
  id: 'n1',
  type: 'assignment',
  payload: { title: 'Контрольная', link: '/assignments' },
  read_at: null,
  created_at: '2026-11-10T10:00:00',
};

const BAD_LINK: AppNotification = {
  id: 'n2',
  type: 'attempt_feedback',
  payload: {
    title: 'Работа',
    teacher: 'Иван',
    task_id: 'task-1',
    link: 'javascript:alert(1)',
  },
  read_at: null,
  created_at: '2026-11-10T10:01:00',
};

const ANNOUNCEMENT: AppNotification = {
  id: 'n3',
  type: 'announcement',
  payload: { title: 'Объявление', classroom_id: 'class-1' },
  read_at: '2026-11-10T10:02:00',
  created_at: '2026-11-10T10:02:00',
};

const NOTIFICATIONS: NotificationsResponse = {
  items: [ASSIGNMENT, BAD_LINK, ANNOUNCEMENT],
  unread: 2,
};

const DEADLINE: AppNotification = {
  id: 'n4',
  type: 'deadline',
  payload: { title: 'Дедлайн', link: '/assignments' },
  read_at: null,
  created_at: '2026-11-10T10:03:00',
};

describe('безопасные ссылки уведомлений (D-007)', () => {
  it('пропускает только относительные пути без схемы и //', () => {
    expect(isSafeNotificationLink('/tasks/1')).toBe(true);
    expect(isSafeNotificationLink('//evil.example')).toBe(false);
    expect(isSafeNotificationLink('http://evil.example')).toBe(false);
    expect(isSafeNotificationLink('javascript:alert(1)')).toBe(false);
    expect(isSafeNotificationLink('/tasks//1')).toBe(false);
    expect(isSafeNotificationLink('/\\evil')).toBe(false);
  });

  it('не подменяет небезопасный payload ссылкой-fallback', () => {
    expect(notificationLink(BAD_LINK)).toBeNull();
  });

  it('строит fallback для старых уведомлений без link', () => {
    const oldFeedback: AppNotification = {
      ...BAD_LINK,
      payload: { title: 'Работа', task_id: 'task-1' },
    };
    const oldAnnouncement: AppNotification = {
      ...ANNOUNCEMENT,
      payload: { title: 'Объявление', classroom_id: 'class-1' },
    };

    expect(notificationLink(oldFeedback)).toBe('/tasks/task-1');
    expect(notificationLink(oldAnnouncement)).toBe('/classrooms/class-1');
    expect(notificationLink(ASSIGNMENT)).toBe('/assignments');
  });
});

describe('страница уведомлений (S47-005)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useNotificationsStore.setState({
      items: [],
      unread: 0,
      filterType: '',
      loading: false,
      error: null,
    });
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path.includes('type=deadline')) {
        return { items: [DEADLINE], unread: 2 };
      }
      return NOTIFICATIONS;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('рендерит список и не делает ссылку из javascript:', async () => {
    renderWithRouter(<NotificationsPage />, { route: '/notifications' });

    expect(await screen.findByText('Центр уведомлений')).toBeInTheDocument();
    expect(screen.getByText('Новое задание: Контрольная')).toBeInTheDocument();
    expect(
      screen.getByText(/Учитель Иван оставил комментарий/),
    ).toBeInTheDocument();

    const badItem = screen
      .getByText(/Учитель Иван оставил комментарий/)
      .closest('li');
    expect(badItem).not.toBeNull();
    expect(within(badItem as HTMLElement).queryByRole('link')).toBeNull();

    const assignmentItem = screen
      .getByText('Новое задание: Контрольная')
      .closest('li');
    expect(
      within(assignmentItem as HTMLElement).getByRole('link', { name: 'Перейти' }),
    ).toHaveAttribute('href', '/assignments');
  });

  it('фильтрует по типу', async () => {
    renderWithRouter(<NotificationsPage />, { route: '/notifications' });
    await screen.findByText('Новое задание: Контрольная');

    await userEvent.selectOptions(
      screen.getByLabelText('Тип уведомления'),
      'deadline',
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenLastCalledWith(
        expect.stringContaining('type=deadline'),
      );
    });
    expect(await screen.findByText('Приближается дедлайн: Дедлайн')).toBeInTheDocument();
  });

  it('отмечает все уведомления прочитанными', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ updated: 2 });
    renderWithRouter(<NotificationsPage />, { route: '/notifications' });
    await screen.findByText('Новое задание: Контрольная');

    await userEvent.click(screen.getByRole('button', { name: 'Прочитать все' }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/me/notifications/read-all');
    });
    expect(await screen.findByText('Непрочитанных: 0')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Прочитать' })).toBeNull();
  });
});

describe('бейдж непрочитанных в шапке (S47-005)', () => {
  afterEach(() => {
    useAuthStore.setState({ user: null });
    useNotificationsStore.setState({
      items: [],
      unread: 0,
      filterType: '',
      loading: false,
      error: null,
    });
    vi.restoreAllMocks();
  });

  it('обновляется после read-all через общий стейт', async () => {
    useAuthStore.setState({
      user: {
        id: 'u1',
        email: 'u@example.com',
        username: 'u1',
        role: 'student',
        level: 'basic',
        created_at: '2026-11-01T10:00:00',
        last_active: '2026-11-10T10:00:00',
        settings: {},
      },
    });
    useNotificationsStore.setState({ unread: 2 });
    vi.spyOn(api, 'get').mockResolvedValue({ items: [], unread: 2 });
    vi.spyOn(api, 'post').mockResolvedValue({ updated: 2 });

    renderWithRouter(<AppLayout />, { route: '/notifications' });

    expect(
      await screen.findByLabelText('Непрочитанных: 2'),
    ).toBeInTheDocument();

    await act(async () => {
      await useNotificationsStore.getState().markAllRead();
    });

    await waitFor(() => {
      expect(screen.queryByLabelText('Непрочитанных: 2')).toBeNull();
    });
    expect(screen.getByText('Уведомления')).toBeInTheDocument();
  });
});
