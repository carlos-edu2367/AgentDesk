import { expect, test } from '@playwright/test'
import { installMockApi } from './mockApi'

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
})

test('opens execution flow and navigates to execution detail', async ({ page }) => {
  await page.goto('/#/executions/run')
  await page.locator('select').first().selectOption('agent_demo')
  await page.getByPlaceholder('What should the agent do?').fill('Say hello')
  await page.getByRole('button', { name: 'Run Agent' }).click()
  await expect(page).toHaveURL(/#\/executions\/execution_demo$/)
  await expect(page.getByText('Execution Detail')).toBeVisible()
  await expect(page.getByText('Hello from the mocked E2E runtime.')).toBeVisible()
})
