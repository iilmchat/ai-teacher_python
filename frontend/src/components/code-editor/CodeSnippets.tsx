import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import {
  MAX_CODE_SNIPPETS,
  MAX_SNIPPET_NAME_LENGTH,
} from '@/lib/codeSnippets';
import type { CodeSnippet } from '@/types/api';

interface CodeSnippetsProps {
  snippets: CodeSnippet[];
  /** Идёт сохранение или удаление — кнопки временно недоступны */
  saving: boolean;
  /** Есть ли что сохранять: пустой код сниппетом не становится */
  canSave: boolean;
  error: string | null;
  onSave: (name: string) => void;
  onApply: (snippet: CodeSnippet) => void;
  onDelete: (snippet: CodeSnippet) => void;
}

/**
 * «Мои сниппеты» (S44-003).
 *
 * Список хранится в `users.settings`; применение подставляет код в редактор
 * одним кликом, удаление убирает сниппет из профиля. Название спрашивается
 * в модальном окне, потому что по коду сниппет не найти.
 */
export function CodeSnippets({
  snippets,
  saving,
  canSave,
  error,
  onSave,
  onApply,
  onDelete,
}: CodeSnippetsProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [validation, setValidation] = useState<string | null>(null);
  const nameId = useId();

  const atLimit = snippets.length >= MAX_CODE_SNIPPETS;

  function openModal() {
    setName('');
    setValidation(null);
    setOpen(true);
  }

  function submit() {
    const trimmed = name.trim();
    if (trimmed.length === 0) {
      setValidation(t('code.snippetsNameRequired'));
      return;
    }
    onSave(trimmed);
    setOpen(false);
  }

  return (
    <Card title={t('code.snippetsTitle')}>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-500">
            {t('code.snippetsCount', {
              count: snippets.length,
              max: MAX_CODE_SNIPPETS,
            })}
          </p>
          <Button
            variant="secondary"
            onClick={openModal}
            disabled={atLimit || !canSave || saving}
          >
            {t('code.snippetsSave')}
          </Button>
        </div>

        {atLimit && (
          <p className="text-xs text-slate-500">
            {t('code.snippetsLimit', { max: MAX_CODE_SNIPPETS })}
          </p>
        )}

        {error && <Alert tone="error">{error}</Alert>}

        {snippets.length === 0 ? (
          <p className="text-sm text-slate-500">{t('code.snippetsEmpty')}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {snippets.map((snippet) => (
              <li
                key={snippet.id}
                data-testid="code-snippet-item"
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-800">
                    {snippet.name}
                  </p>
                  <p className="mt-1 truncate font-mono text-xs text-slate-500">
                    {snippet.code.replace(/\s+/g, ' ')}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button variant="secondary" onClick={() => onApply(snippet)}>
                    {t('code.snippetsApply')}
                  </Button>
                  <Button
                    variant="ghost"
                    className="text-rose-600 hover:bg-rose-50"
                    onClick={() => onDelete(snippet)}
                    disabled={saving}
                  >
                    {t('code.snippetsDelete')}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Modal
        open={open}
        title={t('code.snippetsModalTitle')}
        onClose={() => setOpen(false)}
        closeLabel={t('common.close')}
        footer={
          <Button onClick={submit} loading={saving}>
            {t('code.snippetsModalSave')}
          </Button>
        }
      >
        <div className="flex flex-col gap-2">
          <label
            htmlFor={nameId}
            className="text-sm font-medium text-slate-700"
          >
            {t('code.snippetsNameLabel')}
          </label>
          <input
            id={nameId}
            value={name}
            maxLength={MAX_SNIPPET_NAME_LENGTH}
            autoFocus
            onChange={(event) => {
              setName(event.target.value);
              setValidation(null);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                submit();
              }
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none transition-colors focus:border-indigo-500"
          />
          <p className="text-xs text-slate-500">
            {t('code.snippetsNameHint', { max: MAX_SNIPPET_NAME_LENGTH })}
          </p>
          {validation && (
            <p role="alert" className="text-xs text-rose-600">
              {validation}
            </p>
          )}
        </div>
      </Modal>
    </Card>
  );
}
