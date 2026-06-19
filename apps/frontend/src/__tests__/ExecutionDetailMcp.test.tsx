import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ExecutionDetail } from '../views/ExecutionDetail'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useParams: () => ({ id: 'exec_1' }), useNavigate: () => vi.fn() }
})

vi.mock('../api/executions', () => ({
  executionsApi: {
    get: vi.fn().mockResolvedValue({
      id: 'exec_1',
      type: 'agent',
      target_id: 'agent_1',
      user_input: 'Run MCP',
      status: 'completed',
      approval_mode: 'auto',
      workspace_ids: [],
      created_at: '2026-06-18T00:00:00',
      updated_at: '2026-06-18T00:00:00',
      completed_at: '2026-06-18T00:00:01',
      result: 'Done',
      error: null,
    }),
    cancel: vi.fn(),
  },
}))

vi.mock('../api/approvals', () => ({
  approvalsApi: {
    listForExecution: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('../hooks/useExecutionEvents', () => ({
  useExecutionEvents: () => ({
    connectionStatus: 'closed',
    events: [
      {
        id: 'event_1',
        execution_id: 'exec_1',
        type: 'mcp_tool_started',
        source: 'tool',
        source_id: 'mcp.filesystem.echo',
        content: { tool: 'mcp.filesystem.echo', server_id: 'filesystem' },
        created_at: '2026-06-18T00:00:00',
      },
      {
        id: 'event_2',
        execution_id: 'exec_1',
        type: 'mcp_tool_completed',
        source: 'tool',
        source_id: 'mcp.filesystem.echo',
        content: { tool: 'mcp.filesystem.echo', server_id: 'filesystem', result_preview: '{"ok":true}' },
        created_at: '2026-06-18T00:00:01',
      },
    ],
  }),
}))

describe('ExecutionDetail MCP timeline events', () => {
  it('renders MCP timeline labels', async () => {
    render(<MemoryRouter><ExecutionDetail /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText('MCP tool started')).toBeInTheDocument()
      expect(screen.getByText('MCP tool completed')).toBeInTheDocument()
      expect(screen.getAllByText('MCP').length).toBeGreaterThan(0)
    })
  })
})
