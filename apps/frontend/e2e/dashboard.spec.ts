import { expect, test } from '@playwright/test'
import { installMockApi } from './mockApi'

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
})

test('creates a mocked Ollama provider from the UI', async ({ page }) => {
  await page.goto('/#/providers/new')
  await page.getByPlaceholder('Local Ollama').fill('E2E Ollama')
  await page.getByRole('button', { name: 'Add Provider' }).click()
  await expect(page).toHaveURL(/#\/providers$/)
  await expect(page.getByRole('heading', { name: 'Providers' })).toBeVisible()
})

test('creates a simple mocked agent from the UI', async ({ page }) => {
  await page.goto('/#/agents/new')
  await page.getByPlaceholder('e.g. Research Assistant').fill('E2E Agent')
  await page.getByPlaceholder('You are a helpful assistant...').fill('Answer with short, local-only responses.')
  await page.getByLabel('Provider *').selectOption('provider_ollama')
  await page.locator('#agent-model').selectOption('llama3.1')
  await page.getByRole('button', { name: 'Create Agent' }).click()
  await expect(page).toHaveURL(/#\/agents$/)
  await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible()
})
