import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface CodeBlockProps {
  code: string;
  language?: string;
  /** Отправить код в песочницу (S43-005) */
  onSendToSandbox?: (code: string) => void;
}

/** Блок кода с копированием и переходом в песочницу (без сторонних парсеров) */
export function CodeBlock({ code, language = 'python', onSendToSandbox }: CodeBlockProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="my-2 overflow-hidden rounded-lg border border-slate-700 bg-slate-900">
      <div className="flex items-center justify-between bg-slate-800 px-3 py-1 text-xs text-slate-300">
        <span>{language}</span>
        <span className="flex items-center gap-1">
          {onSendToSandbox && (
            <button
              type="button"
              onClick={() => onSendToSandbox(code)}
              aria-label={t('chat.toSandbox')}
              className="rounded px-2 py-0.5 hover:bg-slate-700"
            >
              {t('chat.toSandbox')}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="rounded px-2 py-0.5 hover:bg-slate-700"
          >
            {copied ? t('chat.copied') : t('chat.copy')}
          </button>
        </span>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}
