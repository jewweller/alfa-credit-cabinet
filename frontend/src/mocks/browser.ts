import { setupWorker } from 'msw/browser';
import { handlersFor } from './compose';
import { apiMode } from './mode';

export const worker = setupWorker(...handlersFor(apiMode()));
