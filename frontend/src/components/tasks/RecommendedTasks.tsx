import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useTasksStore } from '@/store/tasks';

/**
 * Блок «Рекомендуем дальше» (S42-005).
 *
 * Рекомендации приходят с сервера: порядок детерминированный, у каждой
 * задачи есть объяснение, почему она предложена.
 */
export function RecommendedTasks() {
  const { t } = useTranslation();
  const recommended = useTasksStore((state) => state.recommended);
  const loadRecommended = useTasksStore((state) => state.loadRecommended);

  useEffect(() => {
    void loadRecommended();
  }, [loadRecommended]);

  const items = recommended?.items ?? [];

  return (
    <Card title={t('tasks.recommendedTitle')}>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">{t('tasks.recommendedEmpty')}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-slate-100">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <div className="min-w-0">
                <Link
                  to={`/tasks/${item.id}`}
                  className="font-medium text-indigo-700 hover:underline"
                >
                  {item.title}
                </Link>
                <p className="text-xs text-slate-500">{item.reason_text}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {t(`tasks.difficulty.${item.difficulty}`)}
                </span>
                <Link to={`/tasks/${item.id}`} className="inline-block">
                  <Button variant="secondary">{t('tasks.open')}</Button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
