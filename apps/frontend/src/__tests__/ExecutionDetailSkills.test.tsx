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
      user_input: 'Run',
      status: 'completed',
      approval_mode: 'auto',
      workspace_ids: [],
      created_at: '2024-01-01T00:00:00',
      updated_at: '2024-01-01T00:00:00',
      completed_at: '2024-01-01T00:00:01',
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
        type: 'skills_loaded',
        source: 'runtime',
        source_id: 'agent_1',
        content: { count: 1, skills: [{ id: 'skill_report_writer', name: 'Report Writer' }] },
        created_at: '2024-01-01T00:00:00',
      },
      {
        id: 'event_2',
        execution_id: 'exec_1',
        type: 'skill_injected',
        source: 'runtime',
        source_id: 'agent_1',
        content: { skill: { id: 'skill_report_writer', name: 'Report Writer' } },
        created_at: '2024-01-01T00:00:00',
      },
    ],
  }),
}))

describe('ExecutionDetail skill timeline events', () => {
  it('renders skill timeline labels without prompt content', async () => {
    render(<MemoryRouter><ExecutionDetail /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Skills loaded')).toBeInTheDocument()
      expect(screen.getByText('Skill injected')).toBeInTheDocument()
      expect(screen.queryByText('Use summary and findings.')).not.toBeInTheDocument()
    })
  })
})
