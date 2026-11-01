import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { AssignmentTemplates } from '@/components/teacher/AssignmentTemplates';
import { api } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

const getMock = vi.mocked(api.get);
const postMock = vi.mocked(api.post);
const deleteMock = vi.mocked(api.delete);

afterEach(() => {
  vi.clearAllMocks();
});

function renderPanel(selected: string[] = []) {
  return render(
    <AssignmentTemplates classroomId="c1" selectedTaskIds={selected} onApplied={vi.fn()} />,
  );
}

describe('AssignmentTemplates (S28-002 UI)', () => {
  it('показывает список шаблонов и применяет выбранный', async () => {
    getMock.mockResolvedValue({
      items: [{ id: 'tpl1', name: 'Вводный блок', task_ids: ['t1', 't2'], created_at: '' }],
      total: 1,
    });
    postMock.mockResolvedValue({ created: ['t1'], skipped: [], unknown: [] });

    renderPanel();

    await waitFor(() => expect(screen.getByRole('option', { name: /Вводный блок/ })).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Применить' }));

    expect(postMock).toHaveBeenCalledWith('/classrooms/c1/assignments/from-template', {
      template_id: 'tpl1',
    });
    await waitFor(() => expect(screen.getByText(/Создано: 1/)).toBeInTheDocument());
  });

  it('сохраняет выбранные задачи как шаблон', async () => {
    getMock.mockResolvedValue({ items: [], total: 0 });
    postMock.mockResolvedValue({ id: 'tpl2', name: 'Блок 2', task_ids: ['t1'], created_at: '' });

    renderPanel(['t1']);

    await waitFor(() => expect(getMock).toHaveBeenCalled());
    await userEvent.type(screen.getByLabelText('Название шаблона'), 'Блок 2');
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить выбранные' }));

    expect(postMock).toHaveBeenCalledWith('/teacher/assignment-templates', {
      name: 'Блок 2',
      task_ids: ['t1'],
    });
    await waitFor(() => expect(screen.getByText('Шаблон сохранён')).toBeInTheDocument());
  });

  it('удаляет шаблон', async () => {
    getMock.mockResolvedValue({
      items: [{ id: 'tpl3', name: 'Старый', task_ids: [], created_at: '' }],
      total: 1,
    });
    deleteMock.mockResolvedValue(undefined as never);

    renderPanel();
    await waitFor(() => expect(screen.getByText('Старый')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Удалить шаблон: Старый' }));

    expect(deleteMock).toHaveBeenCalledWith('/teacher/assignment-templates/tpl3');
  });

  it('показывает ошибку загрузки', async () => {
    getMock.mockRejectedValue(new Error('boom'));

    renderPanel();

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Не удалось загрузить шаблоны'),
    );
  });
});
