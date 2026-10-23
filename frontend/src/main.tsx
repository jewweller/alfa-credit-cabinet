import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import '@fontsource-variable/inter';
import '@fontsource/geist-mono/400.css';
import '@fontsource/geist-mono/500.css';
import './theme/tokens.css';
import './theme/global.css';
import { applySurface } from './theme/surface';
import { apiMode } from './mocks/mode';

applySurface();

/**
 * Моки включаются и в dev, и в образе Docker (пока бэк не закрывает весь путь: подписание
 * и кабинет банка). Режим — VITE_API_MODE (mocks / mixed / real, см. mocks/mode.ts); без него
 * действует прежний флаг VITE_USE_MOCKS: true — моки, false — все запросы идут в /api.
 */
async function enableMocks() {
  if (apiMode() !== 'real') {
    const { worker } = await import('./mocks/browser');
    // msw 3: опция называется onUnhandledFrame (в v2 была onUnhandledRequest).
    await worker.start({ onUnhandledFrame: 'bypass' });
  }
}

enableMocks().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
