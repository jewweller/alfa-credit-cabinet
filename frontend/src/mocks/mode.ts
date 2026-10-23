// Откуда фронт берёт данные:
//   mocks — всё отвечает MSW (по умолчанию в `npm run dev`);
//   mixed — реализованные на бэке операции идут в настоящий API, остальные — в MSW;
//   real  — всё идёт в настоящий API, MSW не запускается.
// Файл без импорта msw: его подключает main.tsx, а msw не должен попадать в сборку.

export type ApiMode = 'mocks' | 'mixed' | 'real';

export function apiMode(): ApiMode {
  const mode = import.meta.env.VITE_API_MODE;
  if (mode === 'mocks' || mode === 'mixed' || mode === 'real') return mode;
  // Совместимость: раньше режим задавался только VITE_USE_MOCKS.
  return import.meta.env.VITE_USE_MOCKS === 'true' ? 'mocks' : 'real';
}
