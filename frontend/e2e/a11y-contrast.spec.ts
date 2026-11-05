import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

import { expect, test, type Page } from '@playwright/test';

import { registerStudent } from './helpers';

const require = createRequire(import.meta.url);
const AXE_SOURCE = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

interface AxeNode {
  html: string;
  target: string[];
}

interface AxeViolation {
  id: string;
  impact: string | null;
  nodes: AxeNode[];
}

async function runContrast(page: Page): Promise<AxeViolation[]> {
  await page.addScriptTag({ content: AXE_SOURCE });
  const result = await page.evaluate(async () => {
    // @ts-expect-error axe подключается скриптом во время теста
    return await window.axe.run(document, {
      runOnly: { type: 'rule', values: ['color-contrast'] },
    });
  });
  return result.violations as AxeViolation[];
}

async function setTheme(page: Page, theme: 'light' | 'dark') {
  await page.addInitScript((value) => {
    window.localStorage.setItem('ai-teacher.theme', value);
  }, theme);
  await page.emulateMedia({ colorScheme: theme });
}

test.describe('Контраст (S29-003)', () => {
  for (const theme of ['light', 'dark'] as const) {
    test(`0 нарушений color-contrast, тема ${theme}`, async ({ page }) => {
      await setTheme(page, theme);
      await registerStudent(page);

      for (const path of ['/dashboard', '/chat', '/tasks', '/assignments']) {
        await page.goto(path);
        await expect(page.locator('body')).toBeVisible();

        const violations = await runContrast(page);
        const summary = violations
          .flatMap((item) => item.nodes.map((node) => `${item.id}: ${node.target.join(' ')}`))
          .join('\n');
        expect(violations, `${path} (${theme}): ${summary}`).toHaveLength(0);
      }
    });
  }
});
