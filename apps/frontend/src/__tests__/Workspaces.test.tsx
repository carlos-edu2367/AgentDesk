import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Workspaces } from '../views/Workspaces'

vi.mock('../api/workspaces', () => ({
  workspacesApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'w1', name: 'Projects',
        paths: ['C:\\Users\\Carlos\\Projects'],
        permissions: { read: true, write: true, delete: false, execute: false },
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

describe('Workspaces list', () => {
  it('renders workspace name', async () => {
    render(<MemoryRouter><Workspaces /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument()
    })
  })

  it('shows path', async () => {
    render(<MemoryRouter><Workspaces /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText('C:\\Users\\Carlos\\Projects')).toBeInTheDocument()
    })
  })

  it('shows permissions', async () => {
    render(<MemoryRouter><Workspaces /></MemoryRouter>)
    await waitFor(() => {
      expect(screen.getByText(/read, write/)).toBeInTheDocument()
    })
  })
})
