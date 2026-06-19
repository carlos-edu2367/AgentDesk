import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuditLogs } from '../views/AuditLogs'
import { ExecutionDetail } from '../views/ExecutionDetail'
import { Executions } from '../views/Executions'
import { Teams } from '../views/Teams'
import { auditApi } from '../api/audit'
import { executionsApi } from '../api/executions'
import { teamsApi } from '../api/teams'

const navigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useParams: () => ({ id: 'exec_1' }), useNavigate: () => navigate }
})

vi.mock('../api/audit', () => ({
  auditApi: {
    list: vi.fn().mockResolvedValue({
      items: [
        {
          id: 'audit_1',
          execution_id: 'exec_1',
          agent_id: 'agent_1',
          event_type: 'tool_executed',
          risk_level: 'high',
          summary: 'Executed terminal.exec',
          data: { tool: 'terminal.exec' },
          created_at: '2026-06-18T00:00:00',
          tool: 'terminal.exec',
          source: 'core',
          status: 'success',
          approval_mode: 'auto',
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    }),
    get: vi.fn(),
  },
}))

vi.mock('../api/executions', () => ({
  executionsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'exec_1', type: 'agent', target_id: 'agent_1',
        user_input: 'Run terminal', status: 'completed',
        approval_mode: 'auto', workspace_ids: [],
        created_at: '2026-06-18T00:00:00', updated_at: '2026-06-18T00:00:00',
        completed_at: '2026-06-18T00:00:01', result: 'Done', error: null,
      },
    ]),
    get: vi.fn().mockResolvedValue({
      id: 'exec_1',
      type: 'agent',
      target_id: 'agent_1',
      user_input: 'Run terminal',
      status: 'completed',
      approval_mode: 'auto',
      workspace_ids: [],
      created_at: '2026-06-18T00:00:00',
      updated_at: '2026-06-18T00:00:00',
      completed_at: '2026-06-18T00:00:01',
      result: 'Done',
      error: null,
    }),
    detail: vi.fn().mockResolvedValue({
      execution: {
        id: 'exec_1',
        type: 'agent',
        target_id: 'agent_1',
        user_input: 'Run terminal',
        status: 'completed',
        approval_mode: 'auto',
        workspace_ids: [],
        created_at: '2026-06-18T00:00:00',
        updated_at: '2026-06-18T00:00:00',
        completed_at: '2026-06-18T00:00:01',
        result: 'Done',
        error: null,
      },
      events: [],
      audit_logs: [{ id: 'audit_1', event_type: 'tool_executed', risk_level: 'high', summary: 'Executed terminal.exec', execution_id: 'exec_1', agent_id: 'agent_1', data: {}, created_at: '2026-06-18T00:00:00' }],
      approvals: [],
      artifacts: [],
      summary: {
        total_events: 0,
        total_audit_logs: 1,
        tools_used: ['terminal.exec'],
        agents_involved: ['agent_1'],
        mcp_servers_used: ['filesystem'],
        plugins_used: ['plugin_demo'],
        skills_used: ['skill_writer'],
        memories_used: ['mem_1'],
        approval_mode: 'auto',
        critical_actions_count: 1,
        auto_approved_count: 1,
        manual_approved_count: 0,
        manual_rejected_count: 0,
      },
    }),
    export: vi.fn().mockResolvedValue({ format: 'json', path: 'report.json', content: {} }),
    cancel: vi.fn(),
  },
}))

vi.mock('../api/approvals', () => ({
  approvalsApi: {
    listForExecution: vi.fn().mockResolvedValue([]),
    resolve: vi.fn(),
  },
}))

vi.mock('../api/teams', () => ({
  teamsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: 'team_new' }),
    update: vi.fn(),
    updateMcp: vi.fn().mockResolvedValue([]),
    delete: vi.fn(),
  },
}))

