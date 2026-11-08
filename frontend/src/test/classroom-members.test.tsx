import { render, screen, waitFor } from '@testing-library/react';
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
const S1_ID = '33333333-3333-3333-3333-333333333333';
const S2_ID = '44444444-4444-4444-4444-444444444444';

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

function detail(members: { user_id: string; username: string }[]) {
  return {
    id: CLASSROOM_ID,
    name: '7А класс',
    owner_id: OWNER_ID,
    join_code: 'ABC123',
    created_at: '2026-11-01T10:00:00',
    members_count: members.length,
    members: members.map((member) => ({
      ...member,
      role: 'student',
      joined_at: '2026-11-02T10:00:00',
    })),
  };
}

function mockApi(members: { user_id: string; username: string }[]) {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path === `/classrooms/${CLASSROOM_ID}`) {
      return detail(members) as never;
    }
    if (path === `/classrooms/${CLASSROOM_ID}/assignments`) {
      return { items: [] } as never;
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

describe('массовые операции с учениками (S46-005)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER });
    vi.restoreAllMocks();
  });

  it('добавляет учеников списком и показывает отчёт', async () => {
    const user = userEvent.setup();
    mockApi([{ user_id: S1_ID, username: 'student1' }]);
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      added: ['student2'],
      skipped: ['student1'],
      unknown: ['ghost'],
    } as never);
    renderPage();

    await user.type(
      await screen.findByLabelText('Добавить учеников списком логинов'),
      'student1, student2\nghost',
    );
    await user.click(screen.getByRole('button', { name: 'Добавить учеников' }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/members/bulk`,
        { usernames: ['student1', 'student2', 'ghost'] },
      );
    });
    expect(await screen.findByText('Добавлены: student2')).toBeInTheDocument();
    expect(screen.getByText('Уже в классе: student1')).toBeInTheDocument();
    expect(screen.getByText('Не найдены: ghost')).toBeInTheDocument();
  });

  it('массово исключает выбранных учеников', async () => {
    const user = userEvent.setup();
    mockApi([
      { user_id: S1_ID, username: 'student1' },
      { user_id: S2_ID, username: 'student2' },
    ]);
    const remove = vi.spyOn(api, 'delete').mockResolvedValue({
      removed: [S1_ID, S2_ID],
      skipped: [],
    } as never);
    renderPage();

    await user.click(
      await screen.findByLabelText('Выбрать ученика student1'),
    );
    await user.click(screen.getByLabelText('Выбрать ученика student2'));
    expect(screen.getByText('Выбрано учеников: 2')).toBeInTheDocument();
    await user.click(
      screen.getByRole('button', { name: 'Исключить выбранных' }),
    );

    await waitFor(() => {
      expect(remove).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/members/bulk`,
        { user_ids: [S1_ID, S2_ID] },
      );
    });
    expect(await screen.findByText('Исключено учеников: 2')).toBeInTheDocument();
  });

  it('ошибка массового добавления показывается пользователю', async () => {
    const user = userEvent.setup();
    mockApi([]);
    vi.spyOn(api, 'post').mockRejectedValue(new Error('boom'));
    renderPage();

    await user.type(
      await screen.findByLabelText('Добавить учеников списком логинов'),
      'student1',
    );
    await user.click(screen.getByRole('button', { name: 'Добавить учеников' }));

    expect(
      await screen.findByText('Не удалось добавить учеников'),
    ).toBeInTheDocument();
  });
});
