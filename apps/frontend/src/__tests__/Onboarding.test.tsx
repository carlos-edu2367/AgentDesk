import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { OnboardingWizard } from '../components/onboarding/OnboardingWizard'

vi.mock('../api/onboarding', () => ({
  onboardingApi: {
    state: vi.fn().mockResolvedValue({ completed: false, has_providers: false }),
    complete: vi.fn().mockResolvedValue({}),
    createOllamaProvider: vi.fn().mockResolvedValue({ type: 'ollama' }),
    createOpenRouterProvider: vi.fn().mockResolvedValue({ type: 'openrouter' }),
  },
}))

describe('OnboardingWizard', () => {
  beforeEach(() => localStorage.clear())

  it('renders welcome and routes to OpenRouter path', async () => {
    render(<OnboardingWizard onFinished={() => {}} />)
    await screen.findByText('Bem-vindo ao AgentDesk')
    await userEvent.click(screen.getByText('Usar OpenRouter'))
    expect(await screen.findByPlaceholderText('sk-or-...')).toBeInTheDocument()
  })

  it('skip sets localStorage flag and finishes', async () => {
    const onFinished = vi.fn()
    render(<OnboardingWizard onFinished={onFinished} />)
    await screen.findByText('Bem-vindo ao AgentDesk')
    await userEvent.click(screen.getByText('Pular por enquanto'))
    await waitFor(() => expect(localStorage.getItem('agentdesk.onboardingSkipped')).toBe('1'))
    expect(onFinished).toHaveBeenCalled()
  })
})
