import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Teams } from '../views/Teams'
import { teamsApi } from '../api/teams'
import { executionsApi } from '../api/executions'
import { conversationsApi } from '../api/conversations'

const navigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('../api/teams', () => ({
  teamsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'team_001',
        name: 'Research Team',
        description: 'Research and writing',
        leader_agent_id: 'agent_leader',
        member_agent_ids: ['agent_member'],
        execution_strategy: 'leader_managed',
        memory_config: { use_global: true, use_team_memory: true, allow_member_memories: true },
        tools_policy: { inherit_from_agents: true, additional_capabilities: [], blocked_tools: [] },
        created_at: '2024-01-01T00:00:00',
        updated_at: '2024-01-01T00:00:00',
      },
    ]),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('../api/conversations', () => ({
  conversationsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({
      id: 'conv_new_team',
      type: 'team',
      target_id: 'team_001',
      title: 'Research Team',
      created_at: '',
      updated_at: '',
    }),
  },
}))

vi.mock('../api/agents', () => ({
  agentsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'agent_leader',
        name: 'Leader',
        description: 'Coordinates work',
        system_prompt: '',
        model_config: { provider_id: 'p1', model: 'llama3', temperature: 0.4, top_p: 0.9, context_window: 8192, max_tokens: 2048, stream: true },
        capabilities: ['agent_control'],
        explicit_tools: [],
        blocked_tools: [],
        skills: [],
        plugins: [],
        mcp_servers: [],
        memory_config: { use_global: true, use_agent_memory: true, use_team_memory: true },
        created_at: '2024-01-01T00:00:00',
        updated_at: '2024-01-01T00:00:00',
      },
      {
        id: 'agent_member',
        name: 'Member',
        description: 'Does work',
        system_prompt: '',
        model_config: { provider_id: 'p1', model: 'llama3', temperature: 0.4, top_p: 0.9, context_window: 8192, max_tokens: 2048, stream: true },
        capabilities: [],
        explicit_tools: [],
        blocked_tools: [],
        skills: [],
        plugins: [],
        mcp_servers: [],
        memory_config: { use_global: true, use_agent_memory: true, use_team_memory: true },
        created_at: '2024-01-01T00:00:00',
        updated_at: '2024-01-01T00:00:00',
      },
    ]),
  },
}))

vi.mock('../api/skills', () => ({
  skillsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'skill_team_planner', name: 'Team Planner', version: '0.1.0', description: 'Plans team work', tags: ['team'], prompt: 'Plan clearly.', examples: [] },
    ]),
  },
}))

vi.mock('../api/workspaces', () => ({
  workspacesApi: {
    list: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../api/executions', () => ({
  executionsApi: {
    runTeam: vi.fn().mockResolvedValue({ execution_id: 'exec_team_001', status: 'running' }),
  },
}))

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('Teams page', () => {
  beforeEach(() => {
    navigate.mockReset()
    vi.mocked(conversationsApi.list).mockResolvedValue([])
    vi.mocked(conversationsApi.create).mockResolvedValue({
      id: 'conv_new_team',
      type: 'team',
      target_id: 'team_001',
      title: 'Research Team',
      workspace_ids: [],
      created_at: '',
      updated_at: '',
    })
  })

  it('renders configured teams', async () => {
    render(<MemoryRouter><Teams /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getAllByText('Research Team').length).toBeGreaterThan(0)
      expect(screen.getByText('Research and writing')).toBeInTheDocument()
    })
  })

  it('executes a team and navigates to execution detail', async () => {
    render(<MemoryRouter><Teams /></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('Research Team').length).toBeGreaterThan(0))

    await userEvent.type(screen.getByLabelText('Team message'), 'Write a report')
    await userEvent.click(screen.getByRole('button', { name: 'Run Team' }))

    await waitFor(() => {
      expect(executionsApi.runTeam).toHaveBeenCalledWith({
        team_id: 'team_001',
        message: 'Write a report',
        approval_mode: 'manual',
        workspace_ids: [],
        stream: true,
      })
      expect(navigate).toHaveBeenCalledWith('/executions/exec_team_001')
    })
  })

  it('continues the latest existing team chat', async () => {
    vi.mocked(conversationsApi.list).mockResolvedValueOnce([
      {
        id: 'conv_existing_team',
        type: 'team',
        target_id: 'team_001',
        title: 'Previous team chat',
        workspace_ids: [],
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-21T00:00:00Z',
      },
    ])

    render(<MemoryRouter><Teams /></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('Research Team').length).toBeGreaterThan(0))

    await userEvent.click(screen.getByRole('button', { name: 'Chat' }))

    await waitFor(() => {
      expect(conversationsApi.list).toHaveBeenCalledWith({ type: 'team', target_id: 'team_001' })
      expect(conversationsApi.create).not.toHaveBeenCalled()
      expect(navigate).toHaveBeenCalledWith('/conversations/conv_existing_team')
    })
  })

  it('creates a team from the form', async () => {
    vi.mocked(teamsApi.create).mockResolvedValueOnce({} as never)
    render(<MemoryRouter><Teams /></MemoryRouter>)
    await waitFor(() => expect(screen.getAllByText('Research Team').length).toBeGreaterThan(0))

    await userEvent.click(screen.getByRole('button', { name: 'New Team' }))
    await userEvent.type(screen.getByLabelText('Name'), 'New Team')
    await userEvent.selectOptions(screen.getByLabelText('Leader agent'), 'agent_leader')
    await userEvent.click(screen.getByLabelText('Member'))
    await userEvent.click(screen.getByLabelText('Team Planner'))
    await userEvent.click(screen.getByRole('button', { name: 'Create Team' }))

    await waitFor(() => {
      expect(teamsApi.create).toHaveBeenCalledWith(expect.objectContaining({
        name: 'New Team',
        leader_agent_id: 'agent_leader',
        member_agent_ids: ['agent_member'],
        skills: ['skill_team_planner'],
        execution_strategy: 'leader_managed',
      }))
    })
  })
})
