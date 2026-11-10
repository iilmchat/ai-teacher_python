import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { notificationLink, notificationText } from '@/lib/notifications';
import { useNotificationsStore } from '@/store/notifications';

const TYPES = [
  'assignment',
  'deadline',
  'achievement',
  'attempt_feedback',
  'announcement',
] as const;

export function NotificationsPage() {
  const { t } = useTranslation();
  const items = useNotificationsStore((state) => state.items);
  const unread = useNotificationsStore((state) => state.unread);
  const filterType = useNotificationsStore((state) => state.filterType);
  const loading = useNotificationsStore((state) => state.loading);
  const error = useNotificationsStore((state) => state.error);
  const load = useNotificationsStore((state) => state.load);
  const setFilterType = useNotificationsStore((state) => state.setFilterType);
  const markRead = useNotificationsStore((state) => state.markRead);
  const markAllRead = useNotificationsStore((state) => state.markAllRead);

  useEffect(() => {
    void load(filterType);
  }, [filterType, load]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {t('notifications.title')}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {t('notifications.subtitle')}
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => void markAllRead()}
          disabled={unread === 0 || loading}
        >
          {t('notifications.readAll')}
        </Button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card title={t('notifications.filter')}>
        <div className="flex flex-wrap items-end justify-between gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-xs font-medium text-slate-600">
              {t('notifications.type')}
            </span>
            <select
              aria-label={t('notifications.type')}
              value={filterType}
              onChange={(event) => setFilterType(event.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">{t('notifications.filterAll')}</option>
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {t(`notifications.types.${type}`)}
                </option>
              ))}
            </select>
          </label>
          <p className="text-sm text-slate-600">
            {t('notifications.unread', { count: unread })}
          </p>
        </div>
      </Card>

      {loading && items.length === 0 && <Spinner />}

      <Card title={t('notifications.listTitle')}>
        {!loading && items.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-500">
            {t('notifications.empty')}
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {items.map((item) => {
              const link = notificationLink(item);
              return (
                <li
                  key={item.id}
                  className={`rounded-lg border p-3 ${
                    item.read_at
                      ? 'border-slate-100 bg-white'
                      : 'border-indigo-100 bg-indigo-50/40'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {t(`notifications.types.${item.type}`, {
                          defaultValue: item.type,
                        })}
                      </span>
                      <p className="mt-2 text-sm font-medium text-slate-800">
                        {notificationText(item, t)}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {new Date(item.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {!item.read_at && (
                        <Button
                          variant="ghost"
                          onClick={() => void markRead(item.id)}
                        >
                          {t('notifications.read')}
                        </Button>
                      )}
                      {link && (
                        <Link
                          to={link}
                          onClick={() => void markRead(item.id)}
                          className="text-sm font-medium text-indigo-700 hover:underline"
                        >
                          {t('notifications.open')}
                        </Link>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
