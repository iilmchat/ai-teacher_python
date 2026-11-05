import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

test.describe('Чат', () => {
  test('создаёт сессию и получает ответ ассистента', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/chat');

    await page.getByRole('button', { name: 'Новый чат' }).click();
    const input = page.getByLabel('Сообщение');
    await expect(input).toBeVisible({ timeout: 20_000 });

    await input.fill('Как работает цикл for?');
    await page.getByRole('button', { name: 'Отправить' }).click();

    // Провайдер echo отвечает на базовом уровне наводящим вопросом
    await expect(page.getByText(/Давай разберёмся вместе/)).toBeVisible({
      timeout: 30_000,
    });
    // Вопрос ученика есть в переписке (в ответе echo он тоже цитируется)
    await expect(
      page.getByText('Как работает цикл for?', { exact: true }),
    ).toBeVisible();
  });


  test('ищет по истории чата и открывает сессию', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/chat');

    // Создаём сессию и отправляем сообщение, чтобы было что искать
    await page.getByRole('button', { name: 'Новый чат' }).click();
    const input = page.getByLabel('Сообщение');
    await expect(input).toBeVisible({ timeout: 20_000 });
    await input.fill('Как работает цикл for?');
    await page.getByRole('button', { name: 'Отправить' }).click();
    await expect(page.getByText(/Давай разберёмся вместе/)).toBeVisible({
      timeout: 30_000,
    });

    // Поиск по истории: ILIKE-режим (RAG выключен в e2e)
    const search = page.getByLabel('Поисковый запрос');
    await search.fill('цикл for');
    await page.getByRole('button', { name: 'Найти' }).click();

    await expect(page.getByText(/Найдено: \d+/)).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('mark').first()).toBeVisible();

    // Переход к найденной сессии
    await page.locator('section[aria-label="Поиск по чату"] li button').first().click();
    await expect(page.getByLabel('Сообщение')).toBeVisible();
  });

  test('«Спросить ассистента» переносит контекст задачи в чат', async ({
    page,
  }) => {
    await registerStudent(page);
    await page.goto('/tasks');

    const card = page.getByRole('listitem').filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();

    await page
      .getByRole('link', { name: 'Спросить ассистента' })
      .first()
      .click();

    // Deep-link: контекст задачи виден в адресе и в плашке чата
    await expect(page).toHaveURL(/\/chat\?task=/);
    await expect(page.getByText(/Контекст задачи/)).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText('Сумма двух чисел')).toBeVisible();

    await page.getByRole('button', { name: 'Новый чат' }).click();
    const input = page.getByLabel('Сообщение');
    await expect(input).toBeVisible({ timeout: 20_000 });
    await input.fill('С чего начать?');
    await page.getByRole('button', { name: 'Отправить' }).click();
    await expect(page.getByText(/Давай разберёмся вместе/)).toBeVisible({
      timeout: 30_000,
    });

    // Контекст можно снять — плашка исчезает
    await page.getByRole('button', { name: 'Убрать' }).click();
    await expect(page.getByText(/Контекст задачи/)).not.toBeVisible();
  });

  test('уровень выбирается при создании сессии', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/chat');

    await page.getByRole('button', { name: 'Продвинутый' }).click();
    await page.getByRole('button', { name: 'Новый чат' }).click();

    const input = page.getByLabel('Сообщение');
    await expect(input).toBeVisible({ timeout: 20_000 });
    await input.fill('Покажи решение');
    await page.getByRole('button', { name: 'Отправить' }).click();

    // На продвинутом уровне echo отдаёт разбор с блоком кода
    await expect(page.getByText(/Разбор вопроса/)).toBeVisible({ timeout: 30_000 });
  });
});
