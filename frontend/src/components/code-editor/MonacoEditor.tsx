import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type * as Monaco from 'monaco-editor';
import {
  MONACO_EDITOR_MODULE,
  MONACO_LOADER_URL,
} from '@/lib/monacoSetup';

interface MonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  height: string;
  readOnly: boolean;
}

declare global {
  interface Window {
    require?: (dependencies: string[], callback: () => void) => void;
    monaco?: typeof Monaco;
  }
}

let monacoPromise: Promise<void> | null = null;

/** Загрузить AMD-ассеты Monaco с собственного origin (один раз) */
function loadMonaco(): Promise<void> {
  if (window.monaco) {
    return Promise.resolve();
  }
  if (monacoPromise) {
    return monacoPromise;
  }
  monacoPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = MONACO_LOADER_URL;
    script.async = true;
    script.onload = () => {
      if (!window.require) {
        reject(new Error('Monaco AMD loader is unavailable'));
        return;
      }
      window.require([MONACO_EDITOR_MODULE], () => resolve());
    };
    script.onerror = () => reject(new Error('Failed to load Monaco assets'));
    document.head.appendChild(script);
  });
  return monacoPromise;
}

/** Monaco, загружаемый отдельным чанком и локальными ассетами (S19-001). */
export default function MonacoEditor({
  value,
  onChange,
  height,
  readOnly,
}: MonacoEditorProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<Monaco.editor.IStandaloneCodeEditor | null>(null);
  const onChangeRef = useRef(onChange);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  onChangeRef.current = onChange;

  useEffect(() => {
    let disposed = false;

    loadMonaco()
      .then(() => {
        if (disposed || !containerRef.current || !window.monaco) {
          return;
        }
        const editor = window.monaco.editor.create(containerRef.current, {
          value,
          language: 'python',
          theme: 'vs-dark',
          readOnly,
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          quickSuggestions: false,
        });
        editor.onDidChangeModelContent(() => {
          onChangeRef.current(editor.getValue());
        });
        editorRef.current = editor;
        setReady(true);
      })
      .catch(() => setFailed(true));

    return () => {
      disposed = true;
      editorRef.current?.dispose();
      editorRef.current = null;
    };
    // Редактор создаётся один раз; value/readOnly обновляются отдельно.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const editor = editorRef.current;
    if (editor && editor.getValue() !== value) {
      editor.setValue(value);
    }
  }, [value]);

  useEffect(() => {
    editorRef.current?.updateOptions({ readOnly });
  }, [readOnly]);

  if (failed) {
    return (
      <div style={{ height }} className="rounded-lg border border-rose-300 p-4 text-sm text-rose-600">
        {t('code.editorLoadError')}
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-300">
      <div ref={containerRef} style={{ height }} />
      {!ready && (
        <div
          style={{ height }}
          className="absolute inset-0 flex items-center justify-center p-4 text-sm text-slate-400"
        >
          {t('common.loading')}
        </div>
      )}
    </div>
  );
}
