/**
 * Передача кода между чатом и песочницей (S43-005).
 *
 * Код ходит через два слота в localStorage:
 * - `incoming` — код, который передали из другой страницы; песочница
 *   забирает его один раз при открытии;
 * - `draft` — код, с которым работает ученик в песочнице. Он хранится в
 *   общем формате редактора (S44-004): с временем сохранения и сроком
 *   жизни 30 дней.
 *
 * Слоты разведены намеренно: переданный код не должен молча затирать
 * черновик — песочница спрашивает подтверждение.
 */

import { clearEditorState, readEditorState, writeEditorState } from '@/lib/editorState';

/** Ключ черновика до S44-004: читаем его один раз и переносим */
const LEGACY_DRAFT_KEY = 'ai-teacher.code.draft';
const INCOMING_KEY = 'ai-teacher.code.incoming';

/** Код, который ученик напечатал в песочнице */
export function readCodeDraft(): string | null {
  const state = readEditorState('code');
  if (state !== null) {
    try {
      // Если новый формат уже есть, старый ключ мог остаться от сбоя
      // миграции. Он не должен «воскреснуть» после истечения TTL.
      localStorage.removeItem(LEGACY_DRAFT_KEY);
    } catch {
      // localStorage недоступен — новая запись всё равно прочитана.
    }
    return state.code;
  }

  // Старые версии хранили просто строку без времени и TTL. Переносим её
  // в новый формат, чтобы ученик не потерял черновик после обновления.
  try {
    const legacy = localStorage.getItem(LEGACY_DRAFT_KEY);
    if (legacy !== null) {
      writeEditorState('code', legacy);
      localStorage.removeItem(LEGACY_DRAFT_KEY);
      return legacy;
    }
  } catch {
    // localStorage недоступен — работаем без сохранения.
  }
  return null;
}

/** Сохранить код песочницы (черновик) */
export function writeCodeDraft(code: string): void {
  writeEditorState('code', code);
  try {
    localStorage.removeItem(LEGACY_DRAFT_KEY);
  } catch {
    // Старый ключ уже не нужен; ошибка не мешает новой записи.
  }
}

/** Удалить сохранённый код песочницы */
export function clearCodeDraft(): void {
  clearEditorState('code');
  try {
    localStorage.removeItem(LEGACY_DRAFT_KEY);
  } catch {
    // Новый ключ уже удалён; старый ключ мог не существовать.
  }
}

/** Передать код на другую страницу (чат → песочница) */
export function putIncomingCode(code: string): void {
  try {
    localStorage.setItem(INCOMING_KEY, code);
  } catch {
    // Без localStorage код не переживёт переход — интерфейс сообщит об ошибке.
  }
}

/** Забрать переданный код (песочница забирает один раз) */
export function takeIncomingCode(): string | null {
  try {
    const code = localStorage.getItem(INCOMING_KEY);
    if (code !== null) {
      localStorage.removeItem(INCOMING_KEY);
    }
    return code;
  } catch {
    return null;
  }
}

/** Есть ли непрочитанный переданный код */
export function hasIncomingCode(): boolean {
  try {
    return localStorage.getItem(INCOMING_KEY) !== null;
  } catch {
    return false;
  }
}

/** Текст сообщения с кодом как вложением (код уходит вложением, а не «решением») */
export function buildCodeAttachment(code: string, intro: string): string {
  return `${intro}\n\n\`\`\`python\n${code.replace(/\s+$/, '')}\n\`\`\``;
}
