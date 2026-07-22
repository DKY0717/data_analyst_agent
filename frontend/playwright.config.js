import { defineConfig, devices } from '@playwright/test'

const backendPort = process.env.E2E_BACKEND_PORT || '8001'
const frontendPort = process.env.E2E_FRONTEND_PORT || '3000'
const baseURL = process.env.E2E_BASE_URL || `http://localhost:${frontendPort}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: process.env.E2E_MANAGED_SERVERS === '1' ? undefined : [
    {
      command: `python -m uvicorn app.main:app --port ${backendPort}`,
      cwd: '../backend',
      port: Number(backendPort),
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: `npm run dev -- --port ${frontendPort} --strictPort`,
      port: Number(frontendPort),
      reuseExistingServer: false,
      timeout: 30000,
      env: {
        VITE_API_PROXY_TARGET: `http://127.0.0.1:${backendPort}`,
        VITE_DEV_PORT: frontendPort,
        VITE_STRICT_PORT: 'true',
      },
    },
  ],
})
