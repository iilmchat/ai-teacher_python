/**
 * Передача кода между чатом и песочницей (S43-005).
 *
 * Код ходит через два слота в localStorage:
 * - `incoming` — код, который передали из другой страницы; песочница
 *   забирает его один раз при открытии;
 * - `draft` — код, с которым работает ученик в песочнице.
 *
 * Слоты разведены намеренно: переданный код не должен молча затирать
 * черновик — песочница спрашивает подтверждение.
 */

const DRAFT_KEY = 'ai-teacher.code.draft';
const INCOMING_KEY = 'ai-teacher.code.incoming';

/** Код, который ученик напечатал в песочнице */
export function readCodeDraft(): string | null {
  try {
    return localStorage.getItem(DRAFT_KEY);
  } catch {
    return null;
  }
}

/** Сохранить код песочницы (черновик) */
export function writeCodeDraft(code: string): void {
  try {
    localStorage.setItem(DRAFT_KEY, code);
  } catch {
    // Приватный режим браузера: черновик просто не сохранится.
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
