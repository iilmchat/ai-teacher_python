import { CodeBlock } from '@/components/chat/CodeBlock';
import { splitCodeFences } from '@/lib/markdown';

interface RichTextProps {
  text: string;
  /** Отправить блок кода в песочницу (S43-005) */
  onSendToSandbox?: (code: string) => void;
}

export function RichText({ text, onSendToSandbox }: RichTextProps) {
  const segments = splitCodeFences(text);

  return (
    <div className="flex flex-col gap-1">
      {segments.map((segment, index) =>
        segment.kind === 'code' ? (
          <CodeBlock
            key={`code-${index}`}
            code={segment.value}
            onSendToSandbox={onSendToSandbox}
          />
        ) : (
          <p key={`text-${index}`} className="whitespace-pre-wrap break-words">
            {segment.value}
          </p>
        ),
      )}
    </div>
  );
}
