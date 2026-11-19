import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';

export type ExportDataset = 'users' | 'tasks' | 'attempts' | 'activity';
export type ExportFormat = 'csv' | 'json';

const DATASETS: ExportDataset[] = ['users', 'tasks', 'attempts', 'activity'];
const FORMATS: ExportFormat[] = ['csv', 'json'];

/** Выгрузка аналитики из админки (S47-002). */
export function AdminExportCard() {
  const { t } = useTranslation();
  const [dataset, setDataset] = useState<ExportDataset>('users');
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function download() {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const blob = await api.download(
        `/admin/analytics/export?dataset=${dataset}&format=${format}`,
      );
      const stamp = new Date().toISOString().slice(0, 10);
      saveBlob(blob, `export-${dataset}-${stamp}.${format}`);
      setNotice(t('admin.export.downloaded'));
    } catch {
      setError(t('admin.export.error'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card
      title={t('admin.export.title')}
      description={t('admin.export.description')}
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="export-dataset"
            className="text-sm font-medium text-slate-700"
          >
            {t('admin.export.dataset')}
          </label>
          <select
            id="export-dataset"
            value={dataset}
            onChange={(event) => setDataset(event.target.value as ExportDataset)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {DATASETS.map((item) => (
              <option key={item} value={item}>
                {t(`admin.export.datasets.${item}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label
            htmlFor="export-format"
            className="text-sm font-medium text-slate-700"
          >
            {t('admin.export.format')}
          </label>
          <select
            id="export-format"
            value={format}
            onChange={(event) => setFormat(event.target.value as ExportFormat)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {FORMATS.map((item) => (
              <option key={item} value={item}>
                {item.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button onClick={() => void download()} loading={loading}>
            {t('admin.export.download')}
          </Button>
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        {t('admin.export.limitHint')}
      </p>
      {error && (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}
      {notice && (
        <div className="mt-3">
          <Alert tone="success">{notice}</Alert>
        </div>
      )}
    </Card>
  );
}
