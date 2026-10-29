// Копирует локальные ассеты Monaco в public/ (S19-001, KI-013).
import { cpSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const source = join(root, '..', 'node_modules', 'monaco-editor', 'min', 'vs');
const target = join(root, '..', 'public', 'monaco', 'vs');

rmSync(target, { recursive: true, force: true });
mkdirSync(target, { recursive: true });
cpSync(source, target, { recursive: true });
console.log(`Monaco assets copied to ${target}`);
