import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type {
  AdminTaskItem,
  AdminTaskListResponse,
  AdminUserItem,
  AdminUserListResponse,
  AnalyticsResponse,
  UserRole,
} from '@/types/api';

const ROLES: UserRole[] = ['student', 'teacher', 'admin'];

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function AdminPage() {
  const { t } = useTranslation();
  const currentUserId = useAuthStore((state) => state.user?.id);

  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [tasks, setTasks] = useState<AdminTaskItem[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [analyticsData, usersData, tasksData] = await Promise.all([
        api.get<AnalyticsResponse>('/admin/analytics'),
        api.get<AdminUserListResponse>(
          `/admin/users?limit=50${search ? `&search=${encodeURIComponent(search)}` : ''}`,
        ),
        api.get<AdminTaskListResponse>('/admin/tasks?limit=50'),
      ]);
      setAnalytics(analyticsData);
      setUsers(usersData.items);
      setTasks(tasksData.items);
    } catch {
      setError(t('admin.loadError'));
    } finally {
      setLoading(false);
    }
  }, [search, t]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function changeRole(userId: string, role: UserRole) {
    setNotice(null);
    try {
      const updated = await api.patch<AdminUserItem>(`/admin/users/${userId}`, { role });
      setUsers((items) => items.map((item) => (item.id === userId ? updated : item)));
      setNotice(t('admin.roleSaved'));
    } catch {
      setError(t('admin.roleError'));
    }
  }

  async function removeUser(userId: string) {
    setNotice(null);
    try {
      await api.delete(`/admin/users/${userId}`);
      setUsers((items) => items.filter((item) => item.id !== userId));
      setNotice(t('admin.userDeleted'));
    } catch {
      setError(t('admin.userDeleteError'));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t('admin.title')}</h1>
        <Button variant="secondary" onClick={() => void loadAll()} loading={loading}>
          {t('admin.refresh')}
        </Button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}
      {loading && !analytics && <Spinner />}

      {analytics && (
        <>
          <Card title={t('admin.overview')}>
            <div className="grid gap-3 sm:grid-cols-4">
              <Metric label={t('admin.usersTotal')} value={analytics.users.total} />
              <Metric label={t('admin.active24h')} value={analytics.users.active_24h} />
              <Metric label={t('admin.tasksTotal')} value={analytics.tasks.total} />
              <Metric label={t('admin.completed')} value={analytics.learning.completed} />
              <Metric label={t('admin.attempts')} value={analytics.learning.attempts} />
              <Metric label={t('admin.avgAttempts')} value={analytics.learning.average_attempts} />
              <Metric label={t('admin.messages')} value={analytics.activity.messages} />
              <Metric label={t('admin.executions')} value={analytics.activity.executions} />
            </div>
            <p className="mt-3 text-xs text-slate-400">
              {t('admin.generatedAt')}: {new Date(analytics.generated_at).toLocaleString('ru-RU')}
            </p>
          </Card>

          <Card title={t('admin.llmTitle')}>
            {analytics.llm.last_24h.requests === 0 ? (
              <p className="text-sm text-slate-500">{t('admin.llmEmpty')}</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-4">
                <Metric
                  label={t('admin.llmProvider')}
                  value={Object.keys(analytics.llm.last_24h.by_provider).join(', ') || '—'}
                />
                <Metric label={t('admin.llmRequests')} value={analytics.llm.last_24h.requests} />
                <Metric label={t('admin.llmErrors')} value={analytics.llm.last_24h.errors} />
                <Metric
                  label={t('admin.llmLatency')}
                  value={`${analytics.llm.last_24h.avg_latency_ms} ms`}
                />
                <Metric
                  label={t('admin.llmFirstToken')}
                  value={`${analytics.llm.last_24h.avg_first_token_ms} ms`}
                />
                <Metric label={t('admin.llmTokens')} value={analytics.llm.last_24h.total_tokens} />
                <Metric label={t('admin.llmFallback')} value={analytics.llm.fallback_used} />
              </div>
            )}
          </Card>
        </>
      )}

      <Card title={t('admin.usersTitle')}>
        <div className="mb-3 flex items-end gap-2">
          <div className="flex-1">
            <Input
              label={t('admin.search')}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('admin.searchPlaceholder')}
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <Table>
            <thead className="text-xs uppercase text-slate-500">
              <Tr>
                <Th className="py-2">{t('admin.colUser')}</Th>
                <Th className="py-2">{t('admin.colEmail')}</Th>
                <Th className="py-2">{t('admin.colRole')}</Th>
                <Th className="py-2">{t('admin.colActions')}</Th>
              </Tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <Tr key={user.id} className="border-t border-slate-100">
                  <Td className="py-2 font-medium text-slate-800">{user.username}</Td>
                  <Td className="py-2 text-slate-600">{user.email}</Td>
                  <Td className="py-2">
                    <select
                      aria-label={`${t('admin.colRole')}: ${user.username}`}
                      value={user.role}
                      disabled={user.id === currentUserId}
                      onChange={(event) =>
                        void changeRole(user.id, event.target.value as UserRole)
                      }
                      className="rounded border border-slate-300 px-2 py-1 text-xs"
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {t(`profile.roles.${role}`)}
                        </option>
                      ))}
                    </select>
                  </Td>
                  <Td className="py-2">
                    <Button
                      variant="ghost"
                      disabled={user.id === currentUserId}
                      onClick={() => void removeUser(user.id)}
                    >
                      {t('admin.delete')}
                    </Button>
                  </Td>
                </Tr>
              ))}
              {users.length === 0 && !loading && (
                <Tr>
                  <Td colSpan={4} className="py-4 text-center text-slate-500">
                    {t('admin.nothingFound')}
                  </Td>
                </Tr>
              )}
            </tbody>
          </Table>
        </div>
      </Card>

      <Card title={t('admin.tasksTitle')}>
        <ul className="flex flex-col gap-1 text-sm">
          {tasks.map((task) => (
            <li key={task.id} className="flex items-center justify-between border-t border-slate-100 py-2">
              <span className={task.is_active ? 'text-slate-800' : 'text-slate-400 line-through'}>
                {task.title}
              </span>
              <span className="text-xs text-slate-500">
                {t(`tasks.difficulty.${task.difficulty}`)} ·{' '}
                {t('admin.casesCount', { count: task.test_cases_count })}
              </span>
            </li>
          ))}
          {tasks.length === 0 && !loading && (
            <li className="py-4 text-center text-slate-500">{t('admin.nothingFound')}</li>
          )}
        </ul>
      </Card>
    </div>
  );
}
