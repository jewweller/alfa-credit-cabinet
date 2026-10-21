import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Когда VITE_USE_MOCKS=false, запросы /api уходят в настоящий бэкенд.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
