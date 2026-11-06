import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { CodeAnalysis } from '@/components/code-editor/CodeAnalysis';
import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { OutputPanel } from '@/components/code-editor/OutputPanel';
import { SandboxLimits } from '@/components/code-editor/SandboxLimits';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { readCodeDraft, takeIncomingCode, writeCodeDraft } from '@/lib/codeTransfer';
import type {
  AnalyzeResponse,
  ExecutionResult,
  LintResponse,
  SandboxLimits as SandboxLimitsData,
} from '@/types/api';

const STARTER_CODE = `# Напишите код и нажмите «Запустить»
name = input("Как тебя зовут? ")
print(f"Привет, {name}!")
`;

export function CodePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [code, setCode] = useState<string>(() => readCodeDraft() ?? STARTER_CODE);
  const [pending, setPending] = useState<string | null>(null);
  const [stdin, setStdin] = useState('');
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [lint, setLint] = useState<LintResponse | null>(null);
  const [limits, setLimits] = useState<SandboxLimitsData | null>(null);
  const [limitsError, setLimitsError] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Лимиты песочницы не зависят от кода и запрашиваются один раз (S44-001).
  useEffect(() => {
    let active = true;

    api
      .get<SandboxLimitsData>('/code/limits')
      .then((data) => {
        if (active) {
          setLimits(data);
        }
      })
      .catch(() => {
        if (active) {
          setLimitsError(true);
        }
      });

    return () => {
      active = false;
    };
  }, []);

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
        api.post<ExecutionResult>('/code/execute', { code, stdin }),
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

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await api.post<AnalyzeResponse>('/code/analyze', { code });
      setAnalysis(result);
    } catch {
      setAnalyzeError(t('code.analyzeError'));
    } finally {
      setAnalyzing(false);
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

      <div className="flex flex-col gap-1">
        <label htmlFor="code-stdin" className="text-sm font-medium text-slate-700">
          {t('code.stdinLabel')}
        </label>
        <textarea
          id="code-stdin"
          value={stdin}
          onChange={(event) => setStdin(event.target.value)}
          rows={3}
          aria-describedby="code-stdin-hint"
          className="resize-y rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm shadow-sm outline-none transition-colors focus:border-indigo-500"
        />
        <p id="code-stdin-hint" className="text-xs text-slate-500">
          {t('code.stdinHint')}
        </p>
      </div>

      <SandboxLimits limits={limits} error={limitsError} />

      <OutputPanel result={result} issues={lint?.issues ?? []} running={running} />

      <CodeAnalysis
        analysis={analysis}
        analyzing={analyzing}
        error={analyzeError}
        onAnalyze={() => void handleAnalyze()}
      />
    </div>
  );
}
