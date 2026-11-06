import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { CodeAnalysis } from '@/components/code-editor/CodeAnalysis';
import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { CodeHistory } from '@/components/code-editor/CodeHistory';
import { CodeSnippets } from '@/components/code-editor/CodeSnippets';
import { OutputPanel } from '@/components/code-editor/OutputPanel';
import { SandboxLimits } from '@/components/code-editor/SandboxLimits';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { downloadCode, loadCodeFile, type CodeFileError } from '@/lib/codeFiles';
import { MAX_CODE_SNIPPETS, newCodeSnippet, parseCodeSnippets } from '@/lib/codeSnippets';
import {
  clearCodeDraft,
  readCodeDraft,
  takeIncomingCode,
  writeCodeDraft,
} from '@/lib/codeTransfer';
import { readEditorState } from '@/lib/editorState';
import { useAuthStore } from '@/store/auth';
import type {
  AnalyzeResponse,
  CodeSnippet,
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

/** Причина отказа при загрузке файла → ключ перевода (S44-003) */
const FILE_ERROR_KEYS: Record<CodeFileError, string> = {
  extension: 'code.fileErrorExtension',
  size: 'code.fileErrorSize',
  length: 'code.fileErrorLength',
  read: 'code.fileErrorRead',
};

export function CodePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [code, setCode] = useState<string>(() => readCodeDraft() ?? STARTER_CODE);
  const [pending, setPending] = useState<string | null>(null);
  const [pendingUpload, setPendingUpload] = useState<string | null>(null);
  /** Когда код песочницы сохранён локально; null — сохранения нет */
  const [savedAt, setSavedAt] = useState<number | null>(
    () => readEditorState('code')?.savedAt ?? null,
  );
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
  const [fileError, setFileError] = useState<string | null>(null);
  const [snippetSaving, setSnippetSaving] = useState(false);
  const [snippetError, setSnippetError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const settings = useAuthStore((state) => state.user?.settings);
  const setCodeSnippets = useAuthStore((state) => state.setCodeSnippets);
  const snippets = parseCodeSnippets(settings);

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
    setSavedAt(Date.now());
  }, []);

  function handleChange(value: string) {
    setCode(value);
    writeCodeDraft(value);
    setSavedAt(Date.now());
  }

  function acceptIncoming() {
    if (pending === null) {
      return;
    }
    setCode(pending);
    writeCodeDraft(pending);
    setSavedAt(Date.now());
    setPending(null);
  }

  function handleClearSaved() {
    clearCodeDraft();
    setSavedAt(null);
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

  /** Сбросить прошлый результат, когда в редактор приходит другой код */
  function clearResult() {
    setResult(null);
    setLint(null);
    setAnalysis(null);
    setAnalyzeError(null);
    setError(null);
  }

  function handleRestart(historyCode: string) {
    // Возвращаем код в редактор, но не запускаем его автоматически (S44-002).
    handleChange(historyCode);
    clearResult();
  }

  function handleDownload() {
    downloadCode(code);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Сбрасываем input: тот же файл можно выбрать повторно.
    event.target.value = '';
    if (!file) {
      return;
    }

    setFileError(null);
    const loaded = await loadCodeFile(file);
    if (!loaded.ok) {
      setFileError(t(FILE_ERROR_KEYS[loaded.error]));
      return;
    }

    // Локальный черновик мог быть изменён позже, чем файл. Не заменяем его
    // молча: ученик сам решает, что важнее (S44-004).
    const saved = readEditorState('code');
    if (saved !== null && saved.code !== loaded.code && saved.savedAt > file.lastModified) {
      setPendingUpload(loaded.code);
      return;
    }

    applyUploadedCode(loaded.code);
  }

  /**
   * Поставить код из файла в редактор. В localStorage он попадёт только
   * после явного редактирования (S44-004).
   */
  function applyUploadedCode(loaded: string) {
    setCode(loaded);
    setPendingUpload(null);
    clearResult();
  }

  function acceptUpload() {
    if (pendingUpload === null) {
      return;
    }
    // Ученик выбрал файл вместо сохранённого черновика: старую запись
    // убираем, но сам файл не сохраняем до первой правки.
    clearCodeDraft();
    setSavedAt(null);
    applyUploadedCode(pendingUpload);
  }

  function handleApplySnippet(snippet: CodeSnippet) {
    handleChange(snippet.code);
    clearResult();
  }

  async function handleSaveSnippet(name: string) {
    if (snippets.length >= MAX_CODE_SNIPPETS) {
      setSnippetError(t('code.snippetsLimitError', { max: MAX_CODE_SNIPPETS }));
      return;
    }

    setSnippetSaving(true);
    setSnippetError(null);
    try {
      await setCodeSnippets([...snippets, newCodeSnippet(name, code)]);
    } catch {
      setSnippetError(t('code.snippetsSaveError'));
    } finally {
      setSnippetSaving(false);
    }
  }

  async function handleDeleteSnippet(snippet: CodeSnippet) {
    if (!window.confirm(t('code.snippetsDeleteConfirm', { name: snippet.name }))) {
      return;
    }

    setSnippetSaving(true);
    setSnippetError(null);
    try {
      await setCodeSnippets(snippets.filter((item) => item.id !== snippet.id));
    } catch {
      setSnippetError(t('code.snippetsDeleteError'));
    } finally {
      setSnippetSaving(false);
    }
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

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={handleDownload}>
          {t('code.download')}
        </Button>
        <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
          {t('code.upload')}
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".py,text/x-python"
          aria-label={t('code.upload')}
          data-testid="code-file-input"
          className="sr-only"
          onChange={(event) => void handleFileChange(event)}
        />
        {savedAt !== null && (
          <Button variant="secondary" onClick={handleClearSaved}>
            {t('code.clearSaved')}
          </Button>
        )}
      </div>

      {pendingUpload !== null && (
        <Alert tone="warning">
          <p>{t('code.uploadNewerSaved')}</p>
          <div className="mt-2 flex gap-2">
            <Button onClick={acceptUpload}>{t('code.uploadReplace')}</Button>
            <Button variant="secondary" onClick={() => setPendingUpload(null)}>
              {t('code.uploadKeep')}
            </Button>
          </div>
        </Alert>
      )}

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

      {fileError && <Alert tone="error">{fileError}</Alert>}

      <CodeEditor value={code} onChange={handleChange} height="360px" />

      <CodeSnippets
        snippets={snippets}
        saving={snippetSaving}
        canSave={code.trim().length > 0}
        error={snippetError}
        onSave={handleSaveSnippet}
        onApply={handleApplySnippet}
        onDelete={handleDeleteSnippet}
      />

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
