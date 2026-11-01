import {
  Children,
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useMemo,
  useState,
  type HTMLAttributes,
  type ReactElement,
  type ReactNode,
  type ThHTMLAttributes,
  type TdHTMLAttributes,
} from 'react';

interface TableProps {
  children: ReactNode;
  caption?: string;
  className?: string;
  /** На мобильных (<sm) строки превращаются в карточки (S29-001) */
  responsive?: boolean;
}

interface TableContextValue {
  headers: string[];
  registerHeader: (label: string) => void;
}

const TableContext = createContext<TableContextValue | null>(null);

/**
 * Таблица с адаптивным режимом (S29-001).
 *
 * На экранах уже 640px заголовки скрываются, а каждая строка (`Tr`) становится
 * карточкой: подписи колонок приходят из `data-label`, который проставляет
 * `Tr` на основе зарегистрированных `Th`. Горизонтальный скролл не нужен.
 */
export function Table({
  children,
  caption,
  className = '',
  responsive = true,
}: TableProps) {
  const [headers, setHeaders] = useState<string[]>([]);

  const value = useMemo<TableContextValue>(
    () => ({
      headers,
      registerHeader: (label: string) =>
        setHeaders((current) => (current.includes(label) ? current : [...current, label])),
    }),
    [headers],
  );

  return (
    <TableContext.Provider value={value}>
      <div className="w-full overflow-x-auto">
        <table
          data-cards={responsive ? 'true' : undefined}
          className={`w-full text-left text-sm ${className}`}
        >
          {caption && (
            <caption className="pb-2 text-left text-xs text-slate-500">{caption}</caption>
          )}
          {children}
        </table>
      </div>
    </TableContext.Provider>
  );
}

export function Th({ children, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  const context = useContext(TableContext);
  const label = typeof children === 'string' ? children : '';

  // Регистрируем заголовок после монтирования; повторный вызов не меняет список
  useEffect(() => {
    if (context && label) context.registerHeader(label);
  }, [context, label]);

  return (
    <th
      scope="col"
      className="whitespace-nowrap px-2 py-2 text-xs font-medium uppercase text-slate-500"
      {...props}
    >
      {children}
    </th>
  );
}

export function Tr({ children, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  const context = useContext(TableContext);
  const headers = context?.headers ?? [];
  const labelled = Children.map(children, (child, index) => {
    if (!isValidElement(child)) return child;
    const label = headers[index];
    if (!label) return child;
    return cloneElement(child as ReactElement<{ 'data-label'?: string }>, {
      'data-label': label,
    });
  });

  return <tr {...props}>{labelled}</tr>;
}

export function Td({ children, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className="px-2 py-2 text-slate-600" {...props}>
      {children}
    </td>
  );
}
