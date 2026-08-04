import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: process.env.DEMO_BASE_URL || 'http://localhost:3001',
    trace: 'retain-on-failure',
  },
})
