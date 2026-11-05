import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { ChatTaskContext } from '@/store/chat';

interface TaskContextBannerProps {
  task: ChatTaskContext;
  onClear: () => void;
}

/** Плашка «в чате открыта задача» с возможностью снять контекст (S42-006) */
export function TaskContextBanner({ task, onClear }: TaskContextBannerProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm">
      <span className="min-w-0 text-slate-700">
        <span className="font-medium">{t('chat.taskContext.label')}: </span>
        <Link
          to={`/tasks/${task.id}`}
          className="break-words text-indigo-700 hover:underline"
        >
          {task.title}
        </Link>
      </span>
      <button
        type="button"
        onClick={onClear}
        aria-label={t('chat.taskContext.clear')}
        className="rounded px-2 py-0.5 text-xs text-slate-600 hover:bg-white hover:text-indigo-700"
      >
        {t('chat.taskContext.clear')}
      </button>
    </div>
  );
}
