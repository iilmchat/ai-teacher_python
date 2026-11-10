import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import { useAuthStore } from '@/store/auth';
import type {
  AdminQualityResponse,
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
  const [quality, setQuality] = useState<AdminQualityResponse | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [tasks, setTasks] = useState<AdminTaskItem[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [exporting, setExporting] = useState(false);
  const [analyticsDataset, setAnalyticsDataset] = useState<
    'users' | 'tasks' | 'attempts' | 'activity'
  >('users');
  const [analyticsFormat, setAnalyticsFormat] = useState<'csv' | 'json'>('csv');
  const [analyticsExporting, setAnalyticsExporting] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [analyticsData, usersData, tasksData, qualityData] = await Promise.all([
        api.get<AnalyticsResponse>('/admin/analytics'),
        api.get<AdminUserListResponse>(
          `/admin/users?limit=50${search ? `&search=${encodeURIComponent(search)}` : ''}`,
        ),
        api.get<AdminTaskListResponse>('/admin/tasks?limit=50'),
        api.get<AdminQualityResponse>('/admin/quality'),
      ]);
      setAnalytics(analyticsData);
      setUsers(usersData.items);
      setTasks(tasksData.items);
      setQuality(qualityData);
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

  async function downloadQuality() {
    setExporting(true);
    setError(null);
    setNotice(null);
    try {
      const blob = await api.download(
        `/admin/quality/export?format=${exportFormat}`,
      );
      const stamp = new Date().toISOString().slice(0, 10);
      saveBlob(blob, `quality-negative-${stamp}.${exportFormat}`);
      setNotice(t('admin.qualityExported'));
    } catch {
      setError(t('admin.qualityExportError'));
    } finally {
      setExporting(false);
    }
  }

  async function downloadAnalytics() {
    setAnalyticsExporting(true);
    setError(null);
    setNotice(null);
    try {
      const blob = await api.download(
        `/admin/analytics/export?dataset=${analyticsDataset}&format=${analyticsFormat}`,
      );
      const stamp = new Date().toISOString().slice(0, 10);
      saveBlob(blob, `analytics-${analyticsDataset}-${stamp}.${analyticsFormat}`);
      setNotice(t('admin.analyticsExported'));
    } catch {
      setError(t('admin.analyticsExportError'));
    } finally {
      setAnalyticsExporting(false);
    }
  }

  function levelLabel(name: string): string {
    if (name === 'unknown') {
      return t('admin.qualityUnknownLevel');
    }
    return ['basic', 'intermediate', 'advanced'].includes(name)
      ? t(`levels.${name}`)
      : name;
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

      <Card title={t('admin.analyticsExportTitle')}>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium text-slate-600">
              {t('admin.analyticsExportDataset')}
            </span>
            <select
              aria-label={t('admin.analyticsExportDataset')}
              value={analyticsDataset}
              onChange={(event) =>
                setAnalyticsDataset(
                  event.target.value as
                    | 'users'
                    | 'tasks'
                    | 'attempts'
                    | 'activity',
                )
              }
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
            >
              {(['users', 'tasks', 'attempts', 'activity'] as const).map((value) => (
                <option key={value} value={value}>
                  {t(`admin.analyticsDatasets.${value}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium text-slate-600">
              {t('admin.analyticsExportFormat')}
            </span>
            <select
              aria-label={t('admin.analyticsExportFormat')}
              value={analyticsFormat}
              onChange={(event) =>
                setAnalyticsFormat(event.target.value === 'json' ? 'json' : 'csv')
              }
              className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </label>
          <Button
            variant="secondary"
            loading={analyticsExporting}
            onClick={() => void downloadAnalytics()}
          >
            {t('admin.analyticsExport')}
          </Button>
        </div>
      </Card>

      <Card title={t('admin.qualityTitle')}>
        {quality && (
          <>
            <div className="mb-3 flex flex-wrap items-end justify-end gap-2">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-xs font-medium text-slate-600">
                  {t('admin.qualityExportFormat')}
                </span>
                <select
                  aria-label={t('admin.qualityExportFormat')}
                  value={exportFormat}
                  onChange={(event) =>
                    setExportFormat(event.target.value === 'json' ? 'json' : 'csv')
                  }
                  className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
                >
                  <option value="csv">CSV</option>
                  <option value="json">JSON</option>
                </select>
              </label>
              <Button
                variant="secondary"
                loading={exporting}
                onClick={() => void downloadQuality()}
              >
                {t('admin.qualityExport')}
              </Button>
            </div>

            {quality.total === 0 ? (
              <p className="text-sm text-slate-500">{t('admin.qualityEmpty')}</p>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-4">
                  <Metric label={t('admin.qualityTotal')} value={quality.total} />
                  <Metric label={t('admin.qualityPositive')} value={quality.positive} />
                  <Metric label={t('admin.qualityNegative')} value={quality.negative} />
                  <Metric
                    label={t('admin.qualityApproval')}
                    value={`${Math.round(quality.approval_rate * 100)}%`}
                  />
                </div>

                {quality.by_provider.length > 0 && (
                  <div className="mt-4 overflow-x-auto">
                    <Table>
                      <thead className="text-xs uppercase text-slate-500">
                        <Tr>
                          <Th className="py-2">{t('admin.qualityProvider')}</Th>
                          <Th className="py-2">{t('admin.qualityTotal')}</Th>
                          <Th className="py-2">{t('admin.qualityPositive')}</Th>
                          <Th className="py-2">{t('admin.qualityNegative')}</Th>
                          <Th className="py-2">{t('admin.qualityApproval')}</Th>
                        </Tr>
                      </thead>
                      <tbody>
                        {quality.by_provider.map((row) => (
                          <Tr key={row.name} className="border-t border-slate-100">
                            <Td className="py-2 font-medium text-slate-800">{row.name}</Td>
                            <Td className="py-2">{row.total}</Td>
                            <Td className="py-2">{row.positive}</Td>
                            <Td className="py-2">{row.negative}</Td>
                            <Td className="py-2">
                              {Math.round(row.approval_rate * 100)}%
                            </Td>
                          </Tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>
                )}
              </>
            )}

            {quality.by_level.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <h3 className="mb-2 text-sm font-semibold text-slate-800">
                  {t('admin.qualityByLevel')}
                </h3>
                <Table>
                  <thead className="text-xs uppercase text-slate-500">
                    <Tr>
                      <Th className="py-2">{t('admin.qualityLevel')}</Th>
                      <Th className="py-2">{t('admin.qualityTotal')}</Th>
                      <Th className="py-2">{t('admin.qualityPositive')}</Th>
                      <Th className="py-2">{t('admin.qualityNegative')}</Th>
                      <Th className="py-2">{t('admin.qualityApproval')}</Th>
                    </Tr>
                  </thead>
                  <tbody>
                    {quality.by_level.map((row) => (
                      <Tr key={row.name} className="border-t border-slate-100">
                        <Td className="py-2 font-medium text-slate-800">
                          {levelLabel(row.name)}
                        </Td>
                        <Td className="py-2">{row.total}</Td>
                        <Td className="py-2">{row.positive}</Td>
                        <Td className="py-2">{row.negative}</Td>
                        <Td className="py-2">
                          {Math.round(row.approval_rate * 100)}%
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}

            {quality.top_problem_topics.length > 0 && (
              <div className="mt-4 overflow-x-auto">
                <h3 className="mb-2 text-sm font-semibold text-slate-800">
                  {t('admin.qualityTopics')}
                </h3>
                <Table>
                  <thead className="text-xs uppercase text-slate-500">
                    <Tr>
                      <Th className="py-2">{t('admin.qualityTopicKind')}</Th>
                      <Th className="py-2">{t('admin.qualityTopicName')}</Th>
                      <Th className="py-2">{t('admin.qualityNegative')}</Th>
                    </Tr>
                  </thead>
                  <tbody>
                    {quality.top_problem_topics.map((row) => (
                      <Tr
                        key={`${row.kind}:${row.name}`}
                        className="border-t border-slate-100"
                      >
                        <Td className="py-2 text-slate-600">
                          {row.kind === 'none'
                            ? '—'
                            : t(`admin.qualityTopicKinds.${row.kind}`)}
                        </Td>
                        <Td className="py-2 font-medium text-slate-800">
                          {row.kind === 'none'
                            ? t('admin.qualityNoTask')
                            : row.name}
                        </Td>
                        <Td className="py-2">{row.negative}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            )}

            {quality.negative_samples.length > 0 && (
              <ul className="mt-4 flex flex-col gap-2 text-sm">
                {quality.negative_samples.map((item) => (
                  <li
                    key={item.message_id}
                    className="rounded-lg border border-rose-100 bg-rose-50 p-2 text-xs text-slate-700"
                  >
                    <span className="font-medium text-rose-700">
                      {item.provider} · {item.model}
                    </span>
                    {item.comment && <p className="mt-1">{item.comment}</p>}
                    <p className="mt-1 line-clamp-2 text-slate-500">{item.content}</p>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>

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
