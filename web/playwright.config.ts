import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', timeout: 45000, expect: { timeout: 15000 },
  fullyParallel: false, workers: 1, retries: 0,
  reporter: [['list']], use: { baseURL: 'http://localhost:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    { command: 'python ../scripts/e2e_services.py', url: 'http://127.0.0.1:8000/health', timeout: 90000, reuseExistingServer: false },
    { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: !process.env.CI }
  ]
});
