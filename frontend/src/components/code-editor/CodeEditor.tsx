import Editor, { type OnMount } from '@monaco-editor/react';
import { useTranslation } from 'react-i18next';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
}

/**
 * Обёртка Monaco.
 *
 * В e2e-режиме (`VITE_E2E=1`) рендерится обычная textarea: Playwright не должен
 * зависеть от загрузки Monaco с CDN (KI-013), а логика страниц проверяется
 * одинаково. В обычном режиме используется редактор.
 */
export function CodeEditor({
  value,
  onChange,
  height = '320px',
  readOnly = false,
}: CodeEditorProps) {
  const { t } = useTranslation();
  const isE2E = import.meta.env.VITE_E2E === '1';

  const handleMount: OnMount = (editor) => {
    // Отключаем лишние подсказки, чтобы не пугать новичков
    editor.updateOptions({ quickSuggestions: false });
  };

  if (isE2E) {
    return (
      <textarea
        data-testid="code-input"
        aria-label={t('code.editorLabel')}
        value={value}
        readOnly={readOnly}
        onChange={(event) => onChange(event.target.value)}
        style={{ height }}
        className="w-full rounded-lg border border-slate-300 bg-slate-900 p-3 font-mono text-sm text-slate-100"
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-300">
      <Editor
        height={height}
        defaultLanguage="python"
        theme="vs-dark"
        value={value}
        onChange={(next) => onChange(next ?? '')}
        onMount={handleMount}
        loading={<div className="p-4 text-sm text-slate-400">{t('common.loading')}</div>}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
        }}
      />
    </div>
  );
}
