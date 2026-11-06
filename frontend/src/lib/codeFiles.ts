/**
 * Скачивание и загрузка кода песочницы (S44-003).
 *
 * Загрузка проверяется до замены кода в редакторе: расширение `.py`,
 * размер файла до 200 КБ и длина текста до лимита песочницы. Проверки
 * продублированы на клиенте, чтобы ученик сразу видел причину отказа.
 */

import { saveBlob } from '@/lib/download';

/** Максимальный размер загружаемого файла — 200 КБ */
export const MAX_CODE_FILE_BYTES = 200 * 1024;

/** Максимальная длина кода — как у запуска в песочнице */
export const MAX_CODE_LENGTH = 20_000;

/** Единственное допустимое расширение файла */
export const CODE_FILE_EXTENSION = '.py';

export type CodeFileError = 'extension' | 'size' | 'length' | 'read';

export type CodeFileLoadResult =
  | { ok: true; code: string }
  | { ok: false; error: CodeFileError };

/** Файл с расширением `.py` (регистр не важен) */
export function isPythonFile(file: Pick<File, 'name'>): boolean {
  return file.name.toLowerCase().endsWith(CODE_FILE_EXTENSION);
}

/** Проверить файл до чтения: расширение и размер */
export function validateCodeFile(
  file: Pick<File, 'name' | 'size'>,
): CodeFileError | null {
  if (!isPythonFile(file)) {
    return 'extension';
  }
  if (file.size > MAX_CODE_FILE_BYTES) {
    return 'size';
  }
  return null;
}

/** Прочитать текст файла (FileReader работает и в браузере, и в jsdom) */
function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error ?? new Error('read failed'));
    reader.readAsText(file);
  });
}

/** Проверить и прочитать локальный файл, не меняя редактор при ошибке */
export async function loadCodeFile(file: File): Promise<CodeFileLoadResult> {
  const invalid = validateCodeFile(file);
  if (invalid !== null) {
    return { ok: false, error: invalid };
  }

  let code: string;
  try {
    code = await readFileText(file);
  } catch {
    return { ok: false, error: 'read' };
  }

  if (code.length > MAX_CODE_LENGTH) {
    return { ok: false, error: 'length' };
  }

  return { ok: true, code };
}

/** Скачать текущий код как `code.py` */
export function downloadCode(code: string): void {
  saveBlob(
    new Blob([code], { type: 'text/x-python;charset=utf-8' }),
    'code.py',
  );
}
