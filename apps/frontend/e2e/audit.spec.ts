import { expect, test } from '@playwright/test'
import { installMockApi } from './mockApi'

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
})

test('audit logs page renders with mocked API', async ({ page }) => {
  await page.goto('/#/audit')
  await expect(page.getByRole('heading', { name: 'Audit Logs' })).toBeVisible()
  await expect(page.getByText(/audit/i).first()).toBeVisible()
})
