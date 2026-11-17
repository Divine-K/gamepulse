import { defineConfig } from '@playwright/test'

const API = 'http://localhost:8100'
const WEB = 'http://localhost:5174'

/**
 * End-to-end tests run against an isolated stack: a dedicated API + database on port 8100 and the
 * production build of the dashboard on port 5174. Uses the installed Google Chrome, so no browser
 * download is needed.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: [['list']],
  use: {
    baseURL: WEB,
    channel: 'chrome',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      testIgnore: /responsive/,
      use: { viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile',
      testMatch: /responsive/,
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
  webServer: [
    {
      command: '.venv/bin/python scripts/run_e2e_api.py',
      cwd: '../backend',
      url: `${API}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run build && npm run preview -- --port 5174 --strictPort --host localhost',
      env: { VITE_API_BASE_URL: API },
      url: WEB,
      reuseExistingServer: false,
      timeout: 90_000,
    },
  ],
})
