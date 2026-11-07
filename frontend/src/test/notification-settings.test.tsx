import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AppLayout } from '@/components/layout/AppLayout';
import { NotificationSettingsCard } from '@/components/profile/NotificationSettingsCard';
import i18n from '@/i18n';
import { api } from '@/lib/api';
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

describe('настройки уведомлений (S45-004)', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru');
    useAuthStore.setState({ user: USER, error: null, loading: false });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('по умолчанию оба переключателя включены и порог — 3 дня', () => {
    renderWithRouter(<NotificationSettingsCard />);

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
    for (const box of checkboxes) {
      expect(box).toBeChecked();
    }
    expect(screen.getByLabelText('Напомнить за')).toHaveValue('3');
  });

  it('выключение писем сохраняет email_notifications=false', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'patch').mockResolvedValue({
      ...USER,
      settings: { email_notifications: false },
    });

    renderWithRouter(<NotificationSettingsCard />);
    await user.click(screen.getAllByRole('checkbox')[0]);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/users/me/settings', {
        email_notifications: false,
      });
    });
    expect(useAuthStore.getState().user?.settings).toEqual({
      email_notifications: false,
    });
  });

  it('смена порога дней отправляет deadline_days', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'patch').mockResolvedValue({
      ...USER,
      settings: { deadline_days: 7 },
    });

    renderWithRouter(<NotificationSettingsCard />);
    await user.selectOptions(screen.getByLabelText('Напомнить за'), '7');

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/users/me/settings', {
        deadline_days: 7,
      });
    });
  });

  it('ошибка сохранения показывается пользователю', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'patch').mockRejectedValue(new Error('boom'));

    renderWithRouter(<NotificationSettingsCard />);
    await user.click(screen.getAllByRole('checkbox')[1]);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Не удалось сохранить настройки',
      );
    });
  });
});

describe('переключатель языка в шапке (S45-004)', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    useAuthStore.setState({ user: null });
  });

  it('гость переключает язык сразу, без запроса к серверу', async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: null });
    const patch = vi.spyOn(api, 'patch');

    renderWithRouter(<AppLayout />, { route: '/login' });
    await user.selectOptions(
      screen.getByLabelText('Язык интерфейса'),
      'English',
    );

    await waitFor(() => {
      expect(i18n.language).toBe('en');
    });
    expect(patch).not.toHaveBeenCalled();
  });

  it('авторизованный пользователь сохраняет язык в профиле', async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: USER });
    vi.spyOn(api, 'patch').mockResolvedValue({
      ...USER,
      settings: { language: 'en' },
    });

    renderWithRouter(<AppLayout />);
    await user.selectOptions(
      screen.getByLabelText('Язык интерфейса'),
      'English',
    );

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/users/me/settings', {
        language: 'en',
      });
    });
    await waitFor(() => {
      expect(i18n.language).toBe('en');
    });
  });
});
