import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminAuditPage } from '@/pages/AdminAuditPage';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import { renderWithRouter } from '@/test/utils';
import type { AuditLogListResponse } from '@/types/api';

vi.mock('@/lib/download', () => ({ saveBlob: vi.fn() }));

const LOG: AuditLogListResponse = {
  total: 120,
  items: [
    {
      id: 'a1',
      actor_id: 'u1',
      actor_username: 'admin1',
      actor_role: 'admin',
      action: 'task.moderated',
      entity_type: 'task',
      entity_id: '11111111-2222-3333-4444-555555555555',
      payload: {},
      ip: '127.0.0.1',
      created_at: '2026-11-08T10:00:00',
    },
    {
      id: 'a2',
      actor_id: null,
      actor_username: null,
      actor_role: 'system',
      action: 'audit.exported',
      entity_type: 'audit',
      entity_id: null,
      payload: {},
      ip: null,
      created_at: '2026-11-08T10:01:00',
    },
  ],
};

describe('AdminAuditPage (S47-001)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(saveBlob).mockClear();
    vi.spyOn(api, 'get').mockResolvedValue(LOG);
  });

  it('показывает записи и ссылку на сущность', async () => {
    renderWithRouter(<AdminAuditPage />, { route: '/admin/audit' });

    expect(await screen.findByText('task.moderated')).toBeInTheDocument();
    expect(screen.getByText('admin1')).toBeInTheDocument();
    const link = screen.getByRole('link', {
      name: /task · 11111111/,
    });
    expect(link).toHaveAttribute(
      'href',
      '/tasks/11111111-2222-3333-4444-555555555555',
    );
    // Неизвестный тип сущности — без ссылки
    expect(screen.queryByRole('link', { name: /audit/ })).not.toBeInTheDocument();
  });

  it('применяет поиск и сбрасывает страницу', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AdminAuditPage />, { route: '/admin/audit' });

    await screen.findByText('task.moderated');
    await user.type(screen.getByLabelText('Поиск по действию'), 'moderated');
    await user.click(screen.getByRole('button', { name: 'Применить' }));

    await waitFor(() => {
      const calls = vi.mocked(api.get).mock.calls;
      const last = calls[calls.length - 1][0];
      expect(last).toContain('search=moderated');
      expect(last).toContain('skip=0');
    });
  });

  it('переходит на следующую страницу', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AdminAuditPage />, { route: '/admin/audit' });

    await screen.findByText('task.moderated');
    await user.click(screen.getByRole('button', { name: 'Вперёд' }));

    await waitFor(() => {
      const calls = vi.mocked(api.get).mock.calls;
      const last = calls[calls.length - 1][0];
      expect(last).toContain('skip=50');
    });
  });

  it('скачивает CSV с текущими фильтрами', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'download').mockResolvedValue(
      new Blob(['created_at,action'], { type: 'text/csv' }),
    );
    renderWithRouter(<AdminAuditPage />, { route: '/admin/audit' });

    await screen.findByText('task.moderated');
    await user.click(screen.getByRole('button', { name: 'Скачать CSV' }));

    await waitFor(() => {
      expect(api.download).toHaveBeenCalledTimes(1);
    });
    expect(vi.mocked(api.download).mock.calls[0][0]).toContain(
      '/admin/audit/export?',
    );
    expect(saveBlob).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Файл скачан')).toBeInTheDocument();
  });
});
