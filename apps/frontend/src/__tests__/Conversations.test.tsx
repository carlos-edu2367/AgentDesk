import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Conversations } from '../views/Conversations'
import { conversationsApi } from '../api/conversations'

const navigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('../api/conversations', () => ({
  conversationsApi: {
    list: vi.fn(),
  },
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <Conversations />
    </MemoryRouter>,
  )
}

describe('Conversations page', () => {
  beforeEach(() => {
    navigate.mockReset()
    vi.mocked(conversationsApi.list).mockResolvedValue([
      {
        id: 'conv_recent',
        type: 'agent',
        target_id: 'agent_001',
        title: 'Recent agent chat',
        workspace_ids: [],
        created_at: '2026-06-20T10:00:00Z',
        updated_at: '2026-06-21T10:00:00Z',
      },
      {
        id: 'conv_team',
        type: 'team',
        target_id: 'team_001',
        title: 'Research team chat',
        workspace_ids: [],
        created_at: '2026-06-19T10:00:00Z',
        updated_at: '2026-06-20T10:00:00Z',
      },
    ])
  })

  it('lists previous conversations and opens one to continue it', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Recent agent chat')).toBeInTheDocument()
      expect(screen.getByText('Research team chat')).toBeInTheDocument()
    })

    await userEvent.click(screen.getAllByRole('button', { name: 'Open' })[0])

    expect(conversationsApi.list).toHaveBeenCalledWith({ limit: 100 })
    expect(navigate).toHaveBeenCalledWith('/conversations/conv_recent')
  })
})
