import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { TeacherStudentsPage } from '@/pages/TeacherStudentsPage';
import { api } from '@/lib/api';
import { renderWithRouter } from '@/test/utils';

const STUDENT = {
  id: 'student-1',
  email: 'student@example.com',
  username: 'student',
  level: 'basic' as const,
  completed_tasks: 1,
  attempts: 2,
  last_active: '2026-11-08T10:00:00',
};

const PROGRESS = {
  student: STUDENT,
  total_tasks: 2,
  completed: 1,
  in_progress: 1,
  completion_rate: 50,
  items: [
    {
      task_id: 'task-1',
      title: 'Сумма двух чисел',
      difficulty: 'easy' as const,
      status: 'completed' as const,
      attempts: 1,
      completed_at: '2026-11-08T09:00:00',
      best_solution: 'a = int(input())\nb = int(input())\nprint(a + b)',
    },
    {
      task_id: 'task-2',
      title: 'Циклы',
      difficulty: 'medium' as const,
      status: 'in_progress' as const,
      attempts: 1,
      completed_at: null,
      best_solution: null,
    },
  ],
};

const ATTEMPTS = {
  total: 1,
  items: [
    {
      id: 'attempt-1',
      task_id: 'task-1',
      task_title: 'Сумма двух чисел',
      passed: true,
      passed_count: 2,
      total_count: 2,
      created_at: '2026-11-08T09:00:00',
    },
  ],
};

const DETAIL = {
  ...ATTEMPTS.items[0],
  student_id: 'student-1',
  code: 'a = int(input())\nb = int(input())\nprint(a + b)',
  results: [
    {
      index: 0,
      passed: true,
      description: 'Положительные',
      input: '2\n3\n',
      expected_output: '5',
      actual_output: '5',
      error: null,
    },
  ],
  feedback: [
    {
      id: 'feedback-1',
      comment: 'Разбери второй тест',
      teacher_name: 'teacher',
      created_at: '2026-11-08T10:00:00',
    },
  ],
};

describe('работы ученика в кабинете учителя (S46-001)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/teacher/students') {
        return { total: 1, items: [STUDENT] } as never;
      }
      if (path.endsWith('/progress')) {
        return PROGRESS as never;
      }
      if (path.endsWith('/attempts')) {
        return ATTEMPTS as never;
      }
      if (path.includes('/attempts/')) {
        return DETAIL as never;
      }
      throw new Error(`unexpected path ${path}`);
    });
  });

  it('вкладка «Работы» показывает попытки ученика', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TeacherStudentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Прогресс' }));
    await screen.findByText('Сумма двух чисел');
    await user.click(screen.getByRole('tab', { name: 'Работы' }));

    expect(await screen.findByText('Сумма двух чисел')).toBeInTheDocument();
    expect(screen.getByText(/Решено:/)).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/teacher/students/student-1/attempts');
  });

  it('работа открывается с кодом и разбором тест-кейсов', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TeacherStudentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Прогресс' }));
    await screen.findByText('Сумма двух чисел');
    await user.click(screen.getByRole('tab', { name: 'Работы' }));
    await user.click(await screen.findByRole('button', { name: 'Открыть' }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        '/teacher/students/student-1/attempts/attempt-1',
      );
    });
    const editor = await screen.findByTestId('monaco-mock');
    expect(editor).toHaveValue(DETAIL.code);
    expect(screen.getByText('Ожидалось')).toBeInTheDocument();
  });

  it('ошибка загрузки работ показывается пользователю', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/teacher/students') {
        return { total: 1, items: [STUDENT] } as never;
      }
      if (path.endsWith('/progress')) {
        return PROGRESS as never;
      }
      throw new Error('boom');
    });
    renderWithRouter(<TeacherStudentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Прогресс' }));
    await user.click(screen.getByRole('tab', { name: 'Работы' }));

    expect(
      await screen.findByText('Не удалось загрузить работы'),
    ).toBeInTheDocument();
  });

  it('последнее успешное решение показывается в прогрессе', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TeacherStudentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Прогресс' }));

    expect(await screen.findByText('Показать')).toBeInTheDocument();
  });

  it('существующий комментарий учителя виден в работе (S46-002)', async () => {
    const user = userEvent.setup();
    renderWithRouter(<TeacherStudentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Прогресс' }));
    await user.click(await screen.findByRole('tab', { name: 'Работы' }));
    await user.click(await screen.findByRole('button', { name: 'Открыть' }));

    expect(await screen.findByText('Разбери второй тест')).toBeInTheDocument();
  });

  it('учитель отправляет комментарий к работе (S46-002)', async () => {
    const user = userEvent.setup();
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      id: 'feedback-new',
      comment: 'Молодец',
      teacher_name: 'teacher',
      created_at: '2026-11-08T11:00:00',
    } as never);
    renderWithRouter(<TeacherStudentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Прогресс' }));
    await user.click(await screen.findByRole('tab', { name: 'Работы' }));
    await user.click(await screen.findByRole('button', { name: 'Открыть' }));
    await user.type(
      await screen.findByLabelText(
        'Что ученику стоит исправить или попробовать?',
      ),
      'Молодец',
    );
    await user.click(
      screen.getByRole('button', { name: 'Отправить комментарий' }),
    );

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/teacher/attempts/attempt-1/feedback', {
        comment: 'Молодец',
      });
    });
    expect(await screen.findByText('Молодец')).toBeInTheDocument();
  });

  it('открывает работы ученика по ссылке из drill-down (S46-003)', async () => {
    renderWithRouter(<TeacherStudentsPage />, {
      route: '/teacher/students?student=student-1&tab=works',
    });

    expect(await screen.findByRole('tab', { name: 'Работы' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(await screen.findByText('Сумма двух чисел')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/teacher/students/student-1/attempts');
  });
});
