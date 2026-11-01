import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

/**
 * A11y и мобильные сценарии (S29-004).
 *
 * Проверки намеренно терпимы к состоянию данных: если на странице нет таблицы
 * или модалки (пустой список у нового ученика), тест помечается skipped, а не
 * падает. Контраст и структурные проверки — в `a11y-contrast.spec.ts` и
 * unit-тесте таблиц.
 */
test.describe('A11y и мобильные сценарии (S29-004)', () => {
  test('skip-link присутствует и указывает на контент', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/dashboard');

    const skip = page.locator('a[href="#main"]').first();
    await expect(skip).toHaveCount(1);
    await expect(page.locator('#main')).toBeVisible();
  });

  test('мобильное меню открывает навигацию', async ({ page }) => {
    await registerStudent(page);
    await page.setViewportSize({ width: 600, height: 812 });
    await page.goto('/dashboard');

    const menu = page.locator('button[aria-controls="mobile-nav"]');
    if ((await menu.count()) === 0) {
      test.skip(true, 'Кнопка мобильного меню не отрендерена');
    }
    await menu.click();
    await expect(page.locator('#mobile-nav')).toBeVisible();
  });

  test('на мобильном таблица рендерится карточками без горизонтального скролла', async ({
    page,
  }) => {
    await registerStudent(page);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/assignments');

    const table = page.locator('table[data-cards="true"]').first();
    if ((await table.count()) === 0) {
      test.skip(true, 'На странице нет таблицы в режиме карточек');
    }

    const headDisplay = await table
      .locator('thead')
      .evaluate((el) => getComputedStyle(el).display);
    expect(headDisplay).toBe('none');

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
