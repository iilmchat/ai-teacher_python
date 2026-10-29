import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { TaskForm } from '@/components/teacher/TaskForm';
import { TeacherRoute } from '@/components/TeacherRoute';
import { api } from '@/lib/api';
import { TeacherTasksPage } from '@/pages/TeacherTasksPage';
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

describe('TeacherRoute', () => {
  it('пускает преподавателя и администратора', () => {
    useAuthStore.setState({ user: makeUser('teacher') });
    const { unmount } = renderWithRouter(
      <TeacherRoute>
        <div>кабинет</div>
      </TeacherRoute>,
    );
    expect(screen.getByText('кабинет')).toBeInTheDocument();
    unmount();

    useAuthStore.setState({ user: makeUser('admin') });
    renderWithRouter(
      <TeacherRoute>
        <div>кабинет</div>
      </TeacherRoute>,
    );
    expect(screen.getByText('кабинет')).toBeInTheDocument();
  });

  it('закрывает доступ ученику', () => {
    useAuthStore.setState({ user: makeUser('student') });

    renderWithRouter(
      <TeacherRoute>
        <div>кабинет</div>
      </TeacherRoute>,
    );

    expect(screen.queryByText('кабинет')).not.toBeInTheDocument();
    expect(screen.getByText(/Доступ только для преподавателя/)).toBeInTheDocument();
  });
});

describe('TaskForm', () => {
  it('добавляет и удаляет тест-кейс', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TaskForm onSubmit={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getAllByLabelText(/Ввод \(stdin\)/)).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Добавить кейс' }));
    expect(screen.getAllByLabelText(/Ввод \(stdin\)/)).toHaveLength(2);
    await user.click(screen.getAllByRole('button', { name: 'Удалить' })[1]);
    expect(screen.getAllByLabelText(/Ввод \(stdin\)/)).toHaveLength(1);
  });

  it('валидирует обязательные поля', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TaskForm onSubmit={vi.fn()} onCancel={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(screen.getByRole('alert')).toHaveTextContent(/Название/);
  });

  it('отправляет заполненную форму', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithRouter(<TaskForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText('Название'), 'Сумма чисел');
    await user.type(
      screen.getByLabelText('Условие'),
      'Считайте два числа и выведите сумму.',
    );
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Сумма чисел' }),
    );
  });
});

describe('TeacherTasksPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: makeUser('teacher') });
    vi.restoreAllMocks();
  });

  it('загружает задачи и открывает форму', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      total: 1,
      items: [
        {
          id: '22222222-2222-2222-2222-222222222222',
          title: 'Циклы',
          difficulty: 'easy',
          category: 'loops',
          tags: ['for'],
          test_cases_count: 2,
          hints_count: 1,
          is_active: true,
          created_at: '2026-10-29T10:00:00',
        },
      ],
    });

    renderWithRouter(<TeacherTasksPage />);

    await waitFor(() => expect(screen.getByText('Циклы')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Новая задача' }));

    expect(screen.getByTestId('task-form')).toBeInTheDocument();
  });
});
