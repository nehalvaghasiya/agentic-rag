import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': { target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:8001', changeOrigin: true }, '/metrics': 'http://127.0.0.1:8001' } },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    include: ['src/test/**/*.test.{js,jsx,ts,tsx}'],
    clearMocks: true,
    restoreMocks: true,
  },
})
