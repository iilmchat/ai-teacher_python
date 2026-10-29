import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react';

interface TableProps {
  children: ReactNode;
  caption?: string;
  className?: string;
}

export function Table({ children, caption, className = '' }: TableProps) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={`w-full text-left text-sm ${className}`}>
        {caption && <caption className="pb-2 text-left text-xs text-slate-500">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}

export function Th({ children, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
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

export function Td({ children, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className="px-2 py-2 text-slate-600" {...props}>
      {children}
    </td>
  );
}
