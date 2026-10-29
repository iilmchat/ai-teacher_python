import { useState } from 'react';
import { useTranslation } from 'react-i18next';

interface CodeBlockProps {
  code: string;
  language?: string;
}

/** Блок кода с копированием (без сторонних markdown-парсеров) */
export function CodeBlock({ code, language = 'python' }: CodeBlockProps) {
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
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="rounded px-2 py-0.5 hover:bg-slate-700"
        >
          {copied ? t('chat.copied') : t('chat.copy')}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed text-slate-100">
        <code>{code}</code>
      </pre>
    </div>
  );
}
