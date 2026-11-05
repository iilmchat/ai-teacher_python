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

  test('рекомендуется следующая задача с пояснением', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/dashboard');

    await expect(page.getByText('Рекомендуем дальше')).toBeVisible({
      timeout: 20_000,
    });
    // У нового ученика есть рекомендация с пояснением
    await expect(page.getByText(/С чего начать/).first()).toBeVisible({
      timeout: 20_000,
    });
  });

  test('поиск и фильтры каталога работают', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    // Счётчик найденного
    await expect(page.getByText(/Найдено задач:/)).toBeVisible({
      timeout: 20_000,
    });

    // Поиск по названию
    await page.getByLabel('Поиск по задачам').fill('Сумма');
    await expect(page.getByText('Сумма двух чисел')).toBeVisible({
      timeout: 20_000,
    });

    // Пустое состояние с подсказкой
    await page.getByLabel('Поиск по задачам').fill('несуществующая задача');
    await expect(
      page.getByText(/По вашему фильтру ничего не найдено/),
    ).toBeVisible({ timeout: 20_000 });

    // Сброс фильтров возвращает каталог
    await page.getByRole('button', { name: 'Сбросить фильтры' }).click();
    await expect(page.getByText('Сумма двух чисел')).toBeVisible({
      timeout: 20_000,
    });

    // Фильтры отражаются в URL — ссылкой можно поделиться
    await page.getByLabel('Поиск по задачам').fill('Сумма');
    await expect(page).toHaveURL(/q=/, { timeout: 20_000 });
  });

  test('черновик сохраняется и восстанавливается', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    const card = page.getByRole('listitem').filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();

    await page.getByTestId('code-input').fill('print("черновик")');

    // Индикатор автосохранения
    await expect(page.getByText(/Черновик сохранён в/)).toBeVisible({
      timeout: 20_000,
    });

    // После перезагрузки страницы черновик на месте
    await page.reload();
    await expect(page.getByTestId('code-input')).toHaveValue(
      'print("черновик")',
      { timeout: 20_000 },
    );
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
