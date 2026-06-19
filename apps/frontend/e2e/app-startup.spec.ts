import { expect, test } from '@playwright/test'
import { installMockApi } from './mockApi'

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
})

test('app opens without a blank screen and dashboard shows backend health', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.getByText('Backend')).toBeVisible()
  await expect(page.getByText('ok').first()).toBeVisible()
  await expect(page.locator('body')).not.toHaveText('')
})

test('core MVP pages render from sidebar navigation', async ({ page }) => {
  await page.goto('/')
  for (const label of ['Providers', 'Agents', 'Executions', 'Audit Logs', 'Memory', 'Skills', 'Plugins', 'MCP Servers', 'Teams']) {
    await page.getByRole('link', { name: label }).click()
    await expect(page.getByRole('heading', { name: label })).toBeVisible()
  }
})
