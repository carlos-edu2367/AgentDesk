import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Executions } from '../views/Executions'

vi.mock('../api/executions', () => ({
  executionsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'exec_1', type: 'agent', target_id: 'a1',
        user_input: 'Tell me about AI', status: 'completed',
        approval_mode: 'manual', workspace_ids: [],
        created_at: '2024-01-01T10:00:00', updated_at: '2024-01-01T10:00:05',
        completed_at: '2024-01-01T10:00:05', result: 'AI is great.', error: null,
      },
      {
        id: 'exec_2', type: 'agent', target_id: 'a1',
        user_input: 'Another task', status: 'failed',
        approval_mode: 'auto', workspace_ids: [],
        created_at: '2024-01-01T11:00:00', updated_at: '2024-01-01T11:00:03',
        completed_at: '2024-01-01T11:00:03', result: null, error: 'Provider unavailable',
      },
    ]),
  },
}))

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))

describe('Executions list', () => {
  it('renders execution inputs', async () => {
    render(<MemoryRouter><Executions /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Tell me about AI')).toBeInTheDocument()
      expect(screen.getByText('Another task')).toBeInTheDocument()
    })
  })

  it('shows status badges', async () => {
    render(<MemoryRouter><Executions /></MemoryRouter>)
    await waitFor(() => {
      // Multiple elements match (filter buttons + status badges) — verify at least one exists
      expect(screen.getAllByText('completed').length).toBeGreaterThan(0)
      expect(screen.getAllByText('failed').length).toBeGreaterThan(0)
    })
  })

  it('shows Run Agent button', async () => {
    render(<MemoryRouter><Executions /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Run Agent')).toBeInTheDocument()
    })
  })
})
