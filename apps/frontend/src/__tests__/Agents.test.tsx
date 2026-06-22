import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Agents } from '../views/Agents'
import { conversationsApi } from '../api/conversations'

const navigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

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

vi.mock('../api/conversations', () => ({
  conversationsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({
      id: 'conv_new',
      type: 'agent',
      target_id: 'agent_001',
      title: 'Test Agent',
      created_at: '',
      updated_at: '',
    }),
  },
}))

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('Agents list', () => {
  beforeEach(() => {
    navigate.mockReset()
    vi.mocked(conversationsApi.list).mockResolvedValue([])
    vi.mocked(conversationsApi.create).mockResolvedValue({
      id: 'conv_new',
      type: 'agent',
      target_id: 'agent_001',
      title: 'Test Agent',
      workspace_ids: [],
      created_at: '',
      updated_at: '',
    })
  })

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

  it('continues the latest existing agent chat', async () => {
    vi.mocked(conversationsApi.list).mockResolvedValueOnce([
      {
        id: 'conv_existing',
        type: 'agent',
        target_id: 'agent_001',
        title: 'Previous chat',
        workspace_ids: [],
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-21T00:00:00Z',
      },
    ])

    render(<MemoryRouter><Agents /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('Test Agent')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Chat' }))

    await waitFor(() => {
      expect(conversationsApi.list).toHaveBeenCalledWith({ type: 'agent', target_id: 'agent_001' })
      expect(conversationsApi.create).not.toHaveBeenCalled()
      expect(navigate).toHaveBeenCalledWith('/conversations/conv_existing')
    })
  })
})
