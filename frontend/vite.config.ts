/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  build: {
    rolldownOptions: {
      output: {
        // Split heavy third-party code into separately cached chunks. The charting library is left
        // out on purpose: it must stay in the lazily loaded chart pages, not in the entry graph.
        codeSplitting: {
          groups: [
            {
              name: 'motion',
              test: /node_modules[\\/](motion|framer-motion|motion-dom|motion-utils)/,
              priority: 20,
            },
            {
              name: 'forms',
              test: /node_modules[\\/](zod|react-hook-form|@hookform)/,
              priority: 20,
            },
            {
              name: 'react',
              test: /node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler|@tanstack)/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // Playwright specs in e2e/ are run by `npm run e2e`, not by Vitest.
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
