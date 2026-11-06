import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { OutputPanel } from '@/components/code-editor/OutputPanel';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { readCodeDraft, takeIncomingCode, writeCodeDraft } from '@/lib/codeTransfer';
import type { ExecutionResult, LintResponse } from '@/types/api';

const STARTER_CODE = `# Напишите код и нажмите «Запустить»
name = input("Как тебя зовут? ")
print(f"Привет, {name}!")
`;

export function CodePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [code, setCode] = useState<string>(() => readCodeDraft() ?? STARTER_CODE);
  const [pending, setPending] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [lint, setLint] = useState<LintResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Код из чата не должен молча затирать черновик: спрашиваем (S43-005).
  useEffect(() => {
    const incoming = takeIncomingCode();
    if (!incoming) {
      return;
    }
    const draft = readCodeDraft();
    if (draft && draft.trim() && draft.trim() !== incoming.trim()) {
      setPending(incoming);
      return;
    }
    setCode(incoming);
    writeCodeDraft(incoming);
  }, []);

  function handleChange(value: string) {
    setCode(value);
    writeCodeDraft(value);
  }

  function acceptIncoming() {
    if (pending === null) {
      return;
    }
    setCode(pending);
    writeCodeDraft(pending);
    setPending(null);
  }

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

  function handleAskAssistant() {
    // Код уходит в чат как вложение и ждёт отправки (S43-005).
    navigate('/chat', { state: { code } });
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t('code.title')}</h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleAskAssistant}>
            {t('code.askAssistant')}
          </Button>
          <Button onClick={() => void handleRun()} loading={running}>
            {t('code.run')}
          </Button>
        </div>
      </header>

      <p className="text-sm text-slate-600">{t('code.subtitle')}</p>

      {pending !== null && (
        <Alert tone="warning">
          <p>{t('code.replaceDraft')}</p>
          <div className="mt-2 flex gap-2">
            <Button onClick={acceptIncoming}>{t('code.replaceYes')}</Button>
            <Button variant="secondary" onClick={() => setPending(null)}>
              {t('code.replaceNo')}
            </Button>
          </div>
        </Alert>
      )}

      {error && <Alert tone="error">{error}</Alert>}

      <CodeEditor value={code} onChange={handleChange} height="360px" />

      <OutputPanel result={result} issues={lint?.issues ?? []} running={running} />
    </div>
  );
}
