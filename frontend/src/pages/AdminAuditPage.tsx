import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import type { AuditLogItem, AuditLogListResponse } from '@/types/api';

const PAGE_SIZE = 50;

interface Filters {
  action: string;
  entityType: string;
  actorId: string;
  search: string;
}

const EMPTY_FILTERS: Filters = {
  action: '',
  entityType: '',
  actorId: '',
  search: '',
};

/** Относительный маршрут сущности; неизвестный тип — без ссылки (S47-001). */
function entityPath(item: AuditLogItem): string | null {
  if (!item.entity_id) {
    return null;
  }
  if (item.entity_type === 'task') {
    return `/tasks/${item.entity_id}`;
  }
  if (item.entity_type === 'user') {
    return `/admin/users/${item.entity_id}`;
  }
  if (item.entity_type === 'classroom') {
    return `/classrooms/${item.entity_id}`;
  }
  return null;
}

function toQuery(filters: Filters, skip: number): string {
  const params = new URLSearchParams();
  if (filters.action.trim()) params.set('action', filters.action.trim());
  if (filters.entityType.trim()) params.set('entity_type', filters.entityType.trim());
  if (filters.actorId.trim()) params.set('actor_id', filters.actorId.trim());
  if (filters.search.trim()) params.set('search', filters.search.trim());
  params.set('skip', String(skip));
  params.set('limit', String(PAGE_SIZE));
  return params.toString();
}

export function AdminAuditPage() {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [skip, setSkip] = useState(0);
  const [data, setData] = useState<AuditLogListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<AuditLogListResponse>(
        `/admin/audit?${toQuery(filters, skip)}`,
      );
      setData(response);
    } catch {
      setError(t('adminAudit.loadError'));
    } finally {
      setLoading(false);
    }
  }, [filters, skip, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setSkip(0);
    setFilters(draft);
  }

  function resetFilters() {
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setSkip(0);
  }

  async function exportCsv() {
    setNotice(null);
    setError(null);
    try {
      const blob = await api.download(`/admin/audit/export?${toQuery(filters, 0)}`);
      const stamp = new Date().toISOString().slice(0, 10);
      saveBlob(blob, `audit-${stamp}.csv`);
      setNotice(t('adminAudit.exported'));
    } catch {
      setError(t('adminAudit.exportError'));
    }
  }

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {t('adminAudit.title')}
          </h1>
          <Link to="/admin" className="text-sm text-indigo-700 hover:underline">
            {t('adminAudit.back')}
          </Link>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => void load()}
            loading={loading}
          >
            {t('admin.refresh')}
          </Button>
          <Button variant="secondary" onClick={() => void exportCsv()}>
            {t('adminAudit.exportCsv')}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <Card title={t('adminAudit.filters')}>
        <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={applyFilters}>
          <Input
            label={t('adminAudit.search')}
            value={draft.search}
            onChange={(event) =>
              setDraft({ ...draft, search: event.target.value })
            }
            placeholder={t('adminAudit.searchPlaceholder')}
          />
          <Input
            label={t('adminAudit.action')}
            value={draft.action}
            onChange={(event) =>
              setDraft({ ...draft, action: event.target.value })
            }
            placeholder="task.moderated"
          />
          <Input
            label={t('adminAudit.entityType')}
            value={draft.entityType}
            onChange={(event) =>
              setDraft({ ...draft, entityType: event.target.value })
            }
            placeholder="user, task, classroom"
          />
          <Input
            label={t('adminAudit.actorId')}
            value={draft.actorId}
            onChange={(event) =>
              setDraft({ ...draft, actorId: event.target.value })
            }
            placeholder="00000000-0000-0000-0000-000000000000"
          />
          <div className="flex items-end gap-2">
            <Button type="submit">{t('adminAudit.apply')}</Button>
            <Button type="button" variant="ghost" onClick={resetFilters}>
              {t('adminAudit.reset')}
            </Button>
          </div>
        </form>
      </Card>

      <Card title={t('adminAudit.journal')}>
        {loading && !data ? (
          <Spinner />
        ) : (
          <>
            <Table caption={t('adminAudit.caption')}>
              <thead>
                <Tr>
                  <Th>{t('adminAudit.time')}</Th>
                  <Th>{t('adminAudit.action')}</Th>
                  <Th>{t('adminAudit.actor')}</Th>
                  <Th>{t('adminAudit.entity')}</Th>
                  <Th>{t('adminAudit.ip')}</Th>
                </Tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((item) => {
                  const path = entityPath(item);
                  return (
                    <Tr key={item.id} className="border-t border-slate-100">
                      <Td className="whitespace-nowrap text-xs text-slate-500">
                        {new Date(item.created_at).toLocaleString()}
                      </Td>
                      <Td className="font-mono text-xs text-slate-800">
                        {item.action}
                      </Td>
                      <Td>
                        <span className="font-medium text-slate-800">
                          {item.actor_username ?? '—'}
                        </span>
                        <span className="ml-1 text-xs text-slate-400">
                          {item.actor_role}
                        </span>
                      </Td>
                      <Td className="text-xs">
                        {path ? (
                          <Link
                            to={path}
                            className="text-indigo-700 hover:underline"
                          >
                            {item.entity_type} · {item.entity_id?.slice(0, 8)}
                          </Link>
                        ) : (
                          <span className="text-slate-500">
                            {item.entity_type}
                            {item.entity_id ? ` · ${item.entity_id.slice(0, 8)}` : ''}
                          </span>
                        )}
                      </Td>
                      <Td className="text-xs text-slate-500">{item.ip ?? '—'}</Td>
                    </Tr>
                  );
                })}
                {data && data.items.length === 0 && (
                  <Tr>
                    <Td colSpan={5} className="py-4 text-center text-slate-500">
                      {t('adminAudit.empty')}
                    </Td>
                  </Tr>
                )}
              </tbody>
            </Table>

            <div className="mt-3 flex items-center justify-between gap-2 text-sm">
              <span className="text-slate-500">
                {t('adminAudit.page', { page, pages, total })}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  disabled={skip === 0}
                  onClick={() =>
                    setSkip((value) => Math.max(0, value - PAGE_SIZE))
                  }
                >
                  {t('adminAudit.prev')}
                </Button>
                <Button
                  variant="secondary"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip((value) => value + PAGE_SIZE)}
                >
                  {t('adminAudit.next')}
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
