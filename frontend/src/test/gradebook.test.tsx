import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { GradebookPage } from '@/pages/GradebookPage';

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), download: vi.fn() },
}));

const getMock = vi.mocked(api.get);
const downloadMock = vi.mocked(api.download);

afterEach(() => {
  vi.clearAllMocks();
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/classrooms/c1/gradebook']}>
      <Routes>
        <Route path="/classrooms/:classroomId/gradebook" element={<GradebookPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('GradebookPage (S28-003 UI)', () => {
  it('рендерит матрицу «ученик × задача» и сводку', async () => {
    getMock.mockResolvedValue({
      students: [{ id: 's1', username: 'Аня' }],
      tasks: [{ id: 't1', title: 'Циклы' }],
      cells: [
        {
          student_id: 's1',
          task_id: 't1',
          status: 'completed',
          attempts: 2,
          completed_at: '2026-10-31T10:00:00',
        },
      ],
      completion_rate: 0.5,
      overdue: 1,
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('Аня')).toBeInTheDocument());
    expect(screen.getByText('Циклы')).toBeInTheDocument();
    expect(screen.getByText('выполнено')).toBeInTheDocument();
    expect(screen.getByText('Попыток: 2')).toBeInTheDocument();
    expect(screen.getByText(/50%/)).toBeInTheDocument();
    expect(screen.getByText(/просрочено: 1/)).toBeInTheDocument();
  });

  it('скачивает CSV', async () => {
    getMock.mockResolvedValue({
      students: [],
      tasks: [],
      cells: [],
      completion_rate: 0,
      overdue: 0,
    });
    downloadMock.mockResolvedValue(new Blob(['student'], { type: 'text/csv' }));

    renderPage();
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: 'Скачать CSV' }));

    expect(downloadMock).toHaveBeenCalledWith('/classrooms/c1/gradebook/csv');
  });

  it('показывает ошибку загрузки', async () => {
    getMock.mockRejectedValue(new Error('boom'));

    renderPage();

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить журнал'),
    );
  });
});
