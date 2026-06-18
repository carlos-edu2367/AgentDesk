import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Providers } from '../views/Providers'

vi.mock('../api/providers', () => ({
  providersApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'p1', name: 'Local Ollama', type: 'ollama', base_url: 'http://localhost:11434', enabled: true, config: {} },
      { id: 'p2', name: 'OpenRouter', type: 'openrouter', base_url: 'https://openrouter.ai/api/v1', enabled: true, config: { api_key: 'sk-...4321' } },
    ]),
    health: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('Providers list', () => {
  it('renders provider names', async () => {
    render(<MemoryRouter><Providers /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Local Ollama')).toBeInTheDocument()
      expect(screen.getByText('OpenRouter')).toBeInTheDocument()
    })
  })

  it('shows type badges', async () => {
    render(<MemoryRouter><Providers /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('ollama')).toBeInTheDocument()
      expect(screen.getByText('openrouter')).toBeInTheDocument()
    })
  })

  it('shows Add Provider button', async () => {
    render(<MemoryRouter><Providers /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getAllByText('Add Provider')[0]).toBeInTheDocument()
    })
  })
})
