import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Agents } from '../views/Agents'

vi.mock('../api/agents', () => ({
  agentsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'agent_001',
        name: 'Test Agent',
        description: 'A test agent',
        system_prompt: 'You are helpful.',
        model_config: { provider_id: 'p1', model: 'llama3', temperature: 0.4, top_p: 0.9, context_window: 8192, max_tokens: 2048, stream: true },
        capabilities: [],
        explicit_tools: [],
        blocked_tools: [],
        skills: [],
        plugins: [],
        mcp_servers: [],
        memory_config: { use_global: true, use_agent_memory: true, use_team_memory: false },
        created_at: '2024-01-01T00:00:00',
        updated_at: '2024-01-01T00:00:00',
      },
    ]),
    delete: vi.fn(),
  },
}))

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('Agents list', () => {
  it('renders agent name', async () => {
    render(<MemoryRouter><Agents /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Test Agent')).toBeInTheDocument()
    })
  })

  it('renders agent description', async () => {
    render(<MemoryRouter><Agents /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('A test agent')).toBeInTheDocument()
    })
  })

  it('shows New Agent button', async () => {
    render(<MemoryRouter><Agents /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('New Agent')).toBeInTheDocument()
    })
  })
})
