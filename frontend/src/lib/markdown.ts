/**
 * Разбор markdown-подобного текста ассистента на обычный текст и блоки кода.
 */

export type MarkdownSegment =
  | { kind: 'text'; value: string }
  | { kind: 'code'; value: string };

const CODE_FENCE = /```[a-zA-Z]*\n?([\s\S]*?)```/g;

export function splitCodeFences(text: string): MarkdownSegment[] {
  const segments: MarkdownSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  CODE_FENCE.lastIndex = 0;
  while ((match = CODE_FENCE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: 'text', value: text.slice(lastIndex, match.index) });
    }
    segments.push({ kind: 'code', value: match[1].trimEnd() });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    segments.push({ kind: 'text', value: text.slice(lastIndex) });
  }

  return segments;
}
