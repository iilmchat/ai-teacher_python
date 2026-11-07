import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { PasswordChangeCard } from '@/components/profile/PasswordChangeCard';
import { ApiError, api } from '@/lib/api';
import { getAccessToken, getRefreshToken, setTokens } from '@/lib/token';
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

describe('смена пароля (S45-001)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER, error: null, loading: false });
    localStorage.removeItem('ai-teacher.access');
    localStorage.removeItem('ai-teacher.refresh');
  });

  it('успешная смена обновляет токены и показывает подтверждение', async () => {
    const user = userEvent.setup();
    const postSpy = vi
      .spyOn(api, 'post')
      .mockResolvedValue({
        access_token: 'new-access',
        refresh_token: 'new-refresh',
        token_type: 'bearer',
      });
    vi.spyOn(api, 'get').mockResolvedValue(USER);

    renderWithRouter(<PasswordChangeCard />);

    await user.type(
      screen.getByLabelText('Текущий пароль'),
      'password123',
    );
    await user.type(screen.getByLabelText('Новый пароль'), 'newpassword456');
    await user.type(
      screen.getByLabelText('Повторите новый пароль'),
      'newpassword456',
    );
    await user.click(screen.getByRole('button', { name: 'Сменить пароль' }));

    await waitFor(() => {
      expect(screen.getByText(/Пароль изменён/)).toBeInTheDocument();
    });
    expect(postSpy).toHaveBeenCalledWith('/users/me/password', {
      current_password: 'password123',
      new_password: 'newpassword456',
    });
    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('new-refresh');
  });

  it('кнопка недоступна, пока пароли не совпадают', () => {
    const user = userEvent.setup();

    renderWithRouter(<PasswordChangeCard />);

    void user.type(screen.getByLabelText('Текущий пароль'), 'password123');
    void user.type(screen.getByLabelText('Новый пароль'), 'newpassword456');

    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('ошибка сервера: неверный текущий пароль', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'post').mockRejectedValue(
      new ApiError(400, 'Неверный текущий пароль'),
    );

    renderWithRouter(<PasswordChangeCard />);

    await user.type(screen.getByLabelText('Текущий пароль'), 'wrongpass123');
    await user.type(screen.getByLabelText('Новый пароль'), 'newpassword456');
    await user.type(
      screen.getByLabelText('Повторите новый пароль'),
      'newpassword456',
    );
    await user.click(screen.getByRole('button', { name: 'Сменить пароль' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Неверный текущий пароль',
      );
    });
  });

  it('после смены state пользователя перезагружается', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'post').mockResolvedValue({
      access_token: 'access2',
      refresh_token: 'refresh2',
      token_type: 'bearer',
    });
    const changedUser = { ...USER, username: 'tester2' };
    vi.spyOn(api, 'get').mockResolvedValue(changedUser);

    renderWithRouter(<PasswordChangeCard />);

    await user.type(screen.getByLabelText('Текущий пароль'), 'password123');
    await user.type(screen.getByLabelText('Новый пароль'), 'newpassword456');
    await user.type(
      screen.getByLabelText('Повторите новый пароль'),
      'newpassword456',
    );
    await user.click(screen.getByRole('button', { name: 'Сменить пароль' }));

    await waitFor(() => {
      expect(useAuthStore.getState().user?.username).toBe('tester2');
    });
    expect(getRefreshToken()).toBe('refresh2');
  });

  it('токены не меняются при отклонённой смене', async () => {
    const user = userEvent.setup();
    setTokens({ access: 'keep-access', refresh: 'keep-refresh' });
    vi.spyOn(api, 'post').mockRejectedValue(new Error('Неверный текущий пароль'));

    renderWithRouter(<PasswordChangeCard />);

    await user.type(screen.getByLabelText('Текущий пароль'), 'password123');
    await user.type(screen.getByLabelText('Новый пароль'), 'newpassword456');
    await user.type(
      screen.getByLabelText('Повторите новый пароль'),
      'newpassword456',
    );
    await user.click(screen.getByRole('button', { name: 'Сменить пароль' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(getAccessToken()).toBe('keep-access');
    expect(getRefreshToken()).toBe('keep-refresh');
  });
});
