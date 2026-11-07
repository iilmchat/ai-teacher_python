import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { SessionsCard } from '@/components/profile/SessionsCard';
import { api } from '@/lib/api';
import { getAccessToken, getRefreshToken } from '@/lib/token';
import { useAuthStore } from '@/store/auth';
import { renderWithRouter } from '@/test/utils';

const USER = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'test@example.com',
  username: 'tester',
  role: 'student' as const,
  level: 'basic' as const,
  created_at: '2026-10-29T10:00:00',
  last_active: '2026-10-29T10:00:00',
  settings: {},
};

const SESSIONS = [
  {
    id: 'session-current',
    created_at: '2026-11-07T10:00:00',
    last_used_at: '2026-11-07T12:00:00',
    user_agent: 'Mozilla/5.0 (текущий)',
    ip: '192.168.1.10',
    current: true,
  },
  {
    id: 'session-other',
    created_at: '2026-11-06T08:00:00',
    last_used_at: '2026-11-06T09:00:00',
    user_agent: 'Phone',
    ip: '10.0.0.2',
    current: false,
  },
];

describe('активные сессии (S45-005)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER, error: null, loading: false });
    localStorage.setItem('ai-teacher.access', 'old-access');
    localStorage.setItem('ai-teacher.refresh', 'old-refresh');
  });

  it('список показывает устройства и помечает текущее', async () => {
    vi.spyOn(api, 'get').mockResolvedValue(SESSIONS);

    renderWithRouter(<SessionsCard />);

    expect(await screen.findByText('Mozilla/5.0 (текущий)')).toBeInTheDocument();
    expect(screen.getByText('Это устройство')).toBeInTheDocument();
    expect(screen.getByText('Phone')).toBeInTheDocument();
    // Кнопка отзыва только у чужой сессии
    expect(screen.getAllByRole('button', { name: 'Отозвать' })).toHaveLength(1);
  });

  it('отзыв сессии вызывает DELETE и перезагружает список', async () => {
    const user = userEvent.setup();
    const get = vi.spyOn(api, 'get').mockResolvedValue(SESSIONS);
    const remove = vi
      .spyOn(api, 'delete')
      .mockResolvedValue(undefined as unknown as never);

    renderWithRouter(<SessionsCard />);
    await screen.findByText('Phone');
    await user.click(screen.getByRole('button', { name: 'Отозвать' }));

    await waitFor(() => {
      expect(remove).toHaveBeenCalledWith('/users/me/sessions/session-other');
    });
    await waitFor(() => {
      expect(get).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText('Сессия отозвана')).toBeInTheDocument();
  });

  it('ошибка загрузки списка показывается пользователю', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new Error('boom'));

    renderWithRouter(<SessionsCard />);

    expect(
      await screen.findByText('Не удалось загрузить сессии'),
    ).toBeInTheDocument();
  });

  it('«выйти везде» подтверждается и сохраняет новую пару токенов', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'get').mockResolvedValue(SESSIONS);
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      access_token: 'new-access',
      refresh_token: 'new-refresh',
      token_type: 'bearer',
    });

    renderWithRouter(<SessionsCard />);
    await screen.findByText('Phone');
    await user.click(
      screen.getByRole('button', { name: 'Выйти на всех устройствах' }),
    );

    const dialog = screen.getByRole('dialog');
    await user.click(
      within(dialog).getByRole('button', { name: 'Выйти везде' }),
    );

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/users/me/sessions/revoke-others');
    });
    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('new-refresh');
    expect(
      await screen.findByText('Все другие сессии завершены'),
    ).toBeInTheDocument();
  });

  it('отмена подтверждения не завершает сессии', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'get').mockResolvedValue(SESSIONS);
    const post = vi.spyOn(api, 'post');

    renderWithRouter(<SessionsCard />);
    await screen.findByText('Phone');
    await user.click(
      screen.getByRole('button', { name: 'Выйти на всех устройствах' }),
    );
    await user.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });
});
