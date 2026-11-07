import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { useAuthStore } from '@/store/auth';
import type { UiLanguage, UserPreferences } from '@/types/api';

const DEADLINE_OPTIONS = [1, 2, 3, 5, 7, 14] as const;

/**
 * Настройки уведомлений и языка (S45-004).
 *
 * Хранятся в `users.settings`; отсутствующий ключ означает включённое
 * уведомление и порог 3 дня (см. `notification_prefs.py`). Каждое
 * изменение сохраняется сразу — отдельной кнопки «Сохранить» нет.
 */
export function NotificationSettingsCard() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const savePreferences = useAuthStore((state) => state.savePreferences);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'idle' | 'saved' | 'error'>('idle');

  if (!user) {
    return null;
  }

  const settings = user.settings ?? {};
  const language: UiLanguage = settings.language === 'en' ? 'en' : 'ru';
  const emailEnabled = settings.email_notifications !== false;
  const deadlinesEnabled = settings.deadline_notifications !== false;
  const deadlineDays =
    typeof settings.deadline_days === 'number' ? settings.deadline_days : 3;

  async function update(changes: Partial<UserPreferences>) {
    if (saving) {
      return;
    }
    setSaving(true);
    setStatus('idle');
    try {
      await savePreferences(changes);
      setStatus('saved');
    } catch {
      setStatus('error');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-1 text-sm text-slate-700">
        {t('profile.notifications.email')}
        <span className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={emailEnabled}
            disabled={saving}
            onChange={(event) =>
              void update({ email_notifications: event.target.checked })
            }
          />
          <span className="text-xs text-slate-500">
            {t('profile.notifications.emailHint')}
          </span>
        </span>
      </label>

      <label className="flex flex-col gap-1 text-sm text-slate-700">
        {t('profile.notifications.deadlines')}
        <span className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={deadlinesEnabled}
            disabled={saving}
            onChange={(event) =>
              void update({ deadline_notifications: event.target.checked })
            }
          />
          <span className="text-xs text-slate-500">
            {t('profile.notifications.deadlinesHint')}
          </span>
        </span>
      </label>

      <label
        htmlFor="deadline-days"
        className="flex flex-col gap-1 text-sm text-slate-700"
      >
        {t('profile.notifications.days')}
        <select
          id="deadline-days"
          value={deadlineDays}
          disabled={saving || !deadlinesEnabled}
          onChange={(event) =>
            void update({ deadline_days: Number(event.target.value) })
          }
          className="w-40 rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
        >
          {DEADLINE_OPTIONS.map((days) => (
            <option key={days} value={days}>
              {t('profile.notifications.daysValue', { count: days })}
            </option>
          ))}
        </select>
      </label>

      <label
        htmlFor="profile-language"
        className="flex flex-col gap-1 text-sm text-slate-700"
      >
        {t('language.label')}
        <select
          id="profile-language"
          value={language}
          disabled={saving}
          onChange={(event) =>
            void update({ language: event.target.value as UiLanguage })
          }
          className="w-40 rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
        >
          <option value="ru">{t('language.ru')}</option>
          <option value="en">{t('language.en')}</option>
        </select>
      </label>

      {status === 'saved' && (
        <Alert tone="success">{t('profile.notifications.saved')}</Alert>
      )}
      {status === 'error' && (
        <Alert tone="error">{t('profile.notifications.error')}</Alert>
      )}
    </div>
  );
}
