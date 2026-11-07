import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { DataExportCard } from '@/components/profile/DataExportCard';
import { NotificationSettingsCard } from '@/components/profile/NotificationSettingsCard';
import { PasswordChangeCard } from '@/components/profile/PasswordChangeCard';
import { ProfileEditCard } from '@/components/profile/ProfileEditCard';
import { DangerZoneCard } from '@/components/profile/DangerZoneCard';
import { useAuthStore } from '@/store/auth';
import type { UserLevel } from '@/types/api';

const LEVELS: UserLevel[] = ['basic', 'intermediate', 'advanced'];

export function ProfilePage() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const setLevel = useAuthStore((state) => state.setLevel);
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  if (!user) {
    return null;
  }

  async function handleSave(level: UserLevel) {
    setStatus('saving');
    try {
      await setLevel(level);
      setStatus('saved');
    } catch {
      setStatus('error');
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4">
      <Card title={t('profile.title')}>
        <dl className="grid gap-2 text-sm">
          <div className="flex justify-between border-b border-slate-100 py-2">
            <dt className="text-slate-500">{t('profile.username')}</dt>
            <dd className="font-medium text-slate-900">{user.username}</dd>
          </div>
          <div className="flex justify-between border-b border-slate-100 py-2">
            <dt className="text-slate-500">{t('profile.email')}</dt>
            <dd className="font-medium text-slate-900">{user.email}</dd>
          </div>
          <div className="flex justify-between py-2">
            <dt className="text-slate-500">{t('profile.role')}</dt>
            <dd className="font-medium text-slate-900">{t(`profile.roles.${user.role}`)}</dd>
          </div>
        </dl>
      </Card>

      <Card
        title={t('profile.appearance')}
        description={t('profile.appearanceHint')}
      >
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-700">{t('theme.label')}</span>
          <ThemeToggle />
        </div>
      </Card>

      <Card title={t('profile.edit.title')}>
        <ProfileEditCard />
      </Card>

      <Card
        title={t('profile.password.title')}
        description={t('profile.password.hint')}
      >
        <PasswordChangeCard />
      </Card>

      <Card title={t('profile.export.title')}>
        <DataExportCard />
      </Card>

      <Card title={t('profile.notifications.title')}>
        <NotificationSettingsCard />
      </Card>

      <Card title={t('profile.level')} description={t('profile.levelHint')}>
        <div className="flex flex-wrap gap-2">
          {LEVELS.map((level) => (
            <Button
              key={level}
              variant={user.level === level ? 'primary' : 'secondary'}
              loading={status === 'saving' && user.level !== level}
              onClick={() => void handleSave(level)}
            >
              {t(`levels.${level}`)}
            </Button>
          ))}
        </div>

        {status === 'saved' && (
          <div className="mt-3">
            <Alert tone="success">{t('profile.saved')}</Alert>
          </div>
        )}
        {status === 'error' && (
          <div className="mt-3">
            <Alert tone="error">{t('errors.generic')}</Alert>
          </div>
        )}
      </Card>

      <Card title={t('profile.danger.zone')}>
        <DangerZoneCard />
      </Card>
    </div>
  );
}
