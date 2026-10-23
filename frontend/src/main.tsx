import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import '@fontsource-variable/inter';
import '@fontsource/geist-mono/400.css';
import '@fontsource/geist-mono/500.css';
import './theme/tokens.css';
import './theme/global.css';
import { applySurface } from './theme/surface';

applySurface();

async function enableMocks() {
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === 'true') {
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
