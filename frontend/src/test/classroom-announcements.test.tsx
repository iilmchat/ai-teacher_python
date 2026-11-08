import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { AssignmentsPage } from '@/pages/AssignmentsPage';
import { ClassroomDetailPage } from '@/pages/ClassroomDetailPage';
import { useAuthStore } from '@/store/auth';
import type { AnnouncementItem, User } from '@/types/api';

const OWNER_ID = '11111111-1111-1111-1111-111111111111';
const STUDENT_ID = '22222222-2222-2222-2222-222222222222';
const CLASSROOM_ID = '33333333-3333-3333-3333-333333333333';
const ANNOUNCEMENT_ID = '44444444-4444-4444-4444-444444444444';

function makeUser(id: string, role: User['role'], username: string): User {
  return {
    id,
    email: `${username}@example.com`,
    username,
    role,
    level: 'basic',
    created_at: '2026-11-08T10:00:00',
    last_active: '2026-11-08T10:00:00',
    settings: {},
  };
}

const TEACHER = makeUser(OWNER_ID, 'teacher', 'teacher');
const STUDENT = makeUser(STUDENT_ID, 'student', 'student');

const ANNOUNCEMENT: AnnouncementItem = {
  id: ANNOUNCEMENT_ID,
  classroom_id: CLASSROOM_ID,
  classroom_name: '7А класс',
  author_id: OWNER_ID,
  author_name: 'teacher',
  title: 'Контрольная в пятницу',
  body: 'Повторите циклы и функции.',
  created_at: '2026-11-08T10:00:00',
  can_delete: true,
};

function mockClassroomApi(options: {
  announcements: AnnouncementItem[];
  ownerId?: string;
}) {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path === `/classrooms/${CLASSROOM_ID}`) {
      return {
        id: CLASSROOM_ID,
        name: '7А класс',
        owner_id: options.ownerId ?? OWNER_ID,
        join_code: 'ABC123',
        created_at: '2026-11-01T10:00:00',
        members_count: 1,
        members: [],
      } as never;
    }
    if (path === `/classrooms/${CLASSROOM_ID}/assignments`) {
      return { items: [] } as never;
    }
    if (path === `/classrooms/${CLASSROOM_ID}/announcements`) {
      return { items: options.announcements } as never;
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

function renderClassroom() {
  return render(
    <MemoryRouter initialEntries={[`/classrooms/${CLASSROOM_ID}`]}>
      <Routes>
        <Route path="/classrooms/:classroomId" element={<ClassroomDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('объявления класса (S46-006)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('учитель публикует объявление и видит его в списке', async () => {
    useAuthStore.setState({ user: TEACHER });
    let announcements: AnnouncementItem[] = [];
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === `/classrooms/${CLASSROOM_ID}`) {
        return {
          id: CLASSROOM_ID,
          name: '7А класс',
          owner_id: OWNER_ID,
          join_code: 'ABC123',
          created_at: '2026-11-01T10:00:00',
          members_count: 1,
          members: [],
        } as never;
      }
      if (path === `/classrooms/${CLASSROOM_ID}/announcements`) {
        return { items: announcements } as never;
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
    const post = vi.spyOn(api, 'post').mockImplementation(async () => {
      announcements = [ANNOUNCEMENT];
      return ANNOUNCEMENT as never;
    });
    const user = userEvent.setup();
    renderClassroom();

    expect(
      await screen.findByText('Объявлений пока нет'),
    ).toBeInTheDocument();
    await user.type(
      screen.getByLabelText('Тема объявления'),
      'Контрольная в пятницу',
    );
    await user.type(
      screen.getByLabelText('Текст объявления для учеников'),
      'Повторите циклы и функции.',
    );
    await user.click(screen.getByRole('button', { name: 'Опубликовать' }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/announcements`,
        {
          title: 'Контрольная в пятницу',
          body: 'Повторите циклы и функции.',
        },
      );
    });
    expect(
      await screen.findByText('Объявление опубликовано'),
    ).toBeInTheDocument();
    expect(
      await screen.findByText('Повторите циклы и функции.'),
    ).toBeInTheDocument();
  });

  it('ученик видит объявление, но не форму публикации', async () => {
    useAuthStore.setState({ user: STUDENT });
    mockClassroomApi({
      announcements: [{ ...ANNOUNCEMENT, can_delete: false }],
    });
    renderClassroom();

    expect(
      await screen.findByText('Контрольная в пятницу'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Повторите циклы и функции/),
    ).toBeInTheDocument();
    expect(
      screen.queryByLabelText('Тема объявления'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Опубликовать' }),
    ).not.toBeInTheDocument();
  });

  it('учитель удаляет объявление', async () => {
    useAuthStore.setState({ user: TEACHER });
    mockClassroomApi({ announcements: [ANNOUNCEMENT] });
    const remove = vi.spyOn(api, 'delete').mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderClassroom();

    await user.click(await screen.findByRole('button', { name: 'Удалить' }));

    await waitFor(() => {
      expect(remove).toHaveBeenCalledWith(
        `/classrooms/${CLASSROOM_ID}/announcements/${ANNOUNCEMENT_ID}`,
      );
    });
    expect(await screen.findByText('Объявление удалено')).toBeInTheDocument();
  });

  it('ученик видит ленту объявлений в «Моих заданиях»', async () => {
    useAuthStore.setState({ user: STUDENT });
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/me/assignments') {
        return { items: [] } as never;
      }
      if (path === '/me/announcements') {
        return { items: [ANNOUNCEMENT] } as never;
      }
      throw new Error(`unexpected path ${path}`);
    });
    render(
      <MemoryRouter>
        <AssignmentsPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText('Контрольная в пятницу'),
    ).toBeInTheDocument();
    expect(screen.getByText(/7А класс · teacher/)).toBeInTheDocument();
    expect(
      screen.getByText('Повторите циклы и функции.'),
    ).toBeInTheDocument();
  });
});
