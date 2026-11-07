import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { UserSession } from '@/types/api';

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

/**
 * Активные сессии (S45-005): список устройств, отзыв по одному и
 * «выйти на всех устройствах» (закрывает KI-028).
 *
 * Текущую сессию точечно не отзываем — для неё есть обычный выход.
 */
export function SessionsCard() {
  const { t } = useTranslation();
  const revokeOtherSessions = useAuthStore((state) => state.revokeOtherSessions);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSessions(await api.get<UserSession[]>('/users/me/sessions'));
    } catch {
      setError(t('profile.sessions.error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRevoke(session: UserSession) {
    setRevokingId(session.id);
    setError(null);
    setNotice(null);
    try {
      await api.delete<unknown>(`/users/me/sessions/${session.id}`);
      setNotice(t('profile.sessions.revoked'));
      await load();
    } catch {
      setError(t('profile.sessions.revokeError'));
    } finally {
      setRevokingId(null);
    }
  }

  async function handleSignOutEverywhere() {
    setSigningOut(true);
    setError(null);
    try {
      await revokeOtherSessions();
      setNotice(t('profile.sessions.signOutDone'));
      setConfirmOpen(false);
      await load();
    } catch {
      setError(t('profile.sessions.signOutError'));
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-slate-600">{t('profile.sessions.hint')}</p>

      {loading ? (
        <p className="text-sm text-slate-500">{t('common.loading')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {sessions.map((session) => (
            <li
              key={session.id}
              className="flex flex-col gap-1 rounded-lg border border-slate-200 p-3 text-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-slate-800">
                  {session.user_agent || t('profile.sessions.unknownDevice')}
                </span>
                {session.current ? (
                  <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
                    {t('profile.sessions.current')}
                  </span>
                ) : (
                  <Button
                    variant="secondary"
                    loading={revokingId === session.id}
                    onClick={() => void handleRevoke(session)}
                  >
                    {t('profile.sessions.revoke')}
                  </Button>
                )}
              </div>
              <span className="text-xs text-slate-500">
                {t('profile.sessions.created')}: {formatDate(session.created_at)}
                {' · '}
                {t('profile.sessions.lastUsed')}:{' '}
                {formatDate(session.last_used_at)}
                {session.ip ? ` · ${t('profile.sessions.ip')}: ${session.ip}` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div>
        <Button variant="secondary" onClick={() => setConfirmOpen(true)}>
          {t('profile.sessions.signOutOthers')}
        </Button>
      </div>

      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}

      <Modal
        open={confirmOpen}
        onClose={() => !signingOut && setConfirmOpen(false)}
        title={t('profile.sessions.signOutOthers')}
      >
        <div className="flex flex-col gap-3 text-sm">
          <p>{t('profile.sessions.signOutConfirm')}</p>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setConfirmOpen(false)}
              disabled={signingOut}
            >
              {t('profile.sessions.cancel')}
            </Button>
            <Button
              onClick={() => void handleSignOutEverywhere()}
              loading={signingOut}
            >
              {t('profile.sessions.confirm')}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
