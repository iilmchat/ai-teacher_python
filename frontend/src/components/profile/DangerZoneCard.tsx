import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

/**
 * Опасная зона профиля: удаление аккаунта (S45-002).
 *
 * Подтверждение — пароль + явное подтверждение в модальном окне:
 * операция необратима (анонимизация, `S26-004`), текст совпадает с
 * `docs/PRIVACY.md`.
 */
export function DangerZoneCard() {
  const { t } = useTranslation();
  const deleteAccount = useAuthStore((state) => state.deleteAccount);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (deleting || password.length === 0) {
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteAccount(password);
      // После успешного удаления стор разлогинен: страница уйдёт на /login.
    } catch (err) {
      setDeleting(false);
      setError(
        err instanceof ApiError ? err.message : t('profile.danger.error'),
      );
    }
  }

  function close() {
    if (deleting) {
      return;
    }
    setOpen(false);
    setPassword('');
    setError(null);
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-slate-600">{t('profile.danger.hint')}</p>
      <Button variant="secondary" onClick={() => setOpen(true)} className="text-rose-700">
        {t('profile.danger.open')}
      </Button>

      {error && <Alert tone="error">{error}</Alert>}

      <Modal open={open} onClose={close} title={t('profile.danger.title')}>
        <div className="flex flex-col gap-3 text-sm">
          <p>{t('profile.danger.confirm')}</p>
          <label htmlFor="delete-password" className="text-slate-700">
            {t('profile.danger.password')}
          </label>
          <input
            id="delete-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={close}>
              {t('profile.danger.cancel')}
            </Button>
            <Button
              onClick={() => void handleDelete()}
              loading={deleting}
              disabled={password.length === 0}
            >
              {t('profile.danger.confirmButton')}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
