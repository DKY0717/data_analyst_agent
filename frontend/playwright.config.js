import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'cd ../backend && python -m uvicorn app.main:app --port 8001',
      port: 8001,
      reuseExistingServer: true,
      timeout: 30000,
    },
    {
      command: 'npm run dev',
      port: 3000,
      reuseExistingServer: true,
      timeout: 30000,
    },
  ],
})
