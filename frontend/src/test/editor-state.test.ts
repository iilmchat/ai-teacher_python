import { beforeEach, describe, expect, it } from 'vitest';

import {
  clearEditorState,
  EDITOR_STATE_TTL_MS,
  editorStateKey,
  readEditorState,
  taskEditorContext,
  writeEditorState,
} from '@/lib/editorState';

const NOW = Date.parse('2026-11-06T12:00:00');

describe('локальное состояние редактора (S44-004)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('сохраняет код с временем и читает его по контексту', () => {
    writeEditorState('code', 'print("sandbox")', NOW);
    writeEditorState(taskEditorContext('task-1'), 'print("task")', NOW + 1);

    expect(readEditorState('code', NOW + 10)).toEqual({
      code: 'print("sandbox")',
      savedAt: NOW,
    });
    expect(readEditorState(taskEditorContext('task-1'), NOW + 10)?.code).toBe('print("task")');
    expect(localStorage.getItem(editorStateKey('code'))).not.toBeNull();
    expect(localStorage.getItem(editorStateKey(taskEditorContext('task-1')))).not.toBeNull();
  });

  it('удаляет запись через 30 дней', () => {
    writeEditorState('code', 'print("old")', NOW);

    expect(readEditorState('code', NOW + EDITOR_STATE_TTL_MS - 1)?.code).toBe('print("old")');
    expect(readEditorState('code', NOW + EDITOR_STATE_TTL_MS)).toBeNull();
    expect(localStorage.getItem(editorStateKey('code'))).toBeNull();
  });

  it('удаляет повреждённую запись', () => {
    localStorage.setItem(editorStateKey('code'), 'not-json');

    expect(readEditorState('code', NOW)).toBeNull();
    expect(localStorage.getItem(editorStateKey('code'))).toBeNull();
  });

  it('очищает только выбранный контекст', () => {
    writeEditorState('code', 'print(1)', NOW);
    writeEditorState(taskEditorContext('task-1'), 'print(2)', NOW);

    clearEditorState('code');

    expect(readEditorState('code', NOW)).toBeNull();
    expect(readEditorState(taskEditorContext('task-1'), NOW)?.code).toBe('print(2)');
  });
});
