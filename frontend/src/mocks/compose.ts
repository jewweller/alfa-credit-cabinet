import { http, passthrough } from 'msw';
import { handlers } from './handlers';
import type { ApiMode } from './mode';
// Операции, которые уже реализованы на бэке. Бэкенд-тест сверяет список с контрактом
// (x-implementation-status: implemented в docs/api/openapi.json).
import realOperations from './real-operations.json';

const METHODS = { GET: http.get, POST: http.post, PATCH: http.patch, PUT: http.put, DELETE: http.delete };

/** Пропускают реализованные операции мимо моков, в настоящий API. */
function realApiPassthrough() {
  return realOperations.map(([method, path]) =>
    // Контракт пишет параметры как {id}, MSW — как :id.
    METHODS[method as keyof typeof METHODS](path.replace(/\{(\w+)\}/g, ':$1'), () => passthrough()),
  );
}

/** MSW берёт первый подходящий обработчик: в смешанном режиме пропуск в API стоит раньше моков. */
export function handlersFor(mode: ApiMode) {
  return mode === 'mixed' ? [...realApiPassthrough(), ...handlers] : handlers;
}
