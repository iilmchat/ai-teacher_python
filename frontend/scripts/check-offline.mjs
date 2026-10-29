// Проверка офлайн-сборки (S19-001, KI-013): в dist не должно быть CDN-ссылок.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIST = new URL('../dist/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const FORBIDDEN = ['cdn.jsdelivr.net', 'unpkg.com', 'cdnjs.cloudflare.com'];

function walk(dir) {
  const files = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      files.push(...walk(path));
    } else if (/\.(js|css|html)$/.test(name)) {
      files.push(path);
    }
  }
  return files;
}

let failed = false;
// Сканируем только бандл приложения и index.html: скопированные ассеты Monaco
// лежат локально в dist/monaco и не являются сетевыми зависимостями.
const files = [join(DIST, 'index.html'), ...walk(join(DIST, 'assets'))];
for (const file of files) {
  const content = readFileSync(file, 'utf8');
  for (const host of FORBIDDEN) {
    if (content.includes(host)) {
      console.error(`CDN reference "${host}" found in ${file}`);
      failed = true;
    }
  }
}

if (failed) {
  process.exit(1);
}
console.log('Offline check passed: no CDN references in dist');
