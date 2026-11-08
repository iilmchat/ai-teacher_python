import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { ClassroomDetailPage } from '@/pages/ClassroomDetailPage';
import { useAuthStore } from '@/store/auth';
import type { AssignmentAnalytics, User } from '@/types/api';

const OWNER_ID = '11111111-1111-1111-1111-111111111111';
const CLASSROOM_ID = '22222222-2222-2222-2222-222222222222';
const ASSIGNMENT_ID = '33333333-3333-3333-3333-333333333333';
const TASK_ID = '44444444-4444-4444-4444-444444444444';
const STUDENT_ID = '55555555-5555-5555-5555-555555555555';

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

const ANALYTICS: AssignmentAnalytics = {
  assignment_id: ASSIGNMENT_ID,
  task_id: TASK_ID,
  task_title: 'Сумма двух чисел',
  due_at: '2026-11-01T10:00:00',
  total_students: 2,
  completed: 1,
  in_progress: 1,
  not_started: 0,
  overdue: 1,
  attempts_total: 5,
  attempts_distribution: [
    { attempts: 1, students: 1 },
    { attempts: 4, students: 1 },
  ],
  problem_threshold: 3,
  problem_students: [
    {
      student_id: STUDENT_ID,
      username: 'student2',
      status: 'in_progress',
      attempts: 4,
      completed_at: null,
      overdue: true,
    },
  ],
  students: [
    {
      student_id: '66666666-6666-6666-6666-666666666666',
      username: 'student1',
      status: 'completed',
      attempts: 1,
      completed_at: '2026-11-02T10:00:00',
      overdue: false,
    },
    {
      student_id: STUDENT_ID,
      username: 'student2',
      status: 'in_progress',
      attempts: 4,
      completed_at: null,
      overdue: true,
    },
  ],
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
      return {
        items: [
          {
            id: ASSIGNMENT_ID,
            task_id: TASK_ID,
            title: 'Сумма двух чисел',
            difficulty: 'easy',
            due_at: '2026-11-01T10:00:00',
            created_at: '2026-11-01T10:00:00',
            completed_count: 1,
            total_members: 2,
          },
        ],
      } as never;
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
    if (path.endsWith('/analytics')) {
      return ANALYTICS as never;
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

describe('drill-down по назначению (S46-003)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: USER });
    vi.restoreAllMocks();
  });

  it('клик по назначению открывает «кто как справился»', async () => {
    const user = userEvent.setup();
    mockApi();
    renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Сумма двух чисел' }),
    );

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/assignments/${ASSIGNMENT_ID}/analytics`,
      );
    });
    expect(
      await screen.findByText(
        'Кто как справился: Сумма двух чисел',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Выполнили: 1/)).toBeInTheDocument();
    expect(screen.getByText(/В работе: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Просрочили: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Проблемные ученики/)).toBeInTheDocument();
    expect(screen.getAllByText('student2').length).toBeGreaterThan(0);
  });

  it('из панели можно перейти к работам ученика', async () => {
    const user = userEvent.setup();
    mockApi();
    renderPage();

    await user.click(
      await screen.findByRole('button', { name: 'Сумма двух чисел' }),
    );
    const links = await screen.findAllByRole('link', {
      name: 'Открыть работы',
    });

    expect(links[0]).toHaveAttribute(
      'href',
      `/teacher/students?student=66666666-6666-6666-6666-666666666666&tab=works`,
    );
  });
});
