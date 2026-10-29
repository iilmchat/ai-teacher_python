import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import type { ExecutionResult, LintIssue } from '@/types/api';

interface OutputPanelProps {
  result: ExecutionResult | null;
  issues?: LintIssue[];
  running?: boolean;
}

export function OutputPanel({ result, issues = [], running = false }: OutputPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-slate-700">{t('code.output')}</h3>

      {running && <p className="text-sm text-slate-500">{t('code.running')}</p>}

      {!running && !result && (
        <p className="text-sm text-slate-500">{t('code.noOutput')}</p>
      )}

      {result && (
        <>
          {result.violations.length > 0 && (
            <Alert tone="error">{result.violations.join('; ')}</Alert>
          )}

          <pre
            aria-label={t('code.output')}
            className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100"
          >
            {result.output || t('code.noOutput')}
          </pre>

          {result.error && <Alert tone="error">{result.error}</Alert>}

          <p className="text-xs text-slate-500">
            {t('code.executionTime', { seconds: result.execution_time.toFixed(3) })}
          </p>
        </>
      )}

      {issues.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs">
          {issues.map((issue) => (
            <li
              key={`${issue.code}-${issue.line}-${issue.column}`}
              className={
                issue.severity === 'error'
                  ? 'text-rose-700'
                  : issue.severity === 'warning'
                    ? 'text-amber-700'
                    : 'text-slate-600'
              }
            >
              {issue.line}:{issue.column} · {issue.code} · {issue.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
