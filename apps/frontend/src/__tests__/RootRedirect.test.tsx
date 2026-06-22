import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RootRedirect } from '../components/RootRedirect'

const navigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('../api/agents', () => ({
  agentsApi: { list: vi.fn() },
}))
vi.mock('../api/teams', () => ({
  teamsApi: { list: vi.fn() },
}))
vi.mock('../api/conversations', () => ({
  conversationsApi: { create: vi.fn() },
}))

import { agentsApi } from '../api/agents'
import { teamsApi } from '../api/teams'
import { conversationsApi } from '../api/conversations'

const AGENT = { id: 'a1', name: 'Main', model_config: { model: 'x', temperature: 0 } }

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  vi.mocked(agentsApi.list).mockResolvedValue([AGENT] as never)
  vi.mocked(teamsApi.list).mockResolvedValue([] as never)
  vi.mocked(conversationsApi.create).mockResolvedValue({ id: 'conv1' } as never)
})

function renderIt() {
  render(<MemoryRouter><RootRedirect /></MemoryRouter>)
}

describe('RootRedirect', () => {
  it('with no primary set, goes to /agents', async () => {
    renderIt()
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/agents', { replace: true }))
  })

  it('with a valid primary agent, creates a conversation and opens it', async () => {
    localStorage.setItem('agentdesk.primaryTarget', JSON.stringify({ type: 'agent', id: 'a1' }))
    renderIt()
    await waitFor(() => {
      expect(conversationsApi.create).toHaveBeenCalledWith({ type: 'agent', target_id: 'a1', title: 'Main' })
      expect(navigate).toHaveBeenCalledWith('/conversations/conv1', { replace: true })
    })
  })

  it('with a stale primary (deleted agent), clears it and goes to /agents', async () => {
    localStorage.setItem('agentdesk.primaryTarget', JSON.stringify({ type: 'agent', id: 'gone' }))
    renderIt()
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/agents', { replace: true }))
    expect(conversationsApi.create).not.toHaveBeenCalled()
    expect(localStorage.getItem('agentdesk.primaryTarget')).toBeNull()
  })

  it('falls back to /agents when conversation creation fails', async () => {
    localStorage.setItem('agentdesk.primaryTarget', JSON.stringify({ type: 'agent', id: 'a1' }))
    vi.mocked(conversationsApi.create).mockRejectedValue(new Error('boom'))
    renderIt()
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/agents', { replace: true }))
  })
})
