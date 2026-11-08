import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { RecommendedTasks } from '@/components/tasks/RecommendedTasks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { api } from '@/lib/api';
import type {
  AchievementsResponse,
  AppNotification,
  NotificationsResponse,
  ProgressSummary,
  UserStats,
} from '@/types/api';

function notificationText(
  item: AppNotification,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const title = String(item.payload.title ?? '');
  if (item.type === 'assignment') {
    return t('dashboard.notifyAssignment', { title });
  }
  if (item.type === 'deadline') {
    return t('dashboard.notifyDeadline', { title });
  }
  if (item.type === 'achievement') {
    return t('dashboard.notifyAchievement', {
      title: String(item.payload.title ?? ''),
    });
  }
  if (item.type === 'attempt_feedback') {
    return t('dashboard.notifyFeedback', {
      title,
      teacher: String(item.payload.teacher ?? ''),
    });
  }
  if (item.type === 'announcement') {
    return t('dashboard.notifyAnnouncement', {
      title: String(item.payload.classroom_name ?? ''),
    });
  }
  return title;
}

export function DashboardPage() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<UserStats | null>(null);
  const [achievements, setAchievements] = useState<AchievementsResponse['items']>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.get<UserStats>('/me/stats'),
      api.get<AchievementsResponse>('/me/achievements'),
      api.get<NotificationsResponse>('/me/notifications'),
      api.get<ProgressSummary>('/tasks/progress'),
    ])
      .then(([statsData, achievementsData, notificationsData, progressData]) => {
        if (!active) {
          return;
        }
        setStats(statsData);
        setAchievements(achievementsData.items);
        setNotifications(notificationsData.items);
        setUnread(notificationsData.unread);
        setProgress(progressData);
      })
      .catch(() => {
        if (active) {
          setError(t('dashboard.loadError'));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [t]);

  async function readNotification(id: string) {
    await api.post<AppNotification>(`/me/notifications/${id}/read`);
    setNotifications((items) =>
      items.map((item) =>
        item.id === id ? { ...item, read_at: new Date().toISOString() } : item,
      ),
    );
    setUnread((value) => Math.max(0, value - 1));
  }

  if (loading) {
    return <Spinner />;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-slate-900">{t('dashboard.title')}</h1>
      {error && <Alert tone="error">{error}</Alert>}

      {stats && (
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="rounded-xl bg-gradient-to-br from-orange-100 to-amber-50 p-4">
            <p className="text-xs text-amber-700">{t('dashboard.streak')}</p>
            <p className="mt-1 text-3xl font-bold text-amber-800">
              {stats.streak_days} 🔥
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">{t('dashboard.solved')}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {stats.solved}
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">{t('dashboard.avgAttempts')}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {stats.avg_attempts}
            </p>
          </div>
          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-xs text-slate-500">{t('dashboard.achievements')}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              {stats.achievements_count}
            </p>
          </div>
        </div>
      )}

      {progress && (
        <Card title={t('dashboard.progressTitle')}>
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              {t('progress.summary', {
                completed: progress.completed,
                total: progress.total_tasks,
              })}
            </span>
            <span>{progress.completion_rate}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${Math.min(100, progress.completion_rate)}%` }}
            />
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t('dashboard.achievementsTitle')}>
          {achievements.length === 0 ? (
            <p className="text-sm text-slate-500">{t('dashboard.noAchievements')}</p>
          ) : (
            <ul className="grid grid-cols-2 gap-2">
              {achievements.map((item) => (
                <li
                  key={item.code}
                  className="rounded-lg bg-amber-50 p-3"
                  title={item.description}
                >
                  <span className="text-2xl">{item.icon}</span>
                  <p className="mt-1 text-sm font-medium text-slate-800">
                    {item.title}
                  </p>
                  <p className="text-xs text-slate-500">{item.description}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title={t('dashboard.notificationsTitle')}>
          {notifications.length === 0 ? (
            <p className="text-sm text-slate-500">{t('dashboard.noNotifications')}</p>
          ) : (
            <ul className="flex flex-col divide-y divide-slate-100 text-sm">
              {notifications.slice(0, 6).map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-2 py-2">
                  <span className={item.read_at ? 'text-slate-500' : 'font-medium text-slate-800'}>
                    {notificationText(item, t)}
                  </span>
                  {!item.read_at && (
                    <Button
                      variant="ghost"
                      onClick={() => void readNotification(item.id)}
                    >
                      {t('dashboard.markRead')}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {unread > 0 && (
            <p className="mt-2 text-xs text-indigo-700">
              {t('dashboard.unread', { count: unread })}
            </p>
          )}
        </Card>
      </div>

      <RecommendedTasks />

      <Card title={t('dashboard.recentTasks')}>
        {progress && progress.items.length > 0 ? (
          <ul className="flex flex-col divide-y divide-slate-100 text-sm">
            {progress.items.slice(0, 6).map((item) => (
              <li key={item.task_id} className="flex items-center justify-between py-2">
                <Link
                  to={`/tasks/${item.task_id}`}
                  className="font-medium text-indigo-700 hover:underline"
                >
                  {item.title}
                </Link>
                <span className="text-xs text-slate-500">
                  {t(`tasks.status.${item.status}`)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">
            <Link to="/tasks" className="text-indigo-700 hover:underline">
              {t('dashboard.goToTasks')}
            </Link>
          </p>
        )}
      </Card>
    </div>
  );
}
