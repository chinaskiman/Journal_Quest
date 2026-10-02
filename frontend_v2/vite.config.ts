import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The v2 frontend dev server.  All /api traffic is proxied to the LOCAL v2
// backend (127.0.0.1:8001) started by start_backend_v2_dev.bat /
// start_tradequest_v2.bat.  Port 5174 keeps it separate from the Phase 1
// frontend dev server on 5173.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
