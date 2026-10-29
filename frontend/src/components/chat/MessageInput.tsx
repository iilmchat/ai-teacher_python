import { useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';

interface MessageInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
}

export function MessageInput({ onSend, disabled = false }: MessageInputProps) {
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

  return (
    <div className="flex items-end gap-2 border-t border-slate-200 bg-white p-3">
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
  );
}
