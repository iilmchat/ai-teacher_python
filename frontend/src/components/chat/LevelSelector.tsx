import { useTranslation } from 'react-i18next';

import type { UserLevel } from '@/types/api';

const LEVELS: UserLevel[] = ['basic', 'intermediate', 'advanced'];

interface LevelSelectorProps {
  value: UserLevel;
  onChange: (level: UserLevel) => void;
  disabled?: boolean;
}

export function LevelSelector({ value, onChange, disabled = false }: LevelSelectorProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={t('chat.levelLabel')}>
      {LEVELS.map((level) => (
        <button
          key={level}
          type="button"
          disabled={disabled}
          aria-pressed={value === level}
          onClick={() => onChange(level)}
          className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
            value === level
              ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
              : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
          } disabled:cursor-not-allowed disabled:opacity-60`}
        >
          {t(`levels.${level}`)}
        </button>
      ))}
    </div>
  );
}
