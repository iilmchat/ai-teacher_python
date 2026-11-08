import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { AdminUserDetail, AdminUserItem } from '@/types/api';

export function AdminUserPage() {
  const { t } = useTranslation();
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const currentUserId = useAuthStore((state) => state.user?.id);

  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      setDetail(await api.get<AdminUserDetail>(`/admin/users/${userId}`));
    } catch {
      setError(t('admin.userDetail.loadError'));
    } finally {
      setLoading(false);
    }
  }, [userId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleActive() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await api.patch<AdminUserItem>(
        `/admin/users/${detail.user.id}`,
        { is_active: !detail.user.is_active },
      );
      setDetail({ ...detail, user: updated });
      setNotice(
        updated.is_active
          ? t('admin.userDetail.activated')
          : t('admin.userDetail.deactivated'),
      );
    } catch {
      setError(t('admin.userDetail.actionError'));
    } finally {
      setBusy(false);
    }
  }

  async function removeUser() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/admin/users/${detail.user.id}`);
      navigate('/admin');
    } catch {
      setError(t('admin.userDetail.deleteError'));
    } finally {
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  if (loading) {
    return <Spinner />;
  }

  if (!detail) {
    return (
      <div className="flex flex-col gap-3">
        <Alert tone="error">{error ?? t('admin.userDetail.loadError')}</Alert>
        <Link to="/admin" className="text-sm text-indigo-700 hover:underline">
          {t('admin.userDetail.back')}
        </Link>
      </div>
    );
  }

  const user = detail.user;
  const isSelf = user.id === currentUserId;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {t('admin.userDetail.title', { username: user.username })}
          </h1>
          <Link to="/admin" className="text-sm text-indigo-700 hover:underline">
            {t('admin.userDetail.back')}
          </Link>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={isSelf}
            loading={busy}
            onClick={() => void toggleActive()}
          >
            {user.is_active
              ? t('admin.userDetail.deactivate')
              : t('admin.userDetail.activate')}
          </Button>
          <Button
            variant="danger"
            disabled={isSelf}
            onClick={() => setConfirmDelete(true)}
          >
            {t('admin.userDetail.deletePermanent')}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <Card title={t('admin.userDetail.profile')}>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">{t('admin.colUser')}</dt>
            <dd className="font-medium text-slate-900">{user.username}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">{t('admin.colEmail')}</dt>
            <dd className="text-slate-700">{user.email}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">{t('admin.colRole')}</dt>
            <dd className="text-slate-700">{t(`profile.roles.${user.role}`)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">{t('admin.userDetail.level')}</dt>
            <dd className="text-slate-700">{t(`levels.${user.level}`)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">{t('admin.userDetail.status')}</dt>
            <dd>
              <Badge tone={user.is_active ? 'success' : 'danger'}>
                {user.is_active
                  ? t('admin.userDetail.active')
                  : t('admin.userDetail.inactive')}
              </Badge>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">{t('admin.userDetail.createdAt')}</dt>
            <dd className="text-slate-700">
              {new Date(user.created_at).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">{t('admin.userDetail.lastActive')}</dt>
            <dd className="text-slate-700">
              {new Date(user.last_active).toLocaleString()}
            </dd>
          </div>
        </dl>
      </Card>

      <Card title={t('admin.userDetail.progress')}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs text-slate-500">{t('admin.userDetail.solved')}</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">
              {detail.progress.solved}
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs text-slate-500">{t('admin.userDetail.attempts')}</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">
              {detail.progress.attempts}
            </p>
          </div>
        </div>
      </Card>

      <Card title={t('admin.userDetail.sessions')}>
        {detail.sessions.length === 0 ? (
          <p className="text-sm text-slate-500">{t('admin.userDetail.noSessions')}</p>
        ) : (
          <Table>
            <thead>
              <Tr>
                <Th>{t('admin.userDetail.device')}</Th>
                <Th>{t('admin.userDetail.ip')}</Th>
                <Th>{t('admin.userDetail.createdAt')}</Th>
                <Th>{t('admin.userDetail.lastUsed')}</Th>
              </Tr>
            </thead>
            <tbody>
              {detail.sessions.map((session) => (
                <Tr key={session.id} className="border-t border-slate-100">
                  <Td className="text-xs text-slate-700">
                    {session.user_agent ?? '—'}
                  </Td>
                  <Td className="text-xs text-slate-500">{session.ip ?? '—'}</Td>
                  <Td className="whitespace-nowrap text-xs text-slate-500">
                    {new Date(session.created_at).toLocaleString()}
                  </Td>
                  <Td className="whitespace-nowrap text-xs text-slate-500">
                    {new Date(session.last_used_at).toLocaleString()}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Card title={t('admin.userDetail.audit')}>
        {detail.audit.length === 0 ? (
          <p className="text-sm text-slate-500">{t('admin.userDetail.noAudit')}</p>
        ) : (
          <Table>
            <thead>
              <Tr>
                <Th>{t('adminAudit.time')}</Th>
                <Th>{t('adminAudit.action')}</Th>
                <Th>{t('adminAudit.actor')}</Th>
              </Tr>
            </thead>
            <tbody>
              {detail.audit.map((item) => (
                <Tr key={item.id} className="border-t border-slate-100">
                  <Td className="whitespace-nowrap text-xs text-slate-500">
                    {new Date(item.created_at).toLocaleString()}
                  </Td>
                  <Td className="font-mono text-xs text-slate-800">{item.action}</Td>
                  <Td className="text-xs text-slate-600">
                    {item.actor_username ?? '—'}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Modal
        open={confirmDelete}
        title={t('admin.userDetail.deleteTitle')}
        onClose={() => setConfirmDelete(false)}
        closeLabel={t('common.close')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              {t('admin.bulk.cancel')}
            </Button>
            <Button variant="danger" onClick={() => void removeUser()}>
              {t('admin.userDetail.deletePermanent')}
            </Button>
          </>
        }
      >
        <p>{t('admin.userDetail.deleteText', { username: user.username })}</p>
      </Modal>
    </div>
  );
}
