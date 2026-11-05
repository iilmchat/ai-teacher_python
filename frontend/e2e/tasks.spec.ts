import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

test.describe('Задачи', () => {
  test('список задач содержит стартовый набор', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    await expect(page.getByText('Сумма двух чисел')).toBeVisible({ timeout: 20_000 });
    await expect(page.getByRole('progressbar', { name: 'Прогресс' })).toBeVisible();
  });

  test('верное решение засчитывается', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    const card = page.getByRole('listitem').filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();

    await expect(page).toHaveURL(/\/tasks\/[0-9a-f-]+/);
    await page
      .getByTestId('code-input')
      .fill('a = int(input())\nb = int(input())\nprint(a + b)');
    await page.getByRole('button', { name: 'Отправить решение' }).click();

    await expect(page.getByText(/Все тесты пройдены/)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/Пройдено тестов: 3 из 3/)).toBeVisible();
  });

  test('подсказка открывается по одной', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    const card = page.getByRole('listitem').filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();

    await page.getByRole('button', { name: 'Показать подсказку' }).click();
    // Первая подсказка из seed для задачи «Сумма двух чисел»
    await expect(page.getByText(/input\(\) возвращает строку/)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Показать подсказку' })).toBeVisible();
  });

  test('история попыток сохраняется и показывает разбор', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    const card = page.getByRole('listitem').filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();

    await page
      .getByTestId('code-input')
      .fill('a = int(input())\nb = int(input())\nprint(a + b)');
    await page.getByRole('button', { name: 'Отправить решение' }).click();

    await expect(page.getByText(/Все тесты пройдены/)).toBeVisible({ timeout: 60_000 });

    // История попыток: запись о засчитанной отправке
    await expect(page.getByText('История попыток')).toBeVisible();
    await expect(page.getByText(/Решено:/)).toBeVisible();

    // Детали попытки: код и разбор по кейсам
    await page.getByRole('button', { name: 'Подробнее' }).click();
    await expect(page.getByText('print(a + b)')).toBeVisible();
  });

  test('пробная проверка не тратит попытку', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    const card = page.getByRole('listitem').filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();

    await page
      .getByTestId('code-input')
      .fill('a = int(input())\nb = int(input())\nprint(a + b)');
    await page.getByRole('button', { name: 'Пробная проверка' }).click();

    await expect(page.getByText(/Результат пробной проверки/)).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText(/Все тесты пройдены/)).toBeVisible();
    // Попытка не засчитана: счётчик остался нулевым, статус — «не начата»
    await expect(page.getByText(/Попыток: 0/)).toBeVisible();
    await expect(page.getByText(/не начата/)).toBeVisible();
  });
});
