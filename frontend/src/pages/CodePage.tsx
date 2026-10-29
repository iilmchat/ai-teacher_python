import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { OutputPanel } from '@/components/code-editor/OutputPanel';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import type { ExecutionResult, LintResponse } from '@/types/api';

const STARTER_CODE = `# Напишите код и нажмите «Запустить»
name = input("Как тебя зовут? ")
print(f"Привет, {name}!")
`;

export function CodePage() {
  const { t } = useTranslation();
  const [code, setCode] = useState(STARTER_CODE);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [lint, setLint] = useState<LintResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const [execution, lintResult] = await Promise.all([
        api.post<ExecutionResult>('/code/execute', { code }),
        api.post<LintResponse>('/code/lint', { code }),
      ]);
      setResult(execution);
      setLint(lintResult);
    } catch {
      setError(t('code.runError'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t('code.title')}</h1>
        <Button onClick={() => void handleRun()} loading={running}>
          {t('code.run')}
        </Button>
      </header>

      <p className="text-sm text-slate-600">{t('code.subtitle')}</p>

      {error && <Alert tone="error">{error}</Alert>}

      <CodeEditor value={code} onChange={setCode} height="360px" />

      <OutputPanel result={result} issues={lint?.issues ?? []} running={running} />
    </div>
  );
}
