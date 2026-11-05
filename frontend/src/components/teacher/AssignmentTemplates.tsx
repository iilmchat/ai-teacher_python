import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import type { AssignmentTemplateItem, AssignmentTemplateList } from '@/types/api';

interface AssignmentTemplatesProps {
  classroomId: string;
  /** Выбранные задачи для сохранения шаблона */
  selectedTaskIds: string[];
  /** Вызывается после применения шаблона (перезагрузить назначения) */
  onApplied?: () => void;
}

/**
 * Шаблоны назначений учителя (S28-002, UI-шаг).
 *
 * Список шаблонов, применение к классу, сохранение текущего выбора задач и
 * удаление. Все операции best-effort: ошибка показывается в Alert и не ломает
 * страницу.
 */
export function AssignmentTemplates({
  classroomId,
  selectedTaskIds,
  onApplied,
}: AssignmentTemplatesProps) {
  const { t } = useTranslation();
  const [templates, setTemplates] = useState<AssignmentTemplateItem[]>([]);
  const [name, setName] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.get<AssignmentTemplateList>('/teacher/assignment-templates');
      setTemplates(data.items);
      setSelectedId((current) => current || data.items[0]?.id || '');
    } catch {
      setError(t('classrooms.templates.loadError'));
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveTemplate() {
    if (!name.trim() || selectedTaskIds.length === 0) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post<AssignmentTemplateItem>('/teacher/assignment-templates', {
        name: name.trim(),
        task_ids: selectedTaskIds,
      });
      setNotice(t('classrooms.templates.saved'));
      setName('');
      await load();
    } catch {
      setError(t('classrooms.templates.saveError'));
    } finally {
      setBusy(false);
    }
  }

  async function applyTemplate() {
    if (!selectedId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.post<{ created: string[]; skipped: string[]; unknown: string[] }>(
        `/classrooms/${classroomId}/assignments/from-template`,
        { template_id: selectedId },
      );
      setNotice(
        t('classrooms.bulkAssigned', {
          created: result.created.length,
          skipped: result.skipped.length + result.unknown.length,
        }),
      );
      onApplied?.();
    } catch {
      setError(t('classrooms.templates.applyError'));
    } finally {
      setBusy(false);
    }
  }

  async function deleteTemplate(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/teacher/assignment-templates/${id}`);
      await load();
    } catch {
      setError(t('classrooms.templates.deleteError'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label={t('classrooms.templates.title')} className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-slate-700">{t('classrooms.templates.title')}</h3>
      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="flex flex-col gap-2 sm:flex-row">
        <select
          value={selectedId}
          onChange={(event) => setSelectedId(event.target.value)}
          aria-label={t('classrooms.templates.select')}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">{t('classrooms.templates.select')}</option>
          {templates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name} ({template.task_ids.length})
            </option>
          ))}
        </select>
        <Button onClick={() => void applyTemplate()} disabled={!selectedId} loading={busy}>
          {t('classrooms.templates.apply')}
        </Button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={t('classrooms.templates.namePlaceholder')}
          aria-label={t('classrooms.templates.name')}
          maxLength={120}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <Button
          onClick={() => void saveTemplate()}
          disabled={!name.trim() || selectedTaskIds.length === 0}
          loading={busy}
        >
          {t('classrooms.templates.save')}
        </Button>
      </div>

      {templates.length === 0 ? (
        <p className="text-xs text-slate-500">{t('classrooms.templates.empty')}</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {templates.map((template) => (
            <li key={template.id} className="flex items-center gap-1 rounded border border-slate-200 px-2 py-1">
              <span className="text-xs text-slate-600">{template.name}</span>
              <button
                type="button"
                onClick={() => void deleteTemplate(template.id)}
                aria-label={`${t('classrooms.templates.delete')}: ${template.name}`}
                className="text-xs text-slate-400 hover:text-rose-600"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
