#!/usr/bin/env node
/**
 * Аудит локализации (S29-002).
 *
 * 1. В `src/**` (кроме локалей и тестов) не должно быть кириллицы в строковых
 *    литералах — все тексты живут в `src/i18n/locales/*.json`.
 * 2. Наборы ключей `ru.json` и `en.json` должны совпадать.
 *
 * Запуск: `node scripts/check-i18n.mjs` (в CI — до тестов).
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const SRC = 'src';
const SKIP_DIRS = new Set(['i18n/locales', 'test', '__tests__']);
// Примеры кода в песочнице — учебный контент, а не UI-текст
const ALLOWLIST = new Set(['pages/CodePage.tsx']);
const CYRILLIC = /[А-Яа-яЁё]/;
const LITERAL = /(['"`])((?:\\.|(?!\1).)*)\1/g;

function walk(dir) {
  const entries = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const rel = relative(SRC, full).replaceAll('\\', '/');
    if (SKIP_DIRS.has(rel) || ALLOWLIST.has(rel)) continue;
    const stat = statSync(full);
    if (stat.isDirectory()) entries.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(name)) entries.push(full);
  }
  return entries;
}

const problems = [];
for (const file of walk(SRC)) {
  const text = readFileSync(file, 'utf8');
  const lines = text.split('\n');
  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('*') || trimmed.startsWith('/*')) return;
    for (const match of line.matchAll(LITERAL)) {
      if (CYRILLIC.test(match[2])) {
        problems.push(`${relative(SRC, file)}:${index + 1}: ${trimmed}`);
        break;
      }
    }
  });
}

const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([key, value]) =>
    value && typeof value === 'object'
      ? flatten(value, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  );

const ru = JSON.parse(readFileSync(`${SRC}/i18n/locales/ru.json`, 'utf8'));
const en = JSON.parse(readFileSync(`${SRC}/i18n/locales/en.json`, 'utf8'));
const ruKeys = new Set(flatten(ru));
const enKeys = new Set(flatten(en));
const missingInEn = [...ruKeys].filter((key) => !enKeys.has(key));
const missingInRu = [...enKeys].filter((key) => !ruKeys.has(key));

if (problems.length) {
  console.error('Найдена кириллица вне i18n (перенесите текст в locales):');
  for (const problem of problems) console.error(`  ${problem}`);
}
if (missingInEn.length) console.error(`Нет в en.json: ${missingInEn.join(', ')}`);
if (missingInRu.length) console.error(`Нет в ru.json: ${missingInRu.join(', ')}`);

if (problems.length || missingInEn.length || missingInRu.length) {
  process.exit(1);
}
console.log(`i18n OK: ${ruKeys.size} ключей в ru/en, кириллицы вне локалей нет`);
