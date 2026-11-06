import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import type { ExecutionRecord } from '@/types/api';

interface CodeHistoryProps {
  items: ExecutionRecord[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
  onRestart: (code: string) => void;
}

/** Дата запуска в коротком виде: день, месяц, часы и минуты */
function formatTime(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * История запусков песочницы (S44-002).
 *
 * Каждая запись раскрывается: код, вывод и ошибка (если была). Кнопка
 * «Запустить снова» возвращает код в редактор, ничего не запуская сама.
 */
export function CodeHistory({
  items,
  loading,
  error,
  hasMore,
  onLoadMore,
  onRetry,
  onRestart,
}: CodeHistoryProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === 'en' ? 'en-US' : 'ru-RU';

  return (
    <Card title={t('code.historyTitle')}>
      {error && (
        <div className="flex flex-col gap-2">
          <Alert tone="error">{error}</Alert>
          <div>
            <Button variant="secondary" onClick={onRetry}>
              {t('code.historyRetry')}
            </Button>
          </div>
        </div>
      )}

      {!error && loading && items.length === 0 && (
        <p className="text-sm text-slate-500">{t('common.loading')}</p>
      )}

      {!error && !loading && items.length === 0 && (
        <p className="text-sm text-slate-500">{t('code.historyEmpty')}</p>
      )}

      {items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item.id} data-testid="code-history-item">
              <details className="rounded-lg border border-slate-200 px-3 py-2">
                <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm">
                  <span className="text-slate-500">
                    {formatTime(item.created_at, locale)}
                  </span>
                  <Badge tone={item.success ? 'success' : 'danger'}>
                    {item.success
                      ? t('code.historySuccess')
                      : t('code.historyFailed')}
                  </Badge>
                  <span className="text-slate-500">
                    {t('code.historyDuration', {
                      seconds: item.execution_time.toFixed(3),
                    })}
                  </span>
                </summary>

                <div className="mt-3 flex flex-col gap-3 text-sm">
                  <section>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {t('code.historyCode')}
                    </h3>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">
                      {item.code}
                    </pre>
                  </section>

                  <section>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {t('code.historyOutput')}
                    </h3>
                    <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-50 p-2 text-xs text-slate-700">
                      {item.output || t('code.historyNoOutput')}
                    </pre>
                  </section>

                  {item.error && (
                    <section>
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {t('code.historyErrorTitle')}
                      </h3>
                      <pre className="mt-1 max-h-40 overflow-auto rounded bg-rose-50 p-2 text-xs text-rose-700">
                        {item.error}
                      </pre>
                    </section>
                  )}

                  <div>
                    <Button
                      variant="secondary"
                      onClick={() => onRestart(item.code)}
                    >
                      {t('code.historyRunAgain')}
                    </Button>
                  </div>
                </div>
              </details>
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="mt-3">
          <Button variant="secondary" onClick={onLoadMore} loading={loading}>
            {t('code.historyMore')}
          </Button>
        </div>
      )}
    </Card>
  );
}
