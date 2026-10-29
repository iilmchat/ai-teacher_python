import { Suspense, lazy } from 'react';
import { useTranslation } from 'react-i18next';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
}

const MonacoEditor = lazy(() => import('@/components/code-editor/MonacoEditor'));

/**
 * Обёртка редактора.
 *
 * В e2e-режиме (`VITE_E2E=1`) рендерится textarea: Playwright не зависит от
 * Monaco. В обычном режиме Monaco загружается локально отдельным чанком
 * (S19-001), без CDN.
 */
export function CodeEditor({
  value,
  onChange,
  height = '320px',
  readOnly = false,
}: CodeEditorProps) {
  const { t } = useTranslation();
  const isE2E = import.meta.env.VITE_E2E === '1';

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
    <Suspense
      fallback={
        <div style={{ height }} className="rounded-lg border border-slate-300 p-4 text-sm text-slate-400">
          {t('common.loading')}
        </div>
      }
    >
      <MonacoEditor
        value={value}
        onChange={onChange}
        height={height}
        readOnly={readOnly}
      />
    </Suspense>
  );
}
