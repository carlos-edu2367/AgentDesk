import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ConversationView } from '../views/ConversationView'

const sendMessage = vi.fn()
const get = vi.fn()

vi.mock('../api/conversations', () => ({
  conversationsApi: {
    get: (...args: unknown[]) => get(...args),
    sendMessage: (...args: unknown[]) => sendMessage(...args),
  },
}))

// Avoid opening real EventSource connections in jsdom; let tests drive the
// hook's return value to simulate streaming.
let hookReturn: { events: unknown[]; connectionStatus: string } = { events: [], connectionStatus: 'closed' }
vi.mock('../hooks/useExecutionEvents', () => ({
  useExecutionEvents: () => hookReturn,
}))

function ev(execution_id: string, type: string, content: Record<string, unknown> = {}) {
  return { id: Math.random().toString(36).slice(2), execution_id, type, source: 'runtime', source_id: 'agent_1', content, created_at: '2026-06-21T00:00:00' }
}

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/conversations/${id}`]}>
      <Routes>
        <Route path="/conversations/:id" element={<ConversationView />} />
      </Routes>
    </MemoryRouter>,
  )
}

const baseDetail = {
  conversation: { id: 'conv_1', type: 'agent', target_id: 'agent_1', title: 'Researcher', created_at: '', updated_at: '' },
  turns: [],
}

describe('ConversationView', () => {
  beforeEach(() => {
    get.mockReset()
    sendMessage.mockReset()
    hookReturn = { events: [], connectionStatus: 'closed' }
    get.mockResolvedValue(baseDetail)
    sendMessage.mockResolvedValue({ execution_id: 'exec_new', conversation_id: 'conv_1', status: 'running' })
  })

  it('renders the conversation title', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByText('Researcher')).toBeInTheDocument())
  })

  it('sends a message and renders the user bubble', async () => {
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByPlaceholderText('Send a message…')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText('Send a message…'), { target: { value: 'Hello agent' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(sendMessage).toHaveBeenCalledWith('conv_1', { message: 'Hello agent', stream: true }))
  })

  it('streams the live answer and does not fold on a stale terminal event from a previous turn', async () => {
    // liveEvents briefly carries a previous turn's terminal event plus the new
    // turn's streaming chunk. The fold must NOT trigger (would kill the stream).
    hookReturn = {
      connectionStatus: 'open',
      events: [
        ev('exec_OLD', 'execution_completed'),
        ev('exec_new', 'model_chunk', { delta: 'streaming answer' }),
      ],
    }
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByPlaceholderText('Send a message…')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText('Send a message…'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    // The streaming answer for the current turn renders...
    await waitFor(() => expect(screen.getByText('streaming answer')).toBeInTheDocument())
    // ...and no fold refetch happened (get called only on initial mount).
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('folds the turn (refetches) when the current execution emits a terminal event', async () => {
    hookReturn = {
      connectionStatus: 'open',
      events: [ev('exec_new', 'execution_completed')],
    }
    renderAt('conv_1')
    await waitFor(() => expect(screen.getByPlaceholderText('Send a message…')).toBeInTheDocument())

    fireEvent.change(screen.getByPlaceholderText('Send a message…'), { target: { value: 'hi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    // Fold triggers a second conversation fetch (initial + post-completion).
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
  })
})
