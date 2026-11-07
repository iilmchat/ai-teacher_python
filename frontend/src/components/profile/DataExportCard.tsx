import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { saveBlob } from '@/lib/download';
import { api } from '@/lib/api';

/**
 * Карточка «Мои данные» (S45-003): скачивание личного JSON-файла.
 *
 * Выгрузка включает профиль, прогресс, попытки, чаты, уведомления и
 * достижения; эмбеддинги и чужие данные сервером исключены.
 */
export function DataExportCard() {
  const { t } = useTranslation();
  const [downloading, setDownloading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    if (downloading) {
      return;
    }
    setDownloading(true);
    setError(null);
    try {
      const blob = await api.download('/users/me/export');
      const stamp = new Date().toISOString().slice(0, 10);
      saveBlob(blob, `ai-teacher-export-${stamp}.json`);
      setSaved(true);
    } catch {
      setError(t('profile.export.error'));
      setSaved(false);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-slate-600">{t('profile.export.hint')}</p>
      <Button
        onClick={() => void handleDownload()}
        loading={downloading}
        disabled={downloading}
      >
        {t('profile.export.button')}
      </Button>
      {saved && <Alert tone="success">{t('profile.export.saved')}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  );
}
