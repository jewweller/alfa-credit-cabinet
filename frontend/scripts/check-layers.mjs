// Слои фронта (план, раздел 9): страницы и features собираются только из компонентов ui/ —
// без своих стилей. Проверка запускается перед сборкой и падает с понятным списком нарушений.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const LAYERS = ['src/pages', 'src/features'];
const RULES = [
  [/import\s+[^;]*\.css['"]/, 'импорт CSS — стили только в ui/ и theme/'],
  [/\bclassName=/, 'className — вёрстка только в компонентах ui/'],
  [/\bstyle=\{/, 'инлайн-стиль — значения только из токенов в ui/'],
];

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.(tsx?|css)$/.test(name) ? [path] : [];
  });
}

const problems = [];
for (const layer of LAYERS) {
  for (const file of files(join(ROOT, layer))) {
    const rel = relative(ROOT, file);
    if (file.endsWith('.css')) {
      problems.push(`${rel}: CSS-файл в слое ${layer}`);
      continue;
    }
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, i) => {
        for (const [re, why] of RULES) if (re.test(line)) problems.push(`${rel}:${i + 1}: ${why}`);
      });
  }
}

if (problems.length > 0) {
  console.error(`Нарушены слои фронта (план, раздел 9):\n${problems.join('\n')}`);
  process.exit(1);
}
