import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { AdminPage } from '@/pages/AdminPage';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import { renderWithRouter } from '@/test/utils';
import type {
  AdminQualityResponse,
  AdminUserBulkResponse,
  AdminUserItem,
  AnalyticsResponse,
} from '@/types/api';

vi.mock('@/lib/download', () => ({ saveBlob: vi.fn() }));

const USERS: AdminUserItem[] = [
  {
    id: 'u1',
    email: 'one@example.com',
    username: 'one',
    role: 'student',
    level: 'basic',
    is_active: true,
    created_at: '2026-11-01T10:00:00',
    last_active: '2026-11-08T10:00:00',
  },
  {
    id: 'u2',
    email: 'two@example.com',
    username: 'two',
    role: 'student',
    level: 'basic',
    is_active: true,
    created_at: '2026-11-02T10:00:00',
    last_active: '2026-11-08T11:00:00',
  },
];

const ANALYTICS = {
  users: { total: 2, by_role: {}, active_24h: 0, active_7d: 0 },
  tasks: { total: 0, active: 0, easy: 0, medium: 0, hard: 0 },
  learning: { attempts: 0, completed: 0, started: 0, average_attempts: 0 },
  activity: { sessions: 0, messages: 0, executions: 0, failed_executions: 0 },
  llm: {
    last_hour: {
      window_hours: 1,
      requests: 0,
      errors: 0,
      avg_latency_ms: 0,
      p95_latency_ms: 0,
      avg_first_token_ms: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      by_provider: {},
    },
    last_24h: {
      window_hours: 24,
      requests: 0,
      errors: 0,
      avg_latency_ms: 0,
      p95_latency_ms: 0,
      avg_first_token_ms: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      by_provider: {},
    },
    fallback_used: 0,
    recorded_at: '2026-11-08T10:00:00',
  },
  generated_at: '2026-11-08T10:00:00',
} as AnalyticsResponse;

const QUALITY = {
  total: 0,
  positive: 0,
  negative: 0,
  approval_rate: 0,
  by_provider: [],
  by_model: [],
  negative_samples: [],
  generated_at: '2026-11-08T10:00:00',
} as AdminQualityResponse;

describe('AdminPage: выгрузка и массовые действия (S47-002)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(saveBlob).mockClear();
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/admin/analytics') return ANALYTICS;
      if (path === '/admin/quality') return QUALITY;
      if (path.startsWith('/admin/users')) return { total: 2, items: USERS };
      return { total: 0, items: [] };
    });
  });

  it('скачивает выбранный набор в выбранном формате', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'download').mockResolvedValue(
      new Blob(['[]'], { type: 'application/json' }),
    );
    renderWithRouter(<AdminPage />, { route: '/admin' });

    await screen.findByText('Выгрузка данных');
    await user.selectOptions(screen.getByLabelText('Набор'), 'tasks');
    await user.selectOptions(screen.getByLabelText('Формат'), 'json');
    await user.click(screen.getByRole('button', { name: 'Скачать файл' }));

    await waitFor(() => {
      expect(api.download).toHaveBeenCalledWith(
        '/admin/analytics/export?dataset=tasks&format=json',
      );
    });
    expect(saveBlob).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Файл скачан')).toBeInTheDocument();
    expect(screen.getByText(/EXPORT_MAX_ROWS/)).toBeInTheDocument();
  });

  it('применяет массовую смену роли с подтверждением и показывает отчёт', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'patch').mockResolvedValue({
      updated: ['u2'],
      skipped: [{ id: 'u1', reason: 'no_changes' }],
    } satisfies AdminUserBulkResponse);
    renderWithRouter(<AdminPage />, { route: '/admin' });

    await screen.findByText('two');
    await user.click(screen.getByLabelText('Выбрать two'));
    await user.selectOptions(screen.getByLabelText('Новая роль'), 'teacher');
    await user.click(screen.getByRole('button', { name: 'Применить (1)' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Применить изменения к 1/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Применить' }));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/admin/users/bulk', {
        user_ids: ['u2'],
        changes: { role: 'teacher' },
      });
    });
    expect(await screen.findByText('Обновлено: 1')).toBeInTheDocument();
    expect(screen.getByText(/one: без изменений/)).toBeInTheDocument();
  });

  it('ссылка на пользователя ведёт в карточку', async () => {
    renderWithRouter(<AdminPage />, { route: '/admin' });

    const link = await screen.findByRole('link', { name: 'two' });
    expect(link).toHaveAttribute('href', '/admin/users/u2');
  });
});
