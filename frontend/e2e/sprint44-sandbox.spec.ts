import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

test.describe('Спринт 44: песочница', () => {
  test('код → stdin → вывод → история → запустить снова', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/code');

    const editor = page.getByTestId('code-input');
    await editor.fill('name = input()\nprint(f"Привет, {name}!")');
    await page.getByLabel('Ввод (stdin)').fill('Аня');
    await page.getByRole('button', { name: 'Запустить' }).click();

    await expect(page.getByLabel('Результат')).toContainText('Привет, Аня!', {
      timeout: 30_000,
    });

    // Новый запуск сразу виден в истории с длительностью (S44-002).
    const record = page.locator('[data-testid="code-history-item"]').first();
    await expect(record).toBeVisible();
    await record.locator('summary').click();
    await expect(record).toContainText('Успех');
    await expect(record).toContainText('name = input()');
    await expect(record).toContainText('Привет, Аня!');

    // «Запустить снова» возвращает код в редактор и не запускает его (S44-002).
    await record.getByRole('button', { name: 'Запустить снова' }).click();

    const value = await editor.inputValue();
    expect(value).toBe('name = input()\nprint(f"Привет, {name}!")');

    // Прошлый результат очищен, но код и сохранённое состояние на месте.
    await expect(page.getByText('Пока пусто')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Очистить сохранённое' })).toBeVisible();
  });

  test('восстанавливает код после перезагрузки и очищает сохранённое', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/code');

    const editor = page.getByTestId('code-input');
    await editor.fill('x = 44\nprint(x)');

    // Первая правка сохраняет локальную копию и открывает кнопку (S44-004).
    const clear = page.getByRole('button', { name: 'Очистить сохранённое' });
    await expect(clear).toBeVisible();

    await page.reload();
    await expect(editor).toHaveValue('x = 44\nprint(x)');
    await expect(clear).toBeVisible();

    // Очистка убирает только сохранённое состояние, код в редакторе не трогает.
    await clear.click();
    await expect(clear).toBeHidden();
    await expect(editor).toHaveValue('x = 44\nprint(x)');

    // После перезагрузки сохранённый код уже не восстанавливается.
    await page.reload();
    await expect(editor).toHaveValue(/Напишите код/);
    await expect(clear).toBeHidden();
  });

  test('загруженный .py не сохраняется до первой правки', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/code');

    const editor = page.getByTestId('code-input');

    const uploaded = 'print("из файла")\n';
    await page
      .getByTestId('code-file-input')
      .setInputFiles({ name: 'code.py', mimeType: 'text/x-python', buffer: Buffer.from(uploaded) });

    await expect(editor).toHaveValue(uploaded);

    // Загрузка не попадает в локальное состояние: кнопка очистки не появляется.
    const clear = page.getByRole('button', { name: 'Очистить сохранённое' });
    await expect(clear).toBeHidden();

    await page.reload();
    await expect(editor).toHaveValue(/Напишите код/);

    // После первой правки код уже сохраняется.
    await editor.fill(uploaded);
    await expect(clear).toBeVisible();

    await page.reload();
    await expect(editor).toHaveValue(uploaded);
  });
});
