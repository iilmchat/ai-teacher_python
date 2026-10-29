import Editor, { type OnMount } from '@monaco-editor/react';
import { useTranslation } from 'react-i18next';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
}

/**
 * Обёртка Monaco. В тестах и при отсутствии загрузчика используется
 * тот же контракт, поэтому компонент можно замокать.
 */
export function CodeEditor({
  value,
  onChange,
  height = '320px',
  readOnly = false,
}: CodeEditorProps) {
  const { t } = useTranslation();

  const handleMount: OnMount = (editor) => {
    // Отключаем лишние подсказки, чтобы не пугать новичков
    editor.updateOptions({ quickSuggestions: false });
  };

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
