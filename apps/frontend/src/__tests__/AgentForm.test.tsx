import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AgentForm } from '../views/AgentForm'

vi.mock('../api/agents', () => ({
  agentsApi: {
    create: vi.fn().mockResolvedValue({ id: 'agent_new', name: 'New Agent' }),
    get: vi.fn(),
    update: vi.fn(),
  },
}))

vi.mock('../api/providers', () => ({
  providersApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'p1', name: 'Ollama', type: 'ollama', base_url: 'http://localhost:11434', enabled: true, config: {} },
    ]),
    models: vi.fn().mockResolvedValue([{ id: 'llama3', name: 'LLaMA 3' }]),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({}) }
})

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('AgentForm (create)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the form title', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('New Agent')).toBeInTheDocument()
    })
  })

  it('renders name input', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g. Research Assistant')).toBeInTheDocument()
    })
  })

  it('renders system prompt textarea', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('You are a helpful assistant...')).toBeInTheDocument()
    })
  })

  it('shows provider selector after loading', async () => {
    render(<MemoryRouter><AgentForm /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Ollama (ollama)')).toBeInTheDocument()
    })
  })
})
