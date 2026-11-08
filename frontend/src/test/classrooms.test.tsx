import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { AssignmentsPage } from '@/pages/AssignmentsPage';
import { ClassroomsPage } from '@/pages/ClassroomsPage';
import { useAuthStore } from '@/store/auth';
import { renderWithRouter } from '@/test/utils';
import type { User } from '@/types/api';

function makeUser(role: User['role']): User {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    email: 'teacher@example.com',
    username: 'teacher',
    role,
    level: 'basic',
    created_at: '2026-10-29T10:00:00',
    last_active: '2026-10-29T10:00:00',
    settings: {},
  };
}

describe('ClassroomsPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: makeUser('teacher') });
    vi.restoreAllMocks();
  });

  it('показывает классы и форму создания для учителя', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      items: [
        {
          id: '22222222-2222-2222-2222-222222222222',
          name: '7А класс',
          owner_id: '11111111-1111-1111-1111-111111111111',
          join_code: 'ABC123',
          created_at: '2026-10-29T10:00:00',
          members_count: 2,
        },
      ],
    });

    renderWithRouter(<ClassroomsPage />);

    await waitFor(() => expect(screen.getByText('7А класс')).toBeInTheDocument());
    expect(screen.getByText('Создать класс')).toBeInTheDocument();
    expect(screen.getByText('ABC123')).toBeInTheDocument();
  });

  it('скрывает создание класса от ученика', async () => {
    useAuthStore.setState({ user: makeUser('student') });
    vi.spyOn(api, 'get').mockResolvedValue({ items: [] });

    renderWithRouter(<ClassroomsPage />);

    await waitFor(() =>
      expect(screen.getByText(/Вы пока не состоите/)).toBeInTheDocument(),
    );
    expect(screen.queryByText('Создать класс')).not.toBeInTheDocument();
  });
});

describe('AssignmentsPage', () => {
  it('показывает просроченное задание', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/me/announcements') {
        return { items: [] };
      }
      return {
        items: [
          {
            id: '33333333-3333-3333-3333-333333333333',
            classroom_id: '22222222-2222-2222-2222-222222222222',
            classroom_name: '7А класс',
            task_id: '44444444-4444-4444-4444-444444444444',
            title: 'Циклы',
            difficulty: 'easy',
            due_at: '2026-10-01T10:00:00',
            status: 'not_started',
            overdue: true,
          },
        ],
      };
    });

    renderWithRouter(<AssignmentsPage />);

    await waitFor(() => expect(screen.getByText('Циклы')).toBeInTheDocument());
    expect(screen.getByText('просрочено')).toBeInTheDocument();
  });
});
