import { expect, test } from '@playwright/test'

const email = process.env.DEMO_USER_EMAIL
const password = process.env.DEMO_USER_PASSWORD

test('seeded demo login, transcript, SOAP note, and sync flow', async ({ page }) => {
  test.skip(!email || !password, 'DEMO_USER_EMAIL and DEMO_USER_PASSWORD are required')

  await page.goto('/login')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password').fill(password!)
  await page.getByRole('button', { name: 'sign in' }).click()

  await expect(page.getByText('Synthetic demo data · external services disabled')).toBeVisible()
  await page.getByText('SYNTHETIC-DEMO-001').first().click()

  await expect(page.getByRole('button', { name: 'Start Live Recording' })).toBeVisible()
  await expect(page.getByText('Disconnected', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'continue to summarize →', exact: true })).toBeHidden()
  await page.getByRole('button', { name: 'Start Live Recording' }).click()
  await expect(page.getByText('Recording', { exact: true })).toBeVisible()
  await expect(page.getByText('Provider', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Patient', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Recording complete. Transcript saved.')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('button', { name: 'continue to summarize →', exact: true }).click()
  await expect(page.getByText('subjective', { exact: true })).toBeVisible()
  await expect(page.getByText('objective', { exact: true })).toBeVisible()
  await expect(page.getByText('assessment', { exact: true })).toBeVisible()
  await expect(page.getByText('plan', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'sync', exact: true }).first().click()
  await expect(page.getByRole('button', { name: 'sync again', exact: true }).first()).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: '2 summarize', exact: true }).click()
  await expect(page.getByRole('button', { name: 'sync again', exact: true }).first()).toBeVisible()
})
