import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Table, Td, Th, Tr } from '@/components/ui/Table';

function DemoTable() {
  return (
    <Table caption="Ученики">
      <thead>
        <Tr>
          <Th>Имя</Th>
          <Th>Баллы</Th>
        </Tr>
      </thead>
      <tbody>
        <Tr>
          <Td>Аня</Td>
          <Td>5</Td>
        </Tr>
      </tbody>
    </Table>
  );
}

describe('Table cards (S29-001)', () => {
  it('помечает таблицу как адаптивную', () => {
    render(<DemoTable />);

    expect(document.querySelector('table')).toHaveAttribute('data-cards', 'true');
  });

  it('подставляет подписи колонок в ячейки для карточек', () => {
    render(<DemoTable />);

    const cells = screen.getAllByRole('cell');
    expect(cells[0]).toHaveAttribute('data-label', 'Имя');
    expect(cells[1]).toHaveAttribute('data-label', 'Баллы');
  });

  it('responsive=false отключает карточки', () => {
    render(
      <Table responsive={false}>
        <tbody>
          <Tr>
            <Td>x</Td>
          </Tr>
        </tbody>
      </Table>,
    );

    expect(document.querySelector('table')).not.toHaveAttribute('data-cards');
  });
});
