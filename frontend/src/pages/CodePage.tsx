import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { CodeAnalysis } from '@/components/code-editor/CodeAnalysis';
import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { CodeHistory } from '@/components/code-editor/CodeHistory';
import { OutputPanel } from '@/components/code-editor/OutputPanel';
import { SandboxLimits } from '@/components/code-editor/SandboxLimits';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { readCodeDraft, takeIncomingCode, writeCodeDraft } from '@/lib/codeTransfer';
import type {
  AnalyzeResponse,
  ExecutionRecord,
  ExecutionResult,
  LintResponse,
  SandboxLimits as SandboxLimitsData,
} from '@/types/api';

const STARTER_CODE = `# Напишите код и нажмите «Запустить»
name = input("Как тебя зовут? ")
print(f"Привет, {name}!")
`;

/** Сколько записей истории показывать за один раз (S44-002) */
const HISTORY_PAGE_SIZE = 10;

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
  const [history, setHistory] = useState<ExecutionRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Запрашиваем на одну запись больше, чтобы понять, есть ли следующая
  // страница, не делая лишний пустой запрос (S44-002).
  const loadHistory = useCallback(
    async (skip: number, append: boolean) => {
      setHistoryLoading(true);
      setHistoryError(null);
      try {
        const data = await api.get<ExecutionRecord[]>(
          `/code/history?skip=${skip}&limit=${HISTORY_PAGE_SIZE + 1}`,
        );
        const page = data.slice(0, HISTORY_PAGE_SIZE);

        setHistory((previous) => {
          if (!append) {
            return page;
          }
          const known = new Set(previous.map((item) => item.id));
          return [...previous, ...page.filter((item) => !known.has(item.id))];
        });
        setHistoryHasMore(data.length > HISTORY_PAGE_SIZE);
      } catch {
        setHistoryError(t('code.historyError'));
      } finally {
        setHistoryLoading(false);
      }
    },
    [t],
  );

  // История подгружается при открытии страницы (S44-002).
  useEffect(() => {
    void loadHistory(0, false);
  }, [loadHistory]);

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
      // Новый запуск сразу виден в истории (S44-002).
      void loadHistory(0, false);
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

  function handleRestart(historyCode: string) {
    // Возвращаем код в редактор, но не запускаем его автоматически (S44-002).
    handleChange(historyCode);
    setResult(null);
    setLint(null);
    setAnalysis(null);
    setAnalyzeError(null);
    setError(null);
  }

  function handleLoadMoreHistory() {
    void loadHistory(history.length, true);
  }

  function handleRetryHistory() {
    void loadHistory(history.length, history.length > 0);
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

      <CodeHistory
        items={history}
        loading={historyLoading}
        error={historyError}
        hasMore={historyHasMore}
        onLoadMore={handleLoadMoreHistory}
        onRetry={handleRetryHistory}
        onRestart={handleRestart}
      />
    </div>
  );
}
