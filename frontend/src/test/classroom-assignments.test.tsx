import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { ClassroomDetailPage } from '@/pages/ClassroomDetailPage';
import { useAuthStore } from '@/store/auth';
import type { User } from '@/types/api';

const OWNER_ID = '11111111-1111-1111-1111-111111111111';
const CLASSROOM_ID = '22222222-2222-2222-2222-222222222222';
const ASSIGNMENT_ID = '33333333-3333-3333-3333-333333333333';
const TASK_ID = '44444444-4444-4444-4444-444444444444';

const USER: User = {
  id: OWNER_ID,
  email: 'teacher@example.com',
  username: 'teacher',
  role: 'teacher',
  level: 'basic',
  created_at: '2026-11-08T10:00:00',
  last_active: '2026-11-08T10:00:00',
  settings: {},
};

const ASSIGNMENT = {
  id: ASSIGNMENT_ID,
  task_id: TASK_ID,
  title: 'Сумма двух чисел',
  difficulty: 'easy' as const,
  due_at: '2026-11-10T10:00:00',
  created_at: '2026-11-01T10:00:00',
  completed_count: 1,
  total_members: 2,
};

function mockApi() {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path === `/classrooms/${CLASSROOM_ID}`) {
      return {
        id: CLASSROOM_ID,
        name: '7А класс',
        owner_id: OWNER_ID,
        join_code: 'ABC123',
        created_at: '2026-11-01T10:00:00',
        members_count: 2,
        members: [],
      } as never;
    }
    if (path === `/classrooms/${CLASSROOM_ID}/assignments`) {
      return { items: [ASSIGNMENT] } as never;
    }
    if (path === '/teacher/tasks') {
      return { items: [], total: 0 } as never;
    }
    if (path === `/classrooms/${CLASSROOM_ID}/progress`) {
      return {
        students: [],
        tasks: [],
        cells: [],
        completion_rate: 0,
        problem_tasks: [],
      } as never;
    }
    if (path.endsWith('/announcements')) {
      return { items: [] } as never;
    }
    throw new Error(`unexpected path ${path}`);
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/classrooms/${CLASSROOM_ID}`]}>
      <Routes>
        <Route path="/classrooms/:classroomId" element={<ClassroomDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('управление назначениями (S46-004)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER });
    vi.restoreAllMocks();
  });

  it('переносит срок назначения из строки', async () => {
    const user = userEvent.setup();
    mockApi();
    const patch = vi.spyOn(api, 'patch').mockResolvedValue(ASSIGNMENT as never);
    renderPage();

    const input = await screen.findByLabelText('Срок для «Сумма двух чисел»');
    fireEvent.change(input, { target: { value: '2026-12-01T10:00' } });
    await user.click(screen.getByRole('button', { name: 'Сохранить срок' }));

    await waitFor(() => {
      expect(patch).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/assignments/${ASSIGNMENT_ID}`,
        { due_at: new Date('2026-12-01T10:00').toISOString() },
      );
    });
    expect(
      await screen.findByText('Срок назначения обновлён'),
    ).toBeInTheDocument();
  });

  it('снимает назначение после подтверждения', async () => {
    const user = userEvent.setup();
    mockApi();
    const remove = vi.spyOn(api, 'delete').mockResolvedValue(undefined);
    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Снять' }));
    await user.click(
      screen.getByRole('button', { name: 'Точно снять?' }),
    );

    await waitFor(() => {
      expect(remove).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/assignments/${ASSIGNMENT_ID}`,
      );
    });
    expect(await screen.findByText('Назначение снято')).toBeInTheDocument();
  });

  it('массово переносит срок выбранных назначений', async () => {
    const user = userEvent.setup();
    mockApi();
    const patch = vi.spyOn(api, 'patch').mockResolvedValue(ASSIGNMENT as never);
    renderPage();

    await user.click(
      await screen.findByLabelText('Выбрать назначение «Сумма двух чисел»'),
    );
    fireEvent.change(screen.getByLabelText('Новый срок для выбранных'), {
      target: { value: '2026-12-15T09:00' },
    });
    await user.click(screen.getByRole('button', { name: 'Перенести срок' }));

    await waitFor(() => {
      expect(patch).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/assignments/${ASSIGNMENT_ID}`,
        { due_at: new Date('2026-12-15T09:00').toISOString() },
      );
    });
    expect(
      await screen.findByText(/Срок перенесён у назначений: 1/),
    ).toBeInTheDocument();
  });
});
