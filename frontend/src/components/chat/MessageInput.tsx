import { useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import type { PromptTemplate } from '@/lib/promptTemplates';

interface MessageInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  /** Стартовые шаблоны промптов для текущего уровня (S43-004) */
  templates?: PromptTemplate[];
  /** Идентификатор выбранного шаблона */
  selectedTemplateId?: string | null;
  /** Выбрать шаблон: текст подставляется в поле ввода */
  onSelectTemplate?: (templateId: string) => void;
}

export function MessageInput({
  onSend,
  disabled = false,
  templates = [],
  selectedTemplateId = null,
  onSelectTemplate,
}: MessageInputProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');

  function submit() {
    const text = value.trim();
    if (!text || disabled) {
      return;
    }
    onSend(text);
    setValue('');
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter отправляет, Shift+Enter переносит строку (удобно для кода)
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function applyTemplate(template: PromptTemplate) {
    // Шаблон только подставляется: отправляет ученик (S43-004).
    setValue(t(template.textKey));
    onSelectTemplate?.(template.id);
  }

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      {templates.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {templates.map((template) => (
            <button
              key={template.id}
              type="button"
              onClick={() => applyTemplate(template)}
              aria-pressed={selectedTemplateId === template.id}
              className={`rounded-full border px-2.5 py-1 text-xs ${
                selectedTemplateId === template.id
                  ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
                  : 'border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50'
              }`}
            >
              {t(template.titleKey)}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2">
        <label htmlFor="chat-input" className="sr-only">
          {t('chat.inputLabel')}
        </label>
        <textarea
          id="chat-input"
          rows={2}
          value={value}
          disabled={disabled}
          placeholder={t('chat.placeholder')}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          className="max-h-40 min-h-[52px] flex-1 resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <Button type="button" onClick={submit} disabled={disabled || !value.trim()}>
          {t('chat.send')}
        </Button>
      </div>
    </div>
  );
}
