import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ProfileEditCard } from '@/components/profile/ProfileEditCard';
import { DangerZoneCard } from '@/components/profile/DangerZoneCard';
import { ApiError, api } from '@/lib/api';
import { getAccessToken } from '@/lib/token';
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

describe('правка профиля (S45-002)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER, error: null, loading: false });
    localStorage.removeItem('ai-teacher.access');
  });

  it('поля предзаполняются и отправляют PATCH /auth/me', async () => {
    const user = userEvent.setup();
    const patchSpy = vi.spyOn(api, 'patch').mockResolvedValue({
      ...USER,
      email: 'moved@example.com',
    });

    renderWithRouter(<ProfileEditCard />);

    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'moved@example.com');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(screen.getByText(/Профиль обновлён/)).toBeInTheDocument();
    });
    expect(patchSpy).toHaveBeenCalledWith('/auth/me', {
      email: 'moved@example.com',
      username: 'tester',
    });
    expect(useAuthStore.getState().user?.email).toBe('moved@example.com');
  });

  it('кнопка сохранения недоступна без изменений', () => {
    renderWithRouter(<ProfileEditCard />);

    expect(screen.getByRole('button', { name: 'Сохранить' })).toBeDisabled();
  });

  it('ошибка сервера (занятый e-mail) показывается как есть', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'patch').mockRejectedValue(
      new ApiError(400, 'Email already registered'),
    );

    renderWithRouter(<ProfileEditCard />);
    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'busy@example.com');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Email already registered',
      );
    });
  });

  it('кнопка «Отменить правки» возвращает значения профиля', async () => {
    const user = userEvent.setup();

    renderWithRouter(<ProfileEditCard />);
    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'draft@example.com');
    await user.click(screen.getByRole('button', { name: 'Отменить правки' }));

    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
  });
});

describe('удаление аккаунта (S45-002)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER, error: null, loading: false });
    localStorage.setItem('ai-teacher.access', 'access-token');
    localStorage.setItem('ai-teacher.refresh', 'refresh-token');
  });

  it('подтверждение паролем вызывает DELETE /users/me и разлогинивает', async () => {
    const user = userEvent.setup();
    const deleteSpy = vi
      .spyOn(api, 'delete')
      .mockResolvedValue(undefined as unknown as never);

    renderWithRouter(<DangerZoneCard />);
    await user.click(screen.getByRole('button', { name: 'Удалить аккаунт' }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Подтвердите паролем'), 'password123');
    await user.click(screen.getByRole('button', { name: 'Удалить навсегда' }));

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith('/auth/me', { password: 'password123' });
    });
    await waitFor(() => {
      expect(useAuthStore.getState().user).toBeNull();
    });
    expect(getAccessToken()).toBeNull();
  });

  it('неверный пароль сохраняет сессию и показывает ошибку сервера', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'delete').mockRejectedValue(
      new ApiError(400, 'Неверный пароль: удаление отменено'),
    );

    renderWithRouter(<DangerZoneCard />);
    await user.click(screen.getByRole('button', { name: 'Удалить аккаунт' }));
    await user.type(screen.getByLabelText('Подтвердите паролем'), 'wrongpass1');
    await user.click(screen.getByRole('button', { name: 'Удалить навсегда' }));

    await waitFor(() => {
      expect(screen.getAllByText('Неверный пароль: удаление отменено').length).toBeGreaterThan(0);
    });
    expect(getAccessToken()).toBe('access-token');
  });

  it('отмена закрывает модальное окно', async () => {
    const user = userEvent.setup();

    renderWithRouter(<DangerZoneCard />);
    await user.click(screen.getByRole('button', { name: 'Удалить аккаунт' }));
    await user.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
