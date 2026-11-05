import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { AdminPage } from '@/pages/AdminPage';
import { renderWithRouter } from '@/test/utils';
import type { AdminQualityResponse, AnalyticsResponse } from '@/types/api';

const QUALITY: AdminQualityResponse = {
  total: 3,
  positive: 2,
  negative: 1,
  approval_rate: 0.6667,
  by_provider: [
    {
      name: 'deepseek',
      total: 3,
      positive: 2,
      negative: 1,
      approval_rate: 0.6667,
    },
  ],
  by_model: [],
  negative_samples: [
    {
      message_id: 'm1',
      comment: 'Слишком сложно',
      content: 'Текст ответа ассистента',
      provider: 'deepseek',
      model: 'deepseek-chat',
      created_at: '2026-11-06T10:00:00',
    },
  ],
  generated_at: '2026-11-06T10:00:00',
};

const ANALYTICS = {
  users: { total: 1, by_role: {}, active_24h: 0, active_7d: 0 },
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
    recorded_at: '2026-11-06T10:00:00',
  },
  generated_at: '2026-11-06T10:00:00',
} as AnalyticsResponse;

describe('AdminPage: качество ответов (S43-003)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/admin/quality') {
        return QUALITY;
      }
      if (path === '/admin/analytics') {
        return ANALYTICS;
      }
      if (path.startsWith('/admin/users')) {
        return { total: 0, items: [] };
      }
      return { total: 0, items: [] };
    });
  });

  it('показывает счётчики оценок и разрез по провайдеру', async () => {
    renderWithRouter(<AdminPage />, { route: '/admin' });

    expect(await screen.findByText('Качество ответов ассистента')).toBeInTheDocument();
    expect(screen.getAllByText('Оценок').length).toBeGreaterThan(0);
    expect(screen.getAllByText('67%').length).toBeGreaterThan(0);
    expect(screen.getByText('deepseek')).toBeInTheDocument();
  });

  it('показывает негативные оценки с текстом ответа', async () => {
    renderWithRouter(<AdminPage />, { route: '/admin' });

    await waitFor(() => {
      expect(screen.getByText('Слишком сложно')).toBeInTheDocument();
    });
    expect(screen.getByText('Текст ответа ассистента')).toBeInTheDocument();
  });

  it('сообщает, что оценок ещё нет', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/admin/quality') {
        return { ...QUALITY, total: 0, positive: 0, negative: 0, approval_rate: 0 };
      }
      if (path === '/admin/analytics') {
        return ANALYTICS;
      }
      return { total: 0, items: [] };
    });

    renderWithRouter(<AdminPage />, { route: '/admin' });

    expect(
      await screen.findByText(/Оценок пока нет/),
    ).toBeInTheDocument();
  });
});
