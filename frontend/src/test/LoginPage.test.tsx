import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { LoginPage } from '@/pages/LoginPage';
import { useAuthStore } from '@/store/auth';
import { renderWithRouter } from '@/test/utils';

describe('LoginPage', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      initializing: false,
      loading: false,
      error: null,
    });
  });

  it('показывает поля и кнопку входа', () => {
    renderWithRouter(<LoginPage />);

    expect(screen.getByLabelText('Имя пользователя')).toBeInTheDocument();
    expect(screen.getByLabelText('Пароль')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Войти' })).toBeInTheDocument();
  });

  it('отправляет введённые данные в стор', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ login });

    renderWithRouter(<LoginPage />);

    await userEvent.type(screen.getByLabelText('Имя пользователя'), 'tester');
    await userEvent.type(screen.getByLabelText('Пароль'), 'password123');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith('tester', 'password123');
    });
  });

  it('показывает ошибку из стора', () => {
    useAuthStore.setState({ error: 'Неверный пароль' });

    renderWithRouter(<LoginPage />);

    expect(screen.getByRole('alert')).toHaveTextContent('Неверный пароль');
  });

  it('блокирует кнопку во время загрузки', () => {
    useAuthStore.setState({ loading: true });

    renderWithRouter(<LoginPage />);

    expect(screen.getByRole('button', { name: /Войти/ })).toBeDisabled();
  });

  it('ведёт на страницу регистрации', () => {
    renderWithRouter(<LoginPage />);

    expect(screen.getByText('Зарегистрироваться')).toBeInTheDocument();
  });
});