vi.mock('../api/agents', () => ({
  agentsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'agent_1',
        name: 'Leader',
        description: '',
        system_prompt: '',
        model_config: { provider_id: 'p1', model: 'mock', temperature: 0.4, top_p: 0.9, context_window: 8192, max_tokens: 2048, stream: true },
        capabilities: [],
        explicit_tools: [],
        blocked_tools: [],
        skills: [],
        plugins: [],
        mcp_servers: [],
        memory_config: { use_global: true, use_agent_memory: true, use_team_memory: true },
        created_at: '2026-06-18T00:00:00',
        updated_at: '2026-06-18T00:00:00',
      },
    ]),
  },
}))

vi.mock('../api/skills', () => ({ skillsApi: { list: vi.fn().mockResolvedValue([]) } }))
vi.mock('../api/workspaces', () => ({ workspacesApi: { list: vi.fn().mockResolvedValue([]) } }))
vi.mock('../api/mcp', () => ({
  mcpApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'filesystem',
        name: 'Filesystem MCP',
        enabled: true,
        transport: 'stdio',
        command: 'python',
        args: [],
        env: {},
        tools_cache_json: [],
        last_connected_at: null,
        last_error: null,
        created_at: '2026-06-18T00:00:00',
        updated_at: '2026-06-18T00:00:00',
      },
    ]),
  },
}))
vi.mock('../hooks/useExecutionEvents', () => ({ useExecutionEvents: () => ({ events: [], connectionStatus: 'closed' }) }))
vi.mock('../hooks/useBackendHealth', () => ({ useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }) }))

describe('Phase 14 frontend', () => {
  it('renders audit logs and sends filters to the API', async () => {
    render(<MemoryRouter><AuditLogs /></MemoryRouter>)

    await waitFor(() => expect(screen.getAllByText('Executed terminal.exec').length).toBeGreaterThan(0))
    await userEvent.selectOptions(screen.getByLabelText('Risk level'), 'high')
    await userEvent.type(screen.getByLabelText('Search audit logs'), 'terminal')
    await userEvent.click(screen.getByRole('button', { name: 'Apply Filters' }))

    await waitFor(() => {
      expect(auditApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        risk_level: 'high',
        query: 'terminal',
      }))
    })
  })

  it('renders execution detail sections and export buttons', async () => {
    render(<MemoryRouter><ExecutionDetail /></MemoryRouter>)

    await waitFor(() => expect(screen.getAllByText('Overview').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Timeline').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Approvals').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Tools').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Memory').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Skills').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Plugins').length).toBeGreaterThan(0)
    expect(screen.getAllByText('MCP').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Audit').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Export').length).toBeGreaterThan(0)

    await userEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    await waitFor(() => expect(executionsApi.export).toHaveBeenCalledWith('exec_1', 'json'))
  })

  it('passes execution filters and shows export actions on list', async () => {
    render(<MemoryRouter><Executions /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText('Run terminal')).toBeInTheDocument())
    await userEvent.selectOptions(screen.getByLabelText('Approval mode'), 'auto')
    await userEvent.type(screen.getByLabelText('Search executions'), 'terminal')
    await userEvent.click(screen.getByRole('button', { name: 'Apply Filters' }))

    await waitFor(() => {
      expect(executionsApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
        approval_mode: 'auto',
        query: 'terminal',
      }))
    })
    await userEvent.click(screen.getByRole('button', { name: 'Export JSON' }))
    expect(executionsApi.export).toHaveBeenCalledWith('exec_1', 'json')
  })

  it('shows MCP servers in the team form and saves selected IDs', async () => {
    render(<MemoryRouter><Teams /></MemoryRouter>)

    await waitFor(() => expect(screen.getByRole('button', { name: 'New Team' })).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'New Team' }))
    await userEvent.type(screen.getByLabelText('Name'), 'MCP Team')
    await userEvent.selectOptions(screen.getByLabelText('Leader agent'), 'agent_1')
    await userEvent.click(screen.getByLabelText('Filesystem MCP enabled'))
    await userEvent.click(screen.getAllByRole('button', { name: 'Create Team' })[0])

    await waitFor(() => {
      expect(teamsApi.create).toHaveBeenCalledWith(expect.objectContaining({
        mcp_servers: ['filesystem'],
      }))
      expect(teamsApi.updateMcp).toHaveBeenCalledWith('team_new', ['filesystem'])
    })
  })
})
