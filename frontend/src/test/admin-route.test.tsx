import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import '@/i18n';
import { AdminRoute } from '@/components/AdminRoute';
import { useAuthStore } from '@/store/auth';
import { renderWithRouter } from '@/test/utils';
import type { User } from '@/types/api';

function makeUser(role: User['role']): User {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    email: 'user@example.com',
    username: 'user',
    role,
    level: 'basic',
    created_at: '2026-10-29T10:00:00',
    last_active: '2026-10-29T10:00:00',
    settings: {},
  };
}

describe('AdminRoute', () => {
  it('пускает администратора', () => {
    useAuthStore.setState({ user: makeUser('admin') });

    renderWithRouter(
      <AdminRoute>
        <div>админка</div>
      </AdminRoute>,
    );

    expect(screen.getByText('админка')).toBeInTheDocument();
  });

  it('закрывает доступ ученику', () => {
    useAuthStore.setState({ user: makeUser('student') });

    renderWithRouter(
      <AdminRoute>
        <div>админка</div>
      </AdminRoute>,
    );

    expect(screen.queryByText('админка')).not.toBeInTheDocument();
    expect(screen.getByText(/Доступ только для администратора/)).toBeInTheDocument();
  });

  it('закрывает доступ преподавателю', () => {
    useAuthStore.setState({ user: makeUser('teacher') });

    renderWithRouter(
      <AdminRoute>
        <div>админка</div>
      </AdminRoute>,
    );

    expect(screen.queryByText('админка')).not.toBeInTheDocument();
  });
});
