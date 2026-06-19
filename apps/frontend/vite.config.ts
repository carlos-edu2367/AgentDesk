import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // base './' ensures assets load correctly via file:// in Electron
  base: './',
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test-setup.ts',
    exclude: ['node_modules/**', 'dist/**', 'e2e/**'],
  },
  server: {
    port: 5173,
  },
})
