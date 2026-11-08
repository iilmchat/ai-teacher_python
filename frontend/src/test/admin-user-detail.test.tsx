import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { AdminUserPage } from '@/pages/AdminUserPage';
import { api } from '@/lib/api';
import { renderWithRouter } from '@/test/utils';
import type { AdminUserDetail, AdminUserItem } from '@/types/api';

const DETAIL: AdminUserDetail = {
  user: {
    id: 'u2',
    email: 'two@example.com',
    username: 'two',
    role: 'student',
    level: 'intermediate',
    is_active: true,
    created_at: '2026-11-02T10:00:00',
    last_active: '2026-11-08T11:00:00',
  },
  progress: { solved: 5, attempts: 12 },
  audit: [
    {
      id: 'a1',
      actor_id: 'u2',
      actor_username: 'two',
      actor_role: 'student',
      action: 'task.updated',
      entity_type: 'user',
      entity_id: 'u2',
      payload: {},
      ip: '127.0.0.1',
      created_at: '2026-11-08T10:00:00',
    },
  ],
  sessions: [
    {
      id: 's1',
      created_at: '2026-11-07T10:00:00',
      last_used_at: '2026-11-08T10:00:00',
      user_agent: 'Mozilla/5.0 Test',
      ip: '127.0.0.1',
    },
  ],
};

function renderPage() {
  return renderWithRouter(
    <Routes>
      <Route path="/admin/users/:userId" element={<AdminUserPage />} />
    </Routes>,
    { route: '/admin/users/u2' },
  );
}

describe('AdminUserPage (S47-002)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue(DETAIL);
  });

  it('показывает профиль, прогресс, сессии и аудит', async () => {
    renderPage();

    expect(await screen.findByText('Пользователь two')).toBeInTheDocument();
    expect(screen.getByText('two@example.com')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Mozilla/5.0 Test')).toBeInTheDocument();
    expect(screen.getByText('task.updated')).toBeInTheDocument();
  });

  it('деактивирует пользователя через PATCH', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'patch').mockResolvedValue({
      ...DETAIL.user,
      is_active: false,
    } satisfies AdminUserItem);
    renderPage();

    await screen.findByText('Пользователь two');
    await user.click(screen.getByRole('button', { name: 'Деактивировать' }));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/admin/users/u2', {
        is_active: false,
      });
    });
    expect(
      await screen.findByText('Пользователь деактивирован, сессии отозваны'),
    ).toBeInTheDocument();
  });

  it('удаляет пользователя только после подтверждения', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'delete').mockResolvedValue({ deleted: true });
    renderPage();

    await screen.findByText('Пользователь two');
    await user.click(screen.getByRole('button', { name: 'Удалить безвозвратно' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/будет удалена безвозвратно/)).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole('button', { name: 'Удалить безвозвратно' }),
    );

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/admin/users/u2');
    });
  });
});
