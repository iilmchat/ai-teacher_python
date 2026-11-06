import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import type { AnalyzeResponse, LintIssue } from '@/types/api';

const SEVERITIES = ['error', 'warning', 'info'] as const;
type Severity = (typeof SEVERITIES)[number];

const SEVERITY_LABELS: Record<Severity, string> = {
  error: 'code.severityError',
  warning: 'code.severityWarning',
  info: 'code.severityInfo',
};

const STAT_KEYS = [
  'lines',
  'functions',
  'classes',
  'loops',
  'conditions',
  'imports',
] as const;

interface CodeAnalysisProps {
  analysis: AnalyzeResponse | null;
  analyzing: boolean;
  error: string | null;
  onAnalyze: () => void;
}

function issuesBySeverity(issues: LintIssue[]): Array<[Severity, LintIssue[]]> {
  return SEVERITIES.map((severity) => [
    severity,
    issues.filter((issue) => issue.severity === severity),
  ] as [Severity, LintIssue[]]).filter(([, items]) => items.length > 0);
}

/** Блок «Разбор кода»: сводка, метрики и замечания по категориям (S44-001) */
export function CodeAnalysis({
  analysis,
  analyzing,
  error,
  onAnalyze,
}: CodeAnalysisProps) {
  const { t } = useTranslation();

  const hasErrors = analysis?.issues.some((issue) => issue.severity === 'error');
  const hasWarnings = analysis?.issues.some((issue) => issue.severity === 'warning');
  const tone = hasErrors ? 'error' : hasWarnings ? 'warning' : 'success';

  return (
    <Card title={t('code.analyzeTitle')}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">{t('code.analyzeHint')}</p>
        <Button variant="secondary" onClick={onAnalyze} loading={analyzing}>
          {t('code.analyze')}
        </Button>
      </div>

      {error && (
        <div className="mt-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {!analysis && !error && (
        <p className="mt-3 text-sm text-slate-500">{t('code.analyzeEmpty')}</p>
      )}

      {analysis && (
        <div className="mt-3 flex flex-col gap-3">
          <Alert tone={tone}>{analysis.summary}</Alert>

          <div className="flex flex-wrap gap-2 text-xs text-slate-600">
            {STAT_KEYS.map((key) => (
              <span key={key} className="rounded bg-slate-100 px-2 py-1">
                {t(`code.stats.${key}`, { count: analysis.stats[key] ?? 0 })}
              </span>
            ))}
          </div>

          {analysis.issues.length === 0 ? (
            <p className="text-sm text-emerald-700">{t('code.analyzeNoIssues')}</p>
          ) : (
            issuesBySeverity(analysis.issues).map(([severity, issues]) => (
              <section key={severity} className="flex flex-col gap-1">
                <h3 className="text-sm font-semibold text-slate-700">
                  {t(SEVERITY_LABELS[severity])} ({issues.length})
                </h3>
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
              </section>
            ))
          )}
        </div>
      )}
    </Card>
  );
}
