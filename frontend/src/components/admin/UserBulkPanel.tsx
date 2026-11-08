import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { api } from '@/lib/api';
import type {
  AdminUserBulkResponse,
  AdminUserItem,
  UserRole,
} from '@/types/api';

const ROLES: UserRole[] = ['student', 'teacher', 'admin'];

interface Props {
  selectedIds: string[];
  users: AdminUserItem[];
  onApplied: () => void;
}

/** Массовые действия с пользователями (S47-002, D-005). */
export function UserBulkPanel({ selectedIds, users, onApplied }: Props) {
  const { t } = useTranslation();
  const [role, setRole] = useState<'' | UserRole>('');
  const [active, setActive] = useState<'' | 'true' | 'false'>('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<AdminUserBulkResponse | null>(null);

  const hasChanges = role !== '' || active !== '';
  const canApply = selectedIds.length > 0 && hasChanges;

  function nameOf(id: string): string {
    return users.find((item) => item.id === id)?.username ?? id.slice(0, 8);
  }

  async function apply() {
    setConfirmOpen(false);
    setLoading(true);
    setError(null);
    setReport(null);
    const changes: { role?: UserRole; is_active?: boolean } = {};
    if (role) changes.role = role;
    if (active) changes.is_active = active === 'true';
    try {
      const result = await api.patch<AdminUserBulkResponse>('/admin/users/bulk', {
        user_ids: selectedIds,
        changes,
      });
      setReport(result);
      onApplied();
    } catch {
      setError(t('admin.bulk.error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="bulk-role" className="text-xs font-medium text-slate-600">
            {t('admin.bulk.role')}
          </label>
          <select
            id="bulk-role"
            value={role}
            onChange={(event) => setRole(event.target.value as '' | UserRole)}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value="">{t('admin.bulk.noChange')}</option>
            {ROLES.map((item) => (
              <option key={item} value={item}>
                {t(`profile.roles.${item}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label
            htmlFor="bulk-active"
            className="text-xs font-medium text-slate-600"
          >
            {t('admin.bulk.active')}
          </label>
          <select
            id="bulk-active"
            value={active}
            onChange={(event) => setActive(event.target.value as '' | 'true' | 'false')}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
          >
            <option value="">{t('admin.bulk.noChange')}</option>
            <option value="true">{t('admin.bulk.activate')}</option>
            <option value="false">{t('admin.bulk.deactivate')}</option>
          </select>
        </div>
        <Button
          variant="secondary"
          disabled={!canApply}
          loading={loading}
          onClick={() => setConfirmOpen(true)}
        >
          {t('admin.bulk.apply', { count: selectedIds.length })}
        </Button>
      </div>

      <p className="mt-2 text-xs text-slate-500">
        {t('admin.bulk.selected', { count: selectedIds.length })}
      </p>

      {error && (
        <div className="mt-2">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {report && (
        <div className="mt-2 text-sm" role="status">
          <p className="font-medium text-slate-800">
            {t('admin.bulk.report', { updated: report.updated.length })}
          </p>
          {report.skipped.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-xs text-slate-600">
              {report.skipped.map((item) => (
                <li key={`${item.id}-${item.reason}`}>
                  {nameOf(item.id)}: {t(`admin.bulk.reasons.${item.reason}`)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Modal
        open={confirmOpen}
        title={t('admin.bulk.confirmTitle')}
        onClose={() => setConfirmOpen(false)}
        closeLabel={t('common.close')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              {t('admin.bulk.cancel')}
            </Button>
            <Button variant="danger" onClick={() => void apply()}>
              {t('admin.bulk.confirm')}
            </Button>
          </>
        }
      >
        <p>{t('admin.bulk.confirmText', { count: selectedIds.length })}</p>
        <ul className="mt-2 text-xs text-slate-600">
          {role && <li>{t(`admin.bulk.summaryRole`, { role: t(`profile.roles.${role}`) })}</li>}
          {active && (
            <li>
              {active === 'true'
                ? t('admin.bulk.summaryActivate')
                : t('admin.bulk.summaryDeactivate')}
            </li>
          )}
        </ul>
      </Modal>
    </div>
  );
}
