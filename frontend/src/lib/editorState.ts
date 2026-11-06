/**
 * Локальное состояние редактора (S44-004).
 *
 * Код переживает перезагрузку страницы, но не хранится вечно: запись живёт
 * 30 дней. Контекст разделяет песочницу и задачи — `code` и `task:<id>`,
 * чтобы код одной задачи не появлялся в другой.
 */

/** Срок жизни сохранённого кода — 30 дней */
export const EDITOR_STATE_TTL_MS = 30 * 24 * 60 * 60 * 1000;

/** Контекст редактора: общая песочница или конкретная задача */
export type EditorContext = 'code' | `task:${string}`;

export interface EditorState {
  code: string;
  /** Момент сохранения в миллисекундах Unix */
  savedAt: number;
}

const STORAGE_PREFIX = 'ai-teacher.editor.';

/** Ключ localStorage для контекста */
export function editorStateKey(context: EditorContext): string {
  return `${STORAGE_PREFIX}${context}`;
}

/** Контекст редактора задачи */
export function taskEditorContext(taskId: string): EditorContext {
  return `task:${taskId}`;
}

function parseState(raw: string): EditorState | null {
  try {
    const data = JSON.parse(raw) as unknown;
    if (typeof data !== 'object' || data === null) {
      return null;
    }
    const { code, savedAt } = data as Record<string, unknown>;
    if (typeof code !== 'string' || typeof savedAt !== 'number') {
      return null;
    }
    if (!Number.isFinite(savedAt)) {
      return null;
    }
    return { code, savedAt };
  } catch {
    return null;
  }
}

/**
 * Прочитать сохранённый код. Просроченная или повреждённая запись удаляется
 * и не возвращается вызывающему коду.
 */
export function readEditorState(
  context: EditorContext,
  now: number = Date.now(),
): EditorState | null {
  try {
    const key = editorStateKey(context);
    const raw = localStorage.getItem(key);
    if (raw === null) {
      return null;
    }

    const state = parseState(raw);
    if (state === null || now - state.savedAt >= EDITOR_STATE_TTL_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return state;
  } catch {
    // Приватный режим браузера: локальное состояние недоступно.
    return null;
  }
}

/** Сохранить код редактора */
export function writeEditorState(
  context: EditorContext,
  code: string,
  now: number = Date.now(),
): void {
  try {
    const state: EditorState = { code, savedAt: now };
    localStorage.setItem(editorStateKey(context), JSON.stringify(state));
  } catch {
    // Приватный режим браузера: код просто не сохранится.
  }
}

/** Удалить сохранённый код контекста */
export function clearEditorState(context: EditorContext): void {
  try {
    localStorage.removeItem(editorStateKey(context));
  } catch {
    // Нечего очищать, если localStorage недоступен.
  }
}
