import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

type Status = 'idle' | 'saving' | 'saved' | 'error';

/**
 * Правка e-mail и имени пользователя (S45-002).
 *
 * Поля предзаполняются профилем; ошибки сервера (занятый e-mail/имя)
 * показываются как есть — понятное сообщение важнее обобщённого.
 */
export function ProfileEditCard() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const updateProfile = useAuthStore((state) => state.updateProfile);
  const [email, setEmail] = useState(user?.email ?? '');
  const [username, setUsername] = useState(user?.username ?? '');
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | null>(null);

  if (!user) {
    return null;
  }

  function reset() {
    setEmail(user?.email ?? '');
    setUsername(user?.username ?? '');
    setStatus('idle');
    setError(null);
  }

  async function handleSave() {
    if (status === 'saving') {
      return;
    }
    setStatus('saving');
    setError(null);
    try {
      await updateProfile({ email, username });
      setStatus('saved');
    } catch (err) {
      setStatus('error');
      setError(
        err instanceof ApiError ? err.message : t('profile.edit.error'),
      );
    }
  }

  const changed = email !== user.email || username !== user.username;

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="profile-email" className="text-sm text-slate-700">
        {t('profile.edit.email')}
      </label>
      <input
        id="profile-email"
        type="email"
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);
          setStatus('idle');
        }}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
      />

      <label htmlFor="profile-username" className="text-sm text-slate-700">
        {t('profile.edit.username')}
      </label>
      <input
        id="profile-username"
        type="text"
        value={username}
        onChange={(event) => {
          setUsername(event.target.value);
          setStatus('idle');
        }}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
      />

      <div className="flex gap-2">
        <Button
          onClick={() => void handleSave()}
          loading={status === 'saving'}
          disabled={!changed || !email.trim() || !username.trim()}
        >
          {t('profile.edit.save')}
        </Button>
        {changed && (
          <Button variant="secondary" onClick={reset}>
            {t('profile.edit.reset')}
          </Button>
        )}
      </div>

      {status === 'saved' && (
        <Alert tone="success">{t('profile.edit.saved')}</Alert>
      )}
      {status === 'error' && (
        <Alert tone="error">{error ?? t('profile.edit.error')}</Alert>
      )}
    </div>
  );
}
