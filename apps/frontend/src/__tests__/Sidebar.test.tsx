import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'

vi.mock('../hooks/useBackendHealth', () => ({
  useBackendHealth: () => ({ status: 'online', refresh: vi.fn() }),
}))
vi.mock('../hooks/useActiveExecutions', () => ({
  useActiveExecutions: () => ({ conversationIds: new Set(), targetKeys: new Set(), refresh: vi.fn() }),
}))
vi.mock('../api/conversations', () => ({
  conversationsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 'c1', type: 'agent', target_id: 'a1', title: 'First chat', created_at: '', updated_at: '' },
    ]),
  },
}))

beforeEach(() => localStorage.clear())

describe('Sidebar', () => {
  it('renders the new-chat button and nav links', async () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /novo chat/i })).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Teams')).toBeInTheDocument()
    expect(screen.getByText('Configurações')).toBeInTheDocument()
  })

  it('lists recent conversations', async () => {
    render(<MemoryRouter><Sidebar /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('First chat')).toBeInTheDocument())
  })
})
