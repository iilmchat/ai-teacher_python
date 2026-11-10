import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import type { AuditLogItem, AuditLogListResponse } from '@/types/api';

const PAGE_SIZE = 50;

function entityLink(item: AuditLogItem): string | null {
  if (!item.entity_id) {
    return null;
  }
  if (item.entity_type === 'task') {
    return `/tasks/${item.entity_id}`;
  }
  if (item.entity_type === 'classroom') {
    return `/classrooms/${item.entity_id}`;
  }
  return null;
}

export function AdminAuditPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [action, setAction] = useState('');
  const [entityType, setEntityType] = useState('');
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        skip: String(skip),
        limit: String(PAGE_SIZE),
      });
      if (action.trim()) {
        params.set('action', action.trim());
      }
      if (entityType.trim()) {
        params.set('entity_type', entityType.trim());
      }
      const data = await api.get<AuditLogListResponse>(
        `/admin/audit?${params.toString()}`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError(t('admin.auditLoadError'));
    } finally {
      setLoading(false);
    }
  }, [action, entityType, skip, t]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-900">
          {t('admin.auditTitle')}
        </h1>
        <Button variant="secondary" onClick={() => void load()} loading={loading}>
          {t('admin.refresh')}
        </Button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card title={t('admin.auditFilter')}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label={t('admin.auditFilterAction')}
            value={action}
            onChange={(event) => {
              setSkip(0);
              setAction(event.target.value);
            }}
            placeholder="task.created"
          />
          <Input
            label={t('admin.auditFilterEntity')}
            value={entityType}
            onChange={(event) => {
              setSkip(0);
              setEntityType(event.target.value);
            }}
            placeholder="task"
          />
        </div>
      </Card>

      {loading && items.length === 0 ? (
        <Spinner />
      ) : (
        <Card title={t('admin.auditTitle')}>
          <div className="overflow-x-auto">
            <Table>
              <thead className="text-xs uppercase text-slate-500">
                <Tr>
                  <Th className="py-2">{t('admin.auditTime')}</Th>
                  <Th className="py-2">{t('admin.auditAction')}</Th>
                  <Th className="py-2">{t('admin.auditActor')}</Th>
                  <Th className="py-2">{t('admin.auditEntity')}</Th>
                  <Th className="py-2">{t('admin.auditIp')}</Th>
                </Tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const link = entityLink(item);
                  return (
                    <Tr key={item.id} className="border-t border-slate-100">
                      <Td className="py-2 text-xs text-slate-500">
                        {new Date(item.created_at).toLocaleString()}
                      </Td>
                      <Td className="py-2 font-mono text-xs text-slate-800">
                        {item.action}
                      </Td>
                      <Td className="py-2 text-xs text-slate-600">
                        {item.actor_role}
                        {item.actor_id ? ` · ${item.actor_id.slice(0, 8)}` : ''}
                      </Td>
                      <Td className="py-2 text-xs">
                        {link ? (
                          <Link to={link} className="text-indigo-700 hover:underline">
                            {item.entity_type}
                            {item.entity_id ? ` · ${item.entity_id.slice(0, 8)}` : ''}
                          </Link>
                        ) : (
                          <span className="text-slate-600">
                            {item.entity_type}
                            {item.entity_id ? ` · ${item.entity_id.slice(0, 8)}` : ''}
                          </span>
                        )}
                      </Td>
                      <Td className="py-2 text-xs text-slate-500">{item.ip ?? '—'}</Td>
                    </Tr>
                  );
                })}
                {items.length === 0 && !loading && (
                  <Tr>
                    <Td colSpan={5} className="py-4 text-center text-slate-500">
                      {t('admin.auditEmpty')}
                    </Td>
                  </Tr>
                )}
              </tbody>
            </Table>
          </div>

          <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
            <span>
              {t('admin.auditPage', {
                from: total === 0 ? 0 : skip + 1,
                to: Math.min(skip + PAGE_SIZE, total),
                total,
              })}
            </span>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                disabled={skip === 0}
                onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
              >
                {t('admin.auditPrev')}
              </Button>
              <Button
                variant="ghost"
                disabled={skip + PAGE_SIZE >= total}
                onClick={() => setSkip(skip + PAGE_SIZE)}
              >
                {t('admin.auditNext')}
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
