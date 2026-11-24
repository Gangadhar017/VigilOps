import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the Vite dev server proxies /api to the backend published on
// 127.0.0.1:8000 by `docker compose up`, so the browser stays same-origin.  The
// demonstration application's storefront (/orbitcrate/) comes from the stack's
// web entry on 127.0.0.1:8080.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/orbitcrate': { target: process.env.VITE_STORE_TARGET || 'http://127.0.0.1:8080', changeOrigin: true },
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
  },
});
